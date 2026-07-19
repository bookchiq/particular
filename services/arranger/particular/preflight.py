"""Safe score preflight entry point."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from particular.domain.score import Score
from particular.exporters.musicxml import semantic_fingerprint
from particular.importers.musicxml import parse_musicxml
from particular.importers.security import DEFAULT_ARCHIVE_LIMITS, ArchiveLimits, extract_mxl


@dataclass(frozen=True)
class PreflightReport:
    accepted: bool
    part_count: int
    measure_count: int
    warning_count: int
    export_capable: bool
    semantic_fingerprint: str


def preflight(path: Path, limits: ArchiveLimits = DEFAULT_ARCHIVE_LIMITS) -> PreflightReport:
    """Read, safely unpack when necessary, parse, and summarize a source score."""

    data = path.read_bytes()
    if path.suffix.lower() == ".mxl":
        data = extract_mxl(data, limits)
    return summarize_preflight(parse_musicxml(data))


def summarize_preflight(score: Score) -> PreflightReport:
    """Summarize an already parsed score without repeating intake work."""

    return PreflightReport(
        accepted=True,
        part_count=len(score.parts),
        measure_count=sum(len(part.measures) for part in score.parts),
        warning_count=len(score.coverage_warnings),
        export_capable=score.export_capable,
        semantic_fingerprint=semantic_fingerprint(score),
    )
