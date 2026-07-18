"""Semantic check passes for the new validator.

Stage 1: the pass list is empty. Structural diagnostics come from the
parser and `checks.structure`; later stages register signature, bounds,
symbol, and safety passes here.
"""
from __future__ import annotations

from typing import Protocol

from urscript_app.validator_new.ast_nodes import Program
from urscript_app.validator_new.result import Diagnostic


class CheckPass(Protocol):
    """A single semantic validation pass over the parsed program."""

    name: str

    def run(self, program: Program) -> list[Diagnostic]: ...


_PASSES: tuple[CheckPass, ...] = ()


def run_all(program: Program) -> list[Diagnostic]:
    """Run every registered semantic pass in stable order."""
    diagnostics: list[Diagnostic] = []
    for check in _PASSES:
        diagnostics.extend(check.run(program))
    return diagnostics
