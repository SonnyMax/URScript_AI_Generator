"""Public `validate()` entrypoint (Stage 0 stub).

Real lexing, parsing, and semantic checks arrive in later stages; for now
every source is reported valid so the package skeleton, CLI, and result
envelope can be exercised end to end.
"""
from __future__ import annotations

from urscript_app.validator_new.result import ValidationResult


def validate(source: str) -> ValidationResult:
    """Validate URScript source and return a structured verdict.

    Stage 0: always returns a valid, empty result regardless of `source`.
    """
    del source  # unused until the lexer/parser stages land
    return ValidationResult(valid=True, errors=[], warnings=[])
