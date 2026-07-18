"""Public `validate()` entrypoint: lex -> parse -> structure -> semantic passes.

Semantic passes (signatures, bounds, symbols, safety) are empty until the
later stages register them in `checks`.
"""
from __future__ import annotations

from urscript_app.validator_new.checks import run_all
from urscript_app.validator_new.checks.structure import check_structure
from urscript_app.validator_new.lexer import tokenize
from urscript_app.validator_new.parser import parse_tokens
from urscript_app.validator_new.result import Diagnostic, Severity, ValidationResult


def validate(source: str) -> ValidationResult:
    """Validate URScript source and return a structured verdict."""
    tokens, lex_diags = tokenize(source)
    program, parse_diags = parse_tokens(tokens)
    diagnostics = [
        *lex_diags,
        *parse_diags,
        *check_structure(program),
        *run_all(program),
    ]
    diagnostics.sort(key=_position)
    errors = [d for d in diagnostics if d.level == Severity.ERROR.value]
    warnings = [d for d in diagnostics if d.level == Severity.WARNING.value]
    return ValidationResult(valid=not errors, errors=errors, warnings=warnings)


def _position(diag: Diagnostic) -> tuple[int, int]:
    return (diag.line or 0, diag.column or 0)
