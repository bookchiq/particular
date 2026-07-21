from __future__ import annotations

import http.client
import io
import json
import threading
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from particular.demo import MAX_JOBS, MAX_UPLOAD_BYTES, create_server

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
    rights_basis: str | None = "authorized",
    profile_overrides: dict[str, str] | None = None,
    locks: str | list[list[str]] | None = None,
    tier_assignments: str | dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    connection = http.client.HTTPConnection(*address)
    headers = {"X-Particular-Filename": filename}
    if rights_basis is not None:
        headers["X-Particular-Rights-Basis"] = rights_basis
    if profile_overrides is not None:
        headers["X-Particular-Instrument-Profiles"] = json.dumps(profile_overrides)
    if locks is not None:
        headers["X-Particular-Locks"] = locks if isinstance(locks, str) else json.dumps(locks)
    if tier_assignments is not None:
        headers["X-Particular-Tier-Assignments"] = (
            tier_assignments if isinstance(tier_assignments, str) else json.dumps(tier_assignments)
        )
    connection.request("POST", "/api/generate", body, headers)
    response = connection.getresponse()
    payload = cast(dict[str, Any], json.loads(response.read()))
    connection.close()
    return response.status, payload


def test_requires_rights_attestation(demo_server: tuple[str, int]) -> None:
    status, payload = _post(demo_server, FIXTURE.read_bytes(), rights_basis=None)
    assert status == 403
    assert payload["error"] == "rights_attestation_required"


def test_rejects_unknown_rights_basis(demo_server: tuple[str, int]) -> None:
    status, payload = _post(demo_server, FIXTURE.read_bytes(), rights_basis="whatever")
    assert status == 403
    assert payload["error"] == "rights_attestation_required"


def test_records_selected_rights_basis(demo_server: tuple[str, int]) -> None:
    status, payload = _post(demo_server, FIXTURE.read_bytes(), rights_basis="public_domain")
    assert status == 200
    assert payload["manifest"]["operational"]["attestation"]["basis"] == "public_domain"


def test_valid_generation_and_allowlisted_download(demo_server: tuple[str, int]) -> None:
    status, payload = _post(demo_server, FIXTURE.read_bytes())
    assert status == 200
    assert payload["review_required"] is True
    assert len(payload["analysis"]["parts"]) == 4
    assert "violin" in payload["analysis"]["available_instrument_profiles"]
    artifacts = cast(dict[str, str], payload["artifacts"])
    assert set(artifacts) == {
        "source",
        "essential",
        "supported",
        "original",
        "manifest",
        "analysis",
    }

    connection = http.client.HTTPConnection(*demo_server)
    connection.request("GET", artifacts["essential"])
    response = connection.getresponse()
    assert response.status == 200
    assert response.getheader("Content-Type") == "application/vnd.recordare.musicxml+xml"
    assert b"score-partwise" in response.read()
    connection.close()


def test_honors_locked_measures_and_records_them(demo_server: tuple[str, int]) -> None:
    status, payload = _post(demo_server, FIXTURE.read_bytes(), locks=[["P1", "1"]])

    assert status == 200
    assert payload["manifest"]["reproducibility"]["locked_measures"] == [["P1", "1"]]
    # No change of any kind is recorded for the locked measure.
    changes = payload["manifest"]["change_summary"]
    for tier in changes.values():
        for record in [*tier["accepted"], *tier["rejected"]]:
            assert (record["part_id"], record["measure"]) != ("P1", "1")


def test_rejects_malformed_locked_measures(demo_server: tuple[str, int]) -> None:
    status, payload = _post(demo_server, FIXTURE.read_bytes(), locks="not-json")
    assert status == 400
    assert "diagnostic_id" in payload


