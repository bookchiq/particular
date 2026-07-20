"""Loopback-only dependency-free Particular hackathon demo server."""

from __future__ import annotations

import argparse
import json
import secrets
import shutil
import sys
import tempfile
import threading
from collections.abc import Sequence
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote, urlsplit

from particular.application import ARTIFACT_FILENAMES, generate_to_directory
from particular.errors import classify_error

# Director-friendly guidance for transport-level rejections that happen before
# generation. Generation failures draw their guidance from classify_error.
TRANSPORT_GUIDANCE = {
    "not_found": "That resource is not available.",
    "rights_attestation_required": (
        "Confirm you are authorized to arrange this score, then upload it again."
    ),
    "unsupported_filename": "Upload a MusicXML (.musicxml or .xml) or compressed .mxl file.",
    "content_length_required": "The upload was missing its length. Try uploading the file again.",
    "upload_too_large": (
        "This file is larger than the demo accepts. Try a smaller score or a single movement."
    ),
    "incomplete_upload": "The upload did not finish. Check your connection and try again.",
}

MAX_UPLOAD_BYTES = 2_000_000
MAX_JOBS = 8
REPOSITORY_ROOT = Path(__file__).parents[3]
PUBLIC_ROOT = REPOSITORY_ROOT / "apps/web/public"
ARTIFACTS = ARTIFACT_FILENAMES
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}


class DemoServer(ThreadingHTTPServer):
    """Server owning private job storage for its exact lifetime."""

    def __init__(self, address: tuple[str, int]) -> None:
        self.storage_root = Path(tempfile.mkdtemp(prefix="particular-demo-"))
        self.jobs: dict[str, Path] = {}
        self.jobs_lock = threading.Lock()
        try:
            super().__init__(address, DemoHandler)
        except BaseException:
            shutil.rmtree(self.storage_root, ignore_errors=True)
            raise

    def server_close(self) -> None:
        super().server_close()
        shutil.rmtree(self.storage_root, ignore_errors=True)

    def register_job(self, job_id: str, output: Path) -> None:
        """Register an artifact directory and evict the oldest completed job."""

        with self.jobs_lock:
            self.jobs[job_id] = output
            while len(self.jobs) > MAX_JOBS:
                oldest_job_id = next(iter(self.jobs))
                expired = self.jobs.pop(oldest_job_id)
                shutil.rmtree(expired.parent, ignore_errors=True)


class DemoHandler(BaseHTTPRequestHandler):
    server: DemoServer

    def log_message(self, format: str, *args: object) -> None:
        """Avoid logging filenames, paths, or musical request metadata."""

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _error(
        self,
        status: int,
        code: str,
        *,
        message: str | None = None,
        diagnostic_id: str | None = None,
    ) -> None:
        body: dict[str, Any] = {
            "error": code,
            "message": message or TRANSPORT_GUIDANCE.get(code, ""),
        }
        if diagnostic_id is not None:
            body["diagnostic_id"] = diagnostic_id
        self._json(status, body)

    def _profile_overrides(self) -> dict[str, str]:
        raw_overrides = self.headers.get("X-Particular-Instrument-Profiles")
        if raw_overrides is None:
            return {}
        try:
            overrides = json.loads(raw_overrides)
        except json.JSONDecodeError as error:
            raise ValueError("instrument profile overrides must be JSON") from error
        if not isinstance(overrides, dict) or not all(
            isinstance(part_id, str) and isinstance(profile_id, str)
            for part_id, profile_id in overrides.items()
        ):
            raise ValueError("instrument profile overrides must map part IDs to profile IDs")
        return overrides

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/api/generate":
            self._error(HTTPStatus.NOT_FOUND, "not_found")
            return
        if self.headers.get("X-Particular-Rights-Attested") != "true":
            self._error(HTTPStatus.FORBIDDEN, "rights_attestation_required")
            return
        filename = self.headers.get("X-Particular-Filename", "")
        if (
            not filename
            or Path(filename).name != filename
            or Path(filename).suffix.casefold() not in {".xml", ".musicxml", ".mxl"}
        ):
            self._error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "unsupported_filename")
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            length = -1
        if length < 1:
            self._error(HTTPStatus.LENGTH_REQUIRED, "content_length_required")
            return
        if length > MAX_UPLOAD_BYTES:
            self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "upload_too_large")
            return
        contents = self.rfile.read(length)
        if len(contents) != length:
            self._error(HTTPStatus.BAD_REQUEST, "incomplete_upload")
            return
        job_id = secrets.token_urlsafe(18)
        job_root = self.server.storage_root / job_id
        try:
            job_root.mkdir()
            source = job_root / f"source{Path(filename).suffix.casefold()}"
            source.write_bytes(contents)
            output = job_root / "artifacts"
            # The uploader passed the rights-attestation gate above.
            generate_to_directory(source, output, self._profile_overrides(), attested=True)
            manifest = json.loads((output / ARTIFACTS["manifest"]).read_text())
            analysis = json.loads((output / ARTIFACTS["analysis"]).read_text())
        except (OSError, ValueError) as error:
            shutil.rmtree(job_root, ignore_errors=True)
            public = classify_error(error)
            diagnostic_id = secrets.token_hex(8)
            # Correlate without exposing content: only the id and exception class.
            print(
                f"particular-demo diagnostic {diagnostic_id} {type(error).__name__}",
                file=sys.stderr,
            )
            status = (
                HTTPStatus.INTERNAL_SERVER_ERROR
                if public.code == "internal_error"
                else HTTPStatus.BAD_REQUEST
            )
            self._error(status, public.code, message=public.message, diagnostic_id=diagnostic_id)
            return
        source.unlink(missing_ok=True)
        self.server.register_job(job_id, output)
        self._json(
            HTTPStatus.OK,
            {
                "review_required": True,
                "retention": {"max_completed_jobs": MAX_JOBS},
                "analysis": analysis,
                "manifest": manifest,
                "artifacts": {key: f"/artifacts/{job_id}/{key}" for key in ARTIFACTS},
            },
        )

    def do_GET(self) -> None:
        path = unquote(urlsplit(self.path).path)
        if path in STATIC_FILES:
            filename, content_type = STATIC_FILES[path]
            body = (PUBLIC_ROOT / filename).read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        pieces = path.split("/")
        if len(pieces) != 4 or pieces[1] != "artifacts" or pieces[3] not in ARTIFACTS:
            self._error(HTTPStatus.NOT_FOUND, "not_found")
            return
        job_id, artifact = pieces[2], pieces[3]
        with self.server.jobs_lock:
            output = self.server.jobs.get(job_id)
            if output is None:
                artifact_body = None
            else:
                target = output / ARTIFACTS[artifact]
                try:
                    artifact_body = target.read_bytes()
                except OSError:
                    artifact_body = None
        if artifact_body is None:
            self._error(HTTPStatus.NOT_FOUND, "not_found")
            return
        content_type = (
            "application/json"
            if target.suffix == ".json"
            else "application/vnd.recordare.musicxml+xml"
        )
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(artifact_body)))
        self.send_header("Content-Disposition", f'attachment; filename="{target.name}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(artifact_body)


def create_server(host: str = "127.0.0.1", port: int = 8765) -> DemoServer:
    """Create a loopback server; callers own serving and shutdown."""

    return DemoServer((host, port))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m particular.demo")
    parser.add_argument("--port", type=int, default=8765)
    arguments = parser.parse_args(argv)
    server = create_server(port=arguments.port)
    host, port = cast(tuple[str, int], server.server_address)
    print(json.dumps({"url": f"http://{host}:{port}", "loopback_only": True}))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
