"""Per-episode public ID schemes.

IDs are random tokens (never sequential), unique across all tables of an
episode, and never contain ':' (reserved for FX record IDs). They carry no
information about injected errors: every record gets its ID from the same
generator, in an order that does not depend on the error plan.
"""

from __future__ import annotations

import random

STYLES = ("prefixed", "slashed", "hex", "numeric")

_PREFIXES = {
    "prefixed": {
        "sales_invoice": "INV-",
        "purchase_invoice": "BILL-",
        "receipt": "RCPT-",
        "disbursement": "PAY-",
        "refund": "RFND-",
        "doc": "DOC-",
        "row": "GL-",
        "customer": "C-",
        "supplier": "S-",
    },
    "slashed": {
        "sales_invoice": "SI/{y}/",
        "purchase_invoice": "PI/{y}/",
        "receipt": "BR/{y}/",
        "disbursement": "BP/{y}/",
        "refund": "RF/{y}/",
        "doc": "D/{y}/",
        "row": "J/{y}/",
        "customer": "CU/",
        "supplier": "SU/",
    },
    "hex": {
        "sales_invoice": "si_",
        "purchase_invoice": "pi_",
        "receipt": "rc_",
        "disbursement": "dp_",
        "refund": "rf_",
        "doc": "doc_",
        "row": "gl_",
        "customer": "cus_",
        "supplier": "sup_",
    },
    "numeric": {
        "sales_invoice": "1",
        "purchase_invoice": "2",
        "receipt": "3",
        "disbursement": "4",
        "refund": "5",
        "doc": "8",
        "row": "9",
        "customer": "6",
        "supplier": "7",
    },
}

_DIGITS = {"prefixed": 6, "slashed": 6, "hex": 8, "numeric": 7}


class IdFactory:
    def __init__(self, rng: random.Random, style: str, year: int):
        if style not in STYLES:
            raise ValueError(f"unknown id style {style!r}")
        self.rng = rng
        self.style = style
        self.year = year
        self.used: set[str] = set()

    def _token(self) -> str:
        n = _DIGITS[self.style]
        if self.style == "hex":
            return "".join(self.rng.choice("0123456789abcdef") for _ in range(n))
        first = self.rng.choice("123456789")
        return first + "".join(self.rng.choice("0123456789") for _ in range(n - 1))

    def new(self, kind: str) -> str:
        prefix = _PREFIXES[self.style][kind].format(y=self.year)
        for _ in range(10000):
            candidate = prefix + self._token()
            if candidate not in self.used:
                self.used.add(candidate)
                return candidate
        raise RuntimeError("id space exhausted")
