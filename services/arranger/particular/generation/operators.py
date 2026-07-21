"""Pure, conservative localized transformation operators."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

from particular.analysis.difficulty import key_alteration
from particular.domain.score import Event, SourceLocator
from particular.generation.candidates import Candidate, candidate_id

# Semitone offsets of each natural pitch class within an octave.
PITCH_CLASSES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

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
        tiers=("Essential",),
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
        ("Essential", "Supported"),
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
        ("Essential", "Supported", "Original"),
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
        ("Essential", "Supported"),
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
            ("Essential", "Supported"),
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
            ("Essential", "Supported"),
            (right.locator,),
            (right,),
            (changed,),
            {"largest_leap": -float(leap - new_leap)},
            f"A leap of {leap} semitones was folded to {new_leap} by octave placement",
            ("rhythm, onset, and pitch class retained",),
            True,
        )
    return _rejected(operator, events[:1], blocked_reason or "no over-octave leap to fold")


def desyncopate(
    events: tuple[Event, ...],
    protected: frozenset[SourceLocator],
    divisions: int,
) -> Candidate:
    """Re-notate a note tied across a beat as two beat-aligned notes.

    A note that attacks off the beat and is held across the next beat is hard to
    read and count. This splits it at that beat into two notes of the same pitch
    joined by a tie: the sound is identical, but each piece now begins and can be
    counted on a beat. It preserves onset coverage and total duration, and adds
    only a tied continuation — not a new attack — so it leaves tier attack counts
    unchanged.

    The continuation piece keeps the source note's locator with a ``split_index``
    of 1, so it still traces to the note it came from. Notes already inside a tie
    chain, and protected notes, are left alone.
    """

    operator = "desyncopate"
    blocked_reason: str | None = None
    for event in events:
        if event.kind != "note" or event.written_pitch is None:
            continue
        offset = event.onset % divisions
        if offset == 0:
            continue
        beat_boundary = event.onset - offset + divisions
        if event.onset + event.duration <= beat_boundary:
            continue
        if event.tie_start or event.tie_stop:
            blocked_reason = blocked_reason or "tied notes cannot be de-syncopated safely"
            continue
        if event.locator in protected:
            blocked_reason = blocked_reason or "protected role prevents de-syncopation"
            continue
        first_duration = beat_boundary - event.onset
        second_duration = event.duration - first_duration
        first_type = NOTE_TYPES.get(Fraction(first_duration, divisions))
        second_type = NOTE_TYPES.get(Fraction(second_duration, divisions))
        if first_type is None or second_type is None:
            blocked_reason = blocked_reason or "split pieces have no supported note type"
            continue
        first = replace(event, duration=first_duration, note_type=first_type, tie_start=True)
        second = replace(
            event,
            onset=beat_boundary,
            duration=second_duration,
            note_type=second_type,
            tie_start=False,
            tie_stop=True,
            locator=replace(event.locator, split_index=1),
        )
        return Candidate(
            candidate_id(operator, (event,)),
            operator,
            1,
            ("Essential", "Supported"),
            (event.locator,),
            (event,),
            (first, second),
            {"syncopation": -1.0},
            "A note tied across the beat was re-notated as two beat-aligned notes",
            ("pitch, onset, and total duration retained",),
            True,
        )
    return _rejected(operator, events[:1], blocked_reason or "no note is tied across a beat")


def simplify_accidentals(
    events: tuple[Event, ...],
    key_fifths: int | None,
    protected: frozenset[SourceLocator],
) -> Candidate:
    """Naturalize a chromatic note to the key signature ("play it in the key").

    Accidentals are a real reading and fingering burden for less-advanced
    players, and the difficulty model measures that burden but no operator eases
    it. This replaces a note whose written alteration contradicts the key
    signature with the diatonic pitch of the same letter — e.g. an F-sharp in C
    major becomes F-natural — removing the written accidental. Onset and duration
    are untouched, and it changes no note count.

    This is the one reductive operator that alters harmony, so it is deliberately
    conservative: it never touches a protected role (melody, bass, or an exposed
    entrance) or a tied note, and each change is shown in the review ledger for
    the director to accept or reject.
    """

    operator = "accidental-simplify"
    blocked_reason: str | None = None
    for event in events:
        if event.kind != "note" or event.written_pitch is None:
            continue
        if event.pitch_step is None or event.pitch_octave is None:
            continue
        implied = key_alteration(event.pitch_step, key_fifths)
        if event.pitch_alter == implied:
            continue  # already diatonic to the key — no accidental to remove
        if event.tie_start or event.tie_stop:
            blocked_reason = blocked_reason or "tied notes cannot be simplified safely"
            continue
        if event.locator in protected:
            blocked_reason = blocked_reason or "protected role prevents accidental simplification"
            continue
        new_pitch = 12 * (event.pitch_octave + 1) + PITCH_CLASSES[event.pitch_step] + implied
        offset = new_pitch - event.written_pitch
        changed = replace(
            event,
            written_pitch=new_pitch,
            pitch_alter=implied,
            sounding_pitch=None if event.sounding_pitch is None else event.sounding_pitch + offset,
        )
        return Candidate(
            candidate_id(operator, (event,)),
            operator,
            1,
            ("Essential", "Supported"),
            (event.locator,),
            (event,),
            (changed,),
            {"accidental_burden": -1.0},
            "A chromatic note was simplified to the key signature",
            ("rhythm and onset retained",),
            True,
        )
    return _rejected(operator, events[:1], blocked_reason or "no accidental to simplify")
