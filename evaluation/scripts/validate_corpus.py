"""Validate and inventory Particular's versioned evaluation corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast


class CorpusValidationError(ValueError):
    """Raised when corpus metadata or content violates the corpus contract."""


# A pilot score's musical usefulness may only be claimed once at least this many
# qualified reviewers rate it, each at or above the usefulness rating, without a
# blocking disagreement between them.
QUALIFIED_ROLES = {"director", "teacher", "arranger", "specialist"}
MIN_QUALIFIED_REVIEWS = 2
USEFULNESS_MIN_RATING = 3  # "usable with minor edits" or better, on a 1-5 scale.
DISAGREEMENT_SPREAD = 2  # A gap this wide on any dimension blocks a usefulness claim.
RATING_DIMENSIONS = (
    "playability",
    "fidelity",
    "meaningfulness",
    "notation_quality",
    "rehearsal_usefulness",
)


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


@dataclass(frozen=True)
class UsefulnessReport:
    """Whether human evaluation supports claiming musical usefulness yet."""

    reviewed: tuple[str, ...]
    sufficiently_reviewed: tuple[str, ...]
    validated: tuple[str, ...]
    disagreements: tuple[str, ...]
    usefulness_established: bool


def _resolve_ref(ref: str, root: dict[str, Any]) -> dict[str, Any]:
    node: Any = root
    for part in ref.lstrip("#/").split("/"):
        node = node[part]
    return cast(dict[str, Any], node)


def _schema_errors(
    value: Any, schema: dict[str, Any], root: dict[str, Any], path: str
) -> list[str]:
    """Validate a value against the subset of JSON Schema the review schema uses."""

    if "$ref" in schema:
        schema = _resolve_ref(schema["$ref"], root)
    if "enum" in schema and value not in schema["enum"]:
        return [f"{path or 'value'}: not one of {schema['enum']}"]
    if "const" in schema and value != schema["const"]:
        return [f"{path or 'value'}: must equal {schema['const']!r}"]
    kind = schema.get("type")
    errors: list[str] = []
    if kind == "object":
        if not isinstance(value, dict):
            return [f"{path or 'value'}: expected object"]
        properties = schema.get("properties", {})
        for field in schema.get("required", []):
            if field not in value:
                errors.append(f"{path}/{field}: required")
        if schema.get("additionalProperties") is False:
            errors += [
                f"{path}/{key}: unexpected property" for key in value if key not in properties
            ]
        for key, subschema in properties.items():
            if key in value:
                errors += _schema_errors(value[key], subschema, root, f"{path}/{key}")
    elif kind == "array":
        if not isinstance(value, list):
            return [f"{path or 'value'}: expected array"]
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                errors += _schema_errors(item, item_schema, root, f"{path}[{index}]")
    elif kind == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            return [f"{path or 'value'}: expected integer"]
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above maximum {schema['maximum']}")
    elif kind == "string":
        if not isinstance(value, str):
            return [f"{path or 'value'}: expected string"]
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: shorter than {schema['minLength']}")
    elif kind == "boolean" and not isinstance(value, bool):
        errors.append(f"{path or 'value'}: expected boolean")
    return errors


def validate_review_document(document: Any, schema: dict[str, Any]) -> None:
    """Raise if a review document does not conform to the review schema."""

    errors = _schema_errors(document, schema, schema, "")
    if errors:
        raise CorpusValidationError("; ".join(errors))


def evaluate_reviews(reviews_dir: Path, review_schema_path: Path) -> UsefulnessReport:
    """Evaluate collected reviews against the usefulness gate.

    Reviews live as schema-conforming JSON documents. Usefulness for a pilot
    score is only established with enough qualified reviews, all at or above the
    usefulness rating, and without a blocking disagreement. With no reviews the
    gate honestly reports that usefulness is not yet established.
    """

    schema = _load_json(review_schema_path, "review schema")
    by_fixture: dict[str, list[dict[str, Any]]] = {}
    review_paths = sorted(reviews_dir.glob("*.json")) if reviews_dir.is_dir() else []
    for review_path in review_paths:
        document = _load_json(review_path, f"review {review_path.name}")
        try:
            validate_review_document(document, schema)
        except CorpusValidationError as error:
            raise CorpusValidationError(f"{review_path.name}: {error}") from error
        by_fixture.setdefault(str(document["fixture_id"]), []).append(document)

    sufficiently: list[str] = []
    validated: list[str] = []
    disagreements: list[str] = []
    for fixture_id, reviews in sorted(by_fixture.items()):
        qualified = [
            review
            for review in reviews
            if review["evaluator"]["role"] in QUALIFIED_ROLES
            and review["evaluator"]["consent_confirmed"] is True
        ]
        if len(qualified) < MIN_QUALIFIED_REVIEWS:
            continue
        sufficiently.append(fixture_id)
        verdicts = [
            review["score_review"]["rehearsal_usefulness"] >= USEFULNESS_MIN_RATING
            for review in qualified
        ]
        spread = max(
            max(review["score_review"][dimension] for review in qualified)
            - min(review["score_review"][dimension] for review in qualified)
            for dimension in RATING_DIMENSIONS
        )
        disagrees = (any(verdicts) and not all(verdicts)) or spread >= DISAGREEMENT_SPREAD
        if disagrees:
            disagreements.append(fixture_id)
        elif all(verdicts):
            validated.append(fixture_id)
    return UsefulnessReport(
        reviewed=tuple(sorted(by_fixture)),
        sufficiently_reviewed=tuple(sufficiently),
        validated=tuple(validated),
        disagreements=tuple(disagreements),
        usefulness_established=bool(validated),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=("integrity", "usefulness"), default="integrity")
    parser.add_argument("--feature")
    parser.add_argument("--family")
    parser.add_argument("--expected-result", choices=sorted(ALLOWED_RESULTS))
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    manifest = root / "evaluation/corpus/manifest.yaml"
    schema = root / "evaluation/rubrics/review.schema.json"
    try:
        if arguments.mode == "usefulness":
            report = evaluate_reviews(root / "evaluation/results/reviews", schema)
            print(
                json.dumps(
                    {
                        "outcome": "human-usefulness",
                        "usefulness_established": report.usefulness_established,
                        "reviewed": list(report.reviewed),
                        "sufficiently_reviewed": list(report.sufficiently_reviewed),
                        "validated": list(report.validated),
                        "disagreements": list(report.disagreements),
                        "min_qualified_reviews": MIN_QUALIFIED_REVIEWS,
                    }
                )
            )
            return 0
        validate_corpus(root, manifest, schema)
        selected = select_entries(
            load_manifest(manifest),
            feature=arguments.feature,
            family=arguments.family,
            expected_result=arguments.expected_result,
        )
        print(json.dumps({"count": len(selected), "fixtures": [item["id"] for item in selected]}))
        return 0
    except CorpusValidationError as error:
        print(json.dumps({"outcome": arguments.mode, "error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
