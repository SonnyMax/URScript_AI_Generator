"""Diagnostic and result value types for the new URScript validator.

These types are the stable envelope shared by every later stage (lexer,
parser, semantic checks, oracle). Field names `level`, `message`, `line`
are kept identical to the old validator for drop-in compatibility.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Severity(StrEnum):
    """Severity of a diagnostic; the string value is what `Diagnostic.level` mirrors."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class Diagnostic:
    """A single validation finding.

    `level` stays a plain string (mirroring `Severity.value`) for backward
    compatibility with the old validator's envelope. `code` is a stable
    machine-readable identifier such as "E-ARITY" or "W-GRIPPER".
    """

    level: str
    message: str
    line: int | None = None
    column: int | None = None
    code: str | None = None
    end_line: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "line": self.line,
            "column": self.column,
        }


@dataclass
class ValidationResult:
    """Aggregate verdict for one URScript source."""

    valid: bool
    errors: list[Diagnostic] = field(default_factory=list)
    warnings: list[Diagnostic] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """JSON-serializable envelope: {"valid": bool, "errors": [...], "warnings": [...]}."""
        return {
            "valid": self.valid,
            "errors": [d.to_dict() for d in self.errors],
            "warnings": [d.to_dict() for d in self.warnings],
        }
