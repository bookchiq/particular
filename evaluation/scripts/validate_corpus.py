"""Validate and inventory Particular's versioned evaluation corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class CorpusValidationError(ValueError):
    """Raised when corpus metadata or content violates the corpus contract."""


@dataclass(frozen=True)
class InventoryItem:
    """Stable, display-safe summary of a validated fixture."""

    id: str
    path: str
    expected_result: str
    families: tuple[str, ...]
    parser_coverage: tuple[str, ...]
    test_uses: tuple[str, ...]


REQUIRED_ENTRY_FIELDS = (
    "id",
    "path",
    "title",
    "composer",
    "work_status",
    "source",
    "encoding_license",
    "instrumentation",
    "sha256",
    "expected_result",
    "parser_coverage",
    "test_uses",
)
REQUIRED_REVIEW_FIELDS = {"fixture_id", "engine_version", "evaluator", "score_review"}
ALLOWED_RESULTS = {"accept", "reject"}


def _load_json(path: Path, description: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusValidationError(f"invalid {description}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusValidationError(f"{description} must contain an object")
    return value


def load_manifest(path: Path) -> list[dict[str, Any]]:
    """Load the JSON-compatible YAML manifest and return entries in stable order."""

    manifest = _load_json(path, "corpus manifest")
    if manifest.get("version") != 1:
        raise CorpusValidationError("corpus manifest version must be 1")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not all(isinstance(item, dict) for item in entries):
        raise CorpusValidationError("corpus manifest entries must be a list of objects")
    return sorted(entries, key=lambda entry: str(entry.get("id", "")))


def select_entries(
    entries: list[dict[str, Any]],
    *,
    feature: str | None = None,
    family: str | None = None,
    expected_result: str | None = None,
) -> list[dict[str, Any]]:
    """Return a deterministic manifest subset for parser and evaluation jobs."""

    selected = []
    for entry in entries:
        instruments = entry.get("instrumentation", [])
        families = {
            instrument.get("family") for instrument in instruments if isinstance(instrument, dict)
        }
        if feature is not None and feature not in entry.get("parser_coverage", []):
            continue
        if family is not None and family not in families:
            continue
        if expected_result is not None and entry.get("expected_result") != expected_result:
            continue
        selected.append(entry)
    return sorted(selected, key=lambda entry: str(entry.get("id", "")))


def _validate_review_schema(path: Path) -> None:
    schema = _load_json(path, "review schema")
    properties = schema.get("properties")
    required = schema.get("required")
    if schema.get("type") != "object" or not isinstance(properties, dict):
        raise CorpusValidationError("review schema must define an object and properties")
    if not isinstance(required, list) or not REQUIRED_REVIEW_FIELDS.issubset(required):
        raise CorpusValidationError("review schema is missing required review fields")
    evaluator = properties.get("evaluator", {})
    score_review = properties.get("score_review", {})
    if not isinstance(evaluator, dict) or "role" not in evaluator.get("required", []):
        raise CorpusValidationError("review schema must require evaluator role")
    if not isinstance(score_review, dict) or not (
        score_review.get("required") or score_review.get("$ref")
    ):
        raise CorpusValidationError("review schema must require score-level ratings")


def validate_corpus(
    repository_root: Path, manifest_path: Path, review_schema_path: Path
) -> list[InventoryItem]:
    """Validate rights, checksums, selection metadata, and review schema basics."""

    _validate_review_schema(review_schema_path)
    entries = load_manifest(manifest_path)
    errors: list[str] = []
    inventory: list[InventoryItem] = []
    seen_ids: set[str] = set()
    for entry in entries:
        fixture_id = str(entry.get("id", "<missing id>"))
        missing = [field for field in REQUIRED_ENTRY_FIELDS if not entry.get(field)]
        if missing:
            errors.append(f"{fixture_id}: missing {', '.join(missing)}")
            continue
        if fixture_id in seen_ids:
            errors.append(f"{fixture_id}: duplicate id")
            continue
        seen_ids.add(fixture_id)
        if entry["work_status"] not in {"original", "public-domain"}:
            errors.append(f"{fixture_id}: work_status must be original or public-domain")
        if entry["expected_result"] not in ALLOWED_RESULTS:
            errors.append(f"{fixture_id}: invalid expected_result")
        relative_path = Path(str(entry["path"]))
        fixture_path = repository_root / relative_path
        if relative_path.is_absolute() or ".." in relative_path.parts:
            errors.append(f"{fixture_id}: path must remain within the repository")
        elif not fixture_path.is_file():
            errors.append(f"{fixture_id}: fixture does not exist")
        else:
            checksum = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
            if checksum != entry["sha256"]:
                errors.append(
                    f"{fixture_id}: checksum drift (expected {entry['sha256']}, got {checksum})"
                )
        instruments = entry["instrumentation"]
        if not isinstance(instruments, list) or any(
            not isinstance(item, dict)
            or not all(item.get(field) for field in ("part", "instrument", "family"))
            for item in instruments
        ):
            errors.append(f"{fixture_id}: instrumentation entries require part, instrument, family")
            continue
        inventory.append(
            InventoryItem(
                id=fixture_id,
                path=str(entry["path"]),
                expected_result=str(entry["expected_result"]),
                families=tuple(sorted({str(item["family"]) for item in instruments})),
                parser_coverage=tuple(sorted(map(str, entry["parser_coverage"]))),
                test_uses=tuple(sorted(map(str, entry["test_uses"]))),
            )
        )
    if errors:
        raise CorpusValidationError("; ".join(errors))
    return sorted(inventory, key=lambda item: item.id)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--feature")
    parser.add_argument("--family")
    parser.add_argument("--expected-result", choices=sorted(ALLOWED_RESULTS))
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    manifest = root / "evaluation/corpus/manifest.yaml"
    schema = root / "evaluation/rubrics/review.schema.json"
    validate_corpus(root, manifest, schema)
    selected = select_entries(
        load_manifest(manifest),
        feature=arguments.feature,
        family=arguments.family,
        expected_result=arguments.expected_result,
    )
    print(json.dumps({"count": len(selected), "fixtures": [item["id"] for item in selected]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
