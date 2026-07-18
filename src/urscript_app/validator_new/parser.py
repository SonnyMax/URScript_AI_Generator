"""Recursive-descent parser producing the validator AST.

The parser never raises on malformed input: syntax problems become
diagnostics (`E-SYNTAX`, `E-BLOCK` for unclosed blocks, `E-END` for a
stray `end`) and parsing recovers at the next line. Constructs it cannot
model precisely degrade to `Raw` nodes.
"""
from __future__ import annotations

from urscript_app.validator_new import ast_nodes as ast
from urscript_app.validator_new.lexer import Token, TokenKind, tokenize
from urscript_app.validator_new.result import Diagnostic, Severity

_COMPOUND_ASSIGN_OPS = {"+=": "+", "-=": "-", "*=": "*", "/=": "/"}
_COMPARISON_OPS = frozenset({"==", "!=", "<", "<=", ">", ">="})
_END_ONLY = frozenset({"end"})
_IF_TERMINATORS = frozenset({"end", "elif", "else"})
_LINE_END_KINDS = (TokenKind.NEWLINE, TokenKind.EOF)


def parse_tokens(tokens: list[Token]) -> tuple[ast.Program, list[Diagnostic]]:
    """Parse a token stream into a `Program` plus structural diagnostics."""
    parser = _Parser(tokens)
    program = parser.parse_program()
    return program, parser.diagnostics


