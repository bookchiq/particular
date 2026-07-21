# Post-boundary work: what was built after Codex

- Status: Active provenance record (companion to the [Codex authorship boundary](codex-authorship-boundary.md))
- Date established: 2026-07-20
- Purpose: Catalog the work done **after** the Codex boundary commit `4fd0e5a`,
  so the hackathon submission is precise about what Codex did and did not build.

Everything below was authored by **Sarah Lewis with Claude (Anthropic, Claude
Opus 4.8)**, not Codex. The [boundary record](codex-authorship-boundary.md) is
the historical account of the Codex work and is deliberately not rewritten; this
document is the running record of what came after it.

## How to verify the line yourself

- The boundary commit is `4fd0e5a` ("wip: when codex ran out of credits...
  again"). Everything reachable from it is Codex.
- Every change in this document is a squash- or merge-committed PR on top of that
  commit: `git log --first-parent 4fd0e5a..main`.
- Git author is "Sarah Lewis" on both sides of the line (Codex commits under the
  machine identity), so **git authorship does not distinguish the two** — the
  boundary commit and these two documents do.

## Finishing what Codex left mid-flight

Codex ran out of credits mid-task on issue #10 ("analyze sustained ensemble roles
over normalized musical time"), leaving a green but unfinished increment.

- **#34 — completed issue #10.** Active-**span** role classification over
  exact-fraction musical time (a sustained bass note still counts as sounding
  under a later onset), plus the `validate_family` reordering Codex had begun.
  This is the first fully non-Codex unit and it closes the exact task the
  transcript ends on.

## Engine correctness & fidelity

- **#38** — measure difficulty is computed from real passage features, not
  placeholder values.
- **#39** — the change manifest surfaces per-change difficulty deltas and the
  musical roles each change preserved.
- **#40** — measure-level transposition changes are preserved end to end
  (Codex-flagged issue #11).
- **#41** — `.mxl` archives resolve their root score through
  `META-INF/container.xml` instead of guessing.
- **#42** — manifests carry a real engine build identity and the complete set of
  reproducibility inputs, with a normalized-schema version distinct from the
  policy version (Codex-flagged issues #27/#29).
- **#45** — large change ledgers stay scannable and bounded (issue #21).

## Trust, safety & operability

- **#43** — generation failures return safe, actionable guidance with a
  diagnostic id, never leaking score content (issue #22).
- **#44** — every CLI outcome is machine-readable (issue #24).
- **#46** — upload and archive limits are calibrated for real ensemble scores
  and surfaced to the browser before upload (issue #14).
- **#47** — a meaningful rights attestation (versioned, basis-typed) is recorded
  in generation metadata (issue #17).
- **#48** — duplicate generations are prevented and stale async responses are
  discarded (an `AbortController` + monotonic request sequencer).
- **#49** — score artifacts get time-based retention and an explicit
  "delete these files" action, enforced by a background sweep (issue #23).

## Evaluation & the honesty gate

- **#53** — a musical-usefulness gate in corpus validation that reports
  `usefulness_established: false` when no human review exists (issue #25). It
  never fabricates director approval; the gate stays honest that **musical
  quality has not been judged by a human**.

## Accessibility, testing & packaging

- **#54** — DOM-level frontend tests, removing the `--passWithNoTests` CI escape
  Codex flagged (issue #26).
- **#55** — complete keyboard and screen-reader behavior for tier review (ARIA
  Tabs pattern, roving tabindex) (issue #18).
- **#56** — browser assets are packaged into the wheel so the installed demo
  runs (issue #28), with a packaging CI job.
- **#50** — CI actions moved off the deprecated Node 20 runtime; `.lattice/`
  ignored.

## The flagship: score-aware review workspace (#15/#16)

Built in five shipped increments, each its own green-CI PR:

1. **#57 — score map.** A per-measure grid per part; changed measures are
   highlighted and selectable to see exactly what happened in each tier.
2. **#58 — per-part export.** Each part downloads as its own MusicXML file.
3. **#59 — measure locks + regeneration.** A director locks the measures they
   approve and regenerates only the rest; locked measures are folded into the
   reproducibility digest, so the lock is auditable.
4. **#60 — mixed-tier sets.** Each part is assigned its own tier (a Foundation
   cello beside Core violins), composed into one coordinated `custom` set.
   Assignments are recorded but kept out of the reproducibility digest because
   they only select among the already-reproducible tiers.
5. **#61 — engraved notation.** The selected tier renders as real sheet music via
   OpenSheetMusicDisplay. This is **deliberately online-only** (the notation
   library loads from a CDN); the score is still rendered in the browser and
   never uploaded. See [[README]] for the privacy note.

## What is still NOT done (kept honest)

- **Issue #1 — real orchestra-director validation — remains 0 of 5 interviews
  and 0 of 3 design partners.** The director personas are synthetic secondary
  research, still labeled as such. No arrangement has been judged by a human
  musician. This is the single most important unfinished item before any pilot.
- **No PDF export** (needs MuseScore in the toolchain) and **no audio playback**
  (the auditioning half of #16). Only MusicXML export and on-screen engraving
  exist.
- **No musician accounts, rosters, or per-player personalization** — still
  generic coordinated tiers by design.
- The mixed-tier and engraving features are new and **thinly exercised by real
  users**; they are verified by automated tests and browser smoke checks, not by
  a director in a rehearsal.

## Keeping this record accurate

When a change completes or supersedes an issue, update this document rather than
rewriting the boundary record. The point of both files is that the authorship
line stays verifiable long after the hackathon.
