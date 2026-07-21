# ADR 0002: Particular arranges by reduction only; Original is the top tier

- Status: Accepted
- Date: 2026-07-20

## Context

Particular presented three generated tiers — Foundation, Core, and Challenge — with the unchanged score kept alongside as a comparison state ("Original"). "Challenge" implied an arrangement *harder* than the source.

A first-encounter review of the running demo surfaced that both bundled sample scores produced three tiers identical to the source (issue #81). Inspecting the engine confirmed the cause is structural, not a sample problem:

- Every transformation operator in `services/arranger/particular/generation/operators.py` is reductive or safety-only (`rhythm-merge` and `repetition-thin` simplify; `octave-range` only pulls out-of-range notes into range). There is no difficulty-*increasing* operator.
- The simplifying operators do not list "Challenge" in their eligible tiers, and `selector.py` hardcodes that Challenge "retains source detail unless an exceptional range correction is required." **Challenge can never differ from the source by design.**
- Making music genuinely harder means *adding* material (ornaments, divisi, figuration). That is composition, not the faithful, auditable, deterministic reduction Particular exists to do — and it is where deterministic scripting is weakest and musical risk is highest.

The three tier names therefore encoded a direction (harder-than-original) the engine does not and should not implement.

## Decision

Particular arranges **by reduction only.** The engine transforms a score by simplifying it or by making instrument-safety corrections; it never adds musical material to increase difficulty.

The as-written score is the **top rung of the ladder**, not a side comparison. The tiers, from hardest to most accessible, are:

| Tier | Meaning |
| --- | --- |
| **Original** | The score as written — the composer's full text. The hardest tier. |
| **Supported** | Lightly eased — only the busiest passages are simplified. |
| **Essential** | Reduced to the essentials — the most accessible playable version. |

"Challenge" is **retired**, not renamed; there is no tier above Original. The former "Foundation" and "Core" are superseded by "Essential" and "Supported" respectively.

The tier policy thresholds (`profiles/tiers.json`) are reinterpreted: they no longer express difficulty, they express **how aggressively a tier simplifies** (Essential simplifies most, Supported least, Original not at all).

Constrained AI, if ever introduced, may only *propose* reduction candidates that deterministic validators still accept or reject (per ADR 0001). It is never used to add material.

## Consequences

- `CONCEPTS.md` must promote Original from "comparison state" to a first-class top tier, and replace the Foundation/Core/Challenge tier-profile definition with Original/Supported/Essential.
- The tier names change across the engine, contracts, API client, web UI, fixtures, manifests, and docs. Manifests and any persisted tier identifiers need a compatibility path.
- The relabel makes the promise honest but not yet *true*: with only three narrow operators, even "Essential" barely eases a real score. A broader set of reductive operators (thin fast runs, fold large leaps, de-syncopate, simplify accidentals, lengthen shortest durations) is required so the tiers visibly differ on real inputs. Tracked as a follow-up issue.
- A demonstrative sample score (issue #31) remains needed so the reduction is visible in the demo.
- The determinism and reproducibility guarantees of ADR 0001 are preserved; reduction-only keeps every change auditable and safe.

Cross-cutting changes to this direction require a superseding ADR.