def parse_source(source: str) -> tuple[ast.Program, list[Diagnostic]]:
    """Convenience wrapper: tokenize and parse, merging lexer diagnostics."""
    tokens, lex_diags = tokenize(source)
    program, parse_diags = parse_tokens(tokens)
    return program, [*lex_diags, *parse_diags]


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._pos = 0
        self.diagnostics: list[Diagnostic] = []

    # ------------------------------------------------------------------
    # Token stream helpers
    # ------------------------------------------------------------------

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _peek_ahead(self, offset: int) -> Token:
        idx = min(self._pos + offset, len(self._tokens) - 1)
        return self._tokens[idx]

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        if tok.kind is not TokenKind.EOF:
            self._pos += 1
        return tok

    def _match_op(self, value: str) -> bool:
        tok = self._peek()
        if tok.kind is TokenKind.OP and tok.value == value:
            self._advance()
            return True
        return False

    def _expect_op(self, value: str) -> bool:
        tok = self._peek()
        if tok.kind is TokenKind.OP and tok.value == value:
            self._advance()
            return True
        self._error(f"Expected {value!r} but found {_describe(tok)}", tok)
        return False

    def _skip_newlines(self) -> None:
        while self._peek().kind is TokenKind.NEWLINE:
            self._advance()

    def _sync_to_newline(self) -> None:
        while self._peek().kind not in _LINE_END_KINDS:
            self._advance()
        if self._peek().kind is TokenKind.NEWLINE:
            self._advance()

    def _finish_line(self) -> None:
        tok = self._peek()
        if tok.kind is TokenKind.NEWLINE:
            self._advance()
            return
        if tok.kind is TokenKind.EOF:
            return
        self._error(f"Unexpected {_describe(tok)} after end of statement", tok)
        self._sync_to_newline()

    def _error(self, message: str, tok: Token, code: str = "E-SYNTAX") -> None:
        self.diagnostics.append(
            Diagnostic(
                level=Severity.ERROR.value,
                message=message,
                line=tok.line,
                column=tok.column,
                code=code,
            )
        )

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------

    def parse_program(self) -> ast.Program:
        body: list[ast.Stmt] = []
        self._skip_newlines()
        while self._peek().kind is not TokenKind.EOF:
            tok = self._peek()
            if tok.kind is TokenKind.KEYWORD and tok.value == "end":
                self._advance()
                self._error("Stray 'end' with no open block", tok, code="E-END")
                self._sync_to_newline()
            else:
                stmt = self._parse_statement_safe()
                if stmt is not None:
                    body.append(stmt)
            self._skip_newlines()
        return ast.Program(body=tuple(body))

    def _parse_statement_safe(self) -> ast.Stmt | None:
        start = self._pos
        try:
            stmt = self._parse_statement()
        except Exception:
            # Last-resort recovery: the validator must never crash on input.
            self._error("Could not parse statement", self._peek())
            stmt = None
        if self._pos == start:
            # Guarantee progress so malformed input cannot loop forever.
            self._advance()
            self._sync_to_newline()
        return stmt

    def _parse_statement(self) -> ast.Stmt | None:
        tok = self._peek()
        if tok.kind is TokenKind.KEYWORD:
            return self._parse_keyword_statement(tok)
        if tok.kind is TokenKind.NAME:
            return self._parse_name_statement()
        self._error(f"Unexpected {_describe(tok)} at start of statement", tok)
        self._sync_to_newline()
        return None

    def _parse_keyword_statement(self, tok: Token) -> ast.Stmt | None:
        word = tok.value
        if word == "def":
            return self._parse_funcdef()
        if word == "if":
            return self._parse_if()
        if word == "while":
            return self._parse_while()
        if word == "for":
            return self._parse_for()
        if word == "thread":
            return self._parse_thread()
        if word == "return":
            return self._parse_return()
        if word in ("global", "local"):
            return self._parse_scoped_decl()
        if word in ("enter_critical", "exit_critical"):
            self._advance()
            self._finish_line()
            return ast.Critical(enter=word == "enter_critical", line=tok.line)
        if word in ("break", "continue"):
            self._advance()
            self._finish_line()
            return ast.Raw(text=word, line=tok.line)
        if word in ("elif", "else"):
            self._advance()
            self._error(f"'{word}' without a matching 'if'", tok)
            self._sync_to_newline()
            return None
        self._advance()
        self._error(f"Unexpected keyword {word!r} at start of statement", tok)
        self._sync_to_newline()
        return None

    def _parse_funcdef(self) -> ast.FuncDef:
        def_tok = self._advance()
        name = "<anonymous>"
        tok = self._peek()
        if tok.kind is TokenKind.NAME:
            name = self._advance().value
        else:
            self._error("Expected function name after 'def'", tok)
        params: list[str] = []
        if self._match_op("("):
            while self._peek().kind is TokenKind.NAME:
                params.append(self._advance().value)
                if not self._match_op(","):
                    break
            self._expect_op(")")
        else:
            self._error("Expected '(' after function name", self._peek())
        self._expect_op(":")
        self._finish_line()
        body, term = self._parse_block(def_tok, f"'def {name}'", _END_ONLY)
        if term == "end":
            self._advance()
            self._finish_line()
        return ast.FuncDef(
            name=name, params=tuple(params), body=tuple(body), line=def_tok.line
        )

    def _parse_block(
        self, opened: Token, description: str, terminators: frozenset[str]
    ) -> tuple[list[ast.Stmt], str | None]:
        """Collect statements until a terminator keyword (not consumed) or EOF."""
        body: list[ast.Stmt] = []
        self._skip_newlines()
        while True:
            tok = self._peek()
            if tok.kind is TokenKind.EOF:
                self._error(
                    f"Unclosed {description} block: missing 'end'",
                    opened,
                    code="E-BLOCK",
                )
                return body, None
            if tok.kind is TokenKind.KEYWORD and tok.value in terminators:
                return body, tok.value
            stmt = self._parse_statement_safe()
            if stmt is not None:
                body.append(stmt)
            self._skip_newlines()

    def _parse_if(self) -> ast.If:
        if_tok = self._advance()
        cond = self._parse_expression()
        self._expect_op(":")
        self._finish_line()
        body, term = self._parse_block(if_tok, "'if'", _IF_TERMINATORS)
        elifs: list[tuple[ast.Expr, tuple[ast.Stmt, ...]]] = []
        orelse: tuple[ast.Stmt, ...] | None = None
        while term == "elif":
            elif_tok = self._advance()
            elif_cond = self._parse_expression()
            self._expect_op(":")
            self._finish_line()
            elif_body, term = self._parse_block(elif_tok, "'elif'", _IF_TERMINATORS)
            elifs.append((elif_cond, tuple(elif_body)))
        if term == "else":
            else_tok = self._advance()
            self._expect_op(":")
            self._finish_line()
            else_body, term = self._parse_block(else_tok, "'else'", _END_ONLY)
            orelse = tuple(else_body)
        if term == "end":
            self._advance()
            self._finish_line()
        return ast.If(
            cond=cond,
            body=tuple(body),
            elifs=tuple(elifs),
            orelse=orelse,
            line=if_tok.line,
        )

    def _parse_while(self) -> ast.While:
        while_tok = self._advance()
        cond = self._parse_expression()
        self._expect_op(":")
        self._finish_line()
        body, term = self._parse_block(while_tok, "'while'", _END_ONLY)
        if term == "end":
            self._advance()
            self._finish_line()
        return ast.While(cond=cond, body=tuple(body), line=while_tok.line)

    def _parse_for(self) -> ast.For:
        for_tok = self._advance()
        var = ""
        tok = self._peek()
        if tok.kind is TokenKind.NAME:
            var = self._advance().value
        else:
            self._error("Expected loop variable after 'for'", tok)
        tok = self._peek()
        if tok.kind is TokenKind.KEYWORD and tok.value == "in":
            self._advance()
        else:
            self._error("Expected 'in' in for statement", tok)
        iterable = self._parse_expression()
        self._expect_op(":")
        self._finish_line()
        body, term = self._parse_block(for_tok, "'for'", _END_ONLY)
        if term == "end":
            self._advance()
            self._finish_line()
        return ast.For(
            var=var, iterable=iterable, body=tuple(body), line=for_tok.line
        )

    def _parse_thread(self) -> ast.Thread:
        thread_tok = self._advance()
        name = "<anonymous>"
        tok = self._peek()
        if tok.kind is TokenKind.NAME:
            name = self._advance().value
        else:
            self._error("Expected thread name after 'thread'", tok)
        if self._match_op("("):
            self._expect_op(")")
        else:
            self._error("Expected '()' after thread name", self._peek())
        self._expect_op(":")
        self._finish_line()
        body, term = self._parse_block(thread_tok, f"'thread {name}'", _END_ONLY)
        if term == "end":
            self._advance()
            self._finish_line()
        return ast.Thread(name=name, body=tuple(body), line=thread_tok.line)

    def _parse_return(self) -> ast.Return:
        return_tok = self._advance()
        value: ast.Expr | None = None
        if self._peek().kind not in _LINE_END_KINDS:
            value = self._parse_expression()
        self._finish_line()
        return ast.Return(value=value, line=return_tok.line)

    def _parse_scoped_decl(self) -> ast.Global | ast.Local:
        kw_tok = self._advance()
        name = ""
        tok = self._peek()
        if tok.kind is TokenKind.NAME:
            name = self._advance().value
        else:
            self._error(f"Expected variable name after '{kw_tok.value}'", tok)
        value: ast.Expr | None = None
        if self._match_op("="):
            value = self._parse_expression()
        self._finish_line()
        if kw_tok.value == "global":
            return ast.Global(name=name, value=value, line=kw_tok.line)
        return ast.Local(name=name, value=value, line=kw_tok.line)

    def _parse_name_statement(self) -> ast.Stmt:
        name_tok = self._advance()
        nxt = self._peek()
        if nxt.kind is TokenKind.OP and nxt.value == "(":
            call = self._parse_call(name_tok)
            self._finish_line()
            return call
        if nxt.kind is TokenKind.OP and nxt.value == "=":
            self._advance()
            value = self._parse_expression()
            self._finish_line()
            return ast.Assign(target=name_tok.value, value=value, line=name_tok.line)
        if nxt.kind is TokenKind.OP and nxt.value in _COMPOUND_ASSIGN_OPS:
            op_tok = self._advance()
            value = self._parse_expression()
            self._finish_line()
            desugared = ast.BinOp(
                op=_COMPOUND_ASSIGN_OPS[op_tok.value],
                left=ast.Name(id=name_tok.value, line=name_tok.line),
                right=value,
                line=name_tok.line,
            )
            return ast.Assign(
                target=name_tok.value, value=desugared, line=name_tok.line
            )
        # Indexed assignment, struct access, bare names, ...: degrade to Raw.
        return self._raw_rest_of_line(name_tok)

    def _raw_rest_of_line(self, first: Token) -> ast.Raw:
        parts = [first.value]
        while self._peek().kind not in _LINE_END_KINDS:
            parts.append(self._advance().value)
        if self._peek().kind is TokenKind.NEWLINE:
            self._advance()
        return ast.Raw(text=" ".join(parts), line=first.line)

    # ------------------------------------------------------------------
    # Expressions (precedence climbing)
    # ------------------------------------------------------------------

    def _parse_expression(self) -> ast.Expr:
        return self._parse_or()

    def _parse_or(self) -> ast.Expr:
        left = self._parse_and()
        while self._peek().kind is TokenKind.KEYWORD and self._peek().value in (
            "or",
            "xor",
        ):
            op_tok = self._advance()
            right = self._parse_and()
            left = ast.BinOp(op=op_tok.value, left=left, right=right, line=op_tok.line)
        return left

    def _parse_and(self) -> ast.Expr:
        left = self._parse_not()
        while self._peek().kind is TokenKind.KEYWORD and self._peek().value == "and":
            op_tok = self._advance()
            right = self._parse_not()
            left = ast.BinOp(op=op_tok.value, left=left, right=right, line=op_tok.line)
        return left

    def _parse_not(self) -> ast.Expr:
        tok = self._peek()
        if tok.kind is TokenKind.KEYWORD and tok.value == "not":
            self._advance()
            return ast.UnaryOp(op="not", operand=self._parse_not(), line=tok.line)
        return self._parse_comparison()

    def _parse_comparison(self) -> ast.Expr:
        left = self._parse_additive()
        while (
            self._peek().kind is TokenKind.OP
            and self._peek().value in _COMPARISON_OPS
        ):
            op_tok = self._advance()
            right = self._parse_additive()
            left = ast.BinOp(op=op_tok.value, left=left, right=right, line=op_tok.line)
        return left

    def _parse_additive(self) -> ast.Expr:
        left = self._parse_multiplicative()
        while self._peek().kind is TokenKind.OP and self._peek().value in ("+", "-"):
            op_tok = self._advance()
            right = self._parse_multiplicative()
            left = ast.BinOp(op=op_tok.value, left=left, right=right, line=op_tok.line)
        return left

    def _parse_multiplicative(self) -> ast.Expr:
        left = self._parse_unary()
        while self._peek().kind is TokenKind.OP and self._peek().value in (
            "*",
            "/",
            "%",
        ):
            op_tok = self._advance()
            right = self._parse_unary()
            left = ast.BinOp(op=op_tok.value, left=left, right=right, line=op_tok.line)
        return left

    def _parse_unary(self) -> ast.Expr:
        tok = self._peek()
        if tok.kind is TokenKind.OP and tok.value == "-":
            self._advance()
            operand = self._parse_unary()
            if isinstance(operand, ast.Number):
                # Fold to a negative literal so p[-0.1, ...] stays a Number.
                return ast.Number(
                    value=-operand.value, raw=f"-{operand.raw}", line=operand.line
                )
            return ast.UnaryOp(op="-", operand=operand, line=tok.line)
        if tok.kind is TokenKind.OP and tok.value == "+":
            self._advance()
            return self._parse_unary()
        return self._parse_atom()

    def _parse_atom(self) -> ast.Expr:
        tok = self._peek()
        if tok.kind is TokenKind.NUMBER:
            self._advance()
            return ast.Number(value=float(tok.value), raw=tok.value, line=tok.line)
        if tok.kind is TokenKind.STRING:
            self._advance()
            return ast.Str(value=tok.value, line=tok.line)
        if tok.kind is TokenKind.BOOL:
            self._advance()
            return ast.Bool(value=tok.value == "True", line=tok.line)
        if tok.kind is TokenKind.POSE:
            self._advance()
            elements = self._parse_bracket_list("pose literal")
            return ast.PoseLit(elements=tuple(elements), line=tok.line)
        if tok.kind is TokenKind.OP and tok.value == "[":
            elements = self._parse_bracket_list("list literal")
            return ast.ListLit(elements=tuple(elements), line=tok.line)
        if tok.kind is TokenKind.OP and tok.value == "(":
            self._advance()
            inner = self._parse_expression()
            self._expect_op(")")
            return inner
        if tok.kind is TokenKind.NAME:
            self._advance()
            nxt = self._peek()
            if nxt.kind is TokenKind.OP and nxt.value == "(":
                return self._parse_call(tok)
            if nxt.kind is TokenKind.OP and nxt.value == "[":
                # Indexing / matrix access: degrade gracefully to Raw.
                self._parse_bracket_list("index expression")
                return ast.Raw(text=f"{tok.value}[...]", line=tok.line)
            return ast.Name(id=tok.value, line=tok.line)
        self._error(f"Unexpected {_describe(tok)} in expression", tok)
        if tok.kind not in _LINE_END_KINDS:
            self._advance()
        return ast.Raw(text=tok.value, line=tok.line)

    def _parse_call(self, name_tok: Token) -> ast.Call:
        self._advance()  # consume '('
        args: list[ast.Expr] = []
        kwargs: list[tuple[str, ast.Expr]] = []
        if self._match_op(")"):
            return ast.Call(
                name=name_tok.value,
                args=(),
                kwargs=(),
                line=name_tok.line,
                col=name_tok.column,
            )
        while True:
            tok = self._peek()
            if tok.kind in _LINE_END_KINDS:
                self._error(
                    f"Unclosed call to {name_tok.value!r}: missing ')'", name_tok
                )
                break
            nxt = self._peek_ahead(1)
            if (
                tok.kind is TokenKind.NAME
                and nxt.kind is TokenKind.OP
                and nxt.value == "="
            ):
                self._advance()  # keyword name
                self._advance()  # '='
                kwargs.append((tok.value, self._parse_expression()))
            else:
                args.append(self._parse_expression())
            if self._match_op(","):
                continue
            if self._match_op(")"):
                break
            self._error(
                f"Expected ',' or ')' in call to {name_tok.value!r}", self._peek()
            )
            break
        return ast.Call(
            name=name_tok.value,
            args=tuple(args),
            kwargs=tuple(kwargs),
            line=name_tok.line,
            col=name_tok.column,
        )

    def _parse_bracket_list(self, description: str) -> list[ast.Expr]:
        open_tok = self._peek()  # '['
        self._advance()
        elements: list[ast.Expr] = []
        if self._match_op("]"):
            return elements
        while True:
            tok = self._peek()
            if tok.kind in _LINE_END_KINDS:
                self._error(f"Unclosed {description}: missing ']'", open_tok)
                return elements
            elements.append(self._parse_expression())
            if self._match_op(","):
                continue
            if self._match_op("]"):
                return elements
            self._error(f"Expected ',' or ']' in {description}", self._peek())
            return elements


def _describe(tok: Token) -> str:
    if tok.kind is TokenKind.NEWLINE:
        return "end of line"
    if tok.kind is TokenKind.EOF:
        return "end of file"
    return f"token {tok.value!r}"
