from __future__ import annotations

from pathlib import Path

import pytest
from particular.exporters.musicxml import (
    MusicXMLExportError,
    export_musicxml,
    semantic_fingerprint,
)
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


def test_round_trips_a_mid_part_transposition_change() -> None:
    # A B-flat instrument (transpose -2) that switches to concert pitch mid-part.
    xml = (
        b"<score-partwise version='4.0'><part-list><score-part id='P1'>"
        b"<part-name>Doubler</part-name></score-part></part-list><part id='P1'>"
        b"<measure number='1'><attributes><divisions>1</divisions>"
        b"<time><beats>4</beats><beat-type>4</beat-type></time>"
        b"<transpose><chromatic>-2</chromatic></transpose></attributes>"
        b"<note><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration>"
        b"<voice>1</voice></note></measure>"
        b"<measure number='2'><note><pitch><step>E</step><octave>4</octave></pitch>"
        b"<duration>4</duration><voice>1</voice></note></measure>"
        b"<measure number='3'><attributes>"
        b"<transpose><chromatic>0</chromatic></transpose></attributes>"
        b"<note><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration>"
        b"<voice>1</voice></note></measure></part></score-partwise>"
    )

    score = parse_musicxml(xml)
    measures = score.parts[0].measures

    # Transposition is time-varying state, applied to sounding pitch per measure.
    assert [measure.chromatic_transposition for measure in measures] == [-2, -2, 0]
    assert [measure.events[0].sounding_pitch for measure in measures] == [62, 62, 64]

    # The change is preserved on export and re-import without semantic drift.
    reparsed = parse_musicxml(export_musicxml(score))
    reparsed_transpositions = [
        measure.chromatic_transposition for measure in reparsed.parts[0].measures
    ]
    assert reparsed_transpositions == [-2, -2, 0]
    assert semantic_fingerprint(reparsed) == semantic_fingerprint(score)


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


def test_preserves_supported_notation_semantics() -> None:
    xml = b"""<score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Viola</part-name></score-part></part-list>
      <part id="P1"><measure number="1"><attributes><divisions>4</divisions>
        <key><fifths>-3</fifths><mode>minor</mode></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <clef><sign>C</sign><line>3</line></clef></attributes>
        <direction placement="above"><direction-type><words>dolce</words></direction-type>
          <sound tempo="72"/></direction>
        <note><pitch><step>D</step><alter>-1</alter><octave>4</octave></pitch>
          <duration>4</duration><type>quarter</type>
          <notations><tied type="start"/></notations></note>
        <note><pitch><step>D</step><alter>-1</alter><octave>4</octave></pitch>
          <duration>4</duration><tie type="stop"/><type>quarter</type>
        </note>
      </measure></part></score-partwise>"""

    score = parse_musicxml(xml)
    assert score.export_capable is True
    measure = score.parts[0].measures[0]
    assert (measure.key_fifths, measure.key_mode) == (-3, "minor")
    assert (measure.clef_sign, measure.clef_line) == ("C", 3)
    assert measure.directions[0].words == "dolce"
    assert measure.directions[0].tempo == 72.0
    assert measure.events[0].pitch_step == "D"
    assert measure.events[0].pitch_alter == -1
    assert measure.events[0].note_type == "quarter"
    assert measure.events[0].tie_start is True
    assert measure.events[1].tie_stop is True

    exported = export_musicxml(score)
    assert b"<fifths>-3</fifths>" in exported
    assert b"<sign>C</sign>" in exported
    assert b"<words>dolce</words>" in exported
    assert b'tempo="72"' in exported
    assert b"<step>D</step>" in exported
    assert b"<alter>-1</alter>" in exported
    assert b'<tied type="start"' in exported


