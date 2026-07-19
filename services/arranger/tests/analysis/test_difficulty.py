from __future__ import annotations

from pathlib import Path

from particular.analysis.difficulty import analyze_part
from particular.importers.musicxml import parse_musicxml

ROOT = Path(__file__).parents[4]


def test_second_violin_has_explainable_golden_features() -> None:
    score = parse_musicxml(
        (ROOT / "evaluation/fixtures/string-orchestra-second-violin.musicxml").read_bytes()
    )
    analysis = analyze_part(score.parts[1])

    assert analysis.profile_id == "violin"
    assert analysis.vector.note_count == 10
    assert analysis.vector.pitch_range_semitones == 24
    assert analysis.vector.largest_leap_semitones == 19
    assert analysis.vector.shortest_duration_quarters == 0.5
    assert analysis.vector.max_note_density_per_quarter == 2.0
    assert analysis.vector.accidental_burden == 1
    assert analysis.vector.rhythmic_complexity == 0.5


def test_unknown_and_rest_only_part_uses_generic_profile() -> None:
    xml = (
        b"<score-partwise><part-list><score-part id='P1'><part-name>Kazoo</part-name>"
        b"</score-part></part-list><part id='P1'><measure number='1'><attributes>"
        b"<divisions>1</divisions></attributes><note><rest/><duration>4</duration>"
        b"</note></measure></part></score-partwise>"
    )
    analysis = analyze_part(parse_musicxml(xml).parts[0])

    assert analysis.profile_id == "generic"
    assert analysis.warning is not None
    assert analysis.vector.note_count == 0
    assert analysis.vector.pitch_range_semitones == 0


def test_tier_targets_are_ordered() -> None:
    score = parse_musicxml(
        (ROOT / "evaluation/fixtures/mixed-ensemble-transposition.musicxml").read_bytes()
    )
    targets = analyze_part(score.parts[0]).tier_targets
    assert targets["Foundation"] < targets["Core"] < targets["Challenge"]
