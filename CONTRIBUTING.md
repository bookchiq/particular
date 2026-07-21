# Contributing to Particular

Thanks for your interest — whether you're a developer, a musician, or a director
who tried the demo and has thoughts, you're welcome here.

## Ways to help

- **Try it and tell us what confused you.** First-encounter friction is genuinely
  useful; open an issue describing what you expected vs. what happened.
- **Report a bug** or **suggest a feature** using the issue templates.
- **Improve the arranging engine, the docs, or the demo** with a pull request.
- **Musicians and directors:** feedback on whether a generated Supported or
  Essential part is actually rehearsal-usable is the feedback we most need — no
  code required. See [`evaluation/rubrics/arrangement-review.md`](evaluation/rubrics/arrangement-review.md).

## Getting set up

You'll need Node.js 24+, pnpm 10+, Python 3.12+, and uv. Then:

```sh
pnpm install
uv sync --frozen --extra dev
```

Run the demo with `uv run python -m particular.demo` and open
`http://127.0.0.1:8765`. The [README](README.md) has the full CLI and demo guide.

## Making a change

1. Work on a feature branch (never commit directly to `main`).
2. Read [`AGENTS.md`](AGENTS.md) — it holds the product invariants and the
   detailed development rules (musical logic stays in `services/arranger`,
   deterministic validation owns acceptance, conventional commits, etc.).
3. Add focused tests for behaviour changes.
4. Run the fast gate before opening a PR:

   ```sh
   pnpm check
   uv run ruff format --check .
   uv run ruff check .
   uv run mypy services evaluation
   uv run pytest
   ```

5. Open a pull request. The PR template will prompt you for what matters.

## A note on scores

Only **public-domain, original, or explicitly authorized** score material may
enter this repository. Please don't commit private scores, personal data,
credentials, or generated user artifacts. See
[rights and privacy](docs/product/rights-and-privacy.md).

## Questions

Open a [GitHub issue](https://github.com/bookchiq/particular/issues) — questions
are welcome and there's a "question" label for them. Please follow our
[Code of Conduct](CODE_OF_CONDUCT.md).

## Licensing

The code is under the [MIT License](LICENSE). The evaluation corpus is CC0. By
contributing, you agree your contributions are licensed the same way.
