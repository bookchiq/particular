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
class Direction:
    words: str | None = None
    tempo: float | None = None
    placement: str | None = None


@dataclass(frozen=True)
class Event:
    kind: str
    onset: int
    duration: int
    voice: str
    written_pitch: int | None
    sounding_pitch: int | None
    locator: SourceLocator
    tie_start: bool = False
    tie_stop: bool = False
    pitch_step: str | None = None
    pitch_alter: int = 0
    pitch_octave: int | None = None
    note_type: str | None = None


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
    key_fifths: int | None = None
    key_mode: str | None = None
    clef_sign: str | None = None
    clef_line: int | None = None
    directions: tuple[Direction, ...] = ()


@dataclass(frozen=True)
class Part:
    id: str
    name: str
    chromatic_transposition: int
    measures: tuple[Measure, ...]
    diatonic_transposition: int = 0
    instrument_name: str | None = None


@dataclass(frozen=True)
class Score:
    version: str
    title: str
    parts: tuple[Part, ...]
    coverage_warnings: tuple[CoverageWarning, ...] = ()

    @property
    def export_capable(self) -> bool:
        return not self.coverage_warnings
