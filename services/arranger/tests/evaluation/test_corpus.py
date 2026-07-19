from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evaluation.scripts.validate_corpus import (
    CorpusValidationError,
    load_manifest,
    select_entries,
    validate_corpus,
)

REPOSITORY_ROOT = Path(__file__).parents[4]
MANIFEST_PATH = REPOSITORY_ROOT / "evaluation/corpus/manifest.yaml"
SCHEMA_PATH = REPOSITORY_ROOT / "evaluation/rubrics/review.schema.json"


def _write_fixture(root: Path, contents: bytes = b"<score-partwise/>") -> str:
    fixture = root / "evaluation/fixtures/example.musicxml"
    fixture.parent.mkdir(parents=True)
    fixture.write_bytes(contents)
    return hashlib.sha256(contents).hexdigest()


def _entry(checksum: str) -> dict[str, object]:
    return {
        "id": "example",
        "path": "evaluation/fixtures/example.musicxml",
        "title": "Example",
        "composer": "Particular contributors",
        "work_status": "original",
        "source": "Created in-repository for deterministic testing",
        "encoding_license": "CC0-1.0",
        "instrumentation": [{"part": "P1", "instrument": "Violin", "family": "strings"}],
        "sha256": checksum,
        "expected_result": "accept",
        "parser_coverage": ["notes", "rests"],
        "test_uses": ["basic-import"],
    }


def _write_manifest(root: Path, entries: list[dict[str, object]]) -> Path:
    path = root / "evaluation/corpus/manifest.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"version": 1, "entries": entries}), encoding="utf-8")
    return path


def _write_schema(root: Path) -> Path:
    path = root / "evaluation/rubrics/review.schema.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "required": ["fixture_id", "engine_version", "evaluator", "score_review"],
                "properties": {
                    "engine_version": {"type": "string"},
                    "evaluator": {
                        "type": "object",
                        "required": ["role"],
                        "properties": {
                            "role": {"enum": ["director", "teacher", "arranger", "specialist"]}
                        },
                    },
                    "score_review": {
                        "type": "object",
                        "required": ["playability"],
                        "properties": {
                            "playability": {"type": "integer", "minimum": 1, "maximum": 5}
                        },
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("missing", ["source", "encoding_license"])
def test_rejects_missing_rights_metadata(tmp_path: Path, missing: str) -> None:
    checksum = _write_fixture(tmp_path)
    entry = _entry(checksum)
    del entry[missing]

    with pytest.raises(CorpusValidationError, match=missing):
        validate_corpus(tmp_path, _write_manifest(tmp_path, [entry]), _write_schema(tmp_path))


def test_rejects_checksum_drift(tmp_path: Path) -> None:
    checksum = _write_fixture(tmp_path)
    manifest = _write_manifest(tmp_path, [_entry(checksum)])
    schema = _write_schema(tmp_path)
    (tmp_path / "evaluation/fixtures/example.musicxml").write_bytes(b"changed")

    with pytest.raises(CorpusValidationError, match="checksum"):
        validate_corpus(tmp_path, manifest, schema)


def test_rejects_incomplete_review_schema(tmp_path: Path) -> None:
    checksum = _write_fixture(tmp_path)
    schema = _write_schema(tmp_path)
    schema.write_text(json.dumps({"type": "object"}), encoding="utf-8")

    with pytest.raises(CorpusValidationError, match="review schema"):
        validate_corpus(tmp_path, _write_manifest(tmp_path, [_entry(checksum)]), schema)


def test_repository_corpus_is_valid_and_filterable() -> None:
    inventory = validate_corpus(REPOSITORY_ROOT, MANIFEST_PATH, SCHEMA_PATH)

    assert [item.id for item in inventory] == [
        "mixed-ensemble-transposition",
        "string-orchestra-second-violin",
    ]
    entries = load_manifest(MANIFEST_PATH)
    assert [entry["id"] for entry in select_entries(entries, family="strings")] == [
        "mixed-ensemble-transposition",
        "string-orchestra-second-violin",
    ]
    assert [entry["id"] for entry in select_entries(entries, feature="transposition")] == [
        "mixed-ensemble-transposition"
    ]
    assert len(select_entries(entries, expected_result="accept")) == 2
