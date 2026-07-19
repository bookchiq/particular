from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from particular.domain.score import Score
from particular.exporters.musicxml import export_musicxml, semantic_fingerprint
from particular.generation.operators import adjust_octave_range, reduce_rhythm, thin_repetitions
from particular.generation.selector import (
    ArrangementFamily,
    GenerationManifest,
    TierScore,
    generate_arrangement_family,
)
from particular.importers.musicxml import parse_musicxml
from particular.validation.arrangement import ArrangementValidationError, validate_family

ROOT = Path(__file__).parents[4]


def _scores() -> tuple[Score, Score]:
    fixtures = ROOT / "evaluation/fixtures"
    return (
        parse_musicxml((fixtures / "string-orchestra-second-violin.musicxml").read_bytes()),
        parse_musicxml((fixtures / "mixed-ensemble-transposition.musicxml").read_bytes()),
    )


def test_rhythm_merge_only_combines_unprotected_repeated_pitches() -> None:
    strings, _ = _scores()
    events = strings.parts[1].measures[0].events
    unsafe = reduce_rhythm(events, frozenset(), divisions=4)
    assert unsafe.accepted is False
    assert unsafe.rejection_reason == "adjacent notes have different pitches"

    repeated = (
        events[0],
        replace(
            events[1],
            written_pitch=events[0].written_pitch,
            sounding_pitch=events[0].sounding_pitch,
            pitch_step=events[0].pitch_step,
            pitch_alter=events[0].pitch_alter,
            pitch_octave=events[0].pitch_octave,
        ),
    )
    candidate = reduce_rhythm(repeated, frozenset(), divisions=4)
    assert candidate.accepted is True
    assert sum(event.duration for event in candidate.before) == sum(
        event.duration for event in candidate.after
    )
    assert "merged" in candidate.explanation
    assert candidate.after[0].note_type == "quarter"

    rejected = reduce_rhythm(repeated, frozenset({events[0].locator}), divisions=4)
    assert rejected.accepted is False
    assert rejected.rejection_reason is not None
    assert "protected" in rejected.rejection_reason

    tied = (replace(repeated[0], tie_start=True), repeated[1])
    rejected_tie = reduce_rhythm(tied, frozenset(), divisions=4)
    assert rejected_tie.accepted is False
    assert rejected_tie.rejection_reason == "tied notes cannot be merged safely"


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

    tied = (replace(repeated[0], tie_start=True), replace(repeated[1], tie_stop=True))
    rejected_tie = thin_repetitions(tied, frozenset())
    assert rejected_tie.accepted is False
    assert rejected_tie.rejection_reason == "tied notes cannot be thinned safely"


def test_family_is_deterministic_synchronized_and_round_trippable() -> None:
    strings, _ = _scores()
    first = generate_arrangement_family(strings)
    second = generate_arrangement_family(strings)

    assert first.manifest == second.manifest
    assert all(change.part_id and change.measure for change in first.manifest.changes)
    assert [tier.name for tier in first.tiers] == ["Foundation", "Core", "Challenge"]
    validate_family(strings, first)
    reparsed_tiers = []
    for tier in first.tiers:
        reparsed = parse_musicxml(export_musicxml(tier.score))
        assert semantic_fingerprint(reparsed) == semantic_fingerprint(tier.score)
        reparsed_tiers.append(TierScore(tier.name, reparsed))
        assert [measure.duration for part in reparsed.parts for measure in part.measures] == [
            measure.duration for part in strings.parts for measure in part.measures
        ]
    validate_family(strings, ArrangementFamily(tuple(reparsed_tiers), first.manifest))


def test_hard_validator_rejects_duration_and_range_regressions() -> None:
    strings, _ = _scores()
    family = generate_arrangement_family(strings)
    foundation = family.tiers[0]
    first_part = foundation.score.parts[0]
    first_measure = first_part.measures[0]

    bad_duration_measure = replace(first_measure, duration=first_measure.duration + 1)
    bad_duration_part = replace(
        first_part, measures=(bad_duration_measure, *first_part.measures[1:])
    )
    bad_duration_score = replace(
        foundation.score, parts=(bad_duration_part, *foundation.score.parts[1:])
    )
    bad_duration_family = replace(
        family, tiers=(replace(foundation, score=bad_duration_score), *family.tiers[1:])
    )
    with pytest.raises(ArrangementValidationError, match="duration"):
        validate_family(strings, bad_duration_family)

    range_part = foundation.score.parts[1]
    range_measure = range_part.measures[0]
    range_event = range_measure.events[1]
    bad_range_event = replace(
        range_event,
        written_pitch=127,
        sounding_pitch=127,
        pitch_step="G",
        pitch_alter=0,
        pitch_octave=9,
    )
    bad_range_measure = replace(
        range_measure,
        events=(range_measure.events[0], bad_range_event, *range_measure.events[2:]),
    )
    bad_range_part = replace(range_part, measures=(bad_range_measure, *range_part.measures[1:]))
    bad_range_score = replace(
        foundation.score,
        parts=(foundation.score.parts[0], bad_range_part, *foundation.score.parts[2:]),
    )
    bad_range_family = replace(
        family, tiers=(replace(foundation, score=bad_range_score), *family.tiers[1:])
    )
    with pytest.raises(ArrangementValidationError, match="out-of-range"):
        validate_family(strings, bad_range_family)


