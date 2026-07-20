"""Instrument-aware difficulty feature extraction."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from particular.domain.difficulty import DifficultyAnalysis, DifficultyVector, TierPolicy
from particular.domain.score import Part

PROFILE_ROOT = Path(__file__).parents[1] / "profiles"


@dataclass(frozen=True)
class InstrumentProfile:
    profile_id: str
    names: tuple[str, ...]
    written_range: tuple[int, int]


@dataclass(frozen=True)
class InstrumentProfileDocument:
    version: int
    profiles: Mapping[str, InstrumentProfile]


@dataclass(frozen=True)
class ProfileMatch:
    profile_id: str
    confidence: str
    warning: str | None = None


@cache
def _load(name: str) -> dict[str, Any]:
    value = json.loads((PROFILE_ROOT / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"invalid profile document: {name}")
    return value


def parse_instrument_profiles(value: object) -> InstrumentProfileDocument:
    """Deserialize and validate the instrument-profile configuration."""

    if not isinstance(value, dict) or not isinstance(value.get("version"), int):
        raise ValueError("invalid instrument profile document")
    raw_profiles = value.get("profiles")
    if not isinstance(raw_profiles, dict) or "generic" not in raw_profiles:
        raise ValueError("instrument profile document requires a generic profile")
    profiles: dict[str, InstrumentProfile] = {}
    aliases: set[str] = set()
    for profile_id, raw_profile in raw_profiles.items():
        if not isinstance(profile_id, str) or not isinstance(raw_profile, dict):
            raise ValueError("invalid instrument profile")
        names = raw_profile.get("names")
        written_range = raw_profile.get("written_range")
        if (
            not isinstance(names, list)
            or not all(isinstance(name, str) and name.strip() for name in names)
            or not isinstance(written_range, list)
            or len(written_range) != 2
            or not all(isinstance(pitch, int) for pitch in written_range)
            or written_range[0] > written_range[1]
        ):
            raise ValueError(f"invalid profile {profile_id!r}: names or written_range")
        normalized_names = {_normalize_instrument_name(name) for name in names}
        if "" in normalized_names or aliases.intersection(normalized_names):
            raise ValueError(f"invalid profile {profile_id!r}: duplicate instrument name")
        aliases.update(normalized_names)
        profiles[profile_id] = InstrumentProfile(
            profile_id=profile_id,
            names=tuple(names),
            written_range=(written_range[0], written_range[1]),
        )
    return InstrumentProfileDocument(version=value["version"], profiles=profiles)


@cache
def instrument_profiles() -> InstrumentProfileDocument:
    """Return the validated, versioned instrument profile document."""

    return parse_instrument_profiles(_load("instruments.json"))


def _normalize_instrument_name(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name.casefold())
    unaccented = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    normalized = " ".join(re.findall(r"[a-z0-9]+", unaccented))
    return re.sub(r" (?:[0-9]+|[ivx]+)$", "", normalized)


def _profile_for(part: Part, profile_override: str | None = None) -> ProfileMatch:
    document = instrument_profiles()
    if profile_override is not None:
        if profile_override not in document.profiles or profile_override == "generic":
            raise ValueError(f"unknown instrument profile override: {profile_override}")
        return ProfileMatch(profile_override, "director-override")

    aliases = {
        _normalize_instrument_name(name): profile.profile_id
        for profile in document.profiles.values()
        for name in profile.names
    }
    part_match = aliases.get(_normalize_instrument_name(part.name))
    declared_match = (
        aliases.get(_normalize_instrument_name(part.instrument_name))
        if part.instrument_name
        else None
    )
    if part_match and declared_match and part_match != declared_match:
        return ProfileMatch(
            "generic", "ambiguous", "Instrument metadata conflicts; choose an instrument profile."
        )
    if declared_match:
        return ProfileMatch(declared_match, "declared-instrument")
    if part_match:
        return ProfileMatch(part_match, "normalized-name")
    return ProfileMatch(
        "generic",
        "unmatched",
        f"No instrument profile for {part.name!r}; generic constraints applied",
    )


def instrument_range(part: Part, profile_override: str | None = None) -> tuple[int, int]:
    """Return the declared written range for a part's matched profile."""

    profile = instrument_profiles().profiles[_profile_for(part, profile_override).profile_id]
    return profile.written_range


def tier_policy() -> TierPolicy:
    """Return the configured deterministic tier policy."""

    document = _load("tiers.json")
    return TierPolicy(
        version=int(document["version"]),
        targets={key: float(value) for key, value in document["targets"].items()},
    )


def analyze_part(part: Part, profile_override: str | None = None) -> DifficultyAnalysis:
    """Compute independent raw features without presenting a universal grade."""

    profile_document = instrument_profiles()
    policy = tier_policy()
    profile_match = _profile_for(part, profile_override)
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
        profile_id=profile_match.profile_id,
        profile_version=profile_document.version,
        profile_confidence=profile_match.confidence,
        vector=vector,
        tier_targets=policy.targets,
        warning=profile_match.warning,
    )