def test_reports_pdf_export_fallback_without_musescore(
    demo_server: tuple[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    # No MuseScore on PATH → the response advertises the explicit fallback.
    monkeypatch.setenv("PARTICULAR_MUSESCORE", "/no/such/musescore")
    status, payload = _post(demo_server, FIXTURE.read_bytes())

    assert status == 200
    assert payload["pdf"]["available"] is False
    assert payload["pdf"]["exports"] == {}
    assert "MuseScore" in payload["pdf"]["note"]


def test_advertises_pdf_exports_when_musescore_is_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A stub MuseScore that emits a PDF lets the full export path run without the
    # real tool; the server should list per-source PDF downloads that resolve.
    stub = tmp_path / "mscore"
    stub.write_text(
        '#!/bin/sh\nwhile [ "$1" != "-o" ]; do shift; done\nprintf "%%PDF-1.4 stub" > "$2"\n'
    )
    stub.chmod(0o755)
    monkeypatch.setenv("PARTICULAR_MUSESCORE", str(stub))

    server = create_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    address = cast(tuple[str, int], server.server_address)
    try:
        status, payload = _post((str(address[0]), int(address[1])), FIXTURE.read_bytes())
        assert status == 200
        assert payload["pdf"]["available"] is True
        assert set(payload["pdf"]["exports"]) == {"Source", "Essential", "Supported", "Original"}

        connection = http.client.HTTPConnection(str(address[0]), int(address[1]))
        connection.request("GET", cast(str, payload["pdf"]["exports"]["Essential"]))
        response = connection.getresponse()
        body = response.read()
        connection.close()
        assert response.status == 200
        assert response.getheader("Content-Type") == "application/pdf"
        assert body.startswith(b"%PDF")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_serves_playback_timelines_for_original_and_tiers(demo_server: tuple[str, int]) -> None:
    status, payload = _post(demo_server, FIXTURE.read_bytes())
    assert status == 200
    assert set(payload["playback"]) == {"Source", "Essential", "Supported", "Original"}

    connection = http.client.HTTPConnection(*demo_server)
    connection.request("GET", cast(str, payload["playback"]["Essential"]))
    response = connection.getresponse()
    timeline = cast(dict[str, Any], json.loads(response.read()))
    connection.close()

    assert response.status == 200
    assert response.getheader("Content-Type") == "application/json"
    assert timeline["tempo_bpm"] > 0
    assert {part["part_id"] for part in timeline["parts"]} == {"P1", "P2", "P3", "P4"}
    assert any(part["notes"] for part in timeline["parts"])


def test_mixed_tier_set_includes_a_playback_timeline(demo_server: tuple[str, int]) -> None:
    status, payload = _post(demo_server, FIXTURE.read_bytes(), tier_assignments={"P1": "Essential"})
    assert status == 200
    url = payload["custom_set"]["playback_url"]

    connection = http.client.HTTPConnection(*demo_server)
    connection.request("GET", cast(str, url))
    response = connection.getresponse()
    timeline = cast(dict[str, Any], json.loads(response.read()))
    connection.close()

    assert response.status == 200
    assert {part["part_id"] for part in timeline["parts"]} == {"P1", "P2", "P3", "P4"}


def test_builds_and_serves_a_mixed_tier_set(demo_server: tuple[str, int]) -> None:
    status, payload = _post(
        demo_server,
        FIXTURE.read_bytes(),
        tier_assignments={"P1": "Essential", "P3": "Original"},
    )

    assert status == 200
    custom = payload["manifest"]["custom_arrangement"]
    assert custom["assignments"] == {"P1": "Essential", "P3": "Original"}
    # Unassigned parts default to Core in the recorded per-part tiers.
    resolved = {part["part_id"]: part["tier"] for part in custom["parts"]}
    assert resolved == {"P1": "Essential", "P2": "Supported", "P3": "Original", "P4": "Supported"}

    custom_set = payload["custom_set"]
    assert {entry["part_id"] for entry in custom_set["part_exports"]} == {"P1", "P2", "P3", "P4"}

    # The mixed full score and a mixed single part both download as MusicXML.
    for url in (custom_set["url"], custom_set["part_exports"][0]["url"]):
        connection = http.client.HTTPConnection(*demo_server)
        connection.request("GET", cast(str, url))
        response = connection.getresponse()
        body = response.read()
        connection.close()
        assert response.status == 200
        assert response.getheader("Content-Type") == "application/vnd.recordare.musicxml+xml"
        assert b"score-partwise" in body
    assert body.count(b"<part ") == 1


def test_omits_custom_set_without_tier_assignments(demo_server: tuple[str, int]) -> None:
    status, payload = _post(demo_server, FIXTURE.read_bytes())
    assert status == 200
    assert "custom_set" not in payload
    assert "custom_arrangement" not in payload["manifest"]


def test_rejects_malformed_tier_assignments(demo_server: tuple[str, int]) -> None:
    status, payload = _post(demo_server, FIXTURE.read_bytes(), tier_assignments="not-json")
    assert status == 400
    assert "diagnostic_id" in payload


def test_rejects_unknown_tier_in_assignments(demo_server: tuple[str, int]) -> None:
    status, payload = _post(demo_server, FIXTURE.read_bytes(), tier_assignments={"P1": "Expert"})
    assert status == 400
    assert "diagnostic_id" in payload


def test_accepts_director_instrument_profile_override(demo_server: tuple[str, int]) -> None:
    status, payload = _post(demo_server, FIXTURE.read_bytes(), profile_overrides={"P1": "viola"})

    assert status == 200
    assert payload["analysis"]["parts"][0]["profile_confidence"] == "director-override"


def test_evicts_oldest_completed_job(demo_server: tuple[str, int]) -> None:
    first_download: str | None = None
    for index in range(MAX_JOBS + 1):
        status, payload = _post(demo_server, FIXTURE.read_bytes())
        assert status == 200
        if index == 0:
            first_download = cast(dict[str, str], payload["artifacts"])["essential"]

    assert first_download is not None
    connection = http.client.HTTPConnection(*demo_server)
    connection.request("GET", first_download)
    response = connection.getresponse()
    assert response.status == 404
    response.read()
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
            "X-Particular-Rights-Basis": "authorized",
        },
    )
    response = connection.getresponse()
    assert response.status == 413
    response.read()
    connection.close()

    status, _ = _post(demo_server, b"score", filename="score.mid")
    assert status == 415


