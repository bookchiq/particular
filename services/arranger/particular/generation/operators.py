"""Pure, conservative localized transformation operators."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

from particular.domain.score import Event, SourceLocator
from particular.generation.candidates import Candidate, candidate_id

NOTE_TYPES = {
    Fraction(4): "whole",
    Fraction(2): "half",
    Fraction(1): "quarter",
    Fraction(1, 2): "eighth",
    Fraction(1, 4): "16th",
    Fraction(1, 8): "32nd",
    Fraction(1, 16): "64th",
}

# Melodic leaps wider than an octave are the ones worth folding for accessibility;
# anything up to an octave is left as written.
MAX_COMFORTABLE_LEAP = 12


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


def reduce_rhythm(
    events: tuple[Event, ...],
    protected: frozenset[SourceLocator],
    divisions: int,
) -> Candidate:
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
    if pair[0].written_pitch is None or pair[0].written_pitch != pair[1].written_pitch:
        return _rejected(operator, pair, "adjacent notes have different pitches")
    if any(event.tie_start or event.tie_stop for event in pair):
        return _rejected(operator, pair, "tied notes cannot be merged safely")
    if any(event.locator in protected for event in pair):
        return _rejected(operator, pair, "protected role prevents rhythmic merge")
    merged_duration = pair[0].duration + pair[1].duration
    note_type = NOTE_TYPES.get(Fraction(merged_duration, divisions))
    if note_type is None:
        return _rejected(operator, pair, "merged duration has no supported note type")
    merged = replace(pair[0], duration=merged_duration, note_type=note_type)
    return Candidate(
        candidate_id(operator, pair),
        operator,
        1,
        ("Foundation", "Core"),
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
        pitch_octave=(
            None if target.pitch_octave is None else target.pitch_octave + (offset // 12)
        ),
    )
    return Candidate(
        candidate_id(operator, (target,)),
        operator,
        1,
        ("Foundation", "Core", "Challenge"),
        (target.locator,),
        (target,),
        (changed,),
        {"range": -float(abs(offset))},
        f"Note moved {abs(offset) // 12} octave toward the configured range",
        ("rhythm and onset retained",),
        True,
        required_for_safety=True,
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
    if any(event.tie_start or event.tie_stop for event in pair):
        return _rejected(operator, pair, "tied notes cannot be thinned safely")
    if pair[1].locator in protected:
        return _rejected(operator, pair, "protected role prevents density thinning")
    rest = replace(
        pair[1],
        kind="rest",
        written_pitch=None,
        sounding_pitch=None,
        pitch_step=None,
        pitch_alter=0,
        pitch_octave=None,
    )
    return Candidate(
        candidate_id(operator, pair),
        operator,
        1,
        ("Foundation", "Core"),
        tuple(event.locator for event in pair),
        pair,
        (pair[0], rest),
        {"note_density": -1.0},
        "A repeated accompaniment note was replaced by an equal-duration rest",
        ("first entrance and total duration retained",),
        True,
    )


def thin_run(
    events: tuple[Event, ...],
    protected: frozenset[SourceLocator],
    divisions: int,
) -> Candidate:
    """Thin a fast run by absorbing an off-beat note into the note before it.

    Complements :func:`reduce_rhythm` and :func:`thin_repetitions`, which only
    act on repeated (same-pitch) notes. This handles the common busy passage
    those reject: a run of adjacent, equal-duration, *fast* notes at *different*
    pitches (a scale or arpeggio). The later note is absorbed into the earlier
    one, which keeps the passage's onset coverage and total duration intact while
    reducing note density and rhythmic detail.

    The scan skips pairs that are protected or tied and continues, so a protected
    run opening (a common exposed entrance) does not block thinning a safe pair
    later in the same run. Same-pitch pairs are left to the repetition operators.
    """

    operator = "run-thin"
    blocked_reason: str | None = None
    for left, right in zip(events, events[1:], strict=False):
        if left.kind != "note" or right.kind != "note" or left.voice != right.voice:
            continue
        if left.written_pitch is None or right.written_pitch is None:
            continue
        if left.written_pitch == right.written_pitch:
            continue
        if left.onset + left.duration != right.onset or left.duration != right.duration:
            continue
        if Fraction(left.duration, divisions) > Fraction(1, 2):
            continue
        if any(event.tie_start or event.tie_stop for event in (left, right)):
            blocked_reason = blocked_reason or "tied notes cannot be thinned safely"
            continue
        if left.locator in protected or right.locator in protected:
            blocked_reason = blocked_reason or "protected role prevents run thinning"
            continue
        merged_duration = left.duration + right.duration
        note_type = NOTE_TYPES.get(Fraction(merged_duration, divisions))
        if note_type is None:
            blocked_reason = blocked_reason or "merged duration has no supported note type"
            continue
        pair = (left, right)
        merged = replace(left, duration=merged_duration, note_type=note_type)
        return Candidate(
            candidate_id(operator, pair),
            operator,
            1,
            ("Foundation", "Core"),
            tuple(event.locator for event in pair),
            pair,
            (merged,),
            {"note_density": -1.0, "rhythmic_complexity": -1.0},
            "A fast off-beat note was absorbed into the note before it, thinning a run",
            ("earlier onset and total duration retained",),
            True,
        )
    return _rejected(
        operator, events[:1], blocked_reason or "no fast run of distinct notes to thin"
    )


def fold_large_leaps(
    events: tuple[Event, ...],
    minimum: int,
    maximum: int,
    protected: frozenset[SourceLocator],
) -> Candidate:
    """Shrink an over-an-octave melodic leap by octave-placing the leaping note.

    Big register jumps are a real playability burden that the density and rhythm
    operators never touch. When one note leaps more than an octave from the note
    before it, this places that note in the octave (within the instrument's
    written range) closest to the previous note, reducing the leap while keeping
    the note's pitch class, onset, and duration. It changes no note count, so it
    never affects tier note-count monotonicity.

    Protected notes are left alone (folding a melody or bass note would rewrite
    the line), and the scan continues past them to the next foldable leap.
    """

    operator = "leap-fold"
    blocked_reason: str | None = None
    for left, right in zip(events, events[1:], strict=False):
        if left.kind != "note" or right.kind != "note" or left.voice != right.voice:
            continue
        if left.written_pitch is None or right.written_pitch is None:
            continue
        left_pitch = left.written_pitch
        right_pitch = right.written_pitch
        leap = abs(right_pitch - left_pitch)
        if leap <= MAX_COMFORTABLE_LEAP:
            continue
        if not (minimum <= left_pitch <= maximum) or not (minimum <= right_pitch <= maximum):
            # Let the range-safety operator relocate out-of-range notes first;
            # folding toward a note that is about to move would use a stale target.
            blocked_reason = blocked_reason or "range safety handles out-of-range notes first"
            continue
        if right.locator in protected:
            blocked_reason = blocked_reason or "protected role prevents leap folding"
            continue
        placements = [
            pitch
            for pitch in range(right_pitch % 12, maximum + 1, 12)
            if minimum <= pitch <= maximum
        ]
        if not placements:
            blocked_reason = blocked_reason or "no in-range octave for the leaping note"
            continue
        target_pitch = min(placements, key=lambda pitch: abs(pitch - left_pitch))
        new_leap = abs(target_pitch - left_pitch)
        if new_leap >= leap:
            blocked_reason = blocked_reason or "no octave placement reduces the leap"
            continue
        offset = target_pitch - right_pitch
        changed = replace(
            right,
            written_pitch=target_pitch,
            sounding_pitch=None if right.sounding_pitch is None else right.sounding_pitch + offset,
            pitch_octave=None if right.pitch_octave is None else right.pitch_octave + offset // 12,
        )
        return Candidate(
            candidate_id(operator, (right,)),
            operator,
            1,
            ("Foundation", "Core"),
            (right.locator,),
            (right,),
            (changed,),
            {"largest_leap": -float(leap - new_leap)},
            f"A leap of {leap} semitones was folded to {new_leap} by octave placement",
            ("rhythm, onset, and pitch class retained",),
            True,
        )
    return _rejected(operator, events[:1], blocked_reason or "no over-octave leap to fold")
