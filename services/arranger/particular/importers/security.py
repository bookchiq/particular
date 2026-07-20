"""Pre-parse safety controls for XML and MXL inputs."""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import PurePosixPath

# MusicXML rootfile media type declared inside META-INF/container.xml.
MUSICXML_MEDIA_TYPES = frozenset({"application/vnd.recordare.musicxml+xml"})
SCORE_SUFFIXES = frozenset({".xml", ".musicxml"})


class UnsafeScoreError(ValueError):
    """Input failed a safety boundary before musical parsing."""


class ScoreSizeError(UnsafeScoreError):
    """Input exceeds an archive entry-count, entry-size, or total-size limit."""


class ScoreCompressionError(UnsafeScoreError):
    """An archive entry expands at a ratio consistent with a decompression bomb."""


class ScoreComplexityError(UnsafeScoreError):
    """A parsed score exceeds the engine's part-count or event-count limit."""


@dataclass(frozen=True)
class ArchiveLimits:
    """Bounded MXL extraction limits calibrated against real ensemble exports.

    Reference point: an OpenScore Brandenburg movement is ~173 KB compressed and
    expands to ~4.7 MB of MusicXML — legitimate, but rejected by the previous
    4 MB per-entry cap. Full orchestral movements from MuseScore, Dorico,
    Finale, Sibelius, and OpenScore reach tens of MB uncompressed while
    compressing ~10-40x, so these limits give generous headroom while still
    bounding memory and catching decompression bombs (which reach 1000x+).
    """

    max_files: int = 64
    max_total_bytes: int = 80_000_000
    max_entry_bytes: int = 64_000_000
    max_compression_ratio: float = 100.0


DEFAULT_ARCHIVE_LIMITS = ArchiveLimits()


def validate_xml_bytes(data: bytes) -> None:
    """Reject XML constructs that can resolve or expand external content."""

    if b"\x00" in data:
        raise UnsafeScoreError("MusicXML must be UTF-8 encoded")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise UnsafeScoreError("MusicXML must be UTF-8 encoded") from error
    lowered = text.casefold()
    if "<!doctype" in lowered or "<!entity" in lowered:
        raise UnsafeScoreError("DOCTYPE and entity declarations are not allowed")


def _safe_member_path(name: str) -> PurePosixPath:
    """Reject archive member or rootfile paths that could escape the archive."""

    path = PurePosixPath(name)
    if not path.parts or path.is_absolute() or ".." in path.parts or "\\" in name:
        raise UnsafeScoreError("MXL entry path is unsafe")
    return path


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _iter_elements(root: ET.Element, name: str) -> Iterator[ET.Element]:
    """Yield descendants with the given local name, ignoring XML namespaces."""

    for element in root.iter():
        if _local_name(element.tag) == name:
            yield element


def _resolve_rootfile(container_bytes: bytes) -> str:
    """Return the single MusicXML rootfile path declared by container.xml."""

    validate_xml_bytes(container_bytes)
    try:
        root = ET.fromstring(container_bytes)
    except ET.ParseError as error:
        raise UnsafeScoreError("MXL container.xml is malformed") from error
    rootpaths: list[str] = []
    for rootfile in _iter_elements(root, "rootfile"):
        full_path = rootfile.get("full-path")
        if not full_path:
            continue
        media_type = rootfile.get("media-type")
        suffix = PurePosixPath(full_path).suffix.lower()
        if media_type in MUSICXML_MEDIA_TYPES or (media_type is None and suffix in SCORE_SUFFIXES):
            rootpaths.append(full_path)
    if len(rootpaths) != 1:
        raise UnsafeScoreError("MXL container must declare exactly one MusicXML rootfile")
    return _safe_member_path(rootpaths[0]).as_posix()


def _read_member(archive: zipfile.ZipFile, entry: zipfile.ZipInfo) -> bytes:
    try:
        return archive.read(entry)
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError) as error:
        raise UnsafeScoreError("MXL entry cannot be read safely") from error


def extract_mxl(data: bytes, limits: ArchiveLimits = DEFAULT_ARCHIVE_LIMITS) -> bytes:
    """Safely extract the score document an MXL archive identifies as its root.

    Standard MXL packages name their score through ``META-INF/container.xml`` and
    may carry auxiliary XML alongside it. When no container is present, fall back
    to requiring a single unambiguous score member.
    """

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError) as error:
        raise UnsafeScoreError("invalid MXL archive") from error
    with archive:
        entries = [entry for entry in archive.infolist() if not entry.is_dir()]
        if len(entries) > limits.max_files:
            raise ScoreSizeError("MXL contains too many entries")
        total = 0
        by_path: dict[str, zipfile.ZipInfo] = {}
        fallback: list[str] = []
        for entry in entries:
            path = _safe_member_path(entry.filename)
            if path.suffix.lower() in {".zip", ".mxl"}:
                raise UnsafeScoreError("nested archives are not allowed")
            if entry.file_size > limits.max_entry_bytes:
                raise ScoreSizeError("MXL entry size exceeds limit")
            total += entry.file_size
            if total > limits.max_total_bytes:
                raise ScoreSizeError("MXL total size exceeds limit")
            if entry.compress_size == 0:
                ratio = float("inf") if entry.file_size else 1.0
            else:
                ratio = entry.file_size / entry.compress_size
            if ratio > limits.max_compression_ratio:
                raise ScoreCompressionError("MXL compression ratio exceeds limit")
            by_path[path.as_posix()] = entry
            if path.suffix.lower() in SCORE_SUFFIXES and path.parts[0] != "META-INF":
                fallback.append(path.as_posix())
        container = by_path.get("META-INF/container.xml")
        if container is not None:
            resolved = _resolve_rootfile(_read_member(archive, container))
            target = by_path.get(resolved)
            if target is None:
                raise UnsafeScoreError("MXL container rootfile is missing from the archive")
        elif len(fallback) == 1:
            target = by_path[fallback[0]]
        else:
            raise UnsafeScoreError("MXL must contain exactly one score XML document")
        contents = _read_member(archive, target)
    validate_xml_bytes(contents)
    return contents
