# Pilot review documents

Each real evaluation of a generated arrangement goes here as one JSON file
conforming to [`../../rubrics/review.schema.json`](../../rubrics/review.schema.json).
The usefulness gate (`python -m evaluation.scripts.validate_corpus --mode usefulness`)
validates every document against that schema and reports whether musical
usefulness can yet be claimed.

**Musical usefulness is not established.** A pilot score's usefulness may only be
claimed once at least two qualified reviewers (director, teacher, arranger, or
specialist) rate it, each at or above "usable with minor edits," with no blocking
disagreement between them. This directory currently holds no reviews, so the gate
reports `usefulness_established: false` — by design. Populating it with genuine
reviewer evidence is the work tracked in issue #1 (validate the workflow with real
orchestra directors); synthetic reviews must not be committed here.
