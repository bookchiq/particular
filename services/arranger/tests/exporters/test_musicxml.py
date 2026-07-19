from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from particular.exporters.musicxml import export_musicxml, semantic_fingerprint
from particular.importers.musicxml import parse_musicxml

ROOT = Path(__file__).parents[4]


def test_two_round_trips_are_deterministic_for_supported_fixtures() -> None:
    fixtures = ROOT / "evaluation/fixtures"
    for path in sorted(fixtures.glob("*.musicxml")):
        first_score = parse_musicxml(path.read_bytes())
        first_xml = export_musicxml(first_score)
        second_score = parse_musicxml(first_xml)
        second_xml = export_musicxml(second_score)

        assert semantic_fingerprint(first_score) == semantic_fingerprint(second_score)
        assert first_xml == second_xml


def test_current_fixtures_retain_keys_clefs_directions_spelling_and_types() -> None:
    fixtures = ROOT / "evaluation/fixtures"
    score = parse_musicxml((fixtures / "mixed-ensemble-transposition.musicxml").read_bytes())
    exported = export_musicxml(score)

    assert b"<fifths>2</fifths>" in exported
    assert b"<sign>C</sign>" in exported
    assert b"<words>melody</words>" in exported
    assert b"<alter>1</alter>" in exported
    assert b"<type>quarter</type>" in exported
    assert b"<diatonic>-1</diatonic>" in exported


def test_independent_voices_at_the_same_onset_are_not_exported_as_a_chord() -> None:
    source = b"""<score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>
      <part id="P1"><measure number="1"><attributes><divisions>4</divisions>
        <time><beats>4</beats><beat-type>4</beat-type></time></attributes>
        <note><pitch><step>C</step><octave>4</octave></pitch>
          <duration>4</duration><voice>1</voice><type>quarter</type></note>
        <backup><duration>4</duration></backup>
        <note><pitch><step>E</step><octave>4</octave></pitch>
          <duration>4</duration><voice>2</voice><type>quarter</type></note>
        <note><chord/><pitch><step>G</step><octave>4</octave></pitch>
          <duration>4</duration><voice>2</voice><type>quarter</type></note>
      </measure></part></score-partwise>"""

    exported = export_musicxml(parse_musicxml(source))
    measure = ET.fromstring(exported).find("./part/measure")
    assert measure is not None
    notes = measure.findall("note")
    assert len(notes) == 3
    assert notes[1].find("chord") is None
    assert notes[2].find("chord") is not None
    backup_duration = measure.find("backup/duration")
    assert backup_duration is not None
    assert backup_duration.text == "4"
