from __future__ import annotations

import io
import zipfile

import pytest
from particular.importers.security import ArchiveLimits, UnsafeScoreError, extract_mxl


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


def test_rejects_path_traversal_and_nested_archives() -> None:
    with pytest.raises(UnsafeScoreError, match="path"):
        extract_mxl(_archive({"../score.musicxml": b"<score-partwise/>"}))
    with pytest.raises(UnsafeScoreError, match="nested"):
        extract_mxl(_archive({"nested.zip": b"zip"}))


def test_enforces_entry_count_size_and_compression_limits() -> None:
    with pytest.raises(UnsafeScoreError, match="entries"):
        extract_mxl(_archive({"a.xml": b"a", "b.xml": b"b"}), ArchiveLimits(max_files=1))
    with pytest.raises(UnsafeScoreError, match="size"):
        extract_mxl(_archive({"score.xml": b"12345"}), ArchiveLimits(max_entry_bytes=4))
    compressed = _archive({"score.xml": b"0" * 4096}, zipfile.ZIP_DEFLATED)
    with pytest.raises(UnsafeScoreError, match="compression"):
        extract_mxl(compressed, ArchiveLimits(max_compression_ratio=2))
