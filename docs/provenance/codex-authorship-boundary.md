# Codex authorship boundary

- Status: Active provenance record
- Date established: 2026-07-20
- Purpose: Draw a clear, verifiable line between work produced by OpenAI Codex
  and work produced afterward, so the project remains honest about authorship
  for hackathon judging and for anyone who evaluates or contributes to it later.

## Why this document exists

Particular was built during a hackathon whose rules do **not** require that all
work be done by Codex, but **do** require that we be precise about what was and
was not. This document is that record. It marks the exact commit where Codex
stopped and states, as accurately as the git history, GitHub issues, and the
Codex session transcripts allow, what Codex authored, why it made the choices it
did, and what it deliberately left undone.

Everything up to and including the boundary commit below is Codex-authored.
Everything after it — including this document — is later work by Sarah Lewis
with Claude (Anthropic), and must be attributed that way.

## The boundary

| Item                       | Value                                                                                    |
| -------------------------- | ---------------------------------------------------------------------------------------- |
| Boundary commit            | `4fd0e5a8d03e8bdad9ad2cd39b3b6634b5595f1c`                                               |
| Commit subject             | `wip: when codex ran out of credits... again`                                            |
| Committed                  | 2026-07-20 11:47:39 -0700                                                                |
| Branch                     | `fix/sustained-role-analysis` (pushed to `origin`; local and remote identical)           |
| Last _complete_ Codex unit | Issue #8 → PR #33, commit `3e051ac4f5783207431ca8665be75b671034f5b5` (merged 2026-07-20) |

Everything reachable from `4fd0e5a` is Codex. The first non-Codex change is
whatever is committed on top of it.

### Who and what produced the Codex work

- **Author:** OpenAI Codex CLI (GPT-5.6), driven interactively by Sarah Lewis.
- **Git identity:** All commits are attributed to "Sarah Lewis" because Codex
  commits under the machine's git identity. **Git authorship therefore does not
  distinguish Codex from human work** — this document and the boundary commit do.
