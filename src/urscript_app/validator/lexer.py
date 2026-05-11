"""Minimal URScript tokenizer."""
from __future__ import annotations
import re
from dataclasses import dataclass
from enum import Enum, auto


class TT(Enum):
    KEYWORD = auto()
    IDENT = auto()
    NUMBER = auto()
    STRING = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACK = auto()
    RBRACK = auto()
    COMMA = auto()
    OP = auto()
    NEWLINE = auto()
    COMMENT = auto()
    POSE_PREFIX = auto()
    EOF = auto()


KEYWORDS = {
    "def", "end", "if", "elif", "else", "while", "for", "in",
    "thread", "global", "local", "return", "True", "False", "not",
    "and", "or",
}

# Patterns verified to compile. Simple string match (no escape handling needed for URScript).
_PATTERNS: list[tuple[str, str]] = [
    ("COMMENT", r"#[^\n]*"),
    ("STRING",  r'"[^"]*"'),
    ("STRING2", r"'[^']*'"),
    ("NUMBER",  r"-?\d+\.?\d*(?:[eE][+-]?\d+)?"),
    ("IDENT",   r"[A-Za-z_]\w*"),
    ("LPAREN",  r"\("),
    ("RPAREN",  r"\)"),
    ("LBRACK",  r"\["),
    ("RBRACK",  r"\]"),
    ("COMMA",   r","),
    ("OP",      r"==|!=|<=|>=|[+\-*/]=|="),
    ("NEWLINE", r"\n"),
    ("SKIP",    r"[ \t\r]+"),
]

_TOKEN_RE = re.compile("|".join(f"(?P<{n}>{p})" for n, p in _PATTERNS))


@dataclass
class Token:
    type: TT
    value: str
    line: int


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    line = 1
    for m in _TOKEN_RE.finditer(source):
        kind = m.lastgroup
        val = m.group()
        if kind == "SKIP":
            continue
        if kind == "COMMENT":
            tokens.append(Token(TT.COMMENT, val, line))
            continue
        if kind == "NEWLINE":
            line += 1
            tokens.append(Token(TT.NEWLINE, val, line))
            continue
        if kind in ("STRING", "STRING2"):
            tokens.append(Token(TT.STRING, val, line))
        elif kind == "NUMBER":
            tokens.append(Token(TT.NUMBER, val, line))
        elif kind == "IDENT":
            if val in KEYWORDS:
                tokens.append(Token(TT.KEYWORD, val, line))
            elif val == "p":
                tokens.append(Token(TT.POSE_PREFIX, val, line))
            else:
                tokens.append(Token(TT.IDENT, val, line))
        elif kind == "LPAREN":
            tokens.append(Token(TT.LPAREN, val, line))
        elif kind == "RPAREN":
            tokens.append(Token(TT.RPAREN, val, line))
        elif kind == "LBRACK":
            tokens.append(Token(TT.LBRACK, val, line))
        elif kind == "RBRACK":
            tokens.append(Token(TT.RBRACK, val, line))
        elif kind == "COMMA":
            tokens.append(Token(TT.COMMA, val, line))
        elif kind == "OP":
            tokens.append(Token(TT.OP, val, line))
    tokens.append(Token(TT.EOF, "", line))
    return tokens
