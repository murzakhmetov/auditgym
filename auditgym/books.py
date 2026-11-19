"""Bookkeeping engine: hidden history + booking overrides -> ledger lines.

The same engine produces the clean books (no overrides) and the erroneous books
(overrides from inject.py), so every consequence of an injected error is
derived by the policy rules instead of being patched by hand.

Policy implemented here (published in policy.json):
  * invoice posting at the posting timestamp (normally issued_at), base amount
    = round(total * rate(local date of issued_at)), sales Dr 1100 / Cr 4000,
    purchases Dr 5000 / Cr 2000;
  * receipt: Dr 1000 at the payment-date rate; allocate to invoice_refs in the
    listed order, each up to its open balance in document currency; AR relief
    at the booked carrying amount (proportional; the allocation that closes an
    item relieves the remainder); unallocated remainder or null refs -> Cr 2900
    at the payment-date rate; difference -> 7900;
  * disbursement: Dr 2000 relief / Cr 1000, difference -> 7900;
  * refund of a customer credit: Dr 2900 at its carrying amount / Cr 1000,
    difference -> 7900;
  * opening journals at period start for items open before it, and the bank
    opening balance, against 3900.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .history import History, Invoice
from .money import convert_minor, proportional_minor


class BooksError(RuntimeError):
    pass


@dataclass
class Overrides:
    inv_rate: dict = field(default_factory=dict)  # invoice key -> rate string used
    inv_ts: dict = field(default_factory=dict)  # invoice key -> posting datetime
    pay_rate: dict = field(default_factory=dict)
    pay_ts: dict = field(default_factory=dict)
    pay_alloc: dict = field(default_factory=dict)  # payment key -> total allocated (document minor units)
    extra_invoices: list = field(default_factory=list)  # duplicate copies


@dataclass
class LLine:
    ident: tuple
    journal: tuple
    seq: int
    order: int
    ts: datetime
    account: str
    debit: int
    credit: int
    entity: str | None
    invoice: str | None
    payment: str | None
    role: str


@dataclass
class Books:
    lines: list
    booked: dict  # invoice key -> {"rate", "base", "ts"}
    pay_info: dict  # payment key -> details
    invoices: dict  # all invoices posted (history + extra copies)


def policy_rate(h: History, ccy: str, d: date) -> tuple[str, date]:
    if ccy == h.base:
        return "1", d
    for back in range(15):
        day = d - timedelta(days=back)
        r = h.fx.get((day, ccy, h.base))
        if r is not None:
            return r, day
    raise BooksError(f"no FX rate for {ccy} on or before {d}")


def post(h: History, ov: Overrides | None = None) -> Books:
    ov = ov or Overrides()
    invoices: dict[str, Invoice] = dict(h.invoices)
    for inv in ov.extra_invoices:
        invoices[inv.key] = inv
    events = []
    for inv in invoices.values():
        events.append((ov.inv_ts.get(inv.key, inv.issued), 0, inv.key))
    for p in h.payments.values():
        events.append((ov.pay_ts.get(p.key, p.ts), 1, p.key))
    for m in h.misc.values():
        events.append((m.ts, 2, m.key))
    events.sort()

    lines: list[LLine] = []
    booked: dict = {}
    pay_info: dict = {}
    open_items: dict[str, list] = {}  # invoice key -> [doc_open, base_open]
    credits: dict[str, list] = {}  # invoice key -> [doc, base] overpayment credit in 2900
    exp = h.exponents
    seq_counter = [0]

    def emit(journal, ts, account, debit, credit, entity, invoice, payment, role, ident_extra=None):
        if not (h.p0 <= ts < h.cutoff_end):
            return
        if debit < 0 or credit < 0 or (debit == 0) == (credit == 0):
            raise BooksError(f"bad amounts on {journal} {role}: {debit}/{credit}")
        ident = (journal, role, ident_extra)
        lines.append(LLine(ident, journal, seq_counter[0], len(lines), ts, account, debit, credit, entity, invoice, payment, role))

    def opening():
        seq_counter[0] += 1
        items = sorted((k for k, v in open_items.items() if v[0] > 0 and booked[k]["ts"] < h.p0),
                       key=lambda k: (invoices[k].issued, k))
        for k in items:
            inv = invoices[k]
            base = open_items[k][1]
            j = ("open", k)
            if inv.kind == "sales":
                emit(j, h.p0, "1100", base, 0, inv.entity, k, None, "opening_item", k)
                emit(j, h.p0, "3900", 0, base, inv.entity, k, None, "opening_counter", k)
            else:
                emit(j, h.p0, "3900", base, 0, inv.entity, k, None, "opening_counter", k)
                emit(j, h.p0, "2000", 0, base, inv.entity, k, None, "opening_item", k)
            seq_counter[0] += 1
        if h.opening_bank:
            emit(("open_bank",), h.p0, "1000", h.opening_bank, 0, None, None, None, "opening_bank_dr")
            emit(("open_bank",), h.p0, "3900", 0, h.opening_bank, None, None, None, "opening_bank_cr")

    opened = False
    for ts, kind, key in events:
        if not opened and ts >= h.p0:
            opening()
            opened = True
        if ts >= h.cutoff_end:
            continue
        seq_counter[0] += 1
        if kind == 0:
            inv = invoices[key]
            if key in ov.inv_rate:
                rate = ov.inv_rate[key]
            else:
                rate, _ = policy_rate(h, inv.currency, h.local_date(inv.issued))
            base = convert_minor(inv.total, rate, exp[inv.currency], exp[h.base], h.rounding)
            booked[key] = {"rate": rate, "base": base, "ts": ts}
            open_items[key] = [inv.total, base]
            j = ("inv", key)
            if inv.kind == "sales":
                emit(j, ts, "1100", base, 0, inv.entity, key, None, "primary", key)
                emit(j, ts, "4000", 0, base, inv.entity, key, None, "counter", key)
            else:
                emit(j, ts, "5000", base, 0, inv.entity, key, None, "counter", key)
                emit(j, ts, "2000", 0, base, inv.entity, key, None, "primary", key)
        elif kind == 1:
            p = h.payments[key]
            if key in ov.pay_rate:
                rate = ov.pay_rate[key]
            else:
                rate, _ = policy_rate(h, p.currency, h.local_date(p.ts))
            bank = convert_minor(p.amount, rate, exp[p.currency], exp[h.base], h.rounding)
            j = ("pay", key)
            info = {"rate": rate, "bank": bank, "ts": ts, "allocs": [], "unalloc_doc": 0, "unalloc_base": 0, "fx": 0}
            if p.kind in ("receipt", "disbursement"):
                remaining = p.amount
                cap = ov.pay_alloc.get(key)
                allocated = 0
                for ref in p.refs or []:
                    item = open_items.get(ref)
                    if item is None or item[0] <= 0:
                        continue
                    a = min(remaining, item[0])
                    if cap is not None:
                        a = min(a, cap - allocated)
                    if a <= 0:
                        continue
                    relief = item[1] if a == item[0] else proportional_minor(item[1], a, item[0], h.rounding)
                    item[0] -= a
                    item[1] -= relief
                    remaining -= a
                    allocated += a
                    info["allocs"].append((ref, a, relief))
                unalloc_doc = remaining
                unalloc_base = convert_minor(unalloc_doc, rate, exp[p.currency], exp[h.base], h.rounding) if unalloc_doc else 0
                info["unalloc_doc"], info["unalloc_base"] = unalloc_doc, unalloc_base
                reliefs = sum(r for _, _, r in info["allocs"])
                if p.kind == "receipt":
                    fx = bank - reliefs - unalloc_base
                    emit(j, ts, "1000", bank, 0, p.entity, None, key, "bank")
                    for ref, _a, relief in info["allocs"]:
                        if relief:
                            emit(j, ts, "1100", 0, relief, p.entity, ref, key, "relief", ref)
                    if unalloc_base:
                        emit(j, ts, "2900", 0, unalloc_base, p.entity, None, key, "unalloc")
                        if p.refs:
                            c = credits.setdefault(p.refs[0], [0, 0])
                            c[0] += unalloc_doc
                            c[1] += unalloc_base
                    if fx > 0:
                        emit(j, ts, "7900", 0, fx, p.entity, None, key, "fx")
                    elif fx < 0:
                        emit(j, ts, "7900", -fx, 0, p.entity, None, key, "fx")
                else:
                    if unalloc_doc:
                        raise BooksError("disbursement exceeds open payables")
                    fx = reliefs - bank
                    for ref, _a, relief in info["allocs"]:
                        emit(j, ts, "2000", relief, 0, p.entity, ref, key, "relief", ref)
                    if fx > 0:
                        emit(j, ts, "7900", 0, fx, p.entity, None, key, "fx")
                    elif fx < 0:
                        emit(j, ts, "7900", -fx, 0, p.entity, None, key, "fx")
                    emit(j, ts, "1000", 0, bank, p.entity, None, key, "bank")
                info["fx"] = fx
            elif p.kind == "refund":
                c = credits.get(p.refs[0]) if p.refs else None
                if c is None or c[0] < p.amount:
                    raise BooksError("refund exceeds customer credit")
                relief = c[1] if p.amount == c[0] else proportional_minor(c[1], p.amount, c[0], h.rounding)
                c[0] -= p.amount
                c[1] -= relief
                fx = relief - bank
                emit(j, ts, "2900", relief, 0, p.entity, None, key, "credit_relief")
                if fx > 0:
                    emit(j, ts, "7900", 0, fx, p.entity, None, key, "fx")
                elif fx < 0:
                    emit(j, ts, "7900", -fx, 0, p.entity, None, key, "fx")
                emit(j, ts, "1000", 0, bank, p.entity, None, key, "bank")
                info.update({"credit_relief": relief, "fx": fx})
            else:
                raise BooksError(f"unknown payment kind {p.kind}")
            pay_info[key] = info
        else:
            m = h.misc[key]
            j = ("misc", key)
            for i, (acct, dr, cr) in enumerate(m.lines):
                emit(j, m.ts, acct, dr, cr, None, None, None, f"m{i}")
    if not opened:
        opening()
    return Books(lines=lines, booked=booked, pay_info=pay_info, invoices=invoices)


def count_rows(books: Books) -> int:
    return len(books.lines)
