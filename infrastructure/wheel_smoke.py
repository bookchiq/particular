"""Smoke-test an installed Particular wheel.

Run with the interpreter of a clean environment that has only the built wheel
installed. Confirms the demo serves its packaged browser assets and that a full
generation runs end to end from the installed artifact.
"""

from __future__ import annotations

import threading
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from particular.cli import main
from particular.demo import create_server

SCORE = (
    b'<score-partwise version="4.0"><part-list>'
    b'<score-part id="P1"><part-name>Violin</part-name></score-part></part-list>'
    b'<part id="P1"><measure number="1"><attributes><divisions>4</divisions>'
    b"<time><beats>4</beats><beat-type>4</beat-type></time></attributes>"
    b"<note><pitch><step>C</step><octave>5</octave></pitch><duration>4</duration>"
    b"<type>quarter</type></note>"
    b"<note><pitch><step>C</step><octave>5</octave></pitch><duration>4</duration>"
    b"<type>quarter</type></note></measure></part></score-partwise>"
)

ASSETS = {
    "/": b"score-form",
    "/app.css": b".wordmark",
    "/app.js": b"createSequencer",
    "/sequencer.js": b"createSequencer",
}


def check_assets() -> None:
    server = create_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = cast(tuple[str, int], server.server_address)
    try:
        for path, marker in ASSETS.items():
            with urllib.request.urlopen(f"http://{host}:{port}{path}", timeout=5) as response:
                body = response.read()
            if response.status != 200 or marker not in body:
                raise SystemExit(f"asset {path} failed: status {response.status}")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def check_generation() -> None:
    with TemporaryDirectory() as workspace:
        source = Path(workspace) / "score.musicxml"
        source.write_bytes(SCORE)
        output = Path(workspace) / "out"
        status = main(["generate", str(source), str(output), "--rights-basis", "public_domain"])
        if status != 0:
            raise SystemExit(f"generation exited {status}")
        produced = {path.name for path in output.iterdir()}
        expected = {
            "manifest.json",
            "essential.musicxml",
            "supported.musicxml",
            "original.musicxml",
        }
        if not expected <= produced:
            raise SystemExit(f"missing artifacts: {sorted(expected - produced)}")


if __name__ == "__main__":
    check_assets()
    check_generation()
    print("wheel smoke: ok")
