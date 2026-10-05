"""Finite scalar grammar and exact decimal normalization; no device semantics."""
from __future__ import annotations

from decimal import Decimal
import re

from .models import IssueSeverity, Quantity, Unit, ValidationIssue, ValueGrammar, ValueParseResult


_SCALAR = re.compile(
    r"(?P<number>[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+))"
    r"(?P<exponent>[eE][+-]?[0-9]+)?(?P<suffix>meg|[tgkmunpf])?",
    re.IGNORECASE | re.ASCII,
)
_SUFFIX_EXPONENTS = {"t": 12, "g": 9, "meg": 6, "k": 3, "m": -3,
                     "u": -6, "n": -9, "p": -12, "f": -15}
_MAX_LENGTH = 128
_MAX_EXPONENT = 300


def _normalized(literal: str, grammar: ValueGrammar) -> str:
    if len(literal) > _MAX_LENGTH:
        raise ValueError("Scalar literal exceeds the 128-character limit.")
    match = _SCALAR.fullmatch(literal.strip())
    if match is None:
        raise ValueError("Expected a finite decimal scalar with at most one supported suffix.")
    suffix = match.group("suffix")
    if suffix is not None and grammar is not ValueGrammar.SPICE:
        raise ValueError("Suffixes require the explicit spice grammar.")
    exponent_text = match.group("exponent") or ""
    if exponent_text and abs(int(exponent_text[1:])) > _MAX_EXPONENT:
        raise ValueError("Scalar exponent exceeds the M1 limit of 300.")
    # Decimal construction and tuple shifts are exact regardless of context.prec.
    decimal = Decimal(match.group("number") + exponent_text)
    sign, digits, exponent = decimal.as_tuple()
    exponent += _SUFFIX_EXPONENTS.get(suffix.lower() if suffix else "", 0)
    coefficient = "".join(str(digit) for digit in digits).lstrip("0")
    if not coefficient:
        return "0"
    trimmed = coefficient.rstrip("0")
    exponent += len(coefficient) - len(trimmed)
    coefficient = trimmed
    adjusted = exponent + len(coefficient) - 1
    if abs(adjusted) > _MAX_EXPONENT:
        raise ValueError("Normalized scalar exponent exceeds the M1 limit of 300.")
    prefix = "-" if sign else ""
    point = len(coefficient) + exponent
    if point <= 0:
        fixed = "0." + "0" * -point + coefficient
    elif point >= len(coefficient):
        fixed = coefficient + "0" * (point - len(coefficient))
    else:
        fixed = coefficient[:point] + "." + coefficient[point:]
    if len(prefix + fixed) <= _MAX_LENGTH:
        return prefix + fixed
    mantissa = coefficient[0] + ("." + coefficient[1:] if len(coefficient) > 1 else "")
    scientific = prefix + mantissa + "e" + str(adjusted)
    if len(scientific) > _MAX_LENGTH:
        raise ValueError("Normalized scalar exceeds the 128-character limit.")
    return scientific


def parse_quantity(literal: str, unit: Unit, grammar: ValueGrammar) -> ValueParseResult:
    """Preserve literal and emit an exact SI string, or VALUE_INVALID with no quantity.

    spice suffixes are case-insensitive: M/m is milli, Meg is mega. si/manual
    permit plain decimal/exponent input only. No arbitrary expressions or unit
    inference are supported. Wrong API types/configuration raise TypeError or
    ValueError; syntactically invalid scalar text returns a typed diagnosis.
    """
    if not isinstance(literal, str):
        raise TypeError("literal must be a string")
    # Reuse existing unit/enum checks without parsing or mutating a Quantity.
    Quantity(None, None, unit, grammar)
    if grammar is ValueGrammar.UNRESOLVED:
        raise ValueError("unresolved is not a scalar parsing grammar")
    try:
        normalized = _normalized(literal, grammar)
    except ValueError as error:
        issue = ValidationIssue(
            "issue_0001", IssueSeverity.ERROR, "VALUE_INVALID", str(error), (),
            None, None, "literal", "Supply one supported finite scalar value.", (),
        )
        return ValueParseResult(None, (issue,))
    return ValueParseResult(Quantity(literal, normalized, unit, grammar), ())