@pytest.mark.parametrize(
    ("unsupported", "feature"),
    [
        (
            b"<direction><direction-type><dynamics><p/></dynamics></direction-type></direction>",
            "dynamics",
        ),
        (
            b"<note><pitch><step>C</step><octave>4</octave></pitch>"
            b"<duration>4</duration><type>quarter</type><notations>"
            b"<slur type='start'/></notations></note>",
            "slur",
        ),
        (b"<barline location='right'><repeat direction='backward'/></barline>", "barline"),
    ],
)
def test_unsupported_meaning_bearing_notation_blocks_export(
    unsupported: bytes, feature: str
) -> None:
    xml = (
        b"<score-partwise><part-list><score-part id='P1'><part-name>Flute</part-name>"
        b"</score-part></part-list><part id='P1'><measure number='7'><attributes>"
        b"<divisions>4</divisions></attributes>"
        + unsupported
        + b"</measure></part></score-partwise>"
    )

    score = parse_musicxml(xml)
    assert score.export_capable is False
    assert any(
        warning.feature == feature
        and warning.locator.part_id == "P1"
        and warning.locator.measure_number == "7"
        for warning in score.coverage_warnings
    )
    with pytest.raises(MusicXMLExportError, match="unsupported notation"):
        export_musicxml(score)


def test_unmodeled_tied_type_blocks_export() -> None:
    xml = b"""<score-partwise><part-list><score-part id="P1">
      <part-name>Violin</part-name></score-part></part-list><part id="P1">
      <measure number="2"><attributes><divisions>4</divisions></attributes>
      <note><pitch><step>D</step><octave>4</octave></pitch><duration>4</duration>
      <notations><tied type="continue"/></notations></note></measure></part>
      </score-partwise>"""

    score = parse_musicxml(xml)
    assert score.export_capable is False
    assert score.coverage_warnings[0].feature == "tied"


@pytest.mark.parametrize(
    ("attributes", "message"),
    [
        (b"<divisions>0</divisions>", "divisions must be positive"),
        (b"<divisions>-1</divisions>", "divisions must be positive"),
        (
            b"<divisions>4</divisions><time><beats>0</beats><beat-type>4</beat-type></time>",
            "meter values must be positive",
        ),
        (
            b"<divisions>4</divisions><time><beats>4</beats><beat-type>0</beat-type></time>",
            "meter values must be positive",
        ),
    ],
)
def test_rejects_nonpositive_timing_values(attributes: bytes, message: str) -> None:
    xml = (
        b"<score-partwise><part-list><score-part id='P1'><part-name>Flute</part-name>"
        b"</score-part></part-list><part id='P1'><measure number='3'><attributes>"
        + attributes
        + b"</attributes></measure></part></score-partwise>"
    )
    with pytest.raises(MusicXMLParseError, match=message):
        parse_musicxml(xml)


@pytest.mark.parametrize("tempo", ["NaN", "Infinity", "-Infinity", "0", "-72"])
def test_rejects_nonfinite_or_nonpositive_tempo(tempo: str) -> None:
    xml = f"""<score-partwise><part-list><score-part id="P1">
      <part-name>Flute</part-name></score-part></part-list><part id="P1">
      <measure number="1"><attributes><divisions>4</divisions></attributes>
      <direction><sound tempo="{tempo}"/></direction></measure></part>
      </score-partwise>""".encode()
    with pytest.raises(MusicXMLParseError, match="tempo must be finite and positive"):
        parse_musicxml(xml)


def test_nested_unmodeled_semantics_and_mid_measure_directions_block_export() -> None:
    xml = b"""<score-partwise><part-list><score-part id="P1">
      <part-name>Flute</part-name></score-part></part-list><part id="P1">
      <measure number="1"><attributes><divisions>4</divisions>
      <time symbol="common"><beats>4</beats><beat-type>4</beat-type></time></attributes>
      <note><pitch><step>C</step><octave>5</octave></pitch><duration>4</duration></note>
      <direction><direction-type><words>later</words></direction-type></direction>
      </measure></part></score-partwise>"""

    score = parse_musicxml(xml)
    assert score.export_capable is False
    assert {warning.feature for warning in score.coverage_warnings} == {
        "direction-offset",
        "time",
    }


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            b"<part id='P1'><measure number='1'/></part><part id='P1'><measure number='2'/></part>",
            "duplicate part IDs",
        ),
        (
            b"<part id='P1'><measure number='1'/><measure number='1'/></part>",
            "duplicate measure number",
        ),
    ],
)
def test_rejects_identifiers_that_would_alias_source_locators(body: bytes, message: str) -> None:
    xml = (
        b"<score-partwise><part-list><score-part id='P1'><part-name>Flute</part-name>"
        b"</score-part></part-list>" + body + b"</score-partwise>"
    )
    with pytest.raises(MusicXMLParseError, match=message):
        parse_musicxml(xml)
