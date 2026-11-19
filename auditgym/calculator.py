"""Safe arithmetic calculator for the agent tool.

Grammar (no names, no calls, no exponent operator, no scientific notation):
    expr   := term (("+" | "-") term)*
    term   := factor (("*" | "/") factor)*
    factor := ("+" | "-") factor | NUMBER | "(" expr ")"
    NUMBER := digits ["." digits] | "." digits
Evaluation uses Decimal with 34 significant digits. The result is rounded
half-even to 12 decimal places and printed without exponent.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, DivisionByZero, InvalidOperation, localcontext

MAX_LENGTH = 256
MAX_DEPTH = 32
MAX_TOKENS = 200
MAX_ABS = Decimal("1e30")
RESULT_PLACES = 12


class CalcError(ValueError):
    """Raised for any invalid expression. The message is short and safe to show."""


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in " \t":
            i += 1
            continue
        if ch in "+-*/()":
            tokens.append(ch)
            i += 1
            continue
        if ch.isdigit() or ch == ".":
            j = i
            seen_dot = False
            while j < n and (text[j].isdigit() or text[j] == "."):
                if text[j] == ".":
                    if seen_dot:
                        raise CalcError("malformed number")
                    seen_dot = True
                j += 1
            literal = text[i:j]
            if literal == "." or literal.endswith("."):
                raise CalcError("malformed number")
            if not all(c.isascii() for c in literal):
                raise CalcError("only ASCII digits are allowed")
            tokens.append(literal)
            i = j
            continue
        raise CalcError(f"unexpected character at position {i}")
    if len(tokens) > MAX_TOKENS:
        raise CalcError("expression too long")
    return tokens


class _Parser:
    def __init__(self, tokens: list[str]):
        self.tokens = tokens
        self.pos = 0
        self.depth = 0

    def peek(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def take(self) -> str:
        tok = self.peek()
        if tok is None:
            raise CalcError("unexpected end of expression")
        self.pos += 1
        return tok

    def expr(self) -> Decimal:
        value = self.term()
        while self.peek() in ("+", "-"):
            op = self.take()
            rhs = self.term()
            value = value + rhs if op == "+" else value - rhs
            _check(value)
        return value

    def term(self) -> Decimal:
        value = self.factor()
        while self.peek() in ("*", "/"):
            op = self.take()
            rhs = self.factor()
            if op == "*":
                value = value * rhs
            else:
                if rhs == 0:
                    raise CalcError("division by zero")
                value = value / rhs
            _check(value)
        return value

    def factor(self) -> Decimal:
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise CalcError("expression nested too deeply")
        try:
            tok = self.take()
            if tok == "+":
                return self.factor()
            if tok == "-":
                return -self.factor()
            if tok == "(":
                value = self.expr()
                if self.take() != ")":
                    raise CalcError("missing closing parenthesis")
                return value
            if tok in ("*", "/", ")"):
                raise CalcError(f"unexpected token {tok!r}")
            return Decimal(tok)
        finally:
            self.depth -= 1


def _check(value: Decimal) -> None:
    if abs(value) >= MAX_ABS:
        raise CalcError("result out of range")


def evaluate(expression) -> str:
    """Evaluate an arithmetic expression and return a decimal string."""
    if not isinstance(expression, str):
        raise CalcError("expression must be a string")
    if len(expression) > MAX_LENGTH:
        raise CalcError("expression too long")
    if not expression.strip():
        raise CalcError("empty expression")
    tokens = _tokenize(expression)
    with localcontext() as ctx:
        ctx.prec = 34
        ctx.traps[DivisionByZero] = True
        ctx.traps[InvalidOperation] = True
        try:
            parser = _Parser(tokens)
            value = parser.expr()
            if parser.peek() is not None:
                raise CalcError(f"unexpected token {parser.peek()!r}")
            _check(value)
            q = Decimal(1).scaleb(-RESULT_PLACES)
            ctx.prec = 80  # headroom: |value| < 1e30 plus 12 decimal places
            value = value.quantize(q, rounding=ROUND_HALF_EVEN)
        except (InvalidOperation, DivisionByZero) as exc:
            raise CalcError("invalid arithmetic") from exc
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text
