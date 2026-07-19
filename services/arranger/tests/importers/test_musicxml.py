from __future__ import annotations

from pathlib import Path

import pytest
from particular.importers.musicxml import MusicXMLParseError, parse_musicxml

ROOT = Path(__file__).parents[4]
FIXTURES = ROOT / "evaluation/fixtures"


def test_parses_parts_locators_and_transposition() -> None:
    score = parse_musicxml((FIXTURES / "mixed-ensemble-transposition.musicxml").read_bytes())

    assert [part.name for part in score.parts] == ["Flute", "Clarinet in B-flat", "Viola", "Cello"]
    clarinet = score.parts[1]
    assert clarinet.chromatic_transposition == -2
    assert clarinet.measures[0].events[0].written_pitch == 64
    assert clarinet.measures[0].events[0].sounding_pitch == 62
    assert clarinet.measures[0].events[0].locator.part_id == "P2"
    assert clarinet.measures[0].events[0].locator.measure_number == "1"


def test_pickup_measure_retains_actual_duration() -> None:
    xml = (
        b"<score-partwise version='4.0'><part-list><score-part id='P1'>"
        b"<part-name>Flute</part-name></score-part></part-list><part id='P1'>"
        b"<measure number='0' implicit='yes'><attributes><divisions>4</divisions>"
        b"<time><beats>4</beats><beat-type>4</beat-type></time></attributes><note>"
        b"<pitch><step>C</step><octave>5</octave></pitch><duration>4</duration>"
        b"<voice>1</voice></note></measure></part></score-partwise>"
    )

    measure = parse_musicxml(xml).parts[0].measures[0]
    assert measure.implicit is True
    assert measure.duration == 4
    assert measure.nominal_duration == 16


def test_unsupported_notation_is_a_located_warning() -> None:
    xml = (
        b"<score-partwise version='4.0'><part-list><score-part id='P1'>"
        b"<part-name>Violin</part-name></score-part></part-list><part id='P1'>"
        b"<measure number='1'><attributes><divisions>1</divisions></attributes><note>"
        b"<pitch><step>C</step><octave>4</octave></pitch><duration>1</duration>"
        b"<notations><glissando type='start'/></notations></note></measure></part>"
        b"</score-partwise>"
    )

    score = parse_musicxml(xml)
    assert score.export_capable is False
    assert score.coverage_warnings[0].feature == "glissando"
    assert score.coverage_warnings[0].locator.measure_number == "1"


def test_malformed_xml_raises_typed_error() -> None:
    with pytest.raises(MusicXMLParseError, match="malformed"):
        parse_musicxml(b"<score-partwise>")
