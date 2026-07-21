"""Application services composing Particular's deterministic engine."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import shutil
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from particular.analysis.difficulty import analyze_part, instrument_profiles
from particular.domain.score import Score
from particular.exporters.musicxml import (
    export_musicxml,
    export_part_musicxml,
    semantic_fingerprint,
)
from particular.exporters.playback import playback_timeline
from particular.generation.selector import (
    DEFAULT_TIER,
    TIER_NAMES,
    ArrangementFamily,
    compose_mixed_tier,
    generate_arrangement_family,
)
from particular.importers.musicxml import parse_musicxml
from particular.importers.security import extract_mxl
from particular.validation.arrangement import validate_family


def _engine_version() -> str:
    try:
        return importlib.metadata.version("particular-arranger")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0+unknown"


# The installed package version; a build/commit identifier set at deploy time is
# recorded separately as operational metadata.
ENGINE_VERSION = _engine_version()
# Version of the normalized-score representation the engine analyzes and exports.
NORMALIZED_SCHEMA_VERSION = 1
# Cap on listed meaningful rejections per tier; the total is always reported.
MAX_REJECTED_PER_TIER = 50
# Rights bases an uploader may attest to, and the attestation record version.
ATTESTATION_SCHEMA_VERSION = 1
RIGHTS_BASES = ("original", "public_domain", "authorized")


def _build_attestation(rights_basis: str | None, attested_at: str | None) -> dict[str, Any] | None:
    """Return a versioned attestation record, or None when no basis is asserted."""

    if rights_basis is None:
        return None
    if rights_basis not in RIGHTS_BASES:
        raise ValueError(f"unknown rights basis: {rights_basis}")
    return {
        "schema_version": ATTESTATION_SCHEMA_VERSION,
        "basis": rights_basis,
        "attested_at": attested_at,
    }


def _summarize_changes(changes: Any) -> dict[str, Any]:
    """Group ledger records per tier into accepted, meaningful rejections, and
    aggregated no-op statistics, keeping the summary bounded regardless of scale."""

    summary: dict[str, dict[str, Any]] = {}
    for change in changes:
        tier = summary.setdefault(
            change.tier,
            {
                "accepted": [],
                "rejected": [],
                "rejected_total": 0,
                "noops": {"count": 0, "by_operator": {}},
            },
        )
        if change.status == "accepted":
            tier["accepted"].append(asdict(change))
        elif change.applicable:
            tier["rejected_total"] += 1
            if len(tier["rejected"]) < MAX_REJECTED_PER_TIER:
                tier["rejected"].append(asdict(change))
        else:
            noops = tier["noops"]
            noops["count"] += 1
            noops["by_operator"][change.operator] = noops["by_operator"].get(change.operator, 0) + 1
    return summary


ARTIFACT_FILENAMES = {
    "original": "original-normalized.musicxml",
    "foundation": "foundation.musicxml",
    "core": "core.musicxml",
    "challenge": "challenge.musicxml",
    "manifest": "manifest.json",
    "analysis": "analysis.json",
}


def part_export_filename(tier: str, part_id: str) -> str:
    """Stable filename for a single tier part's rehearsal-ready MusicXML."""

    return f"{tier.casefold()}-{part_id}.musicxml"


# The mixed-tier ("custom") set draws each part from a director-chosen tier.
MIXED_TIER_FILENAME = "custom.musicxml"


def mixed_part_export_filename(part_id: str) -> str:
    """Stable filename for a single part of the mixed-tier custom set."""

    return f"custom-{part_id}.musicxml"


# Playback timelines are published per source so the browser can audition any of
# them; "original" and "custom" join the three tiers.
PLAYBACK_SOURCES = ("original", "foundation", "core", "challenge")


def playback_filename(source: str) -> str:
    """Stable filename for a source's deterministic playback timeline."""

    return f"{source.casefold()}.playback.json"


