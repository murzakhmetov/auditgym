"""Evidence-only checker: a second, independent implementation of the rules.

Given one issue type and the cited record IDs, derive (type, affected ID set, amount) from those records and the
published policy alone. This module deliberately shares no helper with the auditor or with money.py:

  * UTC offsets are read from policy.utc_offset_schedule and parsed here;
  * the duplicate signature is built here from the fields named in policy.duplicate_rule;
  * FX conversion uses fractions.Fraction with explicit rounding per policy.rounding.mode.

Imports: the standard library, timeutil.parse_ts (ISO timestamp parsing) and the Episode container only.
"""

from __future__ import annotations

from datetime import date, timedelta
from fractions import Fraction

from .episode import Episode
from .timeutil import parse_ts

# Fields that make two invoices duplicates; every name must appear in policy.duplicate_rule.
DUPLICATE_FIELDS = ("kind", "entity_id", "currency", "total_minor", "issued_at")
LINE_FIELDS = ("description", "quantity", "unit_price_minor", "amount_minor", "ref")
TOLERANCE_MINOR = 2


def _offset_minutes(text: str) -> int:
    sign = -1 if text.startswith("-") else 1
    hh, mm = text[1:].split(":")
    return sign * (int(hh) * 60 + int(mm))


def _local_date(inst, schedule: list) -> date:
    """Company-local calendar date of an instant: the offset in force is the last entry with from_utc <= instant."""
    entries = sorted((parse_ts(e["from_utc"]), _offset_minutes(e["offset"])) for e in schedule)
    offset = entries[0][1]
    for start, off in entries:
        if start <= inst:
            offset = off
    return (inst + timedelta(minutes=offset)).date()


def _round_fraction(value: Fraction, mode: str) -> int:
    floor = value.numerator // value.denominator
    rest = value - floor
    if rest > Fraction(1, 2):
        return floor + 1
    if rest < Fraction(1, 2):
        return floor
    if mode == "half_up":  # half away from zero
        return floor + 1 if value > 0 else floor
    if mode == "half_even":
        return floor if floor % 2 == 0 else floor + 1
    raise ValueError(f"unknown rounding mode {mode!r}")


def convert_fraction(amount_minor: int, rate, src_exp: int, dst_exp: int, mode: str) -> int:
    """round(amount_minor * rate * 10^(dst_exp - src_exp)) in exact rational arithmetic."""
    value = Fraction(int(amount_minor)) * Fraction(str(rate)) * Fraction(10) ** (dst_exp - src_exp)
    return _round_fraction(value, mode)


def _duplicate_signature(doc: dict, rule_text: str):
    if any(name not in rule_text for name in DUPLICATE_FIELDS + LINE_FIELDS):
        return None  # the published rule does not name the fields this checker relies on
    head = tuple(parse_ts(doc[f]) if f == "issued_at" else doc[f] for f in DUPLICATE_FIELDS)
    return head + (tuple(tuple(li[f] for f in LINE_FIELDS) for li in doc["line_items"]),)


