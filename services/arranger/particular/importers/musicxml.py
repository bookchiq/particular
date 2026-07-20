"""Narrow, safe MusicXML adapter for Particular's hackathon corpus."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from math import isfinite

from particular.domain.score import (
    CoverageWarning,
    Direction,
    Event,
    Measure,
    Part,
    Score,
    SourceLocator,
)
from particular.importers.security import UnsafeScoreError, validate_xml_bytes


class MusicXMLParseError(ValueError):
    """MusicXML is malformed or outside the adapter's structural contract."""


PITCH_CLASSES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
SUPPORTED_MEASURE_CHILDREN = {"attributes", "backup", "direction", "forward", "note", "print"}
SUPPORTED_ATTRIBUTE_CHILDREN = {"clef", "divisions", "key", "time", "transpose"}
SUPPORTED_NOTE_CHILDREN = {
    "chord",
    "duration",
    "notations",
    "pitch",
    "rest",
    "tie",
    "type",
    "voice",
}


def _integer(element: ET.Element | None, default: int) -> int:
    if element is None or element.text is None:
        return default
    try:
        return int(element.text)
    except ValueError as error:
        raise MusicXMLParseError(f"invalid integer: {element.text}") from error


def _pitch(note: ET.Element) -> tuple[int, str, int, int] | None:
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
    return 12 * (octave + 1) + PITCH_CLASSES[step] + alter, step, alter, octave


def _warning(
    warnings: list[CoverageWarning],
    seen_warnings: set[CoverageWarning],
    feature: str,
    locator: SourceLocator,
) -> None:
    warning = CoverageWarning(feature, locator, f"{feature} cannot be exported canonically")
    if warning not in seen_warnings:
        seen_warnings.add(warning)
        warnings.append(warning)


def _warn_unmodeled_shape(
    element: ET.Element,
    allowed_children: set[str],
    allowed_attributes: set[str],
    warnings: list[CoverageWarning],
    seen_warnings: set[CoverageWarning],
    locator: SourceLocator,
) -> None:
    if set(element.attrib) - allowed_attributes:
        _warning(warnings, seen_warnings, element.tag, locator)
    for child in element:
        if child.tag not in allowed_children:
            _warning(warnings, seen_warnings, element.tag, locator)


def _warn_simple_children(
    element: ET.Element,
    warnings: list[CoverageWarning],
    seen_warnings: set[CoverageWarning],
    locator: SourceLocator,
) -> None:
    for child in element:
        _warn_unmodeled_shape(child, set(), set(), warnings, seen_warnings, locator)


