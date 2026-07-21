from __future__ import annotations

from pathlib import Path

from particular.exporters.playback import DEFAULT_TEMPO_BPM, playback_timeline
from particular.importers.musicxml import parse_musicxml

ROOT = Path(__file__).parents[4]


def _single_part_score() -> bytes:
    # Two quarter notes (C4, then a rest, then E4) in one 4/4 measure at 4
    # divisions per quarter, so onsets and durations are unambiguous.
    return b"""<score-partwise><part-list><score-part id="P1"><part-name>Viola</part-name>
        </score-part></part-list><part id="P1"><measure number="1"><attributes>
        <divisions>4</divisions><time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        <note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration>
        <type>quarter</type></note>
        <note><rest/><duration>4</duration><type>quarter</type></note>
        <note><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration>
        <type>quarter</type></note>
        </measure></part></score-partwise>"""


def test_timeline_places_notes_in_seconds_and_skips_rests() -> None:
    score = parse_musicxml(_single_part_score())

    timeline = playback_timeline(score)

    assert timeline["tempo_bpm"] == DEFAULT_TEMPO_BPM
    # 90 BPM → 0.6667s per quarter.
    spq = timeline["seconds_per_quarter"]
    assert round(spq, 4) == 0.6667
    (part,) = timeline["parts"]
    assert part["part_id"] == "P1"
    # The rest is skipped, so only the two pitched notes appear.
    assert [note["midi"] for note in part["notes"]] == [60, 64]
    # First note starts at 0; the second starts after a note + a rest (2 quarters).
    assert part["notes"][0]["start"] == 0.0
    assert round(part["notes"][1]["start"], 4) == round(2 * spq, 4)
    assert round(part["notes"][0]["duration"], 4) == round(spq, 4)


def test_timeline_is_deterministic_and_covers_every_part() -> None:
    score = parse_musicxml(
        (ROOT / "evaluation/fixtures/mixed-ensemble-transposition.musicxml").read_bytes()
    )

    first = playback_timeline(score)
    second = playback_timeline(score)

    assert first == second
    assert [part["part_id"] for part in first["parts"]] == [part.id for part in score.parts]
    # Sounding pitch drives playback, so a transposing part's audio pitch differs
    # from its written pitch — every emitted note carries an integer MIDI value.
    assert all(isinstance(note["midi"], int) for part in first["parts"] for note in part["notes"])


def test_explicit_tempo_scales_all_times() -> None:
    score = parse_musicxml(_single_part_score())

    slow = playback_timeline(score, tempo_bpm=60.0)
    fast = playback_timeline(score, tempo_bpm=120.0)

    assert slow["seconds_per_quarter"] == 1.0
    assert fast["seconds_per_quarter"] == 0.5
    # Halving the tempo doubles every start time.
    assert slow["parts"][0]["notes"][1]["start"] == 2 * fast["parts"][0]["notes"][1]["start"]
