"""Structural validator: checks block nesting, def/end balance, basic call shapes."""
from __future__ import annotations
from urscript_app.validator.lexer import Token, TT, tokenize
from urscript_app.validator.result import Diagnostic


# Keywords that open a new block requiring a matching 'end'
_BLOCK_OPENERS = {"def", "if", "while", "for", "thread"}


def parse(source: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    tokens = tokenize(source)

    # --- Block balance check ---
    stack: list[tuple[str, int]] = []  # (keyword, line)
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == TT.KEYWORD:
            if tok.value in _BLOCK_OPENERS:
                stack.append((tok.value, tok.line))
            elif tok.value == "elif" or tok.value == "else":
                if not stack or stack[-1][0] != "if":
                    diagnostics.append(Diagnostic("error", f"Unexpected '{tok.value}' without matching 'if'", tok.line))
            elif tok.value == "end":
                if not stack:
                    diagnostics.append(Diagnostic("error", "Unexpected 'end' — no open block", tok.line))
                else:
                    stack.pop()
        i += 1

    for kw, line in stack:
        diagnostics.append(Diagnostic("error", f"Unclosed '{kw}' block — missing 'end'", line))

    # --- Must have at least one 'def' ---
    has_def = any(t.type == TT.KEYWORD and t.value == "def" for t in tokens)
    if not has_def:
        diagnostics.append(Diagnostic("error", "No 'def ... end' program wrapper found", None))

    # --- Unterminated strings (lexer already handles, but double-check) ---
    raw_lines = source.splitlines()
    for lineno, line in enumerate(raw_lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        single = stripped.count("'") - stripped.count("\'")
        double = stripped.count('"') - stripped.count('\\"')
        if single % 2 != 0:
            diagnostics.append(Diagnostic("warning", "Possible unterminated single-quoted string", lineno))
        if double % 2 != 0:
            diagnostics.append(Diagnostic("warning", "Possible unterminated double-quoted string", lineno))

    return diagnostics
