from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from particular.analysis.difficulty import analyze_part
from particular.application import generation_manifest
from particular.domain.score import Score
from particular.exporters.musicxml import export_musicxml, semantic_fingerprint
from particular.generation.operators import adjust_octave_range, reduce_rhythm, thin_repetitions
from particular.generation.selector import (
    ArrangementFamily,
    GenerationManifest,
    TierScore,
    compose_mixed_tier,
    generate_arrangement_family,
)
from particular.importers.musicxml import parse_musicxml
from particular.validation.arrangement import ArrangementValidationError, validate_family

ROOT = Path(__file__).parents[4]


def _wide_repetitive_score(part_count: int, measure_count: int) -> Score:
    measure = (
        "<attributes><divisions>4</divisions>"
        "<time><beats>4</beats><beat-type>4</beat-type></time></attributes>"
        + "<note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration>"
        "<type>quarter</type></note>" * 4
    )
    measures = "".join(
        f'<measure number="{index + 1}">{measure}</measure>' for index in range(measure_count)
    )
    part_list = "".join(
        f'<score-part id="P{index + 1}"><part-name>Viola</part-name></score-part>'
        for index in range(part_count)
    )
    parts = "".join(f'<part id="P{index + 1}">{measures}</part>' for index in range(part_count))
    return parse_musicxml(
        f"<score-partwise><part-list>{part_list}</part-list>{parts}</score-partwise>".encode()
    )


def _scores() -> tuple[Score, Score]:
    fixtures = ROOT / "evaluation/fixtures"
    return (
        parse_musicxml((fixtures / "string-orchestra-second-violin.musicxml").read_bytes()),
        parse_musicxml((fixtures / "mixed-ensemble-transposition.musicxml").read_bytes()),
    )


def _tier_policy_score() -> Score:
    medium = "".join(
        "<note><pitch><step>C</step><octave>4</octave></pitch><duration>2</duration>"
        "<type>eighth</type></note>"
        for _ in range(7)
    )
    high = "".join(
        "<note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration>"
        "<type>16th</type></note>"
        for _ in range(15)
    )
    return parse_musicxml(
        f"""<score-partwise><part-list><score-part id="P1"><part-name>Viola</part-name>
        </score-part></part-list><part id="P1"><measure number="1"><attributes>
        <divisions>4</divisions><time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes><forward><duration>2</duration></forward>{medium}</measure>
        <measure number="2"><forward><duration>1</duration></forward>{high}</measure>
        </part></score-partwise>""".encode()
    )


def _unchanged_family(score: Score) -> ArrangementFamily:
    targets = analyze_part(score.parts[0]).tier_targets
    tiers = tuple(
        TierScore(name, score, targets[name], "Unchanged test tier")
        for name in ("Foundation", "Core", "Challenge")
    )
    return ArrangementFamily(tiers, GenerationManifest(2, ()))


