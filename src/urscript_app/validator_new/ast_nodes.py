"""Frozen dataclass AST nodes produced by the URScript parser.

Every node is immutable and carries a 1-based `line` for diagnostics.
`Raw` is the graceful-degradation fallback: anything the parser cannot
model precisely becomes a `Raw` node instead of crashing the pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Number:
    value: float
    raw: str  # original source text, keeps int-vs-float distinction
    line: int


@dataclass(frozen=True)
class Str:
    value: str
    line: int


@dataclass(frozen=True)
class Bool:
    value: bool
    line: int


@dataclass(frozen=True)
class Name:
    id: str
    line: int


@dataclass(frozen=True)
class BinOp:
    op: str
    left: Expr
    right: Expr
    line: int


@dataclass(frozen=True)
class UnaryOp:
    op: str
    operand: Expr
    line: int


@dataclass(frozen=True)
class ListLit:
    elements: tuple[Expr, ...]
    line: int


@dataclass(frozen=True)
class PoseLit:
    """The `p[...]` pose literal form."""

    elements: tuple[Expr, ...]
    line: int


@dataclass(frozen=True)
class Call:
    name: str
    args: tuple[Expr, ...]
    kwargs: tuple[tuple[str, Expr], ...]
    line: int
    col: int


@dataclass(frozen=True)
class Raw:
    """Fallback for constructs the parser does not model precisely."""

    text: str
    line: int


@dataclass(frozen=True)
class Assign:
    target: str
    value: Expr
    line: int


@dataclass(frozen=True)
class If:
    cond: Expr
    body: tuple[Stmt, ...]
    elifs: tuple[tuple[Expr, tuple[Stmt, ...]], ...]
    orelse: tuple[Stmt, ...] | None
    line: int


@dataclass(frozen=True)
class While:
    cond: Expr
    body: tuple[Stmt, ...]
    line: int


@dataclass(frozen=True)
class For:
    var: str
    iterable: Expr
    body: tuple[Stmt, ...]
    line: int


@dataclass(frozen=True)
class Thread:
    name: str
    body: tuple[Stmt, ...]
    line: int


@dataclass(frozen=True)
class FuncDef:
    name: str
    params: tuple[str, ...]
    body: tuple[Stmt, ...]
    line: int


@dataclass(frozen=True)
class Return:
    value: Expr | None
    line: int


@dataclass(frozen=True)
class Global:
    name: str
    value: Expr | None
    line: int


@dataclass(frozen=True)
class Local:
    name: str
    value: Expr | None
    line: int


@dataclass(frozen=True)
class Critical:
    """`enter_critical` / `exit_critical` marker statement."""

    enter: bool
    line: int


Expr = Number | Str | Bool | Name | BinOp | UnaryOp | ListLit | PoseLit | Call | Raw

Stmt = (
    FuncDef
    | Assign
    | Call
    | If
    | While
    | For
    | Thread
    | Return
    | Global
    | Local
    | Critical
    | Raw
)


@dataclass(frozen=True)
class Program:
    body: tuple[Stmt, ...]
