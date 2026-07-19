"""Pure, conservative localized transformation operators."""

from __future__ import annotations

from dataclasses import replace

from particular.domain.score import Event, SourceLocator
from particular.generation.candidates import Candidate, candidate_id


def _rejected(operator: str, events: tuple[Event, ...], reason: str) -> Candidate:
    return Candidate(
        id=candidate_id(operator, events),
        operator=operator,
        version=1,
        tiers=("Foundation",),
        locators=tuple(event.locator for event in events),
        before=events,
        after=events,
        difficulty_delta={},
        explanation="No change proposed",
        role_effects=(),
        accepted=False,
        rejection_reason=reason,
    )


def reduce_rhythm(events: tuple[Event, ...], protected: frozenset[SourceLocator]) -> Candidate:
    operator = "rhythm-merge"
    pair: tuple[Event, Event] | None = None
    for left, right in zip(events, events[1:], strict=False):
        if (
            left.kind == right.kind == "note"
            and left.voice == right.voice
            and left.onset + left.duration == right.onset
        ):
            pair = (left, right)
            break
    if pair is None:
        return _rejected(operator, events[:1], "no adjacent notes can be merged")
    if any(event.locator in protected for event in pair):
        return _rejected(operator, pair, "protected role prevents rhythmic merge")
    merged = replace(pair[0], duration=pair[0].duration + pair[1].duration)
    return Candidate(
        candidate_id(operator, pair),
        operator,
        1,
        ("Foundation",),
        tuple(item.locator for item in pair),
        pair,
        (merged,),
        {"note_density": -1.0, "rhythmic_complexity": -1.0},
        "Two adjacent notes were merged into one longer note",
        ("entrance retained",),
        True,
    )


def adjust_octave_range(
    events: tuple[Event, ...],
    minimum: int,
    maximum: int,
    protected: frozenset[SourceLocator],
) -> Candidate:
    operator = "octave-range"
    target = next(
        (
            event
            for event in events
            if event.written_pitch is not None and not minimum <= event.written_pitch <= maximum
        ),
        None,
    )
    if target is None:
        return _rejected(operator, events[:1], "all notes are already within target range")
    if target.locator in protected:
        return _rejected(operator, (target,), "protected role prevents octave adjustment")
    written = target.written_pitch
    assert written is not None
    adjusted = written
    while adjusted > maximum:
        adjusted -= 12
    while adjusted < minimum:
        adjusted += 12
    if not minimum <= adjusted <= maximum:
        return _rejected(operator, (target,), "no octave placement fits the instrument range")
    offset = adjusted - written
    changed = replace(
        target,
        written_pitch=adjusted,
        sounding_pitch=None if target.sounding_pitch is None else target.sounding_pitch + offset,
    )
    return Candidate(
        candidate_id(operator, (target,)),
        operator,
        1,
        ("Foundation", "Core"),
        (target.locator,),
        (target,),
        (changed,),
        {"range": -float(abs(offset))},
        f"Note moved {abs(offset) // 12} octave toward the configured range",
        ("rhythm and onset retained",),
        True,
    )


def thin_repetitions(events: tuple[Event, ...], protected: frozenset[SourceLocator]) -> Candidate:
    operator = "repetition-thin"
    pair: tuple[Event, Event] | None = None
    for left, right in zip(events, events[1:], strict=False):
        if (
            left.kind == right.kind == "note"
            and left.written_pitch == right.written_pitch
            and left.voice == right.voice
        ):
            pair = (left, right)
            break
    if pair is None:
        return _rejected(operator, events[:1], "no repeated accompaniment notes to thin")
    if pair[1].locator in protected:
        return _rejected(operator, pair, "protected role prevents density thinning")
    rest = replace(pair[1], kind="rest", written_pitch=None, sounding_pitch=None)
    return Candidate(
        candidate_id(operator, pair),
        operator,
        1,
        ("Foundation",),
        tuple(event.locator for event in pair),
        pair,
        (pair[0], rest),
        {"note_density": -1.0},
        "A repeated accompaniment note was replaced by an equal-duration rest",
        ("first entrance and total duration retained",),
        True,
    )