def _score_with_repeated_notes(durations: list[int], forward: int) -> Score:
    notes = "".join(
        f"<note><pitch><step>C</step><octave>4</octave></pitch><duration>{duration}</duration>"
        "</note>"
        for duration in durations
    )
    return parse_musicxml(
        f"""<score-partwise><part-list><score-part id="P1"><part-name>Viola</part-name>
        </score-part></part-list><part id="P1"><measure number="1"><attributes>
        <divisions>4</divisions><time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes><forward><duration>{forward}</duration></forward>{notes}</measure>
        </part></score-partwise>""".encode()
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
        reparsed_tiers.append(TierScore(tier.name, reparsed, tier.target, tier.explanation))
        assert [measure.duration for part in reparsed.parts for measure in part.measures] == [
            measure.duration for part in strings.parts for measure in part.measures
        ]
    validate_family(strings, ArrangementFamily(tuple(reparsed_tiers), first.manifest))


def test_tier_policy_uses_passage_difficulty_to_create_ordered_variants() -> None:
    source = _tier_policy_score()

    family = generate_arrangement_family(source)

    vectors = [analyze_part(tier.score.parts[0]).vector for tier in family.tiers]
    assert [vector.note_count for vector in vectors] == [20, 21, 22]
    assert [tier.target for tier in family.tiers] == [0.35, 0.65, 0.9]
    assert len({semantic_fingerprint(tier.score) for tier in family.tiers}) == 3
    assert [
        sum(
            change.status == "accepted" for change in family.manifest.changes if change.tier == tier
        )
        for tier in ("Foundation", "Core", "Challenge")
    ] == [2, 1, 0]
    assert family.tiers[2].explanation.startswith("Unchanged: Challenge retains source detail")
    validate_family(source, family)


def test_locked_measures_are_never_transformed() -> None:
    source = _tier_policy_score()

    unlocked = generate_arrangement_family(source)
    accepted_pairs = {
        (change.part_id, change.measure)
        for change in unlocked.manifest.changes
        if change.status == "accepted"
    }
    assert accepted_pairs, "fixture must change at least one measure to be a meaningful lock test"
    target = sorted(accepted_pairs)[0]

    locked = generate_arrangement_family(source, locked_measures=frozenset({target}))

    # No candidate — accepted or rejected — is ever recorded for the locked measure.
    assert not [
        change for change in locked.manifest.changes if (change.part_id, change.measure) == target
    ]
    # Every other measure is still free to change.
    other_accepted = {
        (change.part_id, change.measure)
        for change in locked.manifest.changes
        if change.status == "accepted"
    }
    assert accepted_pairs - {target} <= other_accepted
    validate_family(source, locked)


def test_compose_mixed_tier_draws_each_part_from_its_assigned_tier() -> None:
    strings, _ = _scores()
    family = generate_arrangement_family(strings)
    part_ids = [part.id for part in strings.parts]
    assignments = {part_ids[0]: "Foundation", part_ids[1]: "Challenge"}

    mixed = compose_mixed_tier(family, assignments)

    foundation = {part.id: part for part in family.tiers[0].score.parts}
    core = {part.id: part for part in family.tiers[1].score.parts}
    challenge = {part.id: part for part in family.tiers[2].score.parts}
    mixed_parts = {part.id: part for part in mixed.parts}

    # Assigned parts come from their tier; unassigned parts default to Core.
    assert mixed_parts[part_ids[0]] is foundation[part_ids[0]]
    assert mixed_parts[part_ids[1]] is challenge[part_ids[1]]
    for part_id in part_ids[2:]:
        assert mixed_parts[part_id] is core[part_id]
    # Part identity and order are preserved, and the result round-trips.
    assert [part.id for part in mixed.parts] == part_ids
    assert semantic_fingerprint(parse_musicxml(export_musicxml(mixed))) == semantic_fingerprint(
        mixed
    )


def test_manifest_records_custom_arrangement_without_touching_digest() -> None:
    source = _tier_policy_score()
    family = generate_arrangement_family(source)

    baseline = generation_manifest(family, "sha256", source)
    custom = generation_manifest(family, "sha256", source, tier_assignments={"P1": "Foundation"})

    assert "custom_arrangement" not in baseline
    assert custom["custom_arrangement"]["assignments"] == {"P1": "Foundation"}
    assert custom["custom_arrangement"]["parts"] == [{"part_id": "P1", "tier": "Foundation"}]
    # Assignments only select among reproducible tiers, so the digest is stable.
    assert custom["reproducibility_digest"] == baseline["reproducibility_digest"]


def test_mixed_tier_rejects_unknown_part_and_tier() -> None:
    source = _tier_policy_score()
    family = generate_arrangement_family(source)

    with pytest.raises(ValueError, match="unknown part"):
        generation_manifest(family, "sha256", source, tier_assignments={"PX": "Core"})
    with pytest.raises(ValueError, match="unknown tier"):
        generation_manifest(family, "sha256", source, tier_assignments={"P1": "Expert"})


def test_manifest_records_locked_measures_in_reproducibility() -> None:
    source = _tier_policy_score()
    locked = frozenset({("P1", "1")})

    manifest = generation_manifest(
        generate_arrangement_family(source, locked_measures=locked),
        "sha256",
        source,
        locked_measures=locked,
    )

    assert manifest["reproducibility"]["locked_measures"] == [["P1", "1"]]
    # The digest depends on the locked set, so unlocked output digests differently.
    unlocked = generation_manifest(generate_arrangement_family(source), "sha256", source)
    assert manifest["reproducibility_digest"] != unlocked["reproducibility_digest"]


def test_manifest_changes_carry_deltas_roles_version_and_locators() -> None:
    source = _tier_policy_score()

    family = generate_arrangement_family(source)

    accepted = [change for change in family.manifest.changes if change.status == "accepted"]
    assert accepted
    for change in accepted:
        assert change.operator_version == 1
        assert change.difficulty_delta
        assert change.role_effects
        assert change.locators
        assert change.locators[0].part_id == change.part_id
    # The new fields stay deterministic across identical runs.
    assert generate_arrangement_family(source).manifest == family.manifest


def test_change_summary_lists_accepted_and_aggregates_noops() -> None:
    source = _tier_policy_score()

    manifest = generation_manifest(generate_arrangement_family(source), "sha256", source)

    foundation = manifest["change_summary"]["Foundation"]
    assert foundation["accepted"]
    sample = foundation["accepted"][0]
    assert {
        "difficulty_delta",
        "role_effects",
        "operator_version",
        "locators",
        "applicable",
    } <= set(sample)
    # No-ops are counted, not listed one record at a time.
    assert foundation["noops"]["count"] >= 1
    assert isinstance(foundation["noops"]["by_operator"], dict)


def test_change_summary_stays_bounded_at_ensemble_scale() -> None:
    source = _wide_repetitive_score(part_count=6, measure_count=12)
    family = generate_arrangement_family(source)

    manifest = generation_manifest(family, "sha256", source)

    # The raw ledger is large, but the summary never grows unbounded.
    assert len(family.manifest.changes) > 200
    for tier in manifest["change_summary"].values():
        assert len(tier["rejected"]) <= 50
        assert tier["rejected_total"] >= len(tier["rejected"])
        assert isinstance(tier["noops"]["count"], int)


def test_tier_policy_explains_unchanged_below_target_passage() -> None:
    source = _score_with_repeated_notes([4, 4], forward=8)

    family = generate_arrangement_family(source)

    assert all(tier.score == source for tier in family.tiers)
    assert family.tiers[0].explanation == (
        "Unchanged: no safe candidate exceeded the 0.35 Foundation target."
    )
    foundation_repetition = next(
        change
        for change in family.manifest.changes
        if change.tier == "Foundation" and change.operator == "repetition-thin"
    )
    assert foundation_repetition.rejection_reason == (
        "passage pressure 0.12 does not exceed target 0.35"
    )


def test_challenge_only_applies_typed_range_safety_correction() -> None:
    source_score = _tier_policy_score()
    part = source_score.parts[0]
    measure = part.measures[0]
    unsafe = replace(
        measure.events[0],
        written_pitch=100,
        sounding_pitch=100,
        pitch_step="E",
        pitch_octave=7,
    )
    changed_measure = replace(measure, events=(unsafe, *measure.events[1:]))
    changed_part = replace(part, measures=(changed_measure, *part.measures[1:]))
    source_score = replace(source_score, parts=(changed_part,))

    family = generate_arrangement_family(source_score)

    challenge = family.tiers[2]
    accepted = [
        change
        for change in family.manifest.changes
        if change.tier == "Challenge" and change.status == "accepted"
    ]
    assert [change.operator for change in accepted] == ["octave-range"]
    assert challenge.explanation == (
        "Applied 1 range correction(s) required for instrument safety."
    )
    source_events = source_score.parts[0].measures[0].events
    challenge_events = challenge.score.parts[0].measures[0].events
    assert [event.locator for event in source_events if event not in challenge_events] == [
        unsafe.locator
    ]
    validate_family(source_score, family)


def test_overlapping_operators_resolve_consistently_across_tiers() -> None:
    source = _score_with_repeated_notes([2, 2, 1, 2, 2, 2, 2, 2], forward=1)

    family = generate_arrangement_family(source)

    statuses = {
        (change.tier, change.operator): change.status
        for change in family.manifest.changes
        if change.operator in {"repetition-thin", "rhythm-merge"}
    }
    assert statuses[("Foundation", "repetition-thin")] == "accepted"
    assert statuses[("Core", "repetition-thin")] == "rejected"
    assert statuses[("Foundation", "rhythm-merge")] == "rejected"
    assert statuses[("Core", "rhythm-merge")] == "rejected"


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
    family = _unchanged_family(score)

    with pytest.raises(ArrangementValidationError, match="noncontiguous"):
        validate_family(score, family)


def test_hard_validator_rejects_duplicate_source_locators() -> None:
    strings, _ = _scores()
    part = strings.parts[0]
    duplicate = replace(part, measures=(*part.measures, part.measures[0]))
    score = replace(strings, parts=(duplicate, *strings.parts[1:]))
    family = _unchanged_family(score)

    with pytest.raises(ArrangementValidationError, match="duplicate source locator"):
        validate_family(score, family)
