from __future__ import annotations

import zipfile
from pathlib import Path

from particular.preflight import preflight

ROOT = Path(__file__).parents[3]


def test_corpus_fixture_preflight_is_stable() -> None:
    report = preflight(ROOT / "evaluation/fixtures/mixed-ensemble-transposition.musicxml")
    assert report.accepted is True
    assert report.part_count == 4
    assert report.measure_count == 4
    assert report.warning_count == 0
    assert len(report.semantic_fingerprint) == 64


def test_preflight_reads_a_safe_mxl_archive(tmp_path: Path) -> None:
    source = ROOT / "evaluation/fixtures/mixed-ensemble-transposition.musicxml"
    archive_path = tmp_path / "fixture.mxl"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("META-INF/container.xml", "<container/>")
        archive.writestr("score.musicxml", source.read_bytes())

    report = preflight(archive_path)
    assert report.accepted is True
    assert report.part_count == 4
