"""Narrow, safe MusicXML adapter for Particular's hackathon corpus."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from particular.domain.score import CoverageWarning, Event, Measure, Part, Score, SourceLocator
from particular.importers.security import UnsafeScoreError, validate_xml_bytes


class MusicXMLParseError(ValueError):
    """MusicXML is malformed or outside the adapter's structural contract."""


PITCH_CLASSES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
UNSUPPORTED_TAGS = {"glissando", "slide", "tuplet", "wavy-line", "technical"}


def _integer(element: ET.Element | None, default: int) -> int:
    if element is None or element.text is None:
        return default
    try:
        return int(element.text)
    except ValueError as error:
        raise MusicXMLParseError(f"invalid integer: {element.text}") from error


def _pitch(note: ET.Element) -> int | None:
    pitch = note.find("pitch")
    if pitch is None:
        return None
    step = pitch.findtext("step")
    if step not in PITCH_CLASSES:
        raise MusicXMLParseError("note has invalid or missing pitch step")
    octave = _integer(pitch.find("octave"), -99)
    if octave == -99:
        raise MusicXMLParseError("note has missing octave")
    alter = _integer(pitch.find("alter"), 0)
    return 12 * (octave + 1) + PITCH_CLASSES[step] + alter


def parse_musicxml(data: bytes) -> Score:
    """Parse supported score-partwise MusicXML into immutable records."""

    try:
        validate_xml_bytes(data)
    except UnsafeScoreError:
        raise
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise MusicXMLParseError(f"malformed MusicXML: {error}") from error
    if root.tag != "score-partwise":
        raise MusicXMLParseError("only score-partwise MusicXML is supported")
    names = {
        item.attrib.get("id", ""): item.findtext("part-name", default="Unnamed part")
        for item in root.findall("./part-list/score-part")
    }
    parts: list[Part] = []
    warnings: list[CoverageWarning] = []
    for part_element in root.findall("part"):
        part_id = part_element.attrib.get("id", "")
        divisions, beats, beat_type, transpose = 1, 4, 4, 0
        measures: list[Measure] = []
        for measure_element in part_element.findall("measure"):
            number = measure_element.attrib.get("number", str(len(measures) + 1))
            attributes = measure_element.find("attributes")
            if attributes is not None:
                divisions = _integer(attributes.find("divisions"), divisions)
                beats = _integer(attributes.find("./time/beats"), beats)
                beat_type = _integer(attributes.find("./time/beat-type"), beat_type)
                transpose = _integer(attributes.find("./transpose/chromatic"), transpose)
            events: list[Event] = []
            for index, note in enumerate(measure_element.findall("note")):
                voice = note.findtext("voice", default="1")
                locator = SourceLocator(part_id, number, voice, index)
                duration = _integer(note.find("duration"), 0)
                if duration <= 0:
                    raise MusicXMLParseError(
                        f"{part_id} measure {number}: duration must be positive"
                    )
                written = _pitch(note)
                events.append(
                    Event(
                        kind="rest" if note.find("rest") is not None else "note",
                        duration=duration,
                        voice=voice,
                        written_pitch=written,
                        sounding_pitch=None if written is None else written + transpose,
                        locator=locator,
                        tie_start=note.find("tie[@type='start']") is not None,
                        tie_stop=note.find("tie[@type='stop']") is not None,
                    )
                )
                for descendant in note.iter():
                    if descendant.tag in UNSUPPORTED_TAGS:
                        warnings.append(
                            CoverageWarning(
                                descendant.tag,
                                locator,
                                f"{descendant.tag} cannot be exported canonically",
                            )
                        )
            duration = sum(event.duration for event in events)
            nominal = divisions * beats * 4 // beat_type
            measures.append(
                Measure(
                    number=number,
                    implicit=measure_element.attrib.get("implicit") == "yes",
                    divisions=divisions,
                    beats=beats,
                    beat_type=beat_type,
                    duration=duration,
                    nominal_duration=nominal,
                    events=tuple(events),
                )
            )
        parts.append(Part(part_id, names.get(part_id, "Unnamed part"), transpose, tuple(measures)))
    if not parts:
        raise MusicXMLParseError("score contains no parts")
    return Score(
        version=root.attrib.get("version", "4.0"),
        title=root.findtext("./work/work-title", default="Untitled"),
        parts=tuple(parts),
        coverage_warnings=tuple(warnings),
    )
