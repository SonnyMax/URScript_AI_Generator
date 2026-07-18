"""Line-based tokenizer for URScript source.

URScript is line-oriented: statements end at end of line, comments run
from '#' to end of line, and string literals have **no escape sequences**
(a backslash is a literal character). The lexer therefore scans one line
at a time and emits a NEWLINE token per source line plus a final EOF.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from urscript_app.validator_new.result import Diagnostic, Severity

KEYWORDS = frozenset({
    "and", "break", "continue", "def", "elif", "else", "end",
    "enter_critical", "exit_critical", "for", "global", "if", "in",
    "local", "not", "or", "return", "thread", "while", "xor",
})

BOOL_LITERALS = frozenset({"True", "False"})

# Two-character operators must be tried before their single-char prefixes.
TWO_CHAR_OPS = ("==", "!=", "<=", ">=", "+=", "-=", "*=", "/=")
SINGLE_CHAR_OPS = frozenset("=<>+-*/%()[],:")


class TokenKind(StrEnum):
    NAME = "name"
    NUMBER = "number"
    STRING = "string"
    BOOL = "bool"
    KEYWORD = "keyword"
    POSE = "pose"  # the 'p' prefix directly before '[' in p[...] literals
    OP = "op"
    NEWLINE = "newline"
    EOF = "eof"


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    value: str
    line: int  # 1-based
    column: int  # 1-based


def tokenize(source: str) -> tuple[list[Token], list[Diagnostic]]:
    """Tokenize `source`, returning the token stream plus lexical diagnostics."""
    tokens: list[Token] = []
    diagnostics: list[Diagnostic] = []
    lines = source.splitlines()
    for line_no, text in enumerate(lines, start=1):
        _scan_line(text, line_no, tokens, diagnostics)
        tokens.append(Token(TokenKind.NEWLINE, "", line_no, len(text) + 1))
    tokens.append(Token(TokenKind.EOF, "", len(lines) + 1, 1))
    return tokens, diagnostics


def _scan_line(
    text: str, line_no: int, tokens: list[Token], diagnostics: list[Diagnostic]
) -> None:
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in " \t\r":
            i += 1
            continue
        if ch == "#":
            return  # comment runs to end of line
        if ch in "\"'":
            i = _scan_string(text, i, line_no, tokens, diagnostics)
            continue
        if ch.isdigit() or (ch == "." and i + 1 < n and text[i + 1].isdigit()):
            i = _scan_number(text, i, line_no, tokens)
            continue
        if ch.isalpha() or ch == "_":
            i = _scan_word(text, i, line_no, tokens)
            continue
        two = text[i : i + 2]
        if two in TWO_CHAR_OPS:
            tokens.append(Token(TokenKind.OP, two, line_no, i + 1))
            i += 2
            continue
        if ch in SINGLE_CHAR_OPS:
            tokens.append(Token(TokenKind.OP, ch, line_no, i + 1))
            i += 1
            continue
        diagnostics.append(_lex_error(f"Unexpected character {ch!r}", line_no, i + 1))
        i += 1


def _scan_string(
    text: str,
    start: int,
    line_no: int,
    tokens: list[Token],
    diagnostics: list[Diagnostic],
) -> int:
    """Scan a string literal; URScript strings have no escape sequences."""
    quote = text[start]
    end = text.find(quote, start + 1)
    if end == -1:
        diagnostics.append(
            _lex_error("Unterminated string literal", line_no, start + 1)
        )
        tokens.append(Token(TokenKind.STRING, text[start + 1 :], line_no, start + 1))
        return len(text)
    tokens.append(Token(TokenKind.STRING, text[start + 1 : end], line_no, start + 1))
    return end + 1


def _scan_number(text: str, start: int, line_no: int, tokens: list[Token]) -> int:
    i = start
    n = len(text)
    while i < n and text[i].isdigit():
        i += 1
    if i < n and text[i] == ".":
        i += 1
        while i < n and text[i].isdigit():
            i += 1
    if i < n and text[i] in "eE":
        j = i + 1
        if j < n and text[j] in "+-":
            j += 1
        if j < n and text[j].isdigit():
            i = j
            while i < n and text[i].isdigit():
                i += 1
    tokens.append(Token(TokenKind.NUMBER, text[start:i], line_no, start + 1))
    return i


def _scan_word(text: str, start: int, line_no: int, tokens: list[Token]) -> int:
    i = start
    n = len(text)
    while i < n and (text[i].isalnum() or text[i] == "_"):
        i += 1
    word = text[start:i]
    if word in BOOL_LITERALS:
        kind = TokenKind.BOOL
    elif word in KEYWORDS:
        kind = TokenKind.KEYWORD
    elif word == "p" and i < n and text[i] == "[":
        kind = TokenKind.POSE
    else:
        kind = TokenKind.NAME
    tokens.append(Token(kind, word, line_no, start + 1))
    return i


def _lex_error(message: str, line: int, column: int) -> Diagnostic:
    return Diagnostic(
        level=Severity.ERROR.value,
        message=message,
        line=line,
        column=column,
        code="E-SYNTAX",
    )
