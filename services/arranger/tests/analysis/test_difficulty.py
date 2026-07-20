from __future__ import annotations

from pathlib import Path

import pytest
from particular.analysis.difficulty import (
    analyze_part,
    parse_instrument_profiles,
)
from particular.importers.musicxml import parse_musicxml

ROOT = Path(__file__).parents[4]


def test_second_violin_has_explainable_golden_features() -> None:
    score = parse_musicxml(
        (ROOT / "evaluation/fixtures/string-orchestra-second-violin.musicxml").read_bytes()
    )
    analysis = analyze_part(score.parts[1])

    assert analysis.profile_id == "violin"
    assert analysis.vector.note_count == 10
    assert analysis.vector.pitch_range_semitones == 24
    assert analysis.vector.largest_leap_semitones == 19
    assert analysis.vector.shortest_duration_quarters == 0.5
    assert analysis.vector.max_note_density_per_quarter == 2.0
    assert analysis.vector.accidental_burden == 1
    assert analysis.vector.rhythmic_complexity == 0.5


def test_unknown_and_rest_only_part_uses_generic_profile() -> None:
    xml = (
        b"<score-partwise><part-list><score-part id='P1'><part-name>Kazoo</part-name>"
        b"</score-part></part-list><part id='P1'><measure number='1'><attributes>"
        b"<divisions>1</divisions></attributes><note><rest/><duration>4</duration>"
        b"</note></measure></part></score-partwise>"
    )
    analysis = analyze_part(parse_musicxml(xml).parts[0])

    assert analysis.profile_id == "generic"
    assert analysis.warning is not None
    assert analysis.vector.note_count == 0
    assert analysis.vector.pitch_range_semitones == 0


def test_tier_targets_are_ordered() -> None:
    score = parse_musicxml(
        (ROOT / "evaluation/fixtures/mixed-ensemble-transposition.musicxml").read_bytes()
    )
    targets = analyze_part(score.parts[0]).tier_targets
    assert targets["Foundation"] < targets["Core"] < targets["Challenge"]


@pytest.mark.parametrize(
    ("part_name", "instrument_name", "profile_id", "confidence"),
    [
        ("Violin 1", None, "violin", "normalized-name"),
        ("Vln. II", None, "violin", "normalized-name"),
        ("Violoncelle 1", None, "cello", "normalized-name"),
        ("Streicher", "Violine", "violin", "declared-instrument"),
    ],
)
def test_common_and_localized_instrument_names_match_profiles(
    part_name: str, instrument_name: str | None, profile_id: str, confidence: str
) -> None:
    xml = _single_part_xml(part_name, instrument_name)

    analysis = analyze_part(parse_musicxml(xml).parts[0])

    assert analysis.profile_id == profile_id
    assert analysis.profile_confidence == confidence


def test_conflicting_part_and_declared_instrument_requires_director_override() -> None:
    part = parse_musicxml(_single_part_xml("Violin 1", "Violoncello")).parts[0]

    ambiguous = analyze_part(part)
    overridden = analyze_part(part, profile_override="violin")

    assert ambiguous.profile_id == "generic"
    assert ambiguous.profile_confidence == "ambiguous"
    assert ambiguous.warning == "Instrument metadata conflicts; choose an instrument profile."
    assert overridden.profile_id == "violin"
    assert overridden.profile_confidence == "director-override"


def test_homonymous_alto_name_does_not_match_viola() -> None:
    analysis = analyze_part(parse_musicxml(_single_part_xml("Alto", "Alto Saxophone")).parts[0])

    assert analysis.profile_id == "generic"
    assert analysis.profile_confidence == "unmatched"


def test_invalid_profile_documents_are_rejected() -> None:
    with pytest.raises(ValueError, match="written_range"):
        parse_instrument_profiles(
            {
                "version": 1,
                "profiles": {
                    "violin": {"names": []},
                    "generic": {"names": [], "written_range": [36, 96]},
                },
            }
        )


def _single_part_xml(part_name: str, instrument_name: str | None) -> bytes:
    declared = (
        f"<score-instrument id='P1-I1'><instrument-name>{instrument_name}</instrument-name>"
        "</score-instrument>"
        if instrument_name
        else ""
    )
    return (
        "<score-partwise><part-list><score-part id='P1'><part-name>"
        f"{part_name}</part-name>{declared}</score-part></part-list><part id='P1'>"
        "<measure number='1'><attributes><divisions>1</divisions></attributes>"
        "<note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration>"
        "</note></measure></part></score-partwise>"
    ).encode()
