"""Money primitives: currency exponents, FX conversion, rounding.

Amounts are integers in minor units. FX rates are decimal strings meaning
"1 unit of source currency = rate units of target currency". All arithmetic
uses Decimal with an explicit rounding mode, so results never depend on floats.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, localcontext

CURRENCY_EXPONENTS = {
    "EUR": 2,
    "USD": 2,
    "GBP": 2,
    "CHF": 2,
    "KZT": 2,
    "AED": 2,
    "JPY": 0,
    "KRW": 0,
    "KWD": 3,
    "BHD": 3,
}

ROUNDING_MODES = {
    "half_even": ROUND_HALF_EVEN,
    "half_up": ROUND_HALF_UP,
}


def exponent(currency: str, exponents: dict | None = None) -> int:
    table = exponents if exponents is not None else CURRENCY_EXPONENTS
    if currency not in table:
        raise KeyError(f"unknown currency {currency!r}")
    return int(table[currency])


def to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        raise TypeError("floats are not allowed for money or rates")
    return Decimal(str(value))


def round_to_int(value: Decimal, rounding: str) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUNDING_MODES[rounding]))


def convert_minor(amount_minor: int, rate, src_exp: int, dst_exp: int, rounding: str) -> int:
    """Convert integer minor units of the source currency into target minor units.

    target = round(amount_minor * rate * 10^(dst_exp - src_exp))
    """
    with localcontext() as ctx:
        ctx.prec = 60
        value = Decimal(int(amount_minor)) * to_decimal(rate) * (Decimal(10) ** (dst_exp - src_exp))
        return round_to_int(value, rounding)


def proportional_minor(total_minor: int, part: int, whole: int, rounding: str) -> int:
    """round(total_minor * part / whole) with the policy rounding mode."""
    if whole == 0:
        raise ZeroDivisionError("whole must be non-zero")
    with localcontext() as ctx:
        ctx.prec = 60
        value = Decimal(int(total_minor)) * Decimal(int(part)) / Decimal(int(whole))
        return round_to_int(value, rounding)


def format_minor(amount_minor: int, exp: int) -> str:
    """Human-readable decimal string, e.g. (125000, 2) -> '1250.00'."""
    sign = "-" if amount_minor < 0 else ""
    digits = str(abs(int(amount_minor)))
    if exp == 0:
        return sign + digits
    digits = digits.rjust(exp + 1, "0")
    return f"{sign}{digits[:-exp]}.{digits[-exp:]}"


def quantize_rate(value: Decimal, places: int) -> str:
    """Rate as a plain decimal string with a fixed number of places."""
    q = Decimal(1).scaleb(-places)
    with localcontext() as ctx:
        ctx.prec = 60
        return format(value.quantize(q, rounding=ROUND_HALF_EVEN), "f")
