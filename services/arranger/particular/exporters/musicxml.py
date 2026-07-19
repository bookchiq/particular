"""Deterministic MusicXML export and semantic fingerprints."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from typing import cast

from particular.domain.score import Event, Score

PITCH_NAMES = (
    ("C", 0),
    ("C", 1),
    ("D", 0),
    ("D", 1),
    ("E", 0),
    ("F", 0),
    ("F", 1),
    ("G", 0),
    ("G", 1),
    ("A", 0),
    ("A", 1),
    ("B", 0),
)


class MusicXMLExportError(ValueError):
    """A normalized score cannot be represented by the narrow exporter."""


def _pitch(parent: ET.Element, event: Event) -> None:
    pitch = ET.SubElement(parent, "pitch")
    assert event.written_pitch is not None
    step, alter = PITCH_NAMES[event.written_pitch % 12]
    octave = event.written_pitch // 12 - 1
    if event.pitch_step is not None and event.pitch_octave is not None:
        step, alter, octave = event.pitch_step, event.pitch_alter, event.pitch_octave
    ET.SubElement(pitch, "step").text = step
    if alter:
        ET.SubElement(pitch, "alter").text = str(alter)
    ET.SubElement(pitch, "octave").text = str(octave)


def _tempo(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)


def export_musicxml(score: Score) -> bytes:
    """Export a supported normalized score using stable element ordering."""

    if not score.export_capable:
        raise MusicXMLExportError("score contains unsupported notation")
    root = ET.Element("score-partwise", {"version": "4.0"})
    work = ET.SubElement(root, "work")
    ET.SubElement(work, "work-title").text = score.title
    part_list = ET.SubElement(root, "part-list")
    for part in score.parts:
        score_part = ET.SubElement(part_list, "score-part", {"id": part.id})
        ET.SubElement(score_part, "part-name").text = part.name
    for part in score.parts:
        part_element = ET.SubElement(root, "part", {"id": part.id})
        for measure in part.measures:
            attributes = {"number": measure.number}
            if measure.implicit:
                attributes["implicit"] = "yes"
            measure_element = ET.SubElement(part_element, "measure", attributes)
            score_attributes = ET.SubElement(measure_element, "attributes")
            ET.SubElement(score_attributes, "divisions").text = str(measure.divisions)
            if measure.key_fifths is not None:
                key = ET.SubElement(score_attributes, "key")
                ET.SubElement(key, "fifths").text = str(measure.key_fifths)
                if measure.key_mode is not None:
                    ET.SubElement(key, "mode").text = measure.key_mode
            time = ET.SubElement(score_attributes, "time")
            ET.SubElement(time, "beats").text = str(measure.beats)
            ET.SubElement(time, "beat-type").text = str(measure.beat_type)
            if part.chromatic_transposition or part.diatonic_transposition:
                transpose = ET.SubElement(score_attributes, "transpose")
                if part.diatonic_transposition:
                    ET.SubElement(transpose, "diatonic").text = str(part.diatonic_transposition)
                ET.SubElement(transpose, "chromatic").text = str(part.chromatic_transposition)
            if measure.clef_sign is not None:
                clef = ET.SubElement(score_attributes, "clef")
                ET.SubElement(clef, "sign").text = measure.clef_sign
                if measure.clef_line is not None:
                    ET.SubElement(clef, "line").text = str(measure.clef_line)
            for item in measure.directions:
                direction_attributes = {"placement": item.placement} if item.placement else {}
                direction = ET.SubElement(measure_element, "direction", direction_attributes)
                if item.words is not None:
                    direction_type = ET.SubElement(direction, "direction-type")
                    ET.SubElement(direction_type, "words").text = item.words
                if item.tempo is not None:
                    ET.SubElement(direction, "sound", {"tempo": _tempo(item.tempo)})
            cursor = 0
            previous_onset: int | None = None
            previous_voice: str | None = None
            for event in measure.events:
                is_chord = event.onset == previous_onset and event.voice == previous_voice
                if not is_chord and event.onset != cursor:
                    movement_name = "forward" if event.onset > cursor else "backup"
                    movement = ET.SubElement(measure_element, movement_name)
                    ET.SubElement(movement, "duration").text = str(abs(event.onset - cursor))
                    cursor = event.onset
                note = ET.SubElement(measure_element, "note")
                if is_chord:
                    ET.SubElement(note, "chord")
                if event.kind == "rest":
                    ET.SubElement(note, "rest")
                elif event.written_pitch is not None:
                    _pitch(note, event)
                else:
                    raise MusicXMLExportError("note event is missing written pitch")
                ET.SubElement(note, "duration").text = str(event.duration)
                ET.SubElement(note, "voice").text = event.voice
                if event.tie_start:
                    ET.SubElement(note, "tie", {"type": "start"})
                if event.tie_stop:
                    ET.SubElement(note, "tie", {"type": "stop"})
                if event.note_type is not None:
                    ET.SubElement(note, "type").text = event.note_type
                if event.tie_start or event.tie_stop:
                    notations = ET.SubElement(note, "notations")
                    if event.tie_start:
                        ET.SubElement(notations, "tied", {"type": "start"})
                    if event.tie_stop:
                        ET.SubElement(notations, "tied", {"type": "stop"})
                previous_onset = event.onset
                previous_voice = event.voice
                if not is_chord:
                    cursor += event.duration
    ET.indent(root, space="  ")
    return cast(
        bytes,
        ET.tostring(root, encoding="utf-8", xml_declaration=True, short_empty_elements=True),
    )


def semantic_fingerprint(score: Score) -> str:
    """Hash the stable musical semantics represented by the normalized model."""

    value = {
        "title": score.title,
        "parts": [
            {
                "id": part.id,
                "name": part.name,
                "transpose": part.chromatic_transposition,
                "diatonic_transpose": part.diatonic_transposition,
                "measures": [
                    {
                        "number": measure.number,
                        "implicit": measure.implicit,
                        "divisions": measure.divisions,
                        "time": [measure.beats, measure.beat_type],
                        "key": [measure.key_fifths, measure.key_mode],
                        "clef": [measure.clef_sign, measure.clef_line],
                        "directions": [
                            [item.words, item.tempo, item.placement] for item in measure.directions
                        ],
                        "events": [
                            [
                                event.kind,
                                event.onset,
                                event.duration,
                                event.voice,
                                event.written_pitch,
                                event.sounding_pitch,
                                event.tie_start,
                                event.tie_stop,
                                event.pitch_step,
                                event.pitch_alter,
                                event.pitch_octave,
                                event.note_type,
                            ]
                            for event in measure.events
                        ],
                    }
                    for measure in part.measures
                ],
            }
            for part in score.parts
        ],
    }
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
