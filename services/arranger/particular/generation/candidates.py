"""Immutable localized transformation candidates."""

from __future__ import annotations

from dataclasses import dataclass

from particular.domain.score import Event, SourceLocator


@dataclass(frozen=True)
class Candidate:
    id: str
    operator: str
    version: int
    tiers: tuple[str, ...]
    locators: tuple[SourceLocator, ...]
    before: tuple[Event, ...]
    after: tuple[Event, ...]
    difficulty_delta: dict[str, float]
    explanation: str
    role_effects: tuple[str, ...]
    accepted: bool
    rejection_reason: str | None = None


def candidate_id(operator: str, events: tuple[Event, ...]) -> str:
    first = events[0].locator
    return f"{operator}:v1:{first.part_id}:{first.measure_number}:{first.event_index}"
