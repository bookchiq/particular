"""Instrument-aware difficulty feature extraction."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from particular.domain.difficulty import DifficultyAnalysis, DifficultyVector
from particular.domain.score import Part

PROFILE_ROOT = Path(__file__).parents[1] / "profiles"


@cache
def _load(name: str) -> dict[str, Any]:
    value = json.loads((PROFILE_ROOT / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"invalid profile document: {name}")
    return value


def _profile_for(part: Part, profiles: dict[str, Any]) -> str:
    normalized = part.name.casefold()
    for profile_id, profile in profiles.items():
        if normalized in profile["names"]:
            return str(profile_id)
    return "generic"


def instrument_range(part: Part) -> tuple[int, int]:
    """Return the declared written range for a part's matched profile."""

    document = _load("instruments.json")
    profile = document["profiles"][_profile_for(part, document["profiles"])]
    return int(profile["written_range"][0]), int(profile["written_range"][1])


def analyze_part(part: Part) -> DifficultyAnalysis:
    """Compute independent raw features without presenting a universal grade."""

    profile_document = _load("instruments.json")
    tier_document = _load("tiers.json")
    profile_id = _profile_for(part, profile_document["profiles"])
    notes = [event for measure in part.measures for event in measure.events if event.kind == "note"]
    pitches = [event.written_pitch for event in notes if event.written_pitch is not None]
    leaps = [abs(right - left) for left, right in zip(pitches, pitches[1:], strict=False)]
    density = [
        len([event for event in measure.events if event.kind == "note"])
        / (measure.nominal_duration / measure.divisions)
        for measure in part.measures
        if measure.nominal_duration
    ]
    durations = [
        event.duration / measure.divisions for measure in part.measures for event in measure.events
    ]
    shortest = min(durations, default=0.0)
    vector = DifficultyVector(
        note_count=len(notes),
        pitch_range_semitones=max(pitches) - min(pitches) if pitches else 0,
        largest_leap_semitones=max(leaps, default=0),
        max_note_density_per_quarter=max(density, default=0.0),
        shortest_duration_quarters=shortest,
        accidental_burden=sum(pitch % 12 in {1, 3, 6, 8, 10} for pitch in pitches),
        rhythmic_complexity=max(0.0, 1.0 - shortest) if notes else 0.0,
    )
    return DifficultyAnalysis(
        profile_id=profile_id,
        profile_version=int(profile_document["version"]),
        vector=vector,
        tier_targets={key: float(value) for key, value in tier_document["targets"].items()},
        warning=(
            f"No instrument profile for {part.name!r}; generic constraints applied"
            if profile_id == "generic"
            else None
        ),
    )
