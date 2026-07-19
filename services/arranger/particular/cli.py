"""Structured deterministic command-line interface for Particular."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from particular.application import analyze_score, generate_to_directory, load_score
from particular.preflight import summarize_preflight


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="particular")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "analyze"):
        command = commands.add_parser(name)
        command.add_argument("source", type=Path)
    generate = commands.add_parser("generate")
    generate.add_argument("source", type=Path)
    generate.add_argument("output", type=Path)
    return parser


def _preflight(source: Path) -> dict[str, Any]:
    score, _ = load_score(source)
    return asdict(summarize_preflight(score))


def main(argv: Sequence[str] | None = None) -> int:
    """Run a command, returning a process status and emitting one JSON document."""

    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "preflight":
            result = _preflight(arguments.source)
        elif arguments.command == "analyze":
            score, _ = load_score(arguments.source)
            result = analyze_score(score)
        else:
            manifest = generate_to_directory(arguments.source, arguments.output)
            result = {
                "ok": True,
                "output": str(arguments.output),
                "source_sha256": manifest["source_sha256"],
            }
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError) as error:
        payload = {
            "ok": False,
            "error": {"type": type(error).__name__, "message": str(error)},
        }
        print(json.dumps(payload, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
