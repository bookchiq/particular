"""Stable tier policy and coordinated arrangement selection."""

from __future__ import annotations

from dataclasses import dataclass, replace

from particular.analysis.difficulty import instrument_range
from particular.analysis.roles import protected_locators
from particular.domain.score import Event, Measure, Part, Score, SourceLocator
from particular.generation.candidates import Candidate
from particular.generation.operators import adjust_octave_range, reduce_rhythm, thin_repetitions


@dataclass(frozen=True)
class TierScore:
    name: str
    score: Score


@dataclass(frozen=True)
class ManifestChange:
    tier: str
    candidate_id: str
    part_id: str
    measure: str
    operator: str
    status: str
    explanation: str
    rejection_reason: str | None


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


def generate_arrangement_family(score: Score) -> ArrangementFamily:
    """Generate three compatible tiers with deterministic conflict resolution."""

    protected = protected_locators(score)
    proposed: list[Candidate] = []
    for part in score.parts:
        minimum, maximum = instrument_range(part)
        for measure in part.measures:
            if not measure.events:
                continue
            proposed.extend(
                (
                    reduce_rhythm(measure.events, protected, measure.divisions),
                    adjust_octave_range(measure.events, minimum, maximum, protected),
                    thin_repetitions(measure.events, protected),
                )
            )
    proposed.sort(key=lambda candidate: candidate.id)
    changes: list[ManifestChange] = []
    tiers: list[TierScore] = []
    for tier in ("Foundation", "Core", "Challenge"):
        selected: list[Candidate] = []
        occupied: set[SourceLocator] = set()
        for candidate in proposed:
            reason = candidate.rejection_reason
            status = "rejected"
            if candidate.accepted and tier in candidate.tiers:
                if occupied.intersection(candidate.locators):
                    reason = "overlaps a higher-priority accepted candidate"
                else:
                    selected.append(candidate)
                    occupied.update(candidate.locators)
                    status = "accepted"
            elif candidate.accepted:
                reason = "operator is not enabled for this tier"
            changes.append(
                ManifestChange(
                    tier,
                    candidate.id,
                    candidate.locators[0].part_id,
                    candidate.locators[0].measure_number,
                    candidate.operator,
                    status,
                    candidate.explanation,
                    reason,
                )
            )
        tiers.append(TierScore(tier, _replace_events(score, tuple(selected))))
    return ArrangementFamily(tuple(tiers), GenerationManifest(1, tuple(changes)))