def _validate_tier_assignments(
    score: Score, tier_assignments: dict[str, str] | None
) -> dict[str, str]:
    assignments = tier_assignments or {}
    unknown_parts = sorted(set(assignments).difference(part.id for part in score.parts))
    if unknown_parts:
        raise ValueError(f"tier assignment references unknown part: {unknown_parts[0]}")
    unknown_tiers = sorted(set(assignments.values()).difference(TIER_NAMES))
    if unknown_tiers:
        raise ValueError(f"tier assignment references unknown tier: {unknown_tiers[0]}")
    return assignments


def _custom_arrangement(score: Score, assignments: dict[str, str]) -> dict[str, Any]:
    """Record the director's chosen tier per part, including defaulted parts."""

    return {
        "assignments": dict(sorted(assignments.items())),
        "parts": [
            {"part_id": part.id, "tier": assignments.get(part.id, DEFAULT_TIER)}
            for part in score.parts
        ],
    }


def _validate_profile_overrides(
    score: Score, profile_overrides: dict[str, str] | None
) -> dict[str, str]:
    overrides = profile_overrides or {}
    unknown_parts = sorted(set(overrides).difference(part.id for part in score.parts))
    if unknown_parts:
        raise ValueError(f"instrument profile override references unknown part: {unknown_parts[0]}")
    return overrides


def load_score(path: Path) -> tuple[Score, str]:
    """Load a supported source safely and return it with its immutable checksum."""

    source = path.read_bytes()
    checksum = hashlib.sha256(source).hexdigest()
    suffix = path.suffix.casefold()
    if suffix == ".mxl":
        xml = extract_mxl(source)
    elif suffix in {".xml", ".musicxml"}:
        xml = source
    else:
        raise ValueError("input must use .musicxml, .xml, or .mxl")
    return parse_musicxml(xml), checksum


def analyze_score(score: Score, profile_overrides: dict[str, str] | None = None) -> dict[str, Any]:
    """Return a stable JSON-ready explanation of part difficulty."""

    overrides = _validate_profile_overrides(score, profile_overrides)
    return {
        "engine_version": ENGINE_VERSION,
        "semantic_fingerprint": semantic_fingerprint(score),
        "available_instrument_profiles": sorted(
            profile_id for profile_id in instrument_profiles().profiles if profile_id != "generic"
        ),
        "parts": [
            {
                "part_id": part.id,
                "part_name": part.name,
                "measures": [measure.number for measure in part.measures],
                **asdict(analyze_part(part, overrides.get(part.id))),
            }
            for part in score.parts
        ],
    }


