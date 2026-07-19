# Arrangement review rubric

Use this rubric for a generated tier, not for the immutable Original score. Reviewers should assess the written part and its ensemble context. A structurally invalid generation is rejected before human review.

## Rating scale

All ratings use the same five-point scale: **1 unacceptable**, **2 major revision**, **3 usable with revision**, **4 rehearsal-ready with minor edits**, and **5 rehearsal-ready as written**.

- **Playability:** The passage fits the target tier's range, rhythm, technique, endurance, and reading demands.
- **Fidelity:** The result retains the source's recognizable contour, cadence points, character, and formal function.
- **Meaningfulness:** The musician still has a musically consequential line rather than filler or excessive rests.
- **Notation quality:** The written result is unambiguous, conventionally spelled, legible, and free of avoidable clutter.
- **Rehearsal usefulness:** The part supports ensemble alignment and can be taught efficiently in rehearsal.

## Review levels

Complete `score_review` for the arrangement as a whole. Add `passage_reviews` for every passage that explains a score-level weakness or demonstrates an important success. Identify passages with part ID and inclusive measure numbers; do not include musician names or private score content in notes.

Record the evaluator's professional role, the engine version, fixture ID, and tier. Estimate `required_edit_minutes` as hands-on notation work after review. Set `rehearsal_ready` only when no hard musical issue remains. Consent must be confirmed before a review enters the evaluation dataset.

## Decision guidance

- Reject any output with broken duration, alignment, range, parseability, transposition, or protected-role coverage regardless of average rating.
- Treat any rating below 3 as a blocking human-usefulness defect.
- Use ratings as ordinal evidence; do not average away a blocking passage.
- Preserve disagreement between qualified reviewers. Record separate reviews instead of reconciling scores in place.

Review records must conform to [`review.schema.json`](review.schema.json). Free-text notes explain ratings but must not contain personal information or material copied from restricted scores.
