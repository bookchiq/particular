"""Hard structural, range, role, and tier-family validators."""

from __future__ import annotations

from particular.analysis.difficulty import instrument_range
from particular.analysis.roles import protected_locators
from particular.domain.score import Score
from particular.generation.selector import ArrangementFamily


class ArrangementValidationError(ValueError):
    """A generated family violates a non-negotiable musical invariant."""


def validate_family(source: Score, family: ArrangementFamily) -> None:
    source_shape = [
        (part.id, [(measure.number, measure.duration) for measure in part.measures])
        for part in source.parts
    ]
    protected = protected_locators(source)
    counts: list[int] = []
    for tier in family.tiers:
        shape = [
            (part.id, [(measure.number, measure.duration) for measure in part.measures])
            for part in tier.score.parts
        ]
        if shape != source_shape:
            raise ArrangementValidationError(f"{tier.name}: structure or duration changed")
        locators = {
            event.locator
            for part in tier.score.parts
            for measure in part.measures
            for event in measure.events
        }
        if not protected.issubset(locators):
            raise ArrangementValidationError(f"{tier.name}: protected ensemble role was removed")
        count = 0
        for part in tier.score.parts:
            minimum, maximum = instrument_range(part)
            for measure in part.measures:
                for event in measure.events:
                    if event.kind == "note" and event.written_pitch is not None:
                        count += 1
                        if not minimum <= event.written_pitch <= maximum:
                            raise ArrangementValidationError(
                                f"{tier.name}: {part.id} has an out-of-range note"
                            )
        counts.append(count)
    if counts != sorted(counts):
        raise ArrangementValidationError("tier note counts are not monotonic")
