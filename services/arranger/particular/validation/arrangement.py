"""Hard structural, range, role, and tier-family validators."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

from particular.analysis.difficulty import instrument_range
from particular.analysis.roles import protected_locators
from particular.domain.score import Event, Measure, Score, SourceLocator
from particular.generation.selector import ArrangementFamily


class ArrangementValidationError(ValueError):
    """A generated family violates a non-negotiable musical invariant."""


PITCH_CLASSES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
EXPECTED_TIERS = ["Essential", "Supported", "Original"]


def _structure(score: Score) -> list[tuple[str, int, int, tuple[Measure, ...]]]:
    return [
        (
            part.id,
            part.chromatic_transposition,
            part.diatonic_transposition,
            tuple(replace(measure, events=()) for measure in part.measures),
        )
        for part in score.parts
    ]


def _voice_coverage(score: Score) -> dict[tuple[str, str, str], tuple[tuple[int, int], ...]]:
    coverage: dict[tuple[str, str, str], list[tuple[int, int]]] = {}
    for part in score.parts:
        for measure in part.measures:
            for event in measure.events:
                key = (part.id, measure.number, event.voice)
                coverage.setdefault(key, []).append((event.onset, event.onset + event.duration))
    merged: dict[tuple[str, str, str], tuple[tuple[int, int], ...]] = {}
    for key, intervals in coverage.items():
        combined: list[tuple[int, int]] = []
        for start, end in sorted(intervals):
            if combined and start <= combined[-1][1]:
                previous_start, previous_end = combined[-1]
                combined[-1] = (previous_start, max(previous_end, end))
            else:
                combined.append((start, end))
        merged[key] = tuple(combined)
    return merged


def _events_by_locator(score: Score) -> dict[SourceLocator, Event]:
    events: dict[SourceLocator, Event] = {}
    for part in score.parts:
        for measure in part.measures:
            for event in measure.events:
                if event.locator in events:
                    raise ArrangementValidationError("score contains a duplicate source locator")
                events[event.locator] = event
    return events


def _validate_ties(score: Score, tier_name: str) -> None:
    active: dict[tuple[str, str, int], Fraction] = {}
    for part in score.parts:
        measure_offset = Fraction()
        for measure in part.measures:
            for event in sorted(
                measure.events, key=lambda item: (item.onset, item.locator.event_index)
            ):
                if not event.tie_start and not event.tie_stop:
                    continue
                if event.kind != "note" or event.written_pitch is None:
                    raise ArrangementValidationError(
                        f"{tier_name}: tie chain contains a non-note event"
                    )
                key = (part.id, event.voice, event.written_pitch)
                onset = measure_offset + Fraction(event.onset, measure.divisions)
                end = onset + Fraction(event.duration, measure.divisions)
                if event.tie_stop:
                    if active.get(key) != onset:
                        raise ArrangementValidationError(
                            f"{tier_name}: tie chain has an unmatched or noncontiguous stop"
                        )
                    del active[key]
                if event.tie_start:
                    if key in active:
                        raise ArrangementValidationError(
                            f"{tier_name}: tie chain has an overlapping start"
                        )
                    active[key] = end
            measure_offset += Fraction(measure.nominal_duration, measure.divisions)
    if active:
        raise ArrangementValidationError(f"{tier_name}: tie chain has an unmatched start")


def _validate_pitch_spelling(score: Score, tier_name: str) -> None:
    for event in _events_by_locator(score).values():
        spelling = (event.pitch_step, event.pitch_octave)
        if event.kind == "rest":
            if event.written_pitch is not None or spelling != (None, None):
                raise ArrangementValidationError(f"{tier_name}: rest contains pitch spelling")
            continue
        if event.written_pitch is None:
            continue
        if spelling == (None, None):
            continue
        if event.pitch_step not in PITCH_CLASSES or event.pitch_octave is None:
            raise ArrangementValidationError(f"{tier_name}: note has incomplete pitch spelling")
        spelled_pitch = (
            12 * (event.pitch_octave + 1) + PITCH_CLASSES[event.pitch_step] + event.pitch_alter
        )
        if spelled_pitch != event.written_pitch:
            raise ArrangementValidationError(
                f"{tier_name}: pitch spelling does not match written pitch"
            )


def validate_family(
    source: Score, family: ArrangementFamily, profile_overrides: dict[str, str] | None = None
) -> None:
    if [tier.name for tier in family.tiers] != EXPECTED_TIERS:
        raise ArrangementValidationError(
            "tier family must contain Essential, Supported, and Original in order"
        )
    source_shape = _structure(source)
    source_coverage = _voice_coverage(source)
    source_events = _events_by_locator(source)
    protected = protected_locators(source)
    counts: list[int] = []
    for tier in family.tiers:
        shape = _structure(tier.score)
        if shape != source_shape:
            raise ArrangementValidationError(f"{tier.name}: structure or duration changed")
        if _voice_coverage(tier.score) != source_coverage:
            raise ArrangementValidationError(f"{tier.name}: voice timeline changed")
        _validate_pitch_spelling(tier.score, tier.name)
        for part in tier.score.parts:
            minimum, maximum = instrument_range(part, (profile_overrides or {}).get(part.id))
            for measure in part.measures:
                for event in measure.events:
                    if (
                        event.kind == "note"
                        and event.written_pitch is not None
                        and not minimum <= event.written_pitch <= maximum
                    ):
                        raise ArrangementValidationError(
                            f"{tier.name}: {part.id} has an out-of-range note"
                        )
        tier_events = _events_by_locator(tier.score)
        if not protected.issubset(tier_events):
            raise ArrangementValidationError(f"{tier.name}: protected ensemble role was removed")
        if any(source_events[locator] != tier_events[locator] for locator in protected):
            raise ArrangementValidationError(f"{tier.name}: protected ensemble role changed")
        _validate_ties(tier.score, tier.name)
        count = 0
        for part in tier.score.parts:
            for measure in part.measures:
                # Count attacks, not note-heads: a tied continuation is the same
                # note re-notated (e.g. by de-syncopation), not new material, so
                # it must not count against a tier being "simpler" than another.
                count += sum(
                    event.kind == "note" and event.written_pitch is not None and not event.tie_stop
                    for event in measure.events
                )
        counts.append(count)
    if counts != sorted(counts):
        raise ArrangementValidationError("tier attack counts are not monotonic")
