"""Loopback-only dependency-free Particular hackathon demo server."""

from __future__ import annotations

import argparse
import json
import secrets
import shutil
import sys
import tempfile
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote, urlsplit

from particular.application import (
    ARTIFACT_FILENAMES,
    RIGHTS_BASES,
    generate_to_directory,
    part_export_filename,
)
from particular.errors import classify_error
from particular.importers.musicxml import MAX_EVENTS, MAX_PARTS
from particular.importers.security import DEFAULT_ARCHIVE_LIMITS

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

MAX_UPLOAD_BYTES = 16_000_000
MAX_JOBS = 8
# Completed jobs are retained for 30 minutes after creation, then deleted even
# if the loopback server stays open; a background sweep enforces this without
# depending on later requests.
DEFAULT_JOB_TTL_SECONDS = 1800.0
SWEEP_INTERVAL_SECONDS = 60.0

# Limits surfaced to the browser so a director sees them before uploading.
PUBLIC_LIMITS = {
    "max_upload_bytes": MAX_UPLOAD_BYTES,
    "max_expanded_total_bytes": DEFAULT_ARCHIVE_LIMITS.max_total_bytes,
    "max_expanded_entry_bytes": DEFAULT_ARCHIVE_LIMITS.max_entry_bytes,
    "max_archive_entries": DEFAULT_ARCHIVE_LIMITS.max_files,
    "max_parts": MAX_PARTS,
    "max_events": MAX_EVENTS,
}
ARTIFACTS = ARTIFACT_FILENAMES


def _load_asset(filename: str) -> bytes:
    """Read a browser asset from the installed package, or the source tree in dev."""

    packaged = resources.files("particular").joinpath("web", filename)
    if packaged.is_file():
        return packaged.read_bytes()
    source = Path(__file__).parents[3] / "apps/web/public" / filename
    return source.read_bytes()


STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/sequencer.js": ("sequencer.js", "text/javascript; charset=utf-8"),
}


@dataclass
class _Job:
    output: Path
    created: float