- **GitHub issues:** All 31 issues (#1, #3–#31) were authored by Codex through
  the `bookchiq` account.
- **A note on tooling honesty:** During its own review passes, Codex invoked
  Claude (Anthropic, via the Claude CLI) as an independent adversarial reviewer
  of its diffs. That cross-check caught real defects (an encoding-bypass, a
  tied-rest bug, an unsafe `alto→viola` instrument alias). This was Codex-
  initiated review of Codex-authored code, so it counts as part of the "Codex"
  work — but it is recorded here so the collaboration is not hidden.

### Source traces

The Codex session transcripts backing this record are the local rollout files:

- **Origin session** `019f77be-8a78-7d32-9caa-234fc8ad43ed` (2026-07-18 17:20 →
  2026-07-19 ~17:00): inception through PR #32. This one long session contains
  the entire build from first idea to differentiated tiers.
- **Final session** `019f80a4-3c40-7670-a6f5-850dd545ab20` (2026-07-20 10:47):
  completed issue #8, then began issue #10, and ended when Codex credits ran out.

(Other same-day "I overheard a conversation…" transcripts are earlier replay
snapshots of the origin session and add nothing past it.)

## What Codex built

Delivered and merged (PRs #2, #32, #33; issues #3–#8 closed):

1. **Market research & framing** — surveyed existing tools and academic work and
   concluded the coordinated mixed-ability ensemble-arrangement niche was open.
2. **Project foundation** — the "Particular" name, the public `bookchiq/particular`
   repo, and the TypeScript/Python monorepo skeleton with reproducible,
   lockfile-honoring CI (commit `7a815ff`).
3. **The MVP plan** — `docs/plans/2026-07-18-001-feat-particular-mvp-plan.md`:
   product contract, deterministic-engine-with-optional-AI architecture, 12
   engineering units plus an upfront director-validation unit, evaluation
   strategy, and security/copyright boundaries.
4. **Product & architecture docs** — ADR 0001 (system boundaries), the difficulty
   model, rights & privacy, the director interview guide, research-consent and
   design-partner criteria, and the corpus-intake process.
5. **Evaluation corpus** — two original CC0 MusicXML fixtures with provenance and
   checksums (commit `525fd26`).
6. **Safe MusicXML intake & round-trip** — a deliberately narrow parser with
   hardened `.mxl` handling, typed failures, transposing-instrument pitch
   semantics, coverage warnings for unsupported notation, and deterministic
   export (commit `8cdb610`).
7. **Explainable difficulty & role analysis** — per-measure, instrument-specific
   difficulty features and conservative protection of melody, bass, harmony,
   rhythm, and exposed entrances (commit `0e20db6`).
8. **Deterministic generator** — three auditable operators (rhythm-subdivision
   reduction, octave correction for out-of-range notes, accompaniment thinning)
   producing coordinated Foundation / Core / Challenge tiers under hard
   synchronization and role-preservation checks (commit `ae125e5`).
9. **CLI pipeline** — one command emits the normalized source, all three tiers,
   an analysis report, and a byte-reproducible audit manifest atomically
   (commit `373591d`).
10. **Local browser demo** — loopback upload with a rights-attestation gate,
    tier selection, a measure-level change ledger, difficulty display, and
    MusicXML download, with bounded temporary storage (commit `2aa003d`).
11. **Post-MVP audit → backlog → hardening** — filed 29 improvement issues, then
    delivered: fail-closed semantic preservation, independent-voice export, safe
    rhythm merging, stronger validators (issues #3–#6); genuinely differentiated
    tiers (issue #7 → PR #32); and safe, typed, confidence-tracked instrument-
    profile matching with CLI/UI overrides (issue #8 → PR #33).

## Key decisions Codex made, and why

- **Deterministic engine at the center; AI may only propose or rank candidates,
  never bypass validation.** Chosen for reproducibility and musical safety —
  re-runs are byte-identical and every change is auditable.
- **MusicXML is canonical; MIDI is a derived playback format only.** MusicXML
  encodes what musicians read; MIDI encodes what a machine plays.
- **`music21` for parsing, MuseScore for print rendering**, with MusicXML
  normalized into an internal model rather than used directly as the datastore
  (interchange is "good but not lossless").
- **Generic coordinated tiers first; per-musician personalization deferred** to
  prove arranging value before adding roster/permission complexity.
- **Rights boundary: public-domain, original, or explicitly authorized scores
  only**, enforced by an upload attestation, because simplifying a copyrighted
  score creates a derivative work.
- **Fail closed on notation it cannot preserve** — unsupported constructs become
  explicit preflight blockers rather than silent data loss.
- **Protect musical structure across the whole score, not per staff**, because
  independent per-part simplification can hollow out the ensemble.

## What Codex explicitly did NOT do (the important part)

**Deferred by MVP scope (stated in the plan, confirmed with Sarah):**

- **No musician accounts, rosters, per-player assignments, self-service
  difficulty controls, or per-musician unique URLs/permissions.** The originally
  envisioned personalization system is entirely unbuilt.
- **No player-specific parts** — only generic coordinated tiers.
- **No director authentication.** Auth boundaries were designed in the plan only;
  the demo is a local loopback tool with no accounts.
- **No PDF export and no playback/auditioning.** MuseScore PDF rendering and MIDI
  preview were planned but not built; only MusicXML export exists.

**Product-validation gate never satisfied — read before any real pilot:**

- **Issue #1 (validate the workflow with real orchestra directors) stands at
  0 of 5 interviews and 0 of 3 design partners.** The four director personas in
  `docs/product/problem-validation.md` are **synthetic secondary research**,
  deliberately labeled as such — they are not real director validation.
- **Musical quality has never been judged by a human.** The passing test suite
  confirms technical correctness (duration, alignment, ranges, protected roles),
  **not** whether the arrangements are musically satisfying. That still requires
  a director or instrumentalist.

**Engine / parser limitations Codex flagged:**

- **Tier differentiation was hollow until the very end.** Before issue #7, tiers
  were displayed but did not drive generation (a demo produced "Foundation: 15
  changes, Core: 0, Challenge: 0"). PR #32 fixed this, so meaningfully distinct
  tiers are recent and thinly exercised.
- **The parser is intentionally narrow** and rejects exotic notation (e.g. a CC0
  Saint-Georges quartet hit an unsupported duration construct and was rejected).
- **Mid-score transposition is unhandled** (tracked as issue #11).
- **The evaluation corpus is two synthetic fixtures** — small, and not real
  repertoire.

**Testing / engineering residuals:**

- **The frontend has no DOM-level tests.** The web test script runs with
  `--passWithNoTests`; browser behavior is covered only by manual checks and
  Python HTTP tests. This is tracked as issue #26.
- **The generation manifest has no independent schema version.** `policy_version`
  covers selection semantics, but non-additive manifest changes will need a
  separate compatibility mechanism, and no snapshot test pins the full manifest
  contract consumed outside Python (issues #27, #29).

**The backlog is the catalog of not-done work.** Codex filed 29 issues and built
none of #9–#31. Its recommended execution order, left for whoever continues:
musical correctness → demo credibility (#7, #8, #12, #14, #31) → director value
(#9, #10, #15, #16, #21, #30) → trust & evaluation (#17, #22–#27) → engineering
hardening (#11, #13, #18–#20, #28, #29). Issue #1 remains blocked on real
director validation.

## Exact state at the seam

The final Codex session finished and merged **issue #8** (PR #33), then started
**issue #10 — "Analyze sustained ensemble roles using normalized musical time"** —
on `fix/sustained-role-analysis`, and ended mid-task when credits ran out.

- **Diagnosis it reached:** role classification only compared notes attacking at
  the same instant and used raw division counts, so a sustained bass note
  "disappeared" under a later entrance in another part.
- **Fix in progress (captured in `4fd0e5a`):** switch to active-**span**
  classification over exact-fraction musical time, so a long note still counts as
  sounding under a later onset; plus a reordering of `validate_family` so the
  instrument-range check runs before the protected-role continuity check (an
  out-of-range test note was being protected and masking the range failure).
- **This is where the transcript ends.** Issue #10 is **not** finished and **no
  PR was opened** for it. The branch is a coherent, green increment, not a
  completed feature.

## Verification snapshot at the boundary

Captured on the boundary commit `4fd0e5a`:

- `uv run pytest services/arranger` — **81 passed**.
- `uv run ruff check services evaluation` — clean.
- `uv run ruff format --check services evaluation` — clean.
- `uv run mypy services evaluation` — no issues in 40 files.

So Codex left the branch **green despite being mid-feature**: the WIP commit is a
passing increment toward issue #10, not a broken checkpoint.

## After this line

All work committed on top of `4fd0e5a` is authored by **Sarah Lewis with Claude
(Anthropic)**, not Codex. Contributors and evaluators should treat the boundary
commit as the authorship dividing line and attribute accordingly. When a change
completes or supersedes a Codex-filed issue, keep this record accurate rather
than rewriting it — the history is the point.
