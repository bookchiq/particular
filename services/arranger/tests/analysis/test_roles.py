from __future__ import annotations

from pathlib import Path

from particular.analysis.roles import analyze_roles, protected_locators
from particular.importers.musicxml import parse_musicxml

ROOT = Path(__file__).parents[4]


def test_mixed_fixture_labels_protected_roles_with_evidence() -> None:
    score = parse_musicxml(
        (ROOT / "evaluation/fixtures/mixed-ensemble-transposition.musicxml").read_bytes()
    )
    labels = analyze_roles(score)

    flute = [label for label in labels if label.locator.part_id == "P1"]
    cello = [label for label in labels if label.locator.part_id == "P4"]
    assert any(label.role == "melody" and label.protected for label in flute)
    assert any(label.role == "bass" and label.protected for label in cello)
    assert {"harmonic_anchor", "rhythmic_drive", "exposed_entrance"}.issubset(
        {label.role for label in labels}
    )
    assert all(label.evidence and 0 <= label.confidence <= 1 for label in labels)
    assert all(label.sounding_pitch is not None for label in labels)


def test_ambiguous_unison_texture_is_conservatively_protected() -> None:
    xml = (
        b"<score-partwise><part-list><score-part id='P1'><part-name>Flute</part-name>"
        b"</score-part><score-part id='P2'><part-name>Violin</part-name></score-part>"
        b"</part-list><part id='P1'><measure number='1'><attributes><divisions>1"
        b"</divisions></attributes><note><pitch><step>C</step><octave>5</octave>"
        b"</pitch><duration>1</duration></note></measure></part><part id='P2'>"
        b"<measure number='1'><attributes><divisions>1</divisions></attributes><note>"
        b"<pitch><step>C</step><octave>5</octave></pitch><duration>1</duration>"
        b"</note></measure></part></score-partwise>"
    )
    labels = analyze_roles(parse_musicxml(xml))
    assert labels
    assert all(label.protected for label in labels)
    assert any("ambiguous" in item for label in labels for item in label.evidence)


def test_aligns_parts_with_different_division_units() -> None:
    xml = b"""<score-partwise><part-list>
    <score-part id='P1'><part-name>Flute</part-name></score-part>
    <score-part id='P2'><part-name>Cello</part-name></score-part></part-list>
    <part id='P1'><measure number='1'><attributes><divisions>4</divisions></attributes>
    <forward><duration>4</duration></forward><note><pitch><step>C</step><octave>5</octave></pitch><duration>4</duration></note></measure></part>
    <part id='P2'><measure number='1'><attributes><divisions>8</divisions></attributes>
    <forward><duration>8</duration></forward><note><pitch><step>C</step><octave>3</octave></pitch><duration>8</duration></note></measure></part>
    </score-partwise>"""

    labels = analyze_roles(parse_musicxml(xml))
    assert any(label.role == "melody" and label.locator.part_id == "P1" for label in labels)
    assert any(label.role == "bass" and label.locator.part_id == "P2" for label in labels)


def test_protects_sustained_bass_under_a_later_entrance() -> None:
    xml = b"""<score-partwise><part-list>
    <score-part id='P1'><part-name>Flute</part-name></score-part>
    <score-part id='P2'><part-name>Cello</part-name></score-part></part-list>
    <part id='P1'><measure number='1'><attributes><divisions>4</divisions></attributes>
    <forward><duration>4</duration></forward><note><pitch><step>G</step><octave>5</octave></pitch><duration>4</duration></note></measure></part>
    <part id='P2'><measure number='1'><attributes><divisions>8</divisions></attributes>
    <note><pitch><step>C</step><octave>3</octave></pitch><duration>16</duration></note></measure></part>
    </score-partwise>"""

    labels = analyze_roles(parse_musicxml(xml))

    bass = [label for label in labels if label.locator.part_id == "P2" and label.role == "bass"]
    assert bass
    assert any("active sounding span" in item for label in bass for item in label.evidence)


def test_flags_later_exposed_entrance_in_a_sparse_texture() -> None:
    xml = b"""<score-partwise><part-list>
    <score-part id='P1'><part-name>Flute</part-name></score-part>
    <score-part id='P2'><part-name>Cello</part-name></score-part></part-list>
    <part id='P1'>
    <measure number='1'><attributes><divisions>4</divisions>
    <time><beats>4</beats><beat-type>4</beat-type></time></attributes>
    <note><rest/><duration>16</duration></note></measure>
    <measure number='2'><note><pitch><step>G</step><octave>5</octave></pitch>
    <duration>16</duration></note></measure></part>
    <part id='P2'>
    <measure number='1'><attributes><divisions>4</divisions>
    <time><beats>4</beats><beat-type>4</beat-type></time></attributes>
    <note><pitch><step>C</step><octave>3</octave></pitch><duration>16</duration></note></measure>
    <measure number='2'><note><rest/><duration>16</duration></note></measure></part>
    </score-partwise>"""

    labels = analyze_roles(parse_musicxml(xml))

    # The flute enters alone in measure 2 after resting: an exposed re-entry.
    flute_exposed = [
        label
        for label in labels
        if label.role == "exposed_entrance" and label.locator.part_id == "P1"
    ]
    assert flute_exposed
    assert flute_exposed[0].confidence >= 0.8 and flute_exposed[0].protected
    assert any("few parts sound" in item for label in flute_exposed for item in label.evidence)
    # The score opening belongs to the cello, and stays distinct from the re-entry.
    opening = [
        label
        for label in labels
        if label.role == "exposed_entrance"
        and any("score opening" in item for item in label.evidence)
    ]
    assert opening and all(label.locator.part_id == "P2" for label in opening)