class DemoServer(ThreadingHTTPServer):
    """Server owning private job storage for its exact lifetime."""

    def __init__(
        self, address: tuple[str, int], job_ttl_seconds: float = DEFAULT_JOB_TTL_SECONDS
    ) -> None:
        self.storage_root = Path(tempfile.mkdtemp(prefix="particular-demo-"))
        self.jobs: dict[str, _Job] = {}
        self.jobs_lock = threading.Lock()
        self.job_ttl_seconds = job_ttl_seconds
        self._stop = threading.Event()
        try:
            super().__init__(address, DemoHandler)
        except BaseException:
            shutil.rmtree(self.storage_root, ignore_errors=True)
            raise
        self._sweeper = threading.Thread(target=self._sweep_loop, daemon=True)
        self._sweeper.start()

    def server_close(self) -> None:
        self._stop.set()
        super().server_close()
        shutil.rmtree(self.storage_root, ignore_errors=True)

    def _sweep_loop(self) -> None:
        while not self._stop.wait(SWEEP_INTERVAL_SECONDS):
            self.purge_expired()

    def _purge_locked(self) -> None:
        cutoff = time.monotonic() - self.job_ttl_seconds
        for job_id in [key for key, job in self.jobs.items() if job.created <= cutoff]:
            expired = self.jobs.pop(job_id)
            shutil.rmtree(expired.output.parent, ignore_errors=True)

    def purge_expired(self) -> None:
        """Delete jobs older than the retention window."""

        with self.jobs_lock:
            self._purge_locked()

    def register_job(self, job_id: str, output: Path) -> None:
        """Register an artifact directory, purge expired jobs, and cap the count."""

        with self.jobs_lock:
            self._purge_locked()
            self.jobs[job_id] = _Job(output, time.monotonic())
            while len(self.jobs) > MAX_JOBS:
                oldest_job_id = next(iter(self.jobs))
                expired = self.jobs.pop(oldest_job_id)
                shutil.rmtree(expired.output.parent, ignore_errors=True)

    def delete_job(self, job_id: str) -> bool:
        """Explicitly remove a job's artifacts; returns whether it existed."""

        with self.jobs_lock:
            job = self.jobs.pop(job_id, None)
            if job is None:
                return False
            shutil.rmtree(job.output.parent, ignore_errors=True)
            return True

    def read_artifact(self, job_id: str, artifact_filename: str) -> bytes | None:
        """Purge expired jobs, then read an artifact atomically under the lock."""

        with self.jobs_lock:
            self._purge_locked()
            job = self.jobs.get(job_id)
            if job is None:
                return None
            try:
                return (job.output / artifact_filename).read_bytes()
            except OSError:
                return None


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
        rights_basis = self.headers.get("X-Particular-Rights-Basis")
        if rights_basis not in RIGHTS_BASES:
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
            # The uploader selected a valid rights basis at the gate above.
            generate_to_directory(
                source, output, self._profile_overrides(), rights_basis=rights_basis
            )
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
                "retention": {
                    "max_completed_jobs": MAX_JOBS,
                    "ttl_seconds": self.server.job_ttl_seconds,
                },
                "job_id": job_id,
                "analysis": analysis,
                "manifest": manifest,
                "artifacts": {key: f"/artifacts/{job_id}/{key}" for key in ARTIFACTS},
                "part_exports": {
                    tier: [
                        {
                            "part_id": part["part_id"],
                            "part_name": part["part_name"],
                            "url": (
                                f"/artifacts/{job_id}/"
                                + part_export_filename(tier, part["part_id"])
                            ),
                        }
                        for part in analysis["parts"]
                    ]
                    for tier in ("Foundation", "Core", "Challenge")
                },
            },
        )

    def do_GET(self) -> None:
        path = unquote(urlsplit(self.path).path)
        if path == "/api/limits":
            self._json(HTTPStatus.OK, PUBLIC_LIMITS)
            return
        if path in STATIC_FILES:
            filename, content_type = STATIC_FILES[path]
            body = _load_asset(filename)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        pieces = path.split("/")
        if len(pieces) != 4 or pieces[1] != "artifacts":
            self._error(HTTPStatus.NOT_FOUND, "not_found")
            return
        job_id, name = pieces[2], pieces[3]
        # Accept a stable key (e.g. "foundation") or a part-export filename; the
        # basename check keeps requests inside the job's artifact directory.
        artifact_filename = ARTIFACTS.get(name, name)
        if not artifact_filename or Path(artifact_filename).name != artifact_filename:
            self._error(HTTPStatus.NOT_FOUND, "not_found")
            return
        artifact_body = self.server.read_artifact(job_id, artifact_filename)
        if artifact_body is None:
            self._error(HTTPStatus.NOT_FOUND, "not_found")
            return
        content_type = (
            "application/json"
            if artifact_filename.endswith(".json")
            else "application/vnd.recordare.musicxml+xml"
        )
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(artifact_body)))
        self.send_header("Content-Disposition", f'attachment; filename="{artifact_filename}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(artifact_body)

    def do_DELETE(self) -> None:
        pieces = unquote(urlsplit(self.path).path).split("/")
        if len(pieces) != 3 or pieces[1] != "artifacts" or not pieces[2]:
            self._error(HTTPStatus.NOT_FOUND, "not_found")
            return
        if self.server.delete_job(pieces[2]):
            self._json(HTTPStatus.OK, {"deleted": True})
        else:
            self._error(HTTPStatus.NOT_FOUND, "not_found")


def create_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    job_ttl_seconds: float = DEFAULT_JOB_TTL_SECONDS,
) -> DemoServer:
    """Create a loopback server; callers own serving and shutdown."""

    return DemoServer((host, port), job_ttl_seconds=job_ttl_seconds)


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
