# Repository instructions

These instructions apply throughout the Particular repository.

## Product invariants

- MusicXML is the canonical interchange format; MIDI is a derived playback format.
- Source scores are immutable. Normalized scores and arrangements are traceable derivatives.
- Particular arranges by reduction only (ADR 0002): Original (as written), Supported, and Essential describe relative Particular tiers, not universal grade levels.
- Deterministic validation owns acceptance. Optional AI may propose or rank candidates but cannot bypass constraints.
- Keep musical analysis, transformation, and validation in `services/arranger`, never in the web application.
- Preserve duration, form, alignment, instrument safety, and protected ensemble roles or report an explicit failure.

Use the canonical language in `CONCEPTS.md`. Record cross-unit architectural decisions as ADRs in `docs/architecture`.

## Development

- Work on feature branches, not `main`.
- Use conventional commit prefixes such as `feat:`, `fix:`, `docs:`, and `chore:`.
- Use `pnpm`; do not add npm or Yarn lockfiles.
- Keep Python compatible with the version declared in `pyproject.toml`.
- Run the validation commands in `README.md` for the area changed.
- Add focused tests with behavior changes. Documentation-only scaffolding may use explicit smoke validation instead.
- Never commit copyrighted or private scores without documented authorization, interview recordings, personal contact data, secrets, or user artifacts.

## Contracts

Cross-service API schemas live in `packages/contracts`. Generated clients live in `packages/api-client`, carry a generated-file header, and are regenerated from a versioned schema. Consumers must not duplicate musical-domain rules from the Python engine.
