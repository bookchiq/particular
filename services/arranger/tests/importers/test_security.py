from __future__ import annotations

import io
import zipfile

import pytest
from particular.importers.security import (
    ArchiveLimits,
    ScoreCompressionError,
    ScoreSizeError,
    UnsafeScoreError,
    extract_mxl,
    validate_xml_bytes,
)


def _archive(entries: dict[str, bytes], compression: int = zipfile.ZIP_STORED) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression) as archive:
        for name, contents in entries.items():
            archive.writestr(name, contents)
    return output.getvalue()


@pytest.mark.parametrize("marker", [b"<!DOCTYPE score-partwise>", b"<!ENTITY x 'bad'>"])
def test_rejects_doctype_and_entities(marker: bytes) -> None:
    with pytest.raises(UnsafeScoreError):
        extract_mxl(_archive({"score.musicxml": marker}))


def test_rejects_non_utf8_xml_before_declaration_scan() -> None:
    encoded = "<!DOCTYPE score-partwise><score-partwise/>".encode("utf-16")
    with pytest.raises(UnsafeScoreError, match="UTF-8"):
        validate_xml_bytes(encoded)
    with pytest.raises(UnsafeScoreError, match="UTF-8"):
        extract_mxl(_archive({"score.musicxml": encoded}))


def test_rejects_path_traversal_and_nested_archives() -> None:
    with pytest.raises(UnsafeScoreError, match="path"):
        extract_mxl(_archive({"../score.musicxml": b"<score-partwise/>"}))
    with pytest.raises(UnsafeScoreError, match="nested"):
        extract_mxl(_archive({"nested.zip": b"zip"}))


def test_size_and_ratio_limits_are_distinct_categories() -> None:
    with pytest.raises(ScoreSizeError, match="entries"):
        extract_mxl(_archive({"a.xml": b"a", "b.xml": b"b"}), ArchiveLimits(max_files=1))
    with pytest.raises(ScoreSizeError, match="size"):
        extract_mxl(_archive({"score.xml": b"12345"}), ArchiveLimits(max_entry_bytes=4))
    compressed = _archive({"score.xml": b"0" * 4096}, zipfile.ZIP_DEFLATED)
    with pytest.raises(ScoreCompressionError, match="compression"):
        extract_mxl(compressed, ArchiveLimits(max_compression_ratio=2))


MUSICXML_MEDIA = "application/vnd.recordare.musicxml+xml"


def _container(*rootfiles: tuple[str, str | None]) -> bytes:
    declared = "".join(
        f'<rootfile full-path="{path}"'
        + (f' media-type="{media}"' if media is not None else "")
        + "/>"
        for path, media in rootfiles
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        f"<rootfiles>{declared}</rootfiles></container>"
    ).encode()


def test_resolves_rootfile_and_ignores_auxiliary_xml() -> None:
    archive = _archive(
        {
            "META-INF/container.xml": _container(("score.musicxml", MUSICXML_MEDIA)),
            "score.musicxml": b"<score-partwise/>",
            "extra.xml": b"<metadata/>",
        }
    )
    assert extract_mxl(archive) == b"<score-partwise/>"


def test_resolves_rootfile_without_media_type_by_suffix() -> None:
    archive = _archive(
        {
            "META-INF/container.xml": _container(("score.musicxml", None)),
            "score.musicxml": b"<score-partwise/>",
        }
    )
    assert extract_mxl(archive) == b"<score-partwise/>"


def test_rejects_missing_rootfile_member() -> None:
    archive = _archive(
        {
            "META-INF/container.xml": _container(("missing.musicxml", MUSICXML_MEDIA)),
            "other.musicxml": b"<score-partwise/>",
        }
    )
    with pytest.raises(UnsafeScoreError, match="rootfile is missing"):
        extract_mxl(archive)


def test_rejects_duplicate_musicxml_rootfiles() -> None:
    archive = _archive(
        {
            "META-INF/container.xml": _container(
                ("a.musicxml", MUSICXML_MEDIA), ("b.musicxml", MUSICXML_MEDIA)
            ),
            "a.musicxml": b"<score-partwise/>",
            "b.musicxml": b"<score-partwise/>",
        }
    )
    with pytest.raises(UnsafeScoreError, match="exactly one"):
        extract_mxl(archive)


def test_rejects_rootfile_path_traversal() -> None:
    archive = _archive(
        {
            "META-INF/container.xml": _container(("../evil.musicxml", MUSICXML_MEDIA)),
            "score.musicxml": b"<score-partwise/>",
        }
    )
    with pytest.raises(UnsafeScoreError, match="unsafe"):
        extract_mxl(archive)


def test_calibrated_limits_accept_a_multi_megabyte_score() -> None:
    # An OpenScore Brandenburg movement expands to ~4.7 MB — over the old 4 MB
    # per-entry cap. A large XML comment stands in for that legitimate bulk.
    score_xml = (
        b"<score-partwise><!--" + b"x" * 4_700_000 + b"-->"
        b"<part-list><score-part id='P1'><part-name>Violin</part-name></score-part></part-list>"
        b"<part id='P1'><measure number='1'><attributes><divisions>1</divisions></attributes>"
        b"<note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration></note>"
        b"</measure></part></score-partwise>"
    )
    archive = _archive(
        {
            "META-INF/container.xml": _container(("score.musicxml", MUSICXML_MEDIA)),
            "score.musicxml": score_xml,
        }
    )

    assert b"score-partwise" in extract_mxl(archive)


def test_rejects_unsupported_rootfile_media_type() -> None:
    archive = _archive(
        {
            "META-INF/container.xml": _container(("cover.png", "image/png")),
            "score.musicxml": b"<score-partwise/>",
        }
    )
    with pytest.raises(UnsafeScoreError, match="rootfile"):
        extract_mxl(archive)
