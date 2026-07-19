from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from particular.demo import MAX_UPLOAD_BYTES, create_server

ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "evaluation/fixtures/mixed-ensemble-transposition.musicxml"


@pytest.fixture
def demo_server() -> Iterator[tuple[str, int]]:
    server = create_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = cast(tuple[str, int], server.server_address)
    try:
        yield str(host), int(port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _post(
    address: tuple[str, int],
    body: bytes,
    *,
    filename: str = "score.musicxml",
    attested: bool = True,
) -> tuple[int, dict[str, Any]]:
    connection = http.client.HTTPConnection(*address)
    headers = {"X-Particular-Filename": filename}
    if attested:
        headers["X-Particular-Rights-Attested"] = "true"
    connection.request("POST", "/api/generate", body, headers)
    response = connection.getresponse()
    payload = cast(dict[str, Any], json.loads(response.read()))
    connection.close()
    return response.status, payload


def test_requires_rights_attestation(demo_server: tuple[str, int]) -> None:
    status, payload = _post(demo_server, FIXTURE.read_bytes(), attested=False)
    assert status == 403
    assert payload["error"] == "rights_attestation_required"


def test_valid_generation_and_allowlisted_download(demo_server: tuple[str, int]) -> None:
    status, payload = _post(demo_server, FIXTURE.read_bytes())
    assert status == 200
    assert payload["review_required"] is True
    assert len(payload["analysis"]["parts"]) == 4
    artifacts = cast(dict[str, str], payload["artifacts"])
    assert set(artifacts) == {"original", "foundation", "core", "challenge", "manifest", "analysis"}

    connection = http.client.HTTPConnection(*demo_server)
    connection.request("GET", artifacts["foundation"])
    response = connection.getresponse()
    assert response.status == 200
    assert response.getheader("Content-Type") == "application/vnd.recordare.musicxml+xml"
    assert b"score-partwise" in response.read()
    connection.close()


@pytest.mark.parametrize("path", ["/artifacts/../secret", "/artifacts/nope/private-score"])
def test_blocks_traversal_and_unknown_artifacts(demo_server: tuple[str, int], path: str) -> None:
    connection = http.client.HTTPConnection(*demo_server)
    connection.request("GET", path)
    assert connection.getresponse().status == 404
    connection.close()


def test_rejects_oversize_and_unsupported_filename(demo_server: tuple[str, int]) -> None:
    connection = http.client.HTTPConnection(*demo_server)
    connection.request(
        "POST",
        "/api/generate",
        headers={
            "Content-Length": str(MAX_UPLOAD_BYTES + 1),
            "X-Particular-Filename": "score.musicxml",
            "X-Particular-Rights-Attested": "true",
        },
    )
    response = connection.getresponse()
    assert response.status == 413
    response.read()
    connection.close()

    status, _ = _post(demo_server, b"score", filename="score.mid")
    assert status == 415


def test_static_page_has_accessible_review_flow() -> None:
    html = (ROOT / "apps/web/public/index.html").read_text()
    assert '<label for="score-file">' in html
    assert 'id="rights-attestation"' in html
    assert 'aria-live="polite"' in html
    assert "Director review required" in html
