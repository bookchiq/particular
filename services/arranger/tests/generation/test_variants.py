from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from particular.domain.score import Score
from particular.exporters.musicxml import export_musicxml
from particular.generation.operators import adjust_octave_range, reduce_rhythm, thin_repetitions
from particular.generation.selector import generate_arrangement_family
from particular.importers.musicxml import parse_musicxml
from particular.validation.arrangement import validate_family

ROOT = Path(__file__).parents[4]


def _scores() -> tuple[Score, Score]:
    fixtures = ROOT / "evaluation/fixtures"
    return (
        parse_musicxml((fixtures / "string-orchestra-second-violin.musicxml").read_bytes()),
        parse_musicxml((fixtures / "mixed-ensemble-transposition.musicxml").read_bytes()),
    )


def test_rhythm_merge_succeeds_and_protected_pair_is_rejected() -> None:
    strings, _ = _scores()
    events = strings.parts[1].measures[0].events
    candidate = reduce_rhythm(events, frozenset())
    assert candidate.accepted is True
    assert sum(event.duration for event in candidate.before) == sum(
        event.duration for event in candidate.after
    )
    assert "merged" in candidate.explanation

    rejected = reduce_rhythm(events, frozenset({events[0].locator}))
    assert rejected.accepted is False
    assert rejected.rejection_reason is not None
    assert "protected" in rejected.rejection_reason


def test_range_adjustment_succeeds_and_reports_infeasible_protected_note() -> None:
    strings, _ = _scores()
    event = strings.parts[1].measures[0].events[-1]
    candidate = adjust_octave_range((event,), 55, 76, frozenset())
    assert event.written_pitch is not None
    assert candidate.after[0].written_pitch == event.written_pitch - 12
    assert candidate.difficulty_delta["range"] < 0

    rejected = adjust_octave_range((event,), 55, 76, frozenset({event.locator}))
    assert rejected.accepted is False
    assert rejected.rejection_reason


def test_density_thinning_preserves_duration_and_rejects_melody_lock() -> None:
    _, mixed = _scores()
    viola_events = mixed.parts[2].measures[0].events
    repeated = (
        viola_events[0],
        replace(
            viola_events[1],
            written_pitch=viola_events[0].written_pitch,
            sounding_pitch=viola_events[0].sounding_pitch,
        ),
    )
    candidate = thin_repetitions(repeated, frozenset())
    assert candidate.after[1].kind == "rest"
    assert sum(item.duration for item in candidate.after) == sum(item.duration for item in repeated)

    rejected = thin_repetitions(repeated, frozenset({repeated[1].locator}))
    assert rejected.accepted is False


def test_family_is_deterministic_synchronized_and_round_trippable() -> None:
    strings, _ = _scores()
    first = generate_arrangement_family(strings)
    second = generate_arrangement_family(strings)

    assert first.manifest == second.manifest
    assert [tier.name for tier in first.tiers] == ["Foundation", "Core", "Challenge"]
    validate_family(strings, first)
    for tier in first.tiers:
        reparsed = parse_musicxml(export_musicxml(tier.score))
        assert [measure.duration for part in reparsed.parts for measure in part.measures] == [
            measure.duration for part in strings.parts for measure in part.measures
        ]


def test_candidate_input_order_does_not_change_manifest() -> None:
    strings, _ = _scores()
    forward = generate_arrangement_family(strings, candidate_order="forward")
    reverse = generate_arrangement_family(strings, candidate_order="reverse")
    assert forward.manifest == reverse.manifest
