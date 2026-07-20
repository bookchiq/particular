"""Stable tier policy and coordinated arrangement selection."""

from __future__ import annotations

from dataclasses import dataclass, replace

from particular.analysis.difficulty import analyze_part, instrument_range, tier_policy
from particular.analysis.roles import protected_locators
from particular.domain.difficulty import DifficultyVector
from particular.domain.score import Event, Measure, Part, Score, SourceLocator
from particular.generation.candidates import Candidate
from particular.generation.operators import adjust_octave_range, reduce_rhythm, thin_repetitions


@dataclass(frozen=True)
class TierScore:
    name: str
    score: Score
    target: float
    explanation: str


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: Candidate
    pressure: float


@dataclass(frozen=True)
class ManifestChange:
    tier: str
    candidate_id: str
    part_id: str
    measure: str
    operator: str
    operator_version: int
    status: str
    explanation: str
    rejection_reason: str | None
    difficulty_delta: dict[str, float]
    role_effects: tuple[str, ...]
    locators: tuple[SourceLocator, ...]
    # True when the operator produced a real transformation (whether or not it
    # was selected); False for structural no-ops that changed nothing.
    applicable: bool


@dataclass(frozen=True)
class GenerationManifest:
    policy_version: int
    changes: tuple[ManifestChange, ...]


@dataclass(frozen=True)
class ArrangementFamily:
    tiers: tuple[TierScore, ...]
    manifest: GenerationManifest


def _replace_events(score: Score, candidates: tuple[Candidate, ...]) -> Score:
    replacements: dict[SourceLocator, tuple[Event, ...]] = {}
    skipped: set[SourceLocator] = set()
    for candidate in candidates:
        replacements[candidate.locators[0]] = candidate.after
        skipped.update(candidate.locators[1:])
    parts: list[Part] = []
    for part in score.parts:
        measures: list[Measure] = []
        for measure in part.measures:
            events: list[Event] = []
            for event in measure.events:
                if event.locator in skipped:
                    continue
                events.extend(replacements.get(event.locator, (event,)))
            measures.append(replace(measure, events=tuple(events)))
        parts.append(replace(part, measures=tuple(measures)))
    return replace(score, parts=tuple(parts))


def _candidate_pressure(candidate: Candidate, vector: DifficultyVector) -> float:
    """Normalize the candidate's relevant passage features to a 0–1 policy pressure."""

    pressures: list[float] = []
    if "note_density" in candidate.difficulty_delta:
        pressures.append(min(1.0, vector.max_note_density_per_quarter / 4.0))
    if "rhythmic_complexity" in candidate.difficulty_delta:
        pressures.append(min(1.0, vector.rhythmic_complexity))
    return max(pressures, default=0.0)


def _tier_explanation(tier: str, target: float, selected: list[Candidate]) -> str:
    safety_count = sum(candidate.required_for_safety for candidate in selected)
    target_count = len(selected) - safety_count
    if safety_count and target_count:
        return (
            f"Applied {target_count} transformation(s) above the {target:.2f} {tier} target "
            f"and {safety_count} range correction(s) required for instrument safety."
        )
    if safety_count:
        return f"Applied {safety_count} range correction(s) required for instrument safety."
    if target_count:
        return (
            f"Applied {target_count} safe transformation(s) where passage difficulty "
            f"exceeded the {target:.2f} {tier} target."
        )
    if tier == "Challenge":
        return (
            "Unchanged: Challenge retains source detail unless an exceptional range "
            "correction is required."
        )
    return f"Unchanged: no safe candidate exceeded the {target:.2f} {tier} target."


def generate_arrangement_family(
    score: Score, profile_overrides: dict[str, str] | None = None
) -> ArrangementFamily:
    """Generate three compatible tiers with deterministic conflict resolution."""

    protected = protected_locators(score)
    proposed: list[ScoredCandidate] = []
    policy = tier_policy()
    for part in score.parts:
        profile_override = (profile_overrides or {}).get(part.id)
        minimum, maximum = instrument_range(part, profile_override)
        for measure in part.measures:
            if not measure.events:
                continue
            candidates = (
                reduce_rhythm(measure.events, protected, measure.divisions),
                adjust_octave_range(measure.events, minimum, maximum, protected),
                thin_repetitions(measure.events, protected),
            )
            vector = analyze_part(replace(part, measures=(measure,)), profile_override).vector
            proposed.extend(
                ScoredCandidate(
                    candidate,
                    (
                        _candidate_pressure(candidate, vector)
                        if candidate.accepted and not candidate.required_for_safety
                        else 0.0
                    ),
                )
                for candidate in candidates
            )
    proposed.sort(key=lambda item: item.candidate.id)
    occupied: set[SourceLocator] = set()
    conflicting: set[str] = set()
    for item in proposed:
        candidate = item.candidate
        if not candidate.accepted:
            continue
        if occupied.intersection(candidate.locators):
            conflicting.add(candidate.id)
        else:
            occupied.update(candidate.locators)
    changes: list[ManifestChange] = []
    tiers: list[TierScore] = []
    for tier in ("Foundation", "Core", "Challenge"):
        target = policy.targets[tier]
        selected: list[Candidate] = []
        for item in proposed:
            candidate = item.candidate
            reason = candidate.rejection_reason
            status = "rejected"
            if (
                candidate.accepted
                and candidate.id not in conflicting
                and tier in candidate.tiers
                and (candidate.required_for_safety or item.pressure > target)
            ):
                selected.append(candidate)
                status = "accepted"
            elif candidate.id in conflicting:
                reason = "overlaps a higher-priority candidate for this arrangement family"
            elif candidate.accepted:
                reason = (
                    "Challenge retains source detail for this operator"
                    if tier not in candidate.tiers
                    else (
                        f"passage pressure {item.pressure:.2f} does not exceed target {target:.2f}"
                    )
                )
            changes.append(
                ManifestChange(
                    tier=tier,
                    candidate_id=candidate.id,
                    part_id=candidate.locators[0].part_id,
                    measure=candidate.locators[0].measure_number,
                    operator=candidate.operator,
                    operator_version=candidate.version,
                    status=status,
                    explanation=candidate.explanation,
                    rejection_reason=reason,
                    difficulty_delta=candidate.difficulty_delta,
                    role_effects=candidate.role_effects,
                    locators=candidate.locators,
                    applicable=candidate.accepted,
                )
            )
        tiers.append(
            TierScore(
                tier,
                _replace_events(score, tuple(selected)),
                target,
                _tier_explanation(tier, target, selected),
            )
        )
    return ArrangementFamily(tuple(tiers), GenerationManifest(policy.version, tuple(changes)))
