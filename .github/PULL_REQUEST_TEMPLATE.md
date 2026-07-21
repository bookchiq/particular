<!-- Thanks for contributing! Keep changes scoped and use a conventional-commit
title (feat:, fix:, docs:, chore:, refactor:). -->

## What & why

<!-- What does this change, and why? Link any issues it closes (e.g. "Closes #12"). -->

## How it was tested

- [ ] `pnpm check`
- [ ] `uv run ruff check .` and `uv run mypy services evaluation`
- [ ] `uv run pytest`
- [ ] Checked in the browser demo (if it touches the UI)

## Checklist

- [ ] Follows the invariants in [AGENTS.md](../AGENTS.md) (musical logic stays in
      `services/arranger`; deterministic validation owns acceptance)
- [ ] Added or updated focused tests for behaviour changes
- [ ] No private or copyrighted scores, personal data, or credentials committed
- [ ] Updated docs/ADRs if a cross-cutting decision changed
