"""Stage 1 tests: lexer, AST shapes for the golden corpus, parser recovery.

Also reproduces every structural behavior asserted in the old
`tests/unit/test_validator.py` so the new validator is a strict superset.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from urscript_app.validator_new import ast_nodes as ast
from urscript_app.validator_new.lexer import TokenKind, tokenize
from urscript_app.validator_new.parser import parse_source
from urscript_app.validator_new.result import ValidationResult
from urscript_app.validator_new.validate import validate

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "urscript"

ALL_FIXTURES = sorted(path.name for path in FIXTURES_DIR.glob("*.urscript"))

# --- source snippets carried over verbatim from the old test suite ---------

VALID_BASIC = """
def program():
  home = [0.0, -1.5708, 0.0, -1.5708, 0.0, 0.0]
  movej(home, a=0.5, v=0.5)
end
"""

VALID_WITH_IO = """
def program():
  set_digital_out(0, True)
  sleep(0.5)
  set_digital_out(0, False)
end
"""

MISSING_END = """
def program():
  movej([0.0, 0.0, 0.0, 0.0, 0.0, 0.0], a=0.5, v=0.5)
"""

NO_DEF = "movej([0.0]*6, a=0.5, v=0.5)"

NESTED_IF_MISSING_END = """
def program():
  if True:
    movej([0.0, 0.0, 0.0, 0.0, 0.0, 0.0], a=0.5, v=0.5)
