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

`pnpm check` runs formatting, linting, TypeScript checking, and workspace tests. The Python commands are intentionally separate so failures remain legible. The CI `evaluation` job is the separate corpus and musical-quality gate; it is currently a documented placeholder until U2 adds its schema and verifier.

## Contributing

Read [AGENTS.md](AGENTS.md) before changing the repository. Work on a feature branch, keep changes scoped, use conventional commits, and update architecture or product documentation when a cross-cutting decision changes. Generated contracts must be reproducible; do not edit generated clients by hand.

Only public-domain, original, or explicitly authorized score material may enter the project. Do not commit private scores, personal research data, credentials, or generated user artifacts. See [rights and privacy](docs/product/rights-and-privacy.md).
