from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evaluation.scripts.validate_corpus import (
    RATING_DIMENSIONS,
    CorpusValidationError,
    evaluate_reviews,
    load_manifest,
    select_entries,
    validate_corpus,
    validate_review_document,
)

REPOSITORY_ROOT = Path(__file__).parents[4]
MANIFEST_PATH = REPOSITORY_ROOT / "evaluation/corpus/manifest.yaml"
SCHEMA_PATH = REPOSITORY_ROOT / "evaluation/rubrics/review.schema.json"


def _review(role: str = "director", usefulness: int = 4) -> dict[str, object]:
    ratings = {dimension: 4 for dimension in RATING_DIMENSIONS}
    ratings["rehearsal_usefulness"] = usefulness
    return {
        "fixture_id": "example",
        "engine_version": "0.0.0",
        "evaluator": {"role": role, "consent_confirmed": True},
        "score_review": ratings,
        "passage_reviews": [],
    }


def _write_review(reviews_dir: Path, name: str, document: dict[str, object]) -> None:
    reviews_dir.mkdir(parents=True, exist_ok=True)
    (reviews_dir / name).write_text(json.dumps(document), encoding="utf-8")


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
        "brandenburg-no3-mvt3-excerpt",
        "mixed-ensemble-transposition",
        "string-orchestra-second-violin",
    ]
    entries = load_manifest(MANIFEST_PATH)
    assert [entry["id"] for entry in select_entries(entries, family="strings")] == [
        "brandenburg-no3-mvt3-excerpt",
        "mixed-ensemble-transposition",
        "string-orchestra-second-violin",
    ]
    assert [entry["id"] for entry in select_entries(entries, feature="transposition")] == [
        "brandenburg-no3-mvt3-excerpt",
        "mixed-ensemble-transposition",
    ]
    assert len(select_entries(entries, expected_result="accept")) == 3


def test_review_document_validation_accepts_and_rejects() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    validate_review_document(_review(), schema)

    without_consent = _review()
    without_consent["evaluator"] = {"role": "director", "consent_confirmed": False}
    with pytest.raises(CorpusValidationError):
        validate_review_document(without_consent, schema)

    missing_field = _review()
    del missing_field["passage_reviews"]
    with pytest.raises(CorpusValidationError, match="passage_reviews"):
        validate_review_document(missing_field, schema)

    with pytest.raises(CorpusValidationError):
        validate_review_document(_review(usefulness=9), schema)


def test_usefulness_needs_two_qualified_reviews(tmp_path: Path) -> None:
    reviews = tmp_path / "reviews"

    empty = evaluate_reviews(reviews, SCHEMA_PATH)
    assert empty.usefulness_established is False
    assert empty.reviewed == ()

    _write_review(reviews, "one.json", _review())
    one = evaluate_reviews(reviews, SCHEMA_PATH)
    assert one.reviewed == ("example",)
    assert one.sufficiently_reviewed == ()
    assert one.usefulness_established is False


def test_two_agreeing_reviews_establish_usefulness(tmp_path: Path) -> None:
    reviews = tmp_path / "reviews"
    _write_review(reviews, "one.json", _review(role="director", usefulness=4))
    _write_review(reviews, "two.json", _review(role="teacher", usefulness=4))

    report = evaluate_reviews(reviews, SCHEMA_PATH)

    assert report.validated == ("example",)
    assert report.disagreements == ()
    assert report.usefulness_established is True


def test_reviewer_disagreement_blocks_usefulness(tmp_path: Path) -> None:
    reviews = tmp_path / "reviews"
    _write_review(reviews, "one.json", _review(role="director", usefulness=5))
    _write_review(reviews, "two.json", _review(role="teacher", usefulness=1))

    report = evaluate_reviews(reviews, SCHEMA_PATH)

    assert report.sufficiently_reviewed == ("example",)
    assert report.disagreements == ("example",)
    assert report.validated == ()
    assert report.usefulness_established is False


def test_malformed_review_document_is_rejected(tmp_path: Path) -> None:
    reviews = tmp_path / "reviews"
    reviews.mkdir()
    (reviews / "bad.json").write_text("{ not json", encoding="utf-8")

    with pytest.raises(CorpusValidationError):
        evaluate_reviews(reviews, SCHEMA_PATH)


def test_repository_reviews_directory_reports_not_established() -> None:
    report = evaluate_reviews(REPOSITORY_ROOT / "evaluation/results/reviews", SCHEMA_PATH)

    assert report.usefulness_established is False
    assert report.validated == ()
