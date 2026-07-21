"""Deterministic note timelines for in-browser audition.

The engine already knows every note's onset, duration, and sounding pitch, so a
playback timeline is a pure, reproducible projection of the normalized score:
absolute note start and duration in seconds, plus MIDI pitch. Rendering it to
sound (a simple Web Audio synth) happens in the browser; this module never makes
sound, so it stays fully unit-testable.
"""

from __future__ import annotations

from typing import Any

from particular.domain.score import Measure, Score

# A neutral audition tempo used when the score states none. Auditioning is about
# hearing relative pitch, rhythm, and coordination, not performance tempo.
DEFAULT_TEMPO_BPM = 90.0


def _score_tempo(score: Score) -> float:
    """Return the first stated tempo in reading order, or the neutral default."""

    for part in score.parts:
        for measure in part.measures:
            for direction in measure.directions:
                if direction.tempo:
                    return float(direction.tempo)
    return DEFAULT_TEMPO_BPM


def _measure_quarters(measure: Measure) -> float:
    """Metric length of a measure in quarter notes."""

    if measure.divisions and measure.nominal_duration:
        return measure.nominal_duration / measure.divisions
    if measure.beat_type:
        return measure.beats * 4.0 / measure.beat_type
    return 0.0


def playback_timeline(score: Score, tempo_bpm: float | None = None) -> dict[str, Any]:
    """Project a score into a deterministic, JSON-ready audition timeline.

    Every note carries its absolute ``start`` and ``duration`` in seconds from
    ``t=0`` and its ``midi`` pitch. Rests advance time but produce no note. Tied
    notes are emitted as they appear (a re-articulation), which is faithful to
    rhythm and pitch and adequate for auditioning.
    """

    tempo = tempo_bpm if tempo_bpm is not None else _score_tempo(score)
    seconds_per_quarter = 60.0 / tempo
    parts: list[dict[str, Any]] = []
    for part in score.parts:
        notes: list[dict[str, Any]] = []
        measure_start = 0.0
        for measure in part.measures:
            if measure.divisions:
                for event in measure.events:
                    if event.kind == "note" and event.sounding_pitch is not None:
                        start = (
                            measure_start + event.onset / measure.divisions
                        ) * seconds_per_quarter
                        duration = (event.duration / measure.divisions) * seconds_per_quarter
                        notes.append(
                            {
                                "start": round(start, 4),
                                "duration": round(duration, 4),
                                "midi": event.sounding_pitch,
                            }
                        )
            measure_start += _measure_quarters(measure)
        parts.append({"part_id": part.id, "part_name": part.name, "notes": notes})
    return {
        "tempo_bpm": tempo,
        "seconds_per_quarter": round(seconds_per_quarter, 6),
        "parts": parts,
    }
