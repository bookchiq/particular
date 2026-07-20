from __future__ import annotations

import json
from pathlib import Path

from particular.cli import main

ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "evaluation/fixtures/string-orchestra-second-violin.musicxml"


def test_generate_command_runs_full_pipeline(capsys: object, tmp_path: Path) -> None:
    output = tmp_path / "arrangement"

    result = main(["generate", str(FIXTURE), str(output)])

    assert result == 0
    assert sorted(path.name for path in output.iterdir()) == [
        "analysis.json",
        "challenge.musicxml",
        "core.musicxml",
        "foundation.musicxml",
        "manifest.json",
        "original-normalized.musicxml",
    ]
    manifest = json.loads((output / "manifest.json").read_text())
    assert len(manifest["source_sha256"]) == 64
    assert manifest["engine_version"] == "0.0.0"
    assert manifest["policy_version"] == 2
    assert set(manifest["operator_versions"]) == {
        "octave-range",
        "repetition-thin",
        "rhythm-merge",
    }
    assert manifest["tiers"][0]["name"] == "Foundation"
    assert manifest["tiers"][0]["target"] == 0.35
    assert manifest["tiers"][2]["explanation"].startswith("Unchanged: Challenge")
    assert any(change["explanation"] for change in manifest["changes"])
    sample_change = manifest["changes"][0]
    assert {
        "difficulty_delta",
        "role_effects",
        "operator_version",
        "locators",
    } <= set(sample_change)
    assert isinstance(sample_change["difficulty_delta"], dict)
    assert isinstance(sample_change["role_effects"], list)
    assert sample_change["locators"][0]["part_id"] == sample_change["part_id"]
    assert manifest["part_profiles"][0] == {
        "part_id": "P1",
        "profile_id": "violin",
        "profile_version": 2,
        "profile_confidence": "declared-instrument",
    }


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
