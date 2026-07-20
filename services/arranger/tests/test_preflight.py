from __future__ import annotations

import zipfile
from pathlib import Path

from particular.importers.musicxml import parse_musicxml
from particular.preflight import preflight, summarize_preflight

ROOT = Path(__file__).parents[3]


def test_corpus_fixture_preflight_is_stable() -> None:
    report = preflight(ROOT / "evaluation/fixtures/mixed-ensemble-transposition.musicxml")
    assert report.accepted is True
    assert report.part_count == 4
    assert report.measure_count == 4
    assert report.warning_count == 0
    assert len(report.semantic_fingerprint) == 64


def test_preflight_discloses_located_lossy_notation() -> None:
    score = parse_musicxml(
        b"<score-partwise><part-list><score-part id='P1'><part-name>Violin</part-name>"
        b"</score-part></part-list><part id='P1'><measure number='12'><attributes>"
        b"<divisions>1</divisions></attributes><direction><direction-type><rehearsal>A"
        b"</rehearsal></direction-type></direction></measure></part></score-partwise>"
    )

    report = summarize_preflight(score)
    assert report.export_capable is False
    assert report.warning_count == 1


def test_preflight_reads_a_safe_mxl_archive(tmp_path: Path) -> None:
    source = ROOT / "evaluation/fixtures/mixed-ensemble-transposition.musicxml"
    archive_path = tmp_path / "fixture.mxl"
    container = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
        '<rootfile full-path="score.musicxml" '
        'media-type="application/vnd.recordare.musicxml+xml"/></rootfiles></container>'
    )
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("score.musicxml", source.read_bytes())

    report = preflight(archive_path)
    assert report.accepted is True
    assert report.part_count == 4
