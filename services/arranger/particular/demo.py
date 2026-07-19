"""Loopback-only dependency-free Particular hackathon demo server."""

from __future__ import annotations

import argparse
import json
import secrets
import shutil
import tempfile
import threading
from collections.abc import Sequence
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote, urlsplit

from particular.application import generate_to_directory

MAX_UPLOAD_BYTES = 2_000_000
MAX_JOBS = 8
REPOSITORY_ROOT = Path(__file__).parents[3]
PUBLIC_ROOT = REPOSITORY_ROOT / "apps/web/public"
ARTIFACTS = {
    "original": "original-normalized.musicxml",
    "foundation": "foundation.musicxml",
    "core": "core.musicxml",
    "challenge": "challenge.musicxml",
    "manifest": "manifest.json",
    "analysis": "analysis.json",
}
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

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/api/generate":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        if self.headers.get("X-Particular-Rights-Attested") != "true":
            self._json(HTTPStatus.FORBIDDEN, {"error": "rights_attestation_required"})
            return
        filename = self.headers.get("X-Particular-Filename", "")
        if (
            not filename
            or Path(filename).name != filename
            or Path(filename).suffix.casefold() not in {".xml", ".musicxml", ".mxl"}
        ):
            self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "unsupported_filename"})
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            length = -1
        if length < 1:
            self._json(HTTPStatus.LENGTH_REQUIRED, {"error": "content_length_required"})
            return
        if length > MAX_UPLOAD_BYTES:
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "upload_too_large"})
            return
        contents = self.rfile.read(length)
        if len(contents) != length:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "incomplete_upload"})
            return
        job_id = secrets.token_urlsafe(18)
        job_root = self.server.storage_root / job_id
        job_root.mkdir()
        source = job_root / f"source{Path(filename).suffix.casefold()}"
        source.write_bytes(contents)
        output = job_root / "artifacts"
        try:
            generate_to_directory(source, output)
            manifest = json.loads((output / ARTIFACTS["manifest"]).read_text())
            analysis = json.loads((output / ARTIFACTS["analysis"]).read_text())
        except (OSError, ValueError) as error:
            shutil.rmtree(job_root, ignore_errors=True)
            self._json(
                HTTPStatus.BAD_REQUEST,
                {"error": "generation_failed", "message": str(error)},
            )
            return
        source.unlink(missing_ok=True)
        self.server.register_job(job_id, output)
        self._json(
            HTTPStatus.OK,
            {
                "review_required": True,
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
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        job_id, artifact = pieces[2], pieces[3]
        with self.server.jobs_lock:
            output = self.server.jobs.get(job_id)
        if output is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        target = output / ARTIFACTS[artifact]
        if not target.is_file():
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        body = target.read_bytes()
        content_type = (
            "application/json"
            if target.suffix == ".json"
            else "application/vnd.recordare.musicxml+xml"
        )
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'attachment; filename="{target.name}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


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
