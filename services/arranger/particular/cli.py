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
        if name == "analyze":
            command.add_argument("--instrument-profile", action="append", default=[])
    generate = commands.add_parser("generate")
    generate.add_argument("source", type=Path)
    generate.add_argument("output", type=Path)
    generate.add_argument("--instrument-profile", action="append", default=[])
    generate.add_argument(
        "--attest",
        action="store_true",
        help="record that you are authorized to arrange this score",
    )
    return parser


def _preflight(source: Path) -> dict[str, Any]:
    score, _ = load_score(source)
    return asdict(summarize_preflight(score))


def _profile_overrides(values: Sequence[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for value in values:
        part_id, separator, profile_id = value.partition("=")
        if not separator or not part_id or not profile_id or part_id in overrides:
            raise ValueError("instrument profiles must use unique PART_ID=PROFILE_ID values")
        overrides[part_id] = profile_id
    return overrides


def main(argv: Sequence[str] | None = None) -> int:
    """Run a command, returning a process status and emitting one JSON document."""

    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "preflight":
            data = _preflight(arguments.source)
        elif arguments.command == "analyze":
            score, _ = load_score(arguments.source)
            data = analyze_score(score, _profile_overrides(arguments.instrument_profile))
        else:
            manifest = generate_to_directory(
                arguments.source,
                arguments.output,
                _profile_overrides(arguments.instrument_profile),
                attested=arguments.attest,
            )
            data = {
                "output": str(arguments.output),
                "source_sha256": manifest["source_sha256"],
            }
        result = {"ok": True, "command": arguments.command, "data": data}
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