def _mxl(entries: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return output.getvalue()


def test_malformed_score_returns_structured_error(demo_server: tuple[str, int]) -> None:
    status, payload = _post(demo_server, b"<score-partwise>")
    assert status == 400
    assert payload["error"] == "malformed_score"
    assert payload["message"]
    assert "diagnostic_id" in payload
    assert "score-partwise" not in payload["message"]


def test_unsafe_archive_upload_is_sanitized(demo_server: tuple[str, int]) -> None:
    status, payload = _post(demo_server, _mxl({"nested.zip": b"zip"}), filename="score.mxl")
    assert status == 400
    assert payload["error"] == "unsafe_archive"
    assert "diagnostic_id" in payload
    assert "nested" not in payload["message"].lower()


def test_oversized_archive_upload_is_sanitized(demo_server: tuple[str, int]) -> None:
    status, payload = _post(
        demo_server, _mxl({f"f{index}.xml": b"x" for index in range(65)}), filename="score.mxl"
    )
    assert status == 400
    assert payload["error"] == "oversized_file"
    assert "diagnostic_id" in payload


def test_limits_endpoint_reports_calibrated_limits(demo_server: tuple[str, int]) -> None:
    connection = http.client.HTTPConnection(*demo_server)
    connection.request("GET", "/api/limits")
    response = connection.getresponse()
    payload = cast(dict[str, Any], json.loads(response.read()))
    connection.close()

    assert response.status == 200
    assert {
        "max_upload_bytes",
        "max_expanded_total_bytes",
        "max_expanded_entry_bytes",
        "max_archive_entries",
        "max_parts",
        "max_events",
    } <= set(payload)
    assert payload["max_upload_bytes"] == MAX_UPLOAD_BYTES


def test_expired_jobs_are_purged_before_lookup() -> None:
    server = create_server(port=0, job_ttl_seconds=0.0)
    try:
        artifacts = server.storage_root / "job1" / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "manifest.json").write_text("{}")
        server.register_job("job1", artifacts)

        # A zero-second TTL means the next lookup finds the job expired.
        assert server.read_artifact("job1", "manifest.json") is None
        assert not artifacts.parent.exists()
    finally:
        server.server_close()


def test_explicit_delete_removes_a_job() -> None:
    server = create_server(port=0)
    try:
        artifacts = server.storage_root / "job1" / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "manifest.json").write_bytes(b"{}")
        server.register_job("job1", artifacts)

        assert server.read_artifact("job1", "manifest.json") == b"{}"
        assert server.delete_job("job1") is True
        assert server.read_artifact("job1", "manifest.json") is None
        assert server.delete_job("job1") is False
    finally:
        server.server_close()


def test_shutdown_removes_all_storage() -> None:
    server = create_server(port=0)
    root = server.storage_root
    assert root.exists()

    server.server_close()

    assert not root.exists()