def test_hard_validator_rejects_protected_role_mutation() -> None:
    strings, _ = _scores()
    family = generate_arrangement_family(strings)
    foundation = family.tiers[0]
    part = foundation.score.parts[0]
    measure = part.measures[0]
    protected_note = measure.events[0]
    changed = replace(
        protected_note,
        kind="rest",
        written_pitch=None,
        sounding_pitch=None,
        pitch_step=None,
        pitch_octave=None,
    )
    changed_measure = replace(measure, events=(changed, *measure.events[1:]))
    changed_part = replace(part, measures=(changed_measure, *part.measures[1:]))
    changed_score = replace(foundation.score, parts=(changed_part, *foundation.score.parts[1:]))
    changed_family = replace(
        family, tiers=(replace(foundation, score=changed_score), *family.tiers[1:])
    )

    with pytest.raises(ArrangementValidationError, match="protected ensemble role changed"):
        validate_family(strings, changed_family)


def test_hard_validator_rejects_meter_and_voice_timeline_drift() -> None:
    strings, _ = _scores()
    family = generate_arrangement_family(strings)
    foundation = family.tiers[0]
    part = foundation.score.parts[1]
    measure = part.measures[0]

    changed_meter = replace(measure, beats=3)
    changed_part = replace(part, measures=(changed_meter, *part.measures[1:]))
    changed_score = replace(
        foundation.score,
        parts=(
            foundation.score.parts[0],
            changed_part,
            *foundation.score.parts[2:],
        ),
    )
    changed_family = replace(
        family, tiers=(replace(foundation, score=changed_score), *family.tiers[1:])
    )
    with pytest.raises(ArrangementValidationError, match="structure"):
        validate_family(strings, changed_family)

    shifted_event = replace(measure.events[2], onset=measure.events[2].onset + 1)
    shifted_measure = replace(
        measure,
        events=(*measure.events[:2], shifted_event, *measure.events[3:]),
    )
    shifted_part = replace(part, measures=(shifted_measure, *part.measures[1:]))
    shifted_score = replace(
        foundation.score,
        parts=(
            foundation.score.parts[0],
            shifted_part,
            *foundation.score.parts[2:],
        ),
    )
    shifted_family = replace(
        family, tiers=(replace(foundation, score=shifted_score), *family.tiers[1:])
    )
    with pytest.raises(ArrangementValidationError, match="voice timeline"):
        validate_family(strings, shifted_family)


def test_hard_validator_rejects_dangling_ties() -> None:
    strings, _ = _scores()
    family = generate_arrangement_family(strings)
    foundation = family.tiers[0]
    part = foundation.score.parts[2]
    measure = part.measures[1]
    dangling = replace(measure.events[0], tie_start=True)
    changed_measure = replace(measure, events=(dangling, *measure.events[1:]))
    changed_part = replace(part, measures=(part.measures[0], changed_measure))
    changed_score = replace(
        foundation.score,
        parts=(
            *foundation.score.parts[:2],
            changed_part,
            *foundation.score.parts[3:],
        ),
    )
    changed_family = replace(
        family, tiers=(replace(foundation, score=changed_score), *family.tiers[1:])
    )

    with pytest.raises(ArrangementValidationError, match="tie chain"):
        validate_family(strings, changed_family)


def test_hard_validator_rejects_incomplete_tiers_and_pitch_spelling_drift() -> None:
    strings, _ = _scores()
    family = generate_arrangement_family(strings)
    with pytest.raises(ArrangementValidationError, match="tier family"):
        validate_family(strings, replace(family, tiers=family.tiers[:2]))

    foundation = family.tiers[0]
    part = foundation.score.parts[1]
    measure = part.measures[0]
    event = measure.events[1]
    inconsistent = replace(event, pitch_step="C", pitch_alter=0, pitch_octave=4)
    changed_measure = replace(
        measure, events=(measure.events[0], inconsistent, *measure.events[2:])
    )
    changed_part = replace(part, measures=(changed_measure, *part.measures[1:]))
    changed_score = replace(
        foundation.score,
        parts=(foundation.score.parts[0], changed_part, *foundation.score.parts[2:]),
    )
    changed_family = replace(
        family, tiers=(replace(foundation, score=changed_score), *family.tiers[1:])
    )
    with pytest.raises(ArrangementValidationError, match="pitch spelling"):
        validate_family(strings, changed_family)


def test_hard_validator_rejects_noncontiguous_ties() -> None:
    score = parse_musicxml(
        b"""<score-partwise><part-list><score-part id="P1"><part-name>Violin</part-name>
        </score-part></part-list><part id="P1"><measure number="1"><attributes>
        <divisions>4</divisions><time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes><note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration>
        <tie type="start"/></note><note><rest/><duration>4</duration></note>
        <note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration>
        <tie type="stop"/></note></measure></part></score-partwise>"""
    )
    family = ArrangementFamily(
        tuple(TierScore(name, score) for name in ("Foundation", "Core", "Challenge")),
        GenerationManifest(1, ()),
    )

    with pytest.raises(ArrangementValidationError, match="noncontiguous"):
        validate_family(score, family)


def test_hard_validator_rejects_duplicate_source_locators() -> None:
    strings, _ = _scores()
    part = strings.parts[0]
    duplicate = replace(part, measures=(*part.measures, part.measures[0]))
    score = replace(strings, parts=(duplicate, *strings.parts[1:]))
    family = ArrangementFamily(
        tuple(TierScore(name, score) for name in ("Foundation", "Core", "Challenge")),
        GenerationManifest(1, ()),
    )

    with pytest.raises(ArrangementValidationError, match="duplicate source locator"):
        validate_family(score, family)
