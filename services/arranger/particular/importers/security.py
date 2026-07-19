"""Pre-parse safety controls for XML and MXL inputs."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath


class UnsafeScoreError(ValueError):
    """Input failed a safety boundary before musical parsing."""


@dataclass(frozen=True)
class ArchiveLimits:
    max_files: int = 32
    max_total_bytes: int = 8_000_000
    max_entry_bytes: int = 4_000_000
    max_compression_ratio: float = 100.0


DEFAULT_ARCHIVE_LIMITS = ArchiveLimits()


def validate_xml_bytes(data: bytes) -> None:
    """Reject XML constructs that can resolve or expand external content."""

    lowered = data.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise UnsafeScoreError("DOCTYPE and entity declarations are not allowed")


def extract_mxl(data: bytes, limits: ArchiveLimits = DEFAULT_ARCHIVE_LIMITS) -> bytes:
    """Safely extract the single score document from an MXL archive."""

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError) as error:
        raise UnsafeScoreError("invalid MXL archive") from error
    with archive:
        entries = [entry for entry in archive.infolist() if not entry.is_dir()]
        if len(entries) > limits.max_files:
            raise UnsafeScoreError("MXL contains too many entries")
        total = 0
        candidates: list[zipfile.ZipInfo] = []
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if not path.parts or path.is_absolute() or ".." in path.parts or "\\" in entry.filename:
                raise UnsafeScoreError("MXL entry path is unsafe")
            if path.suffix.lower() in {".zip", ".mxl"}:
                raise UnsafeScoreError("nested archives are not allowed")
            if entry.file_size > limits.max_entry_bytes:
                raise UnsafeScoreError("MXL entry size exceeds limit")
            total += entry.file_size
            if total > limits.max_total_bytes:
                raise UnsafeScoreError("MXL total size exceeds limit")
            if entry.compress_size == 0:
                ratio = float("inf") if entry.file_size else 1.0
            else:
                ratio = entry.file_size / entry.compress_size
            if ratio > limits.max_compression_ratio:
                raise UnsafeScoreError("MXL compression ratio exceeds limit")
            if path.suffix.lower() in {".xml", ".musicxml"} and path.parts[0] != "META-INF":
                candidates.append(entry)
        if len(candidates) != 1:
            raise UnsafeScoreError("MXL must contain exactly one score XML document")
        contents = archive.read(candidates[0])
    validate_xml_bytes(contents)
    return contents
