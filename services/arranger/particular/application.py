"""Application services composing Particular's deterministic engine."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from particular.analysis.difficulty import analyze_part
from particular.domain.score import Score
from particular.exporters.musicxml import export_musicxml, semantic_fingerprint
from particular.generation.selector import ArrangementFamily, generate_arrangement_family
from particular.importers.musicxml import parse_musicxml
from particular.importers.security import extract_mxl
from particular.validation.arrangement import validate_family

ENGINE_VERSION = "0.0.0"
ARTIFACT_FILENAMES = {
    "original": "original-normalized.musicxml",
    "foundation": "foundation.musicxml",
    "core": "core.musicxml",
    "challenge": "challenge.musicxml",
    "manifest": "manifest.json",
    "analysis": "analysis.json",
}


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


def analyze_score(score: Score) -> dict[str, Any]:
    """Return a stable JSON-ready explanation of part difficulty."""

    return {
        "engine_version": ENGINE_VERSION,
        "semantic_fingerprint": semantic_fingerprint(score),
        "parts": [
            {
                "part_id": part.id,
                "part_name": part.name,
                **asdict(analyze_part(part)),
            }
            for part in score.parts
        ],
    }


def generation_manifest(
    family: ArrangementFamily, source_checksum: str, source: Score
) -> dict[str, Any]:
    """Build the stable, content-minimized generation audit record."""

    changes = [asdict(change) for change in family.manifest.changes]
    operator_versions = {change.operator: 1 for change in family.manifest.changes}
    return {
        "engine_version": ENGINE_VERSION,
        "policy_version": family.manifest.policy_version,
        "source_sha256": source_checksum,
        "source_semantic_fingerprint": semantic_fingerprint(source),
        "operator_versions": dict(sorted(operator_versions.items())),
        "tiers": [
            {"name": tier.name, "semantic_fingerprint": semantic_fingerprint(tier.score)}
            for tier in family.tiers
        ],
        "changes": changes,
    }


def generate_to_directory(source_path: Path, output_path: Path) -> dict[str, Any]:
    """Generate and atomically publish a complete arrangement directory."""

    if output_path.exists():
        raise FileExistsError(f"output directory already exists: {output_path}")
    score, checksum = load_score(source_path)
    family = generate_arrangement_family(score)
    validate_family(score, family)
    analysis = analyze_score(score)
    manifest = generation_manifest(family, checksum, score)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_path.name}-", dir=output_path.parent))
    try:
        (temporary / ARTIFACT_FILENAMES["original"]).write_bytes(export_musicxml(score))
        for tier in family.tiers:
            artifact = ARTIFACT_FILENAMES[tier.name.casefold()]
            (temporary / artifact).write_bytes(export_musicxml(tier.score))
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
