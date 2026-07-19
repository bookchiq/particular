"""Time-aligned, sounding-pitch ensemble role heuristics."""

from __future__ import annotations

from collections import defaultdict

from particular.domain.roles import RoleLabel
from particular.domain.score import Event, Score, SourceLocator


def protected_locators(score: Score) -> frozenset[SourceLocator]:
    """Return events covered by the arrangement family's hard role policy."""

    return frozenset(
        label.locator
        for label in analyze_roles(score)
        if label.role in {"melody", "bass", "exposed_entrance"} and label.confidence >= 0.8
    )


def analyze_roles(score: Score) -> tuple[RoleLabel, ...]:
    """Label observable ensemble roles and conservatively protect uncertain material."""

    aligned: dict[tuple[int, int], list[Event]] = defaultdict(list)
    for part in score.parts:
        measure_offset = 0
        for measure_index, measure in enumerate(part.measures):
            for event in measure.events:
                if event.kind == "note" and event.sounding_pitch is not None:
                    aligned[(measure_index, measure_offset + event.onset)].append(event)
            measure_offset += measure.nominal_duration
    labels: list[RoleLabel] = []
    for (_, onset), events in sorted(aligned.items()):
        pitches = [event.sounding_pitch for event in events if event.sounding_pitch is not None]
        low, high = min(pitches), max(pitches)
        ambiguous = low == high or pitches.count(high) > 1
        shortest = min(event.duration for event in events)
        for event in events:
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
            if event.duration == shortest and len(events) > 1:
                evidence.append("supports rhythmic drive at this onset")
            if onset == 0:
                evidence.append("exposed entrance at score opening")
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
            if event.duration == shortest and len(events) > 1:
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
            if onset == 0:
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
    return tuple(labels)
