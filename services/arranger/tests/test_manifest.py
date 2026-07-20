from __future__ import annotations

from pathlib import Path

import pytest
from particular import application
from particular.application import generate_to_directory, generation_manifest, load_score
from particular.domain.score import Score
from particular.generation.selector import ArrangementFamily, generate_arrangement_family

ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "evaluation/fixtures/string-orchestra-second-violin.musicxml"


def _family_and_source() -> tuple[ArrangementFamily, str, Score]:
    score, checksum = load_score(FIXTURE)
    return generate_arrangement_family(score), checksum, score


def test_reproducibility_digest_is_stable_and_excludes_operational_metadata() -> None:
    family, checksum, score = _family_and_source()

    first = generation_manifest(family, checksum, score, generated_at="2026-01-01T00:00:00+00:00")
    second = generation_manifest(
        family, checksum, score, attested=True, generated_at="2026-12-31T23:59:59+00:00"
    )

    assert first["operational"]["generated_at"] != second["operational"]["generated_at"]
    assert first["operational"]["rights_attested"] is False
    assert second["operational"]["rights_attested"] is True
    # Operational metadata does not participate in the reproducibility identity.
    assert first["reproducibility_digest"] == second["reproducibility_digest"]
    assert len(first["reproducibility_digest"]) == 64


def test_engine_version_change_alters_reproducibility_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    family, checksum, score = _family_and_source()

    baseline = generation_manifest(family, checksum, score)["reproducibility_digest"]
    monkeypatch.setattr(application, "ENGINE_VERSION", "9.9.9")
    changed = generation_manifest(family, checksum, score)["reproducibility_digest"]

    assert baseline != changed


def test_profile_override_alters_reproducibility_identity() -> None:
    family, checksum, score = _family_and_source()

    baseline = generation_manifest(family, checksum, score)["reproducibility_digest"]
    overridden = generation_manifest(family, checksum, score, profile_overrides={"P1": "viola"})[
        "reproducibility_digest"
    ]

    assert baseline != overridden


def test_generate_to_directory_records_operational_metadata(tmp_path: Path) -> None:
    manifest = generate_to_directory(FIXTURE, tmp_path / "arrangement", attested=True)

    assert manifest["operational"]["rights_attested"] is True
    assert manifest["operational"]["generated_at"]
    assert manifest["operational"]["engine_build"] == "development"
    assert manifest["reproducibility"]["engine_version"] == manifest["engine_version"]
