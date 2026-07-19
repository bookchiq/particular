# ADR 0001: Keep musical logic inside the arranger service

- Status: Accepted
- Date: 2026-07-18

## Context

Particular needs a director-facing web workflow, deterministic musical analysis and generation, asynchronous conversion, and cross-language contracts. Musical rules duplicated between the browser, API, and workers would drift and undermine reproducibility.

## Decision

The Python arranger package is the sole authority for score normalization, instrument profiles, difficulty analysis, musical roles, transformation operators, candidate selection, validation, and MusicXML export semantics.

The TypeScript web application owns authentication integration, authorization checks, uploads, workflow orchestration, review presentation, and downloads. It may display engine explanations but must not reproduce or override musical decisions.

Long-running arrangement and engraving work executes asynchronously. The arrangement worker calls the engine package. An isolated rendering worker converts approved artifacts for preview, PDF, and rehearsal playback; it does not alter the canonical score.

The service boundary is described by a versioned OpenAPI schema. Shared schemas live in `packages/contracts`; `packages/api-client` is generated from them and is never edited manually. Source and generated scores use immutable object keys, while relational metadata records ownership and lifecycle.

## Consequences

- The engine can be developed and evaluated through a CLI before the web application exists.
- Deterministic validation has one implementation and remains available without AI.
- Cross-language changes require schema regeneration and compatibility checks.
- Browser-only musical experiments must move into the engine before becoming product behavior.
- Rendering failures can block PDF output without corrupting canonical MusicXML.

Cross-cutting changes to these boundaries require a superseding ADR.
