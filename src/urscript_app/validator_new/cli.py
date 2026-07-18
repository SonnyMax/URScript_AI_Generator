"""Command-line entrypoint — the seed of the dataset-generation oracle.

Usage:
    python -m urscript_app.validator_new PATH        # validate a file
    python -m urscript_app.validator_new -           # read source from stdin

Prints the `ValidationResult` envelope as JSON to stdout.

Exit codes:
    0  valid (warnings alone do not fail the run)
    1  invalid (any error; or any warning with --warnings-as-errors)
    2  input could not be read (missing file, I/O error)

The JSON output always reflects the true validation result; the
`--warnings-as-errors` flag only affects the exit code.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from urscript_app.validator_new.result import ValidationResult
from urscript_app.validator_new.validate import validate

EXIT_VALID = 0
EXIT_INVALID = 1
EXIT_IO_ERROR = 2

STDIN_SENTINEL = "-"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m urscript_app.validator_new",
        description="Validate a URScript file and print a JSON verdict.",
    )
    parser.add_argument(
        "path",
        help=f"Path to a URScript file, or '{STDIN_SENTINEL}' to read from stdin.",
    )
    parser.add_argument(
        "--warnings-as-errors",
        action="store_true",
        help="Exit non-zero when warnings are present, not only on errors.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress JSON output; communicate only via the exit code.",
    )
    return parser


def resolve_exit_code(result: ValidationResult, warnings_as_errors: bool) -> int:
    """Map a validation result to the CLI exit code."""
    if result.errors:
        return EXIT_INVALID
    if warnings_as_errors and result.warnings:
        return EXIT_INVALID
    return EXIT_VALID


def _read_source(path: str) -> str:
    if path == STDIN_SENTINEL:
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """CLI body; returns the process exit code (kept testable in-process)."""
    args = build_arg_parser().parse_args(argv)
    try:
        source = _read_source(args.path)
    except OSError as exc:
        print(f"error: cannot read {args.path!r}: {exc}", file=sys.stderr)
        return EXIT_IO_ERROR

    result = validate(source)
    if not args.quiet:
        print(json.dumps(result.to_dict(), indent=2))
    return resolve_exit_code(result, warnings_as_errors=args.warnings_as_errors)
