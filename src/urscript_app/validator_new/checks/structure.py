"""Structural checks over the finished AST.

Block-balance problems (`E-BLOCK`, `E-END`, `elif`/`else` without `if`)
are reported by the parser while it recovers; this module adds the
whole-program structure rules that need the complete `Program`.
"""
from __future__ import annotations

from urscript_app.validator_new.ast_nodes import FuncDef, Program
from urscript_app.validator_new.result import Diagnostic, Severity

_NODEF_MESSAGE = (
    "Missing 'def ... end' program wrapper: wrap statements in "
    "'def program(): ... end'"
)


def check_structure(program: Program) -> list[Diagnostic]:
    """Return structure diagnostics; currently the E-NODEF wrapper rule."""
    if any(isinstance(stmt, FuncDef) for stmt in program.body):
        return []
    return [
        Diagnostic(
            level=Severity.ERROR.value,
            message=_NODEF_MESSAGE,
            line=1,
            column=1,
            code="E-NODEF",
        )
    ]