end
"""

NASTY_SOURCES = [
    "",
    "end",
    ")",
    "((((((",
    "def",
    "def f(:",
    'x = "unterminated',
    "p[",
    "[1, 2",
    "1 + ",
    "if:",
    "while :\nend",
    "def f():\n  if True:\n",
    "movej(1,",
    "a = = 3",
    "thread :",
    "for x in:",
    "return return",
    "def f():\nend\nend",
    "€ nonsense ∞",
]


def _read(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def _parse_clean(source: str) -> ast.Program:
    program, diags = parse_source(source)
    assert diags == [], [d.message for d in diags]
    return program


def _program_body(fixture: str) -> tuple[ast.Stmt, ...]:
    program = _parse_clean(_read(fixture))
    func = program.body[0]
    assert isinstance(func, ast.FuncDef)
    return func.body


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------


def test_pose_prefix_token() -> None:
    tokens, diags = tokenize("p[1] p q[1]")
    assert diags == []
    words = [
        (t.kind, t.value)
        for t in tokens
        if t.kind in (TokenKind.POSE, TokenKind.NAME)
    ]
    assert words == [
        (TokenKind.POSE, "p"),
        (TokenKind.NAME, "p"),
        (TokenKind.NAME, "q"),
    ]


def test_scientific_number_token() -> None:
    tokens, diags = tokenize("x = 1.5e-3")
    assert diags == []
    numbers = [t.value for t in tokens if t.kind is TokenKind.NUMBER]
    assert numbers == ["1.5e-3"]


def test_string_has_no_escape_sequences() -> None:
    # A backslash before the closing quote is a literal character, not an escape.
    tokens, diags = tokenize('msg = "a\\"')
    assert diags == []
    strings = [t.value for t in tokens if t.kind is TokenKind.STRING]
    assert strings == ["a\\"]


def test_unterminated_string_line_and_column() -> None:
    result = validate('def program():\n  textmsg("oops)\nend\n')
    assert not result.valid
    diag = next(d for d in result.errors if "Unterminated" in d.message)
    assert diag.code == "E-SYNTAX"
    assert diag.line == 2
    assert diag.column == 11


# ---------------------------------------------------------------------------
# Corpus AST shapes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_corpus_parses_cleanly(name: str) -> None:
    program = _parse_clean(_read(name))
    assert isinstance(program.body[0], ast.FuncDef)


def test_a1_ast_shape() -> None:
    body = _program_body("a1_move_home.urscript")
    assert [type(s).__name__ for s in body] == ["Assign", "Call", "Assign", "Call"]
    home = body[0]
    assert isinstance(home, ast.Assign)
    assert isinstance(home.value, ast.ListLit)
    assert len(home.value.elements) == 6
    movej = body[1]
    assert isinstance(movej, ast.Call)
    assert movej.name == "movej"
    assert len(movej.args) == 1
    assert isinstance(movej.args[0], ast.Name)
    assert [kw for kw, _ in movej.kwargs] == ["a", "v"]
    target = body[2]
    assert isinstance(target, ast.Assign)
    assert isinstance(target.value, ast.PoseLit)
    assert len(target.value.elements) == 6


def test_a3_bad_force_mode_call_shape() -> None:
    body = _program_body("a3_force_mode_bad.urscript")
    call = next(
        s for s in body if isinstance(s, ast.Call) and s.name == "force_mode"
    )
    assert len(call.args) == 4
    assert call.kwargs == ()
    assert isinstance(call.args[0], ast.Name)
    assert all(isinstance(arg, ast.Number) for arg in call.args[1:])


def test_a3_good_force_mode_call_shape() -> None:
    body = _program_body("a3_force_mode_good.urscript")
    call = next(
        s for s in body if isinstance(s, ast.Call) and s.name == "force_mode"
    )
    assert len(call.args) == 5
    kinds = [type(arg).__name__ for arg in call.args]
    assert kinds == ["Name", "ListLit", "ListLit", "Number", "ListLit"]
    for arg in call.args:
        if isinstance(arg, ast.ListLit):
            assert len(arg.elements) == 6


def test_a4_while_loop_shape() -> None:
    body = _program_body("a4_safe_loop.urscript")
    assert isinstance(body[0], ast.Assign)
    loop = body[1]
    assert isinstance(loop, ast.While)
    assert isinstance(loop.cond, ast.BinOp)
    assert loop.cond.op == "<"
    assert [type(s).__name__ for s in loop.body] == ["Call", "Call", "Assign"]
    increment = loop.body[2]
    assert isinstance(increment, ast.Assign)
    assert isinstance(increment.value, ast.BinOp)
    assert increment.value.op == "+"


def test_a2_good_io_call_shapes() -> None:
    body = _program_body("a2_pick_place_good.urscript")
    io_calls = [
        s for s in body if isinstance(s, ast.Call) and s.name == "set_digital_out"
    ]
    assert len(io_calls) == 3
    for call in io_calls:
        assert isinstance(call.args[0], ast.Number)
        assert isinstance(call.args[1], ast.Bool)


def test_negative_number_literal_folds() -> None:
    program = _parse_clean("def program():\n  x = -0.5\nend\n")
    func = program.body[0]
    assert isinstance(func, ast.FuncDef)
    assign = func.body[0]
    assert isinstance(assign, ast.Assign)
    assert isinstance(assign.value, ast.Number)
    assert assign.value.value == pytest.approx(-0.5)


# ---------------------------------------------------------------------------
# Language constructs
# ---------------------------------------------------------------------------


def test_if_elif_else_parses() -> None:
    source = (
        "def program():\n"
        "  if x > 1:\n"
        "    sleep(0.1)\n"
        "  elif x > 0:\n"
        "    sleep(0.2)\n"
        "  else:\n"
        "    sleep(0.3)\n"
        "  end\n"
        "end\n"
    )
    program = _parse_clean(source)
    func = program.body[0]
    assert isinstance(func, ast.FuncDef)
    branch = func.body[0]
    assert isinstance(branch, ast.If)
    assert len(branch.elifs) == 1
    assert branch.orelse is not None
    assert len(branch.orelse) == 1


def test_thread_and_critical_parse() -> None:
    source = (
        "def program():\n"
        "  thread t():\n"
        "    enter_critical\n"
        "    sleep(0.1)\n"
        "    exit_critical\n"
        "  end\n"
        "end\n"
    )
    program = _parse_clean(source)
    func = program.body[0]
    assert isinstance(func, ast.FuncDef)
    worker = func.body[0]
    assert isinstance(worker, ast.Thread)
    assert worker.name == "t"
    kinds = [type(s).__name__ for s in worker.body]
    assert kinds == ["Critical", "Call", "Critical"]


def test_for_loop_parses() -> None:
    program = _parse_clean(
        "def program():\n  for i in xs:\n    sleep(0.1)\n  end\nend\n"
    )
    func = program.body[0]
    assert isinstance(func, ast.FuncDef)
    loop = func.body[0]
    assert isinstance(loop, ast.For)
    assert loop.var == "i"
    assert isinstance(loop.iterable, ast.Name)


def test_global_local_declarations_parse() -> None:
    program = _parse_clean("def program():\n  global cnt = 0\n  local j = 1\nend\n")
    func = program.body[0]
    assert isinstance(func, ast.FuncDef)
    assert isinstance(func.body[0], ast.Global)
    assert isinstance(func.body[1], ast.Local)


def test_compound_assignment_desugars() -> None:
    program = _parse_clean("def program():\n  i = 0\n  i += 1\nend\n")
    func = program.body[0]
    assert isinstance(func, ast.FuncDef)
    increment = func.body[1]
    assert isinstance(increment, ast.Assign)
    assert isinstance(increment.value, ast.BinOp)
    assert increment.value.op == "+"


# ---------------------------------------------------------------------------
# Structural errors (superset of the old validator's test suite)
# ---------------------------------------------------------------------------


def test_valid_basic_passes() -> None:
    assert validate(VALID_BASIC).valid


def test_valid_with_io_passes() -> None:
    assert validate(VALID_WITH_IO).valid


def test_missing_end_is_error() -> None:
    result = validate(MISSING_END)
    assert not result.valid
    assert any(d.code == "E-BLOCK" for d in result.errors)
    assert any(
        "end" in d.message.lower() or "unclosed" in d.message.lower()
        for d in result.errors
    )


def test_no_def_wrapper_is_error() -> None:
    result = validate(NO_DEF)
    assert not result.valid
    assert any(d.code == "E-NODEF" for d in result.errors)
    assert any("def" in d.message.lower() for d in result.errors)


def test_nested_if_missing_end() -> None:
    result = validate(NESTED_IF_MISSING_END)
    assert not result.valid
    assert any(d.code == "E-BLOCK" for d in result.errors)


def test_stray_end_reports_e_end() -> None:
    result = validate("def program():\n  sleep(1.0)\nend\nend\n")
    assert not result.valid
    assert any(d.code == "E-END" for d in result.errors)


def test_elif_without_if_is_error() -> None:
    result = validate("def program():\n  elif True:\n  sleep(1.0)\nend\n")
    assert not result.valid
    assert any("elif" in d.message for d in result.errors)


def test_else_without_if_is_error() -> None:
    result = validate("def program():\n  else:\n  sleep(1.0)\nend\n")
    assert not result.valid
    assert any("else" in d.message for d in result.errors)


def test_empty_source_reports_nodef() -> None:
    result = validate("")
    assert not result.valid
    assert [d.code for d in result.errors] == ["E-NODEF"]


@pytest.mark.parametrize("source", NASTY_SOURCES)
def test_never_raises_on_malformed_input(source: str) -> None:
    result = validate(source)
    assert isinstance(result, ValidationResult)
    assert not result.valid