def _direction(
    element: ET.Element,
    warnings: list[CoverageWarning],
    seen_warnings: set[CoverageWarning],
    locator: SourceLocator,
) -> Direction | None:
    _warn_unmodeled_shape(
        element,
        {"direction-type", "sound"},
        {"placement"},
        warnings,
        seen_warnings,
        locator,
    )
    direction_types = element.findall("direction-type")
    for direction_type in direction_types:
        _warn_unmodeled_shape(
            direction_type,
            {child.tag for child in direction_type},
            set(),
            warnings,
            seen_warnings,
            locator,
        )
        for words_element in direction_type.findall("words"):
            _warn_unmodeled_shape(
                words_element,
                set(),
                set(),
                warnings,
                seen_warnings,
                locator,
            )
    supported_words = [child for item in direction_types for child in item if child.tag == "words"]
    unsupported = [child.tag for item in direction_types for child in item if child.tag != "words"]
    for feature in unsupported:
        _warning(warnings, seen_warnings, feature, locator)
    unexpected = {child.tag for child in element if child.tag not in {"direction-type", "sound"}}
    for feature in sorted(unexpected):
        _warning(warnings, seen_warnings, feature, locator)
    sound = element.find("sound")
    tempo: float | None = None
    if sound is not None:
        if set(sound.attrib) - {"tempo"}:
            _warning(warnings, seen_warnings, "sound", locator)
        if "tempo" in sound.attrib:
            try:
                tempo = float(sound.attrib["tempo"])
            except ValueError as error:
                raise MusicXMLParseError("direction has invalid tempo") from error
            if not isfinite(tempo) or tempo <= 0:
                raise MusicXMLParseError("direction tempo must be finite and positive")
    words = " ".join(filter(None, (item.text for item in supported_words))) or None
    if words is None and tempo is None:
        return None
    return Direction(words=words, tempo=tempo, placement=element.attrib.get("placement"))


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
    part_metadata = {
        item.attrib.get("id", ""): (
            item.findtext("part-name", default="Unnamed part"),
            item.findtext("./score-instrument/instrument-name"),
        )
        for item in root.findall("./part-list/score-part")
    }
    parts: list[Part] = []
    warnings: list[CoverageWarning] = []
    seen_warnings: set[CoverageWarning] = set()
    for part_element in root.findall("part"):
        part_id = part_element.attrib.get("id", "")
        if not part_id or any(part.id == part_id for part in parts):
            raise MusicXMLParseError("score contains missing or duplicate part IDs")
        divisions, beats, beat_type, transpose, diatonic_transpose = 1, 4, 4, 0, 0
        key_fifths: int | None = None
        key_mode: str | None = None
        clef_sign: str | None = None
        clef_line: int | None = None
        measures: list[Measure] = []
        seen_measure_numbers: set[str] = set()
        for measure_element in part_element.findall("measure"):
            number = measure_element.attrib.get("number", str(len(measures) + 1))
            if number in seen_measure_numbers:
                raise MusicXMLParseError(f"{part_id}: duplicate measure number {number}")
            seen_measure_numbers.add(number)
            measure_locator = SourceLocator(part_id, number, "1", -1)
            attributes = measure_element.find("attributes")
            if attributes is not None:
                _warn_unmodeled_shape(
                    attributes,
                    SUPPORTED_ATTRIBUTE_CHILDREN,
                    set(),
                    warnings,
                    seen_warnings,
                    measure_locator,
                )
                for child in attributes:
                    if child.tag not in SUPPORTED_ATTRIBUTE_CHILDREN:
                        _warning(warnings, seen_warnings, child.tag, measure_locator)
                divisions = _integer(attributes.find("divisions"), divisions)
                divisions_element = attributes.find("divisions")
                if divisions_element is not None:
                    _warn_unmodeled_shape(
                        divisions_element,
                        set(),
                        set(),
                        warnings,
                        seen_warnings,
                        measure_locator,
                    )
                time = attributes.find("time")
                if time is not None:
                    _warn_unmodeled_shape(
                        time,
                        {"beats", "beat-type"},
                        set(),
                        warnings,
                        seen_warnings,
                        measure_locator,
                    )
                    _warn_simple_children(time, warnings, seen_warnings, measure_locator)
                beats = _integer(attributes.find("./time/beats"), beats)
                beat_type = _integer(attributes.find("./time/beat-type"), beat_type)
                if divisions <= 0:
                    raise MusicXMLParseError(
                        f"{part_id} measure {number}: divisions must be positive"
                    )
                if beats <= 0 or beat_type <= 0:
                    raise MusicXMLParseError(
                        f"{part_id} measure {number}: meter values must be positive"
                    )
                transpose = _integer(attributes.find("./transpose/chromatic"), transpose)
                diatonic_transpose = _integer(
                    attributes.find("./transpose/diatonic"), diatonic_transpose
                )
                transpose_element = attributes.find("transpose")
                if transpose_element is not None:
                    _warn_unmodeled_shape(
                        transpose_element,
                        {"chromatic", "diatonic"},
                        set(),
                        warnings,
                        seen_warnings,
                        measure_locator,
                    )
                    _warn_simple_children(
                        transpose_element, warnings, seen_warnings, measure_locator
                    )
                key = attributes.find("key")
                if key is not None:
                    _warn_unmodeled_shape(
                        key,
                        {"fifths", "mode"},
                        set(),
                        warnings,
                        seen_warnings,
                        measure_locator,
                    )
                    _warn_simple_children(key, warnings, seen_warnings, measure_locator)
                    key_fifths = _integer(key.find("fifths"), 0)
                    key_mode = key.findtext("mode")
                clef = attributes.find("clef")
                if clef is not None:
                    _warn_unmodeled_shape(
                        clef,
                        {"sign", "line"},
                        set(),
                        warnings,
                        seen_warnings,
                        measure_locator,
                    )
                    _warn_simple_children(clef, warnings, seen_warnings, measure_locator)
                    clef_sign = clef.findtext("sign")
                    clef_line = _integer(clef.find("line"), 0) or None
            events: list[Event] = []
            directions: list[Direction] = []
            cursor = 0
            previous_onset = 0
            for child in measure_element:
                if child.tag not in SUPPORTED_MEASURE_CHILDREN:
                    _warning(warnings, seen_warnings, child.tag, measure_locator)
                    continue
                if child.tag == "direction":
                    if cursor != 0:
                        _warning(warnings, seen_warnings, "direction-offset", measure_locator)
                    parsed_direction = _direction(child, warnings, seen_warnings, measure_locator)
                    if parsed_direction is not None:
                        directions.append(parsed_direction)
                    continue
                if child.tag in {"backup", "forward"}:
                    movement = _integer(child.find("duration"), 0)
                    cursor += movement if child.tag == "forward" else -movement
                    if cursor < 0:
                        raise MusicXMLParseError(f"{part_id} measure {number}: backup before start")
                    continue
                if child.tag != "note":
                    continue
                note = child
                index = len(events)
                voice = note.findtext("voice", default="1")
                locator = SourceLocator(part_id, number, voice, index)
                _warn_unmodeled_shape(
                    note,
                    SUPPORTED_NOTE_CHILDREN,
                    set(),
                    warnings,
                    seen_warnings,
                    locator,
                )
                for note_child in note:
                    if note_child.tag not in SUPPORTED_NOTE_CHILDREN:
                        _warning(warnings, seen_warnings, note_child.tag, locator)
                notations = note.find("notations")
                if notations is not None:
                    if notations.attrib:
                        _warning(warnings, seen_warnings, "notations", locator)
                    for notation in notations:
                        if notation.tag != "tied":
                            _warning(warnings, seen_warnings, notation.tag, locator)
                        elif set(notation.attrib) - {"type"} or notation.attrib.get("type") not in {
                            "start",
                            "stop",
                        }:
                            _warning(warnings, seen_warnings, "tied", locator)
                for tie in note.findall("tie"):
                    if set(tie.attrib) - {"type"} or tie.attrib.get("type") not in {
                        "start",
                        "stop",
                    }:
                        _warning(warnings, seen_warnings, "tie", locator)
                pitch_element = note.find("pitch")
                if pitch_element is not None:
                    _warn_unmodeled_shape(
                        pitch_element,
                        {"step", "alter", "octave"},
                        set(),
                        warnings,
                        seen_warnings,
                        locator,
                    )
                    _warn_simple_children(pitch_element, warnings, seen_warnings, locator)
                for simple_tag in {"chord", "duration", "rest", "type", "voice"}:
                    for simple_element in note.findall(simple_tag):
                        _warn_unmodeled_shape(
                            simple_element,
                            set(),
                            set(),
                            warnings,
                            seen_warnings,
                            locator,
                        )
                duration = _integer(note.find("duration"), 0)
                if duration <= 0:
                    raise MusicXMLParseError(
                        f"{part_id} measure {number}: duration must be positive"
                    )
                pitch = _pitch(note)
                written = None if pitch is None else pitch[0]
                onset = previous_onset if note.find("chord") is not None else cursor
                events.append(
                    Event(
                        kind="rest" if note.find("rest") is not None else "note",
                        onset=onset,
                        duration=duration,
                        voice=voice,
                        written_pitch=written,
                        sounding_pitch=None if written is None else written + transpose,
                        locator=locator,
                        tie_start=(
                            note.find("tie[@type='start']") is not None
                            or note.find("./notations/tied[@type='start']") is not None
                        ),
                        tie_stop=(
                            note.find("tie[@type='stop']") is not None
                            or note.find("./notations/tied[@type='stop']") is not None
                        ),
                        pitch_step=None if pitch is None else pitch[1],
                        pitch_alter=0 if pitch is None else pitch[2],
                        pitch_octave=None if pitch is None else pitch[3],
                        note_type=note.findtext("type"),
                    )
                )
                previous_onset = onset
                if note.find("chord") is None:
                    cursor += duration
            duration = max((event.onset + event.duration for event in events), default=0)
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
                    key_fifths=key_fifths,
                    key_mode=key_mode,
                    clef_sign=clef_sign,
                    clef_line=clef_line,
                    directions=tuple(directions),
                )
            )
        parts.append(
            Part(
                id=part_id,
                name=part_metadata.get(part_id, ("Unnamed part", None))[0],
                chromatic_transposition=transpose,
                measures=tuple(measures),
                diatonic_transposition=diatonic_transpose,
                instrument_name=part_metadata.get(part_id, ("Unnamed part", None))[1],
            )
        )
    if not parts:
        raise MusicXMLParseError("score contains no parts")
    return Score(
        version=root.attrib.get("version", "4.0"),
        title=root.findtext("./work/work-title", default="Untitled"),
        parts=tuple(parts),
        coverage_warnings=tuple(warnings),
    )