def test_entrance_over_a_sustained_part_is_not_exposed() -> None:
    xml = b"""<score-partwise><part-list>
    <score-part id='P1'><part-name>Cello</part-name></score-part>
    <score-part id='P2'><part-name>Flute</part-name></score-part></part-list>
    <part id='P1'><measure number='1'><attributes><divisions>4</divisions>
    <time><beats>4</beats><beat-type>4</beat-type></time></attributes>
    <note><pitch><step>C</step><octave>3</octave></pitch><duration>16</duration></note></measure></part>
    <part id='P2'><measure number='1'><attributes><divisions>4</divisions>
    <time><beats>4</beats><beat-type>4</beat-type></time></attributes>
    <forward><duration>8</duration></forward>
    <note><pitch><step>G</step><octave>5</octave></pitch><duration>8</duration></note></measure></part>
    </score-partwise>"""

    labels = analyze_roles(parse_musicxml(xml))

    # The flute enters mid-measure while the cello still sounds: covered, not exposed.
    flute = [label for label in labels if label.locator.part_id == "P2"]
    assert any(label.role == "melody" for label in flute)
    assert not any(label.role == "exposed_entrance" for label in flute)


def test_pickup_measure_normalizes_time_and_marks_opening_entrance() -> None:
    xml = b"""<score-partwise><part-list>
    <score-part id='P1'><part-name>Trumpet</part-name></score-part>
    <score-part id='P2'><part-name>Tuba</part-name></score-part></part-list>
    <part id='P1'>
    <measure number='0' implicit='yes'><attributes><divisions>4</divisions>
    <time><beats>4</beats><beat-type>4</beat-type></time></attributes>
    <note><pitch><step>G</step><octave>4</octave></pitch><duration>4</duration></note></measure>
    <measure number='1'><note><pitch><step>C</step><octave>5</octave></pitch>
    <duration>16</duration></note></measure></part>
    <part id='P2'>
    <measure number='0' implicit='yes'><attributes><divisions>4</divisions>
    <time><beats>4</beats><beat-type>4</beat-type></time></attributes>
    <note><pitch><step>C</step><octave>3</octave></pitch><duration>4</duration></note></measure>
    <measure number='1'><note><pitch><step>C</step><octave>4</octave></pitch>
    <duration>16</duration></note></measure></part>
    </score-partwise>"""

    labels = analyze_roles(parse_musicxml(xml))

    assert labels and all(0 <= label.confidence <= 1 for label in labels)
    # Only the true score opening (the pickup) is an opening entrance.
    opening = [label for label in labels if label.role == "exposed_entrance"]
    assert opening
    assert all(any("score opening" in item for item in label.evidence) for label in opening)
    assert {label.locator.part_id for label in opening} == {"P1", "P2"}
    # The downbeat follows the pickup with no spurious gap, so both parts stay aligned.
    downbeat = {
        label.locator.part_id
        for label in labels
        if label.role in {"melody", "bass"} and label.locator.measure_number == "1"
    }
    assert downbeat == {"P1", "P2"}


def test_protects_a_pedal_tone_under_staggered_entrances() -> None:
    xml = b"""<score-partwise><part-list>
    <score-part id='P1'><part-name>Contrabass</part-name></score-part>
    <score-part id='P2'><part-name>Viola</part-name></score-part>
    <score-part id='P3'><part-name>Violin</part-name></score-part></part-list>
    <part id='P1'><measure number='1'><attributes><divisions>4</divisions>
    <time><beats>4</beats><beat-type>4</beat-type></time></attributes>
    <note><pitch><step>C</step><octave>2</octave></pitch><duration>16</duration></note></measure></part>
    <part id='P2'><measure number='1'><attributes><divisions>4</divisions>
    <time><beats>4</beats><beat-type>4</beat-type></time></attributes>
    <forward><duration>4</duration></forward>
    <note><pitch><step>E</step><octave>4</octave></pitch><duration>8</duration></note></measure></part>
    <part id='P3'><measure number='1'><attributes><divisions>4</divisions>
    <time><beats>4</beats><beat-type>4</beat-type></time></attributes>
    <forward><duration>8</duration></forward>
    <note><pitch><step>G</step><octave>5</octave></pitch><duration>8</duration></note></measure></part>
    </score-partwise>"""

    score = parse_musicxml(xml)
    labels = analyze_roles(score)

    # The held bass keeps being protected as later parts enter above it.
    pedal = [label for label in labels if label.locator.part_id == "P1" and label.role == "bass"]
    assert pedal
    assert any(
        "active sounding span under a later ensemble entrance" in item
        for label in pedal
        for item in label.evidence
    )
    assert any(label.locator.part_id == "P1" for label in labels) and any(
        locator.part_id == "P1" for locator in protected_locators(score)
    )