def generation_manifest(
    family: ArrangementFamily,
    source_checksum: str,
    source: Score,
    profile_overrides: dict[str, str] | None = None,
    rights_basis: str | None = None,
    generated_at: str | None = None,
    locked_measures: frozenset[tuple[str, str]] | None = None,
    tier_assignments: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the stable, content-minimized generation audit record.

    The ``reproducibility`` block holds every input that determines the output,
    condensed into ``reproducibility_digest``; ``operational`` metadata (build
    identity, timestamp, rights attestation) is recorded but never affects it.
    Mixed-tier ``tier_assignments`` only select among the reproducible tiers, so
    they are recorded as a separate ``custom_arrangement`` block, not in the
    reproducibility digest.
    """

    overrides = _validate_profile_overrides(source, profile_overrides)
    assignments = _validate_tier_assignments(source, tier_assignments)
    operator_versions = dict(
        sorted((change.operator, change.operator_version) for change in family.manifest.changes)
    )
    source_fingerprint = semantic_fingerprint(source)
    reproducibility = {
        "engine_version": ENGINE_VERSION,
        "normalized_schema_version": NORMALIZED_SCHEMA_VERSION,
        "source_sha256": source_checksum,
        "source_semantic_fingerprint": source_fingerprint,
        "instrument_profile_version": instrument_profiles().version,
        "tier_policy_version": family.manifest.policy_version,
        "operator_versions": operator_versions,
        "instrument_profile_overrides": dict(sorted(overrides.items())),
        "locked_measures": sorted(list(pair) for pair in (locked_measures or frozenset())),
        "seed": None,
    }
    reproducibility_digest = hashlib.sha256(
        json.dumps(reproducibility, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    manifest: dict[str, Any] = {
        "engine_version": ENGINE_VERSION,
        "policy_version": family.manifest.policy_version,
        "source_sha256": source_checksum,
        "source_semantic_fingerprint": source_fingerprint,
        "operator_versions": operator_versions,
        "reproducibility": reproducibility,
        "reproducibility_digest": reproducibility_digest,
        "operational": {
            "engine_build": os.environ.get("PARTICULAR_BUILD", "development"),
            "generated_at": generated_at,
            "attestation": _build_attestation(rights_basis, generated_at),
        },
        "part_profiles": [
            {
                "part_id": part.id,
                "profile_id": analysis.profile_id,
                "profile_version": analysis.profile_version,
                "profile_confidence": analysis.profile_confidence,
            }
            for part in source.parts
            for analysis in [analyze_part(part, overrides.get(part.id))]
        ],
        "tiers": [
            {
                "name": tier.name,
                "target": tier.target,
                "explanation": tier.explanation,
                "semantic_fingerprint": semantic_fingerprint(tier.score),
            }
            for tier in family.tiers
        ],
        "change_summary": _summarize_changes(family.manifest.changes),
    }
    if assignments:
        manifest["custom_arrangement"] = _custom_arrangement(source, assignments)
    return manifest


def generate_to_directory(
    source_path: Path,
    output_path: Path,
    profile_overrides: dict[str, str] | None = None,
    rights_basis: str | None = None,
    locked_measures: frozenset[tuple[str, str]] | None = None,
    tier_assignments: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Generate and atomically publish a complete arrangement directory.

    When ``tier_assignments`` are supplied, a mixed-tier ``custom`` score (each
    part drawn from its assigned tier) and its per-part exports are published
    alongside the standard tiers.
    """

    if output_path.exists():
        raise FileExistsError(f"output directory already exists: {output_path}")
    score, checksum = load_score(source_path)
    overrides = _validate_profile_overrides(score, profile_overrides)
    assignments = _validate_tier_assignments(score, tier_assignments)
    family = generate_arrangement_family(score, overrides, locked_measures)
    validate_family(score, family, overrides)
    analysis = analyze_score(score, overrides)
    generated_at = datetime.now(UTC).isoformat()
    manifest = generation_manifest(
        family,
        checksum,
        score,
        overrides,
        rights_basis=rights_basis,
        generated_at=generated_at,
        locked_measures=locked_measures,
        tier_assignments=assignments,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_path.name}-", dir=output_path.parent))
    try:

        def _write_playback(source: str, source_score: Score) -> None:
            (temporary / playback_filename(source)).write_text(
                json.dumps(playback_timeline(source_score), separators=(",", ":")),
                encoding="utf-8",
            )

        (temporary / ARTIFACT_FILENAMES["original"]).write_bytes(export_musicxml(score))
        _write_playback("original", score)
        for tier in family.tiers:
            artifact = ARTIFACT_FILENAMES[tier.name.casefold()]
            (temporary / artifact).write_bytes(export_musicxml(tier.score))
            _write_playback(tier.name, tier.score)
            for part in tier.score.parts:
                (temporary / part_export_filename(tier.name, part.id)).write_bytes(
                    export_part_musicxml(tier.score, part.id)
                )
        if assignments:
            mixed = compose_mixed_tier(family, assignments)
            (temporary / MIXED_TIER_FILENAME).write_bytes(export_musicxml(mixed))
            _write_playback("custom", mixed)
            for part in mixed.parts:
                (temporary / mixed_part_export_filename(part.id)).write_bytes(
                    export_part_musicxml(mixed, part.id)
                )
        (temporary / ARTIFACT_FILENAMES["manifest"]).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (temporary / ARTIFACT_FILENAMES["analysis"]).write_text(
            json.dumps(analysis, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.rename(temporary, output_path)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return manifest
