"""Evidence-only checker: a second, independent implementation of the rules.

Given one issue type and the cited record IDs, derive (type, affected ID set, amount) from those records and the
published policy alone. The one exception is the completeness of an unallocated_payment set: the published evidence is
"every ledger row of the invoice on its receivable account 1100", so the checker also reads the ledger to see that no such
row is left out (a set that omits the relief of an earlier part payment shows a larger balance than the invoice had).
This module deliberately shares no helper with the auditor or with money.py:

  * UTC offsets are read from policy.utc_offset_schedule and parsed here;
  * the duplicate signature is built here from the fields named in policy.duplicate_rule (issued_at is not one of them:
    when the two instants differ the rule must state that it need not be identical, and the amount is the later row);
  * FX conversion uses fractions.Fraction with explicit rounding per policy.rounding.mode.

Imports: the standard library, timeutil.parse_ts (ISO timestamp parsing) and the Episode container only.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from fractions import Fraction

from .episode import Episode
from .timeutil import parse_ts

# Fields that make two invoices duplicates; every name must appear in policy.duplicate_rule. issued_at is not one of them,
# but when the two instants differ the rule must say so (REKEY_CLAUSE), or the checker derives nothing.
DUPLICATE_FIELDS = ("kind", "entity_id", "currency", "total_minor")
REKEY_CLAUSE = "issued_at need not be identical"
# The accounts an invoice of each kind posts to: receivable and revenue, payable and expense.
POSTING_ACCOUNTS = {"sales": ("1100", "4000"), "purchase": ("2000", "5000")}
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


# A plain ASCII decimal with at most 30 digits on each side of the point and an optional exponent. Fraction() alone
# also reads "_" separators and non-ASCII digits, so "1e9999_9999" would reach 10 ** 99999999 and never finish.
_RATE_TEXT = re.compile(r"\s*[+-]?(?:[0-9]{1,30}(?:\.[0-9]{0,30})?|\.[0-9]{1,30})(?:[eE]([+-]?[0-9]+))?\s*", re.ASCII)


def _rate_fraction(rate) -> Fraction:
    """Fraction(str(rate)) for a plain decimal, refusing an exponent above 64 and any other form."""
    text = str(rate)
    m = _RATE_TEXT.fullmatch(text)
    if m is None:
        raise ValueError(f"not a decimal rate: {text[:40]!r}")
    if m.group(1) and (len(m.group(1).lstrip("+-")) > 3 or abs(int(m.group(1))) > 64):
        raise ValueError(f"exponent out of range in {text[:40]!r}")
    return Fraction(text)


def convert_fraction(amount_minor: int, rate, src_exp: int, dst_exp: int, mode: str) -> int:
    """round(amount_minor * rate * 10^(dst_exp - src_exp)) in exact rational arithmetic."""
    value = Fraction(int(amount_minor)) * _rate_fraction(rate) * Fraction(10) ** (dst_exp - src_exp)
    return _round_fraction(value, mode)


def _duplicate_signature(doc: dict, rule_text: str):
    if any(name not in rule_text for name in DUPLICATE_FIELDS + LINE_FIELDS):
        return None  # the published rule does not name the fields this checker relies on
    head = tuple(doc[f] for f in DUPLICATE_FIELDS)
    return head + (tuple(tuple(li[f] for f in LINE_FIELDS) for li in doc["line_items"]),)


def _receivable_story(evidence: list, cited_docs: list, cited_rows: list, cited_fx: list, base: str, ledger: list) -> tuple | None:
    """unallocated_payment from the cited records only: the receipt, the sales invoice, the receipt's 2900 row, every
    receivable (1100) row of the invoice and, for a foreign-currency invoice, the receipt's bank (1000) row. Returns
    (payment, invoice, 2900 row, posted, relieved) or None. The invoice's open balance is derived from the 1100 rows
    (debits minus credits, base currency) rather than from the document total, and the story must be closed: the only
    relief among the cited rows is this receipt's and it does not exceed what the receipt paid. In the base currency the
    balance posted on the cited rows covers the receipt and the receipt is exactly its relief plus the 2900 amount. In a
    foreign currency the rows carry base amounts only and the 2900 amount carries the payment-date rate, so the bank row
    (the whole receipt at that rate) is cited: with no relief the whole bank amount sits in 2900, with a relief 2900 holds
    less than the bank amount. The covering test in a foreign currency stays on the document total. Receivable rows of the
    invoice from earlier receipts are allowed (booked before this one: part payments that left the balance), but the set
    must hold every receivable row the invoice has on the ledger, so a set that leaves an earlier relief out (and so shows a
    larger balance than the invoice had) derives nothing."""
    pays = [d for d in cited_docs if "payment_id" in d]
    invs = [d for d in cited_docs if "invoice_id" in d]
    if len(pays) != 1 or len(invs) != 1 or len(cited_rows) < 2 or cited_fx or len(set(evidence)) != len(evidence):
        return None
    p, i = pays[0], invs[0]
    if not (p["kind"] == "receipt" and p["invoice_refs"] and i["invoice_id"] in p["invoice_refs"]
            and i["kind"] == "sales" and i["currency"] == p["currency"] and i["total_minor"] >= p["amount_minor"]):
        return None
    foreign = i["currency"] != base
    bank = [r for r in cited_rows if r["account"] == "1000"]
    unalloc = [r for r in cited_rows if r["account"] == "2900"]
    receivable = [r for r in cited_rows if r["account"] not in ("2900", "1000")]
    if len(unalloc) != 1 or not receivable or len(bank) != (1 if foreign else 0):
        return None
    u = unalloc[0]
    if u["credit_minor"] <= 0 or u["payment_id"] != p["payment_id"]:
        return None
    if bank and not (bank[0]["payment_id"] == p["payment_id"] and bank[0]["debit_minor"] > 0 and bank[0]["credit_minor"] == 0):
        return None
    cited_ids = {r["row_id"] for r in cited_rows}
    if any(r["invoice_id"] == i["invoice_id"] and r["account"] == "1100" and r["row_id"] not in cited_ids for r in ledger):
        return None  # a receivable row of the invoice is left out: the balance on the cited rows is not the invoice's balance
    posted = relieved = prior = 0
    for r in receivable:
        if r["account"] != "1100" or r["invoice_id"] != i["invoice_id"]:
            return None
        if r["debit_minor"] > 0:
            if r["payment_id"] is not None:
                return None  # a debit tied to a payment is not the invoice's posting
            if parse_ts(r["timestamp"]) > parse_ts(u["timestamp"]):
                return None  # booked after the receipt: the receipt could not have found the balance open
            posted += r["debit_minor"]
        elif r["payment_id"] == p["payment_id"]:
            relieved += r["credit_minor"]
        elif r["payment_id"] is not None and r["credit_minor"] > 0 and parse_ts(r["timestamp"]) < parse_ts(u["timestamp"]):
            prior += r["credit_minor"]  # an earlier payment already relieved part of the invoice: the balance is what is left
        else:
            return None  # a credit from nowhere or booked after the receipt: the invoice may be settled elsewhere
    if posted <= 0 or posted - prior - relieved <= 0:
        return None  # no booked balance, or nothing left open for the 2900 amount to belong to
    if 2 * relieved * i["total_minor"] > 2 * posted * p["amount_minor"] + i["total_minor"]:
        return None  # the receipt cannot have relieved more of the invoice than it paid (proportional carrying amount)
    if not foreign and (p["amount_minor"] > posted - prior or relieved + u["credit_minor"] != p["amount_minor"]):
        return None  # base currency: the open balance covers the receipt, which is exactly its relief plus the 2900 amount
    if foreign and (u["credit_minor"] != bank[0]["debit_minor"] if relieved == 0 else u["credit_minor"] >= bank[0]["debit_minor"]):
        return None  # foreign currency: all of the bank amount sits in 2900 when nothing was relieved, else part of it
    return p, i, u, posted - prior, relieved


def unallocated_open_balance(evidence: list, ep: Episode) -> tuple | None:
    """(balance before the receipt, balance after its relief) of the invoice, in base currency, derived from the cited
    receivable rows of an unallocated_payment evidence set; None when the set does not support the story."""
    rows = {r["row_id"]: r for r in ep.ledger}
    docs = {d["doc_id"]: d for d in ep.invoices + ep.payments}
    fxs = {f"{r['date']}:{r['source_currency']}:{r['target_currency']}" for r in ep.fx}
    cited_rows = [rows[e] for e in evidence if e in rows]
    cited_docs = [docs[e] for e in evidence if e in docs]
    cited_fx = [e for e in evidence if e in fxs]
    if any(e not in rows and e not in docs and e not in fxs for e in evidence):
        return None
    story = _receivable_story(evidence, cited_docs, cited_rows, cited_fx, ep.policy["base_currency"], ep.ledger)
    return None if story is None else (story[3], story[3] - story[4])


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
        if a["invoice_id"] == b["invoice_id"]:
            return None
        ra = [r for r in cited_rows if r["invoice_id"] == a["invoice_id"]]
        rb = [r for r in cited_rows if r["invoice_id"] == b["invoice_id"]]
        if len(ra) != 1 or len(rb) != 1 or ra[0]["account"] != rb[0]["account"]:
            return None
        # each row is its own invoice's posting (no payment relief) in an account the invoice kind posts to, booked in the
        # period of the invoice (a posting is booked at its own moment, which may differ from issued_at inside the
        # period: policy posting_rules.posting_timestamp); the amount is the row of the later copy
        if ra[0]["account"] not in POSTING_ACCOUNTS[a["kind"]]:
            return None
        for doc, row in ((a, ra[0]), (b, rb[0])):
            if row["payment_id"] is not None:
                return None
            if (p0 <= parse_ts(row["timestamp"]) < p1) != (p0 <= parse_ts(doc["issued_at"]) < p1):
                return None
        amt_a = ra[0]["debit_minor"] or ra[0]["credit_minor"]
        amt_b = rb[0]["debit_minor"] or rb[0]["credit_minor"]
        inst_a, inst_b = parse_ts(a["issued_at"]), parse_ts(b["issued_at"])
        if inst_a == inst_b:
            if amt_a != amt_b:
                return None  # copies of one instant post equal amounts
        elif REKEY_CLAUSE not in pol["duplicate_rule"]:
            return None  # the published rule does not say that a later copy may carry another issued_at
        # the amount is the row of the later document (equal instants: either row, they are equal)
        later = amt_b if (inst_b, b["invoice_id"]) >= (inst_a, a["invoice_id"]) else amt_a
        return issue_type, frozenset({a["invoice_id"], b["invoice_id"]}), later
    if issue_type == "unallocated_payment":
        story = _receivable_story(evidence, cited_docs, cited_rows, cited_fx, base, ep.ledger)
        if story is None:
            return None
        return issue_type, frozenset({story[0]["payment_id"], story[1]["invoice_id"]}), story[2]["credit_minor"]
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
