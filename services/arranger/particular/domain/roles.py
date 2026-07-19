"""Explainable protected-role records."""

from __future__ import annotations

from dataclasses import dataclass

from particular.domain.score import SourceLocator


@dataclass(frozen=True)
class RoleLabel:
    role: str
    locator: SourceLocator
    sounding_pitch: int | None
    confidence: float
    evidence: tuple[str, ...]
    protected: bool
