from __future__ import annotations

import json
from pathlib import Path

import pytest
from particular.cli import main

ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "evaluation/fixtures/string-orchestra-second-violin.musicxml"


def test_generate_command_runs_full_pipeline(capsys: object, tmp_path: Path) -> None:
    output = tmp_path / "arrangement"

    result = main(["generate", str(FIXTURE), str(output)])

    assert result == 0
    produced = {path.name for path in output.iterdir()}
    assert {
        "analysis.json",
        "essential.musicxml",
        "supported.musicxml",
        "original.musicxml",
        "manifest.json",
        "source-normalized.musicxml",
    } <= produced
    # Per-part exports for every tier (the fixture has parts P1-P4).
    assert {"essential-P1.musicxml", "supported-P4.musicxml", "original-P2.musicxml"} <= produced
    manifest = json.loads((output / "manifest.json").read_text())
    assert len(manifest["source_sha256"]) == 64
    assert manifest["engine_version"] == "0.0.0"
    assert manifest["policy_version"] == 2
    assert set(manifest["operator_versions"]) == {
        "accidental-simplify",
        "desyncopate",
        "leap-fold",
        "octave-range",
        "repetition-thin",
        "rhythm-even",
        "rhythm-merge",
        "run-thin",
    }
    assert manifest["tiers"][0]["name"] == "Essential"
    assert manifest["tiers"][0]["target"] == 0.35
    assert manifest["tiers"][2]["explanation"].startswith("Unchanged: Original")
    summary = manifest["change_summary"]
    assert set(summary) == {"Essential", "Supported", "Original"}
    foundation = summary["Essential"]
    assert set(foundation) == {"accepted", "rejected", "rejected_total", "noops"}
    assert isinstance(foundation["accepted"], list)
    assert isinstance(foundation["noops"]["count"], int)
    assert isinstance(foundation["noops"]["by_operator"], dict)
    assert len(manifest["reproducibility_digest"]) == 64
    assert manifest["reproducibility"]["engine_version"] == manifest["engine_version"]
    assert manifest["operational"]["attestation"] is None
    assert manifest["part_profiles"][0] == {
        "part_id": "P1",
        "profile_id": "violin",
        "profile_version": 2,
        "profile_confidence": "declared-instrument",
    }


def test_generate_records_rights_attestation(tmp_path: Path) -> None:
    output = tmp_path / "attested"

    assert main(["generate", str(FIXTURE), str(output), "--rights-basis", "public_domain"]) == 0

    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["operational"]["attestation"]["basis"] == "public_domain"


def test_unknown_rights_basis_is_a_structured_argument_error(capsys: object) -> None:
    assert main(["generate", str(FIXTURE), "out", "--rights-basis", "nope"]) == 2

    error = json.loads(capsys.readouterr().err)  # type: ignore[attr-defined]
    assert error["error"]["code"] == "invalid_arguments"


def test_preflight_and_analyze_emit_structured_json(capsys: object) -> None:
    assert main(["preflight", str(FIXTURE)]) == 0
    preflight_output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert preflight_output["ok"] is True
    assert preflight_output["command"] == "preflight"
    assert preflight_output["data"]["accepted"] is True

    assert main(["analyze", str(FIXTURE)]) == 0
    analysis_output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert analysis_output["ok"] is True
    assert analysis_output["command"] == "analyze"
    assert analysis_output["data"]["parts"][1]["profile_id"] == "violin"
    assert analysis_output["data"]["parts"][1]["profile_confidence"] == "declared-instrument"

    assert main(["analyze", str(FIXTURE), "--instrument-profile", "P1=viola"]) == 0
    overridden_output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert overridden_output["data"]["parts"][0]["profile_id"] == "viola"
    assert overridden_output["data"]["parts"][0]["profile_confidence"] == "director-override"


def test_invalid_input_leaves_no_output_and_returns_json_error(
    capsys: object, tmp_path: Path
) -> None:
    source = tmp_path / "unsafe.musicxml"
    source.write_text("<!DOCTYPE score-partwise><score-partwise/>")
    output = tmp_path / "must-not-exist"

    assert main(["generate", str(source), str(output)]) != 0
    assert not output.exists()
    error = json.loads(capsys.readouterr().err)  # type: ignore[attr-defined]
    assert error["ok"] is False
    assert error["error"]["type"] == "UnsafeScoreError"
    assert "score-partwise" not in error["error"]["message"]


def test_unknown_instrument_profile_override_returns_json_error(capsys: object) -> None:
    assert main(["analyze", str(FIXTURE), "--instrument-profile", "P99=violin"]) == 1

    error = json.loads(capsys.readouterr().err)  # type: ignore[attr-defined]
    assert error["error"]["message"] == "instrument profile override references unknown part: P99"


def test_generate_success_uses_the_uniform_envelope(capsys: object, tmp_path: Path) -> None:
    assert main(["generate", str(FIXTURE), str(tmp_path / "out")]) == 0

    result = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert result == {
        "ok": True,
        "command": "generate",
        "data": {"output": str(tmp_path / "out"), "source_sha256": result["data"]["source_sha256"]},
    }


@pytest.mark.parametrize("argv", [[], ["bogus"], ["generate", str(FIXTURE)]])
def test_argument_errors_are_structured_json(capsys: object, argv: list[str]) -> None:
    assert main(argv) == 2

    error = json.loads(capsys.readouterr().err)  # type: ignore[attr-defined]
    assert error["ok"] is False
    assert error["command"] is None
    assert error["error"]["code"] == "invalid_arguments"
    assert error["error"]["type"] == "ArgumentError"


def test_missing_source_path_is_structured_json(capsys: object, tmp_path: Path) -> None:
    assert main(["analyze", str(tmp_path / "absent.musicxml")]) == 1

    error = json.loads(capsys.readouterr().err)  # type: ignore[attr-defined]
    assert error["ok"] is False
    assert error["command"] == "analyze"
    assert error["error"]["code"] == "internal_error"
