"""Explainable, non-universal difficulty records."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DifficultyVector:
    note_count: int
    pitch_range_semitones: int
    largest_leap_semitones: int
    max_note_density_per_quarter: float
    shortest_duration_quarters: float
    accidental_burden: int
    rhythmic_complexity: float


@dataclass(frozen=True)
class DifficultyAnalysis:
    profile_id: str
    profile_version: int
    vector: DifficultyVector
    tier_targets: dict[str, float]
    warning: str | None = None


@dataclass(frozen=True)
class TierPolicy:
    version: int
    targets: dict[str, float]