def derive_from_evidence(issue_type: str, evidence: list, ep: Episode) -> tuple | None:
    """Derive (type, frozenset of affected IDs, amount) from the cited records only; None when they do not support it."""
    pol = ep.policy
    base = pol["base_currency"]
    exps = pol["currency_exponents"]
    mode = pol["rounding"]["mode"]
    p0, p1 = parse_ts(pol["reporting_period"]["start"]), parse_ts(pol["reporting_period"]["end"])
    schedule = pol["utc_offset_schedule"]
    holidays = set(pol["fx"]["publication_calendar"]["holidays_without_rates"])
    rows = {r["row_id"]: r for r in ep.ledger}
    docs = {d["doc_id"]: d for d in ep.invoices + ep.payments}
    fxs = {f"{r['date']}:{r['source_currency']}:{r['target_currency']}": r for r in ep.fx}
    cited_rows = [rows[e] for e in evidence if e in rows]
    cited_docs = [docs[e] for e in evidence if e in docs]
    cited_fx = [fxs[e] for e in evidence if e in fxs]
    if len(cited_rows) + len(cited_docs) + len(cited_fx) != len(evidence):
        return None

    def key_of(doc):
        return doc.get("invoice_id") if "invoice_id" in doc else doc.get("payment_id")

    def refers(row, doc):
        return row["invoice_id"] == doc.get("invoice_id") if "invoice_id" in doc else row["payment_id"] == doc.get("payment_id")

    def published(d: date) -> bool:
        return d.weekday() < 5 and d.isoformat() not in holidays

    if issue_type == "duplicate_invoice":
        if len(cited_docs) != 2 or len(cited_rows) != 2 or cited_fx:
            return None
        a, b = cited_docs
        if "invoice_id" not in a or "invoice_id" not in b:
            return None
        sig_a, sig_b = _duplicate_signature(a, pol["duplicate_rule"]), _duplicate_signature(b, pol["duplicate_rule"])
        if sig_a is None or sig_a != sig_b:
            return None
        ra = [r for r in cited_rows if r["invoice_id"] == a["invoice_id"]]
        rb = [r for r in cited_rows if r["invoice_id"] == b["invoice_id"]]
        if len(ra) != 1 or len(rb) != 1 or ra[0]["account"] != rb[0]["account"]:
            return None
        amt = ra[0]["debit_minor"] or ra[0]["credit_minor"]
        if amt != (rb[0]["debit_minor"] or rb[0]["credit_minor"]):
            return None
        return issue_type, frozenset({a["invoice_id"], b["invoice_id"]}), amt
    if issue_type == "unallocated_payment":
        pays = [d for d in cited_docs if "payment_id" in d]
        invs = [d for d in cited_docs if "invoice_id" in d]
        if len(pays) != 1 or len(invs) != 1 or len(cited_rows) != 1 or cited_fx:
            return None
        p, i, r = pays[0], invs[0], cited_rows[0]
        ok = (p["kind"] == "receipt" and p["invoice_refs"] and i["invoice_id"] in p["invoice_refs"]
              and i["kind"] == "sales" and i["currency"] == p["currency"] and i["total_minor"] >= p["amount_minor"]
              and r["account"] == "2900" and r["credit_minor"] > 0 and r["payment_id"] == p["payment_id"])
        return (issue_type, frozenset({p["payment_id"], i["invoice_id"]}), r["credit_minor"]) if ok else None
    if issue_type == "wrong_fx_rate":
        if len(cited_docs) != 1 or len(cited_rows) != 1 or len(cited_fx) != 1:
            return None
        doc, row, fx = cited_docs[0], cited_rows[0], cited_fx[0]
        if doc["currency"] == base or not refers(row, doc) or fx["source_currency"] != doc["currency"] or fx["target_currency"] != base:
            return None
        inst = parse_ts(doc["issued_at"] if "invoice_id" in doc else doc["timestamp"])
        local_d = _local_date(inst, schedule)
        fx_d = date.fromisoformat(fx["date"])
        if fx_d > local_d or any(published(fx_d + timedelta(days=k)) for k in range(1, (local_d - fx_d).days + 1)):
            return None
        amount = doc["total_minor"] if "invoice_id" in doc else doc["amount_minor"]
        expected = convert_fraction(amount, fx["rate"], exps[doc["currency"]], exps[base], mode)
        posted = row["debit_minor"] or row["credit_minor"]
        if "invoice_id" not in doc and row["account"] != "1000":
            return None
        delta = abs(posted - expected)
        return (issue_type, frozenset({key_of(doc)}), delta) if delta > TOLERANCE_MINOR else None
    if issue_type == "wrong_period":
        if len(cited_docs) != 1 or len(cited_rows) != 1 or cited_fx:
            return None
        doc, row = cited_docs[0], cited_rows[0]
        if not refers(row, doc):
            return None
        inst = parse_ts(doc["issued_at"] if "invoice_id" in doc else doc["timestamp"])
        post = parse_ts(row["timestamp"])
        if (p0 <= inst < p1) == (p0 <= post < p1):
            return None
        if "invoice_id" not in doc and row["account"] != "1000":
            return None
        return issue_type, frozenset({key_of(doc)}), row["debit_minor"] or row["credit_minor"]
    return None