def test_concurrent_delete_and_download_is_all_or_nothing() -> None:
    server = create_server(port=0)
    try:
        artifacts = server.storage_root / "job1" / "artifacts"
        artifacts.mkdir(parents=True)
        content = b"x" * 100_000
        (artifacts / "manifest.json").write_bytes(content)
        server.register_job("job1", artifacts)

        reads: list[bytes | None] = []

        def reader() -> None:
            while True:
                body = server.read_artifact("job1", "manifest.json")
                reads.append(body)
                if body is None:
                    return

        thread = threading.Thread(target=reader)
        thread.start()
        server.delete_job("job1")
        thread.join()

        # A read never sees a torn file: it is the whole artifact or nothing.
        assert all(body in (content, None) for body in reads)
        assert reads[-1] is None
    finally:
        server.server_close()


def test_explicit_delete_makes_downloads_unavailable(demo_server: tuple[str, int]) -> None:
    status, payload = _post(demo_server, FIXTURE.read_bytes())
    assert status == 200
    job_id = payload["job_id"]
    download = cast(dict[str, str], payload["artifacts"])["manifest"]

    connection = http.client.HTTPConnection(*demo_server)
    connection.request("DELETE", f"/artifacts/{job_id}")
    delete_response = connection.getresponse()
    delete_body = json.loads(delete_response.read())
    connection.close()
    assert delete_response.status == 200
    assert delete_body == {"deleted": True}

    connection = http.client.HTTPConnection(*demo_server)
    connection.request("GET", download)
    get_response = connection.getresponse()
    get_response.read()
    connection.close()
    assert get_response.status == 404


def test_part_exports_are_listed_and_served_as_single_parts(demo_server: tuple[str, int]) -> None:
    status, payload = _post(demo_server, FIXTURE.read_bytes())
    assert status == 200
    exports = payload["part_exports"]["Essential"]
    assert {entry["part_id"] for entry in exports} == {"P1", "P2", "P3", "P4"}

    connection = http.client.HTTPConnection(*demo_server)
    connection.request("GET", cast(str, exports[0]["url"]))
    response = connection.getresponse()
    body = response.read()
    connection.close()
    assert response.status == 200
    assert response.getheader("Content-Type") == "application/vnd.recordare.musicxml+xml"
    assert body.count(b"<part ") == 1


def test_serves_the_request_sequencer_module(demo_server: tuple[str, int]) -> None:
    connection = http.client.HTTPConnection(*demo_server)
    connection.request("GET", "/sequencer.js")
    response = connection.getresponse()
    body = response.read()
    connection.close()

    assert response.status == 200
    assert b"createSequencer" in body


def test_static_page_has_accessible_review_flow() -> None:
    html = (ROOT / "apps/web/public/index.html").read_text()
    assert '<label for="score-file">' in html
    assert 'name="rights-basis"' in html
    assert 'aria-live="polite"' in html
    assert "Director review required" in html


def _get(address: tuple[str, int], path: str) -> tuple[int, bytes]:
    connection = http.client.HTTPConnection(*address)
    connection.request("GET", path)
    response = connection.getresponse()
    body = response.read()
    connection.close()
    return response.status, body


def test_lists_and_serves_bundled_sample_scores(demo_server: tuple[str, int]) -> None:
    status, body = _get(demo_server, "/api/samples")
    assert status == 200
    samples = json.loads(body)["samples"]
    assert samples and samples[0]["id"] == "brandenburg-no3-mvt3"
    sample = samples[0]
    # Only an honestly-attestable basis is offered for a bundled sample.
    assert sample["rights_basis"] == "public_domain"

    # The served bytes are exactly the corpus fixture (single source of truth).
    status, served = _get(demo_server, sample["url"])
    assert status == 200
    fixture = (ROOT / "evaluation/fixtures/brandenburg-no3-mvt3-excerpt.musicxml").read_bytes()
    assert served == fixture

    # The sample regenerates through the normal generation path.
    generate_status, payload = _post(
        demo_server,
        served,
        filename="brandenburg-no3-mvt3-excerpt.musicxml",
        rights_basis=sample["rights_basis"],
    )
    assert generate_status == 200
    assert payload["job_id"]


def test_rejects_unknown_sample(demo_server: tuple[str, int]) -> None:
    status, _ = _get(demo_server, "/samples/not-a-real-sample.musicxml")
    assert status == 404
