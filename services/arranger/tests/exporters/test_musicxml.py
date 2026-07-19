from __future__ import annotations

from pathlib import Path

from particular.exporters.musicxml import export_musicxml, semantic_fingerprint
from particular.importers.musicxml import parse_musicxml

ROOT = Path(__file__).parents[4]


def test_two_round_trips_are_deterministic_for_supported_fixtures() -> None:
    fixtures = ROOT / "evaluation/fixtures"
    for path in sorted(fixtures.glob("*.musicxml")):
        first_score = parse_musicxml(path.read_bytes())
        first_xml = export_musicxml(first_score)
        second_score = parse_musicxml(first_xml)
        second_xml = export_musicxml(second_score)

        assert semantic_fingerprint(first_score) == semantic_fingerprint(second_score)
        assert first_xml == second_xml
