"""Time-aligned, sounding-pitch ensemble role heuristics."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from particular.domain.roles import RoleLabel
from particular.domain.score import Event, Score, SourceLocator


@dataclass(frozen=True)
class _SoundingSpan:
    event: Event
    start: Fraction
    end: Fraction


def protected_locators(score: Score) -> frozenset[SourceLocator]:
    """Return events covered by the arrangement family's hard role policy."""

    return frozenset(
        label.locator
        for label in analyze_roles(score)
        if label.role in {"melody", "bass", "exposed_entrance"} and label.confidence >= 0.8
    )


def _collect_spans(score: Score) -> list[_SoundingSpan]:
    """Project every sounding note onto exact rational musical time."""

    spans: list[_SoundingSpan] = []
    for part in score.parts:
        measure_offset = Fraction()
        for measure in part.measures:
            for event in measure.events:
                if event.kind == "note" and event.sounding_pitch is not None:
                    start = measure_offset + Fraction(event.onset, measure.divisions)
                    spans.append(
                        _SoundingSpan(
                            event,
                            start,
                            start + Fraction(event.duration, measure.divisions),
                        )
                    )
            # A pickup (implicit) measure elapses its actual content, not a full
            # bar; a normal measure advances by its nominal metric length so a
            # short or overfull bar cannot drift the timeline.
            elapsed = measure.duration if measure.implicit else measure.nominal_duration
            measure_offset += Fraction(elapsed, measure.divisions)
    return spans


def _is_part_entrance(span: _SoundingSpan, part_spans: list[_SoundingSpan]) -> bool:
    """True when the part was silent immediately before this span attacks.

    A note that follows another note in the same part with no gap is a
    continuation, not an entrance. A gap (rest or forward) before the note, or
    the part's very first note, is an entrance.
    """

    for other in part_spans:
        if other is span:
            continue
        if other.start < span.start and other.end >= span.start:
            return False
    return True


def _sounding_part_count(onset: Fraction, spans: list[_SoundingSpan]) -> int:
    """Number of distinct parts sounding at a musical instant."""

    return len({span.event.locator.part_id for span in spans if span.start <= onset < span.end})


def analyze_roles(score: Score) -> tuple[RoleLabel, ...]:
    """Label observable ensemble roles and conservatively protect uncertain material."""

    spans = _collect_spans(score)
    spans_by_part: dict[str, list[_SoundingSpan]] = {}
    for span in spans:
        spans_by_part.setdefault(span.event.locator.part_id, []).append(span)
    # A texture is sparse when at most half the ensemble is sounding. An entrance
    # into a sparse texture is exposed; the same entrance inside a tutti is not.
    total_parts = max(len(score.parts), 1)
    sparse_ceiling = max(1, total_parts // 2)

    labels: list[RoleLabel] = []
    for onset in sorted({span.start for span in spans}):
        active = [span for span in spans if span.start <= onset < span.end]
        events = [span.event for span in active]
        pitches = [event.sounding_pitch for event in events if event.sounding_pitch is not None]
        low, high = min(pitches), max(pitches)
        ambiguous = low == high or pitches.count(high) > 1
        shortest = min(span.end - span.start for span in active)
        exposed_texture = _sounding_part_count(onset, spans) <= sparse_ceiling
        for span in active:
            event = span.event
            pitch = event.sounding_pitch
            evidence: list[str] = []
            if ambiguous:
                role, confidence = "melody", 0.4
                evidence.append("ambiguous unison or doubled upper voice")
            elif pitch == high:
                role, confidence = "melody", 0.82
                evidence.append("highest sounding pitch at ensemble onset")
            elif pitch == low:
                role, confidence = "bass", 0.9
                evidence.append("lowest sounding pitch at ensemble onset")
            else:
                role, confidence = "harmonic_anchor", 0.7
                evidence.append("interior chord tone at ensemble onset")
            drives_rhythm = span.end - span.start == shortest and len(events) > 1
            if drives_rhythm:
                evidence.append("supports rhythmic drive at this onset")
            if span.start < onset:
                evidence.append("active sounding span under a later ensemble entrance")
            # An entrance is a note whose part was silent just before it attacks.
            # Only spans attacking at this onset can be entrances.
            entrance = span.start == onset and _is_part_entrance(
                span, spans_by_part[event.locator.part_id]
            )
            opening_entrance = entrance and span.start == 0
            # "Exposed" is an ensemble judgement: a part stands out because the
            # rest of the ensemble is sparse. A solo line has nothing to be
            # exposed against, so a later re-entry there is just its melody.
            exposed_entrance = (
                entrance and not opening_entrance and exposed_texture and total_parts >= 2
            )
            if opening_entrance:
                evidence.append("exposed entrance at score opening")
            elif exposed_entrance:
                evidence.append("exposed entrance into a sparse texture")
            labels.append(
                RoleLabel(
                    role=role,
                    locator=event.locator,
                    sounding_pitch=pitch,
                    confidence=confidence,
                    evidence=tuple(evidence),
                    protected=True,
                )
            )
            if drives_rhythm:
                labels.append(
                    RoleLabel(
                        role="rhythmic_drive",
                        locator=event.locator,
                        sounding_pitch=pitch,
                        confidence=0.65,
                        evidence=tuple(evidence + ["shortest active value at ensemble onset"]),
                        protected=True,
                    )
                )
            if opening_entrance:
                labels.append(
                    RoleLabel(
                        role="exposed_entrance",
                        locator=event.locator,
                        sounding_pitch=pitch,
                        confidence=0.95,
                        evidence=tuple(evidence + ["begins at the score opening"]),
                        protected=True,
                    )
                )
            elif exposed_entrance:
                labels.append(
                    RoleLabel(
                        role="exposed_entrance",
                        locator=event.locator,
                        sounding_pitch=pitch,
                        confidence=0.9,
                        evidence=tuple(evidence + ["enters after a rest while few parts sound"]),
                        protected=True,
                    )
                )
    return tuple(labels)
