from __future__ import annotations

from pathlib import Path

from particular.analysis.roles import analyze_roles
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
