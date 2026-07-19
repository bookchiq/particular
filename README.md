# Particular

Adaptive arrangements for mixed-ability ensembles. Particular will turn an authorized MusicXML ensemble score into coordinated Foundation, Core, and Challenge parts that remain musically compatible.

The project is at the foundation stage. The [MVP plan](docs/plans/2026-07-18-001-feat-particular-mvp-plan.md) defines the product contract and implementation sequence.

## Repository layout

- `apps/web`: director-facing TypeScript application
- `packages/contracts`: generated and hand-authored cross-service schemas
- `packages/api-client`: generated TypeScript API client
- `services/arranger`: Python musical-domain engine and service
- `evaluation`: authorized corpus metadata, fixtures, rubrics, and results
- `infrastructure`: deployment and isolated-worker assets
- `docs`: product decisions, architecture records, and plans

Musical decisions belong in `services/arranger`; the web application orchestrates workflows and presents results. See [ADR 0001](docs/architecture/0001-system-boundaries.md) and [CONCEPTS.md](CONCEPTS.md).

## Prerequisites

- Node.js 24 LTS or newer
- pnpm 10 or newer (enable through Corepack where available)
- Python 3.12 or newer
- uv 0.10.2

## Setup

```sh
pnpm install
uv sync --frozen --extra dev
```

## Validation

The routine fast gate is:

```sh
pnpm check
uv run ruff format --check .
uv run ruff check .
uv run mypy services evaluation
uv run pytest
```

`pnpm check` runs formatting, linting, TypeScript checking, and workspace tests. The Python commands are intentionally separate so failures remain legible. Run `pnpm check:evaluation` for the separate licensed-corpus integrity gate.

## Deterministic demo CLI

Run the hackathon pipeline from the repository environment:

```sh
uv run python -m particular.cli preflight evaluation/fixtures/string-orchestra-second-violin.musicxml
uv run python -m particular.cli analyze evaluation/fixtures/string-orchestra-second-violin.musicxml
uv run python -m particular.cli generate evaluation/fixtures/string-orchestra-second-violin.musicxml demo-output
```

`generate` accepts `.musicxml`, `.xml`, and safely bounded `.mxl` inputs. The output directory must not already exist. Particular publishes the normalized original, all three deterministic tiers, an analysis report, and an auditable manifest together; invalid input does not leave a partial output directory. This baseline makes no remote AI requests.

## Local browser demo

Start the hackathon interface:

```sh
uv run python -m particular.demo
```

Open `http://127.0.0.1:8765`, attest that you are authorized to adapt the score, and upload MusicXML. The interface shows instrument-aware difficulty features and the accepted or rejected change ledger for each tier, then offers the normalized source, generated variants, analysis, and manifest for download.

The demo binds to loopback only, stores each job in private temporary storage for the server's lifetime, and makes no remote AI requests. Generated parts require director review before rehearsal or distribution.

## Contributing

Read [AGENTS.md](AGENTS.md) before changing the repository. Work on a feature branch, keep changes scoped, use conventional commits, and update architecture or product documentation when a cross-cutting decision changes. Generated contracts must be reproducible; do not edit generated clients by hand.

Only public-domain, original, or explicitly authorized score material may enter the project. Do not commit private scores, personal research data, credentials, or generated user artifacts. See [rights and privacy](docs/product/rights-and-privacy.md).
