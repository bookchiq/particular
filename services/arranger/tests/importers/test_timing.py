from __future__ import annotations

from particular.importers.musicxml import parse_musicxml


def test_sequential_chord_backup_and_forward_onsets() -> None:
    xml = (
        b"<score-partwise><part-list><score-part id='P1'><part-name>Piano</part-name>"
        b"</score-part></part-list><part id='P1'><measure number='1'><attributes>"
        b"<divisions>1</divisions></attributes><note><pitch><step>C</step><octave>4"
        b"</octave></pitch><duration>1</duration></note><note><chord/><pitch><step>E"
        b"</step><octave>4</octave></pitch><duration>1</duration></note><note><pitch>"
        b"<step>D</step><octave>4</octave></pitch><duration>1</duration></note><backup>"
        b"<duration>2</duration></backup><forward><duration>1</duration></forward><note>"
        b"<pitch><step>G</step><octave>3</octave></pitch><duration>1</duration>"
        b"<voice>2</voice></note></measure></part></score-partwise>"
    )
    measure = parse_musicxml(xml).parts[0].measures[0]
    assert [event.onset for event in measure.events] == [0, 0, 1, 1]
    assert measure.duration == 2
