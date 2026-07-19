"""Canonical normalized score records."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceLocator:
    part_id: str
    measure_number: str
    voice: str
    event_index: int


@dataclass(frozen=True)
class CoverageWarning:
    feature: str
    locator: SourceLocator
    message: str


@dataclass(frozen=True)
class Event:
    kind: str
    duration: int
    voice: str
    written_pitch: int | None
    sounding_pitch: int | None
    locator: SourceLocator
    tie_start: bool = False
    tie_stop: bool = False


@dataclass(frozen=True)
class Measure:
    number: str
    implicit: bool
    divisions: int
    beats: int
    beat_type: int
    duration: int
    nominal_duration: int
    events: tuple[Event, ...]


@dataclass(frozen=True)
class Part:
    id: str
    name: str
    chromatic_transposition: int
    measures: tuple[Measure, ...]


@dataclass(frozen=True)
class Score:
    version: str
    title: str
    parts: tuple[Part, ...]
    coverage_warnings: tuple[CoverageWarning, ...] = ()

    @property
    def export_capable(self) -> bool:
        return not self.coverage_warnings
