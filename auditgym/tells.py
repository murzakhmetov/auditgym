"""Shortcut-tell measurement: how well single public features pick out the answer key.

The rules, the context they read and the pooled measurement live here so that the regression test
(tests/test_tells.py, 20 open episodes) and the large reproducible run use one implementation:

    python -m auditgym.tells --n 200 --out runs/tells

generates N episodes from a public master string with the check-set config mix (auditgym.splits.check_set, one
batch of 20 per derived master), measures every document rule, the residual tells (largest foreign purchase,
off-hours payment) and the episode-level rules, and writes summary.md and summary.json. The files hold no
timings and are byte-identical across runs; the elapsed time goes to stdout only.

Line-identical pairs. Decoys (legit_repeat) and the sources of duplicate_invoice errors are drawn by one builder and
a duplicate is a converted pair, so a pair is a duplicate with the same chance whatever its side, shape (the two
invoices carry one instant, or the second is keyed 2 to 9 days later), currency, price, item, terms or payment status.
The rules on pairs (a twin by side, a later line-identical repeat by side, the later member, a foreign-currency pair, a
pair under 300 USD, a subscription item, an earlier member that was paid, a member posted off its issued_at) measure
that; the old generator failed them (a subscription item and a 300 USD floor only on duplicates, a purchase-only pool).
The CLI adds two kinds of rules that need many episodes (PAIR_COUNT_RULES: the number of pairs of an episode against its
size and the number of pairs against the duplicate count) and the table of pairs and duplicates by side and shape.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from . import catalog
from .auditor import OffsetSchedule
from .money import CURRENCY_EXPONENTS
from .timeutil import parse_ts

DEFAULT_MASTER = "auditgym-tells-v1"
BATCH = 20

SPEC_PRECISION, SPEC_RECALL = 0.5, 0.3
STRONG_PRECISION, STRONG_HITS = 0.8, 3

PAIR_MAX_GAP = timedelta(days=10)  # two line-identical invoices further apart are not a pair (2 to 9 days later, plus hours)

SALES = {d: (p, q) for d, p, q in catalog.SALES_ITEMS}
PURCHASES = [(t.split("{")[0].strip(), p) for t, p, _ in catalog.PURCHASE_ITEMS]


def usd(minor: int, ccy: str) -> float:
    return float(Decimal(minor) / (Decimal(10) ** CURRENCY_EXPONENTS[ccy]) * Decimal(catalog.USD_VALUE[ccy]))


def outside_catalogue(inv: dict) -> bool:
    for li in inv["line_items"]:
        if inv["kind"] == "sales":
            (plo, phi), (qlo, qhi) = SALES[li["description"]]
            if not qlo <= li["quantity"] <= qhi:
                return True
        else:
            plo, phi = next(p for prefix, p in PURCHASES if li["description"].startswith(prefix))
        price = usd(li["unit_price_minor"], inv["currency"])
        if not plo * 0.97 <= price <= phi * 1.03:
            return True
    return False


class Ctx:
    """Public view of one episode."""

    def __init__(self, ep):
        self.ep = ep
        self.sched = OffsetSchedule(ep.policy["utc_offset_schedule"])
        self.base = ep.manifest["base_currency"]
        self.p0 = parse_ts(ep.policy["reporting_period"]["start"])
        self.p1 = parse_ts(ep.policy["reporting_period"]["end"])
        self.docs = {}  # id -> (kind, record, instant)
        for inv in ep.invoices:
            self.docs[inv["invoice_id"]] = ("invoice", inv, parse_ts(inv["issued_at"]))
        for p in ep.payments:
            self.docs[p["payment_id"]] = ("payment", p, parse_ts(p["timestamp"]))
        self.paid = {r for p in ep.payments for r in (p["invoice_refs"] or [])}
        self.acct2900 = {r["payment_id"] for r in ep.ledger if r["account"] == "2900" and r["payment_id"]}
        self.rows2900 = sum(1 for r in ep.ledger if r["account"] == "2900")
        self.has1100 = {r["payment_id"] for r in ep.ledger if r["account"] == "1100" and r["payment_id"]}
        self.pay_count = defaultdict(int)  # invoice id -> number of payments that list it
        self.receipt_count = defaultdict(int)  # invoice id -> number of receipts that list it
        for p in ep.payments:
            for r in set(p["invoice_refs"] or []):
                self.pay_count[r] += 1
                self.receipt_count[r] += p["kind"] == "receipt"
        self.opening = {r["invoice_id"] for r in ep.ledger if r["account"] == "3900" and r["invoice_id"]}  # carried in at period start
        self.received = defaultdict(int)  # invoice id -> sum of the receipts that list only it
        for p in ep.payments:
            if p["kind"] == "receipt" and p["invoice_refs"] and len(p["invoice_refs"]) == 1:
                self.received[p["invoice_refs"][0]] += p["amount_minor"]
        self.local_cache = {}
        by_key = defaultdict(list)
        by_lines = defaultdict(list)
        for inv in ep.invoices:
            by_key[(inv["kind"], inv["entity_id"], inv["currency"], inv["total_minor"], parse_ts(inv["issued_at"]))].append(inv["invoice_id"])
            lines = tuple((li["description"].replace(li["ref"], "").strip(), li["quantity"], li["unit_price_minor"], li["amount_minor"])
                          for li in inv["line_items"])
            by_lines[(inv["kind"], inv["entity_id"], inv["currency"], inv["total_minor"], lines)].append(inv["invoice_id"])
        self.twins = {i for ids in by_key.values() if len(ids) > 1 for i in ids}
        by_id = {i["invoice_id"]: i for i in ep.invoices}
        # line-identical pairs (references ignored: the one in a purchase description is stripped), the two invoices at most
        # PAIR_MAX_GAP apart (recurring subscription invoices are 20 or more days apart), ordered by instant and id
        self.pairs = []
        self.pair_shape = {}  # frozenset of the two ids -> "same" (one instant) or "later"
        for group in by_lines.values():
            if len(group) < 2:
                continue
            group = sorted(group, key=lambda i: (parse_ts(by_id[i]["issued_at"]), i))
            n = 0
            while n + 1 < len(group):  # neighbours at most PAIR_MAX_GAP apart; an ordinary invoice of the same price far away does not hide the pair
                ids = group[n:n + 2]
                t0, t1 = (parse_ts(by_id[i]["issued_at"]) for i in ids)
                if t1 - t0 > PAIR_MAX_GAP:
                    n += 1
                    continue
                self.pairs.append(ids)
                self.pair_shape[frozenset(ids)] = "same" if t0 == t1 else "later"
                n += 2
        self.pair_members = {i for ids in self.pairs for i in ids}
        self.pair_later = {ids[1] for ids in self.pairs if self.pair_shape[frozenset(ids)] == "later"}
        self.pair_earlier_of_later = {ids[0] for ids in self.pairs if self.pair_shape[frozenset(ids)] == "later"}
        self.pair_earlier_paid = {i for ids in self.pairs if ids[0] in self.paid for i in ids}  # both members of such a pair
        own_posting = defaultdict(set)  # invoice_id -> instants of its own posting rows (no payment)
        for r in ep.ledger:
            if r["invoice_id"] and not r["payment_id"]:
                own_posting[r["invoice_id"]].add(parse_ts(r["timestamp"]))
        self.off_posting = {i for i in self.pair_members if own_posting[i] - {parse_ts(by_id[i]["issued_at"])}}
        # posting lag: the instant of a document's own posting rows minus the document's instant. Opening items (carried in at
        # period start against 3900) and documents without a posting have none.
        inv_rows, pay_rows = defaultdict(list), defaultdict(list)
        for r in ep.ledger:
            if r["payment_id"]:
                pay_rows[r["payment_id"]].append(r)
            elif r["invoice_id"]:
                inv_rows[r["invoice_id"]].append(r)
        self.lag = {}
        for i, (kind, _rec, inst) in self.docs.items():
            rows = inv_rows[i] if kind == "invoice" else pay_rows[i]
            if rows and not any(r["account"] == "3900" for r in rows):
                self.lag[i] = parse_ts(rows[0]["timestamp"]) - inst
        self.odd_terms_pair = {i for ids in by_key.values() if len(ids) > 1 and any(self.terms(by_id[x]) != 30 for x in ids) for i in ids}
        self.paid_or_odd_pair = {i for ids in by_key.values() if len(ids) > 1
                                 and (any(self.terms(by_id[x]) != 30 for x in ids) or any(x in self.paid for x in ids))
                                 for i in ids}
        self.holidays = set(ep.policy["fx"]["publication_calendar"]["holidays_without_rates"])
        foreign_p = sorted((i for i in ep.invoices if i["kind"] == "purchase" and i["currency"] != self.base),
                           key=lambda i: -usd(i["total_minor"], i["currency"]))
        foreign_s = sorted((i for i in ep.invoices if i["kind"] == "sales" and i["currency"] != self.base),
                           key=lambda i: -usd(i["total_minor"], i["currency"]))
        self.rank_p = {i["invoice_id"]: n for n, i in enumerate(foreign_p, 1)}
        self.rank_s = {i["invoice_id"]: n for n, i in enumerate(foreign_s, 1)}
        every = sorted(ep.invoices, key=lambda i: -usd(i["total_minor"], i["currency"]))
        self.rank_all = {i["invoice_id"]: n for n, i in enumerate(every, 1)}
        self.dominant_p = None  # the largest foreign purchase when it is at least 1.5x the runner-up
        if len(foreign_p) > 1 and usd(foreign_p[0]["total_minor"], foreign_p[0]["currency"]) >= 1.5 * usd(
                foreign_p[1]["total_minor"], foreign_p[1]["currency"]):
            self.dominant_p = foreign_p[0]["invoice_id"]

    def local(self, inst):
        return inst + timedelta(minutes=self.sched.offset_at(inst))

    def minutes_from_boundary(self, inst) -> float:
        return min(abs((inst - self.p0).total_seconds()), abs((inst - self.p1).total_seconds())) / 60.0

    def terms(self, inv) -> int:
        return (self.local(parse_ts(inv["due_at"])).date() - self.local(parse_ts(inv["issued_at"])).date()).days

    def affected(self):
        out = set()
        for issue in self.ep.truth["issues"]:
            out.update(issue["affected_ids"])
        return out


def _inv(c, i):
    return c.docs[i][0] == "invoice"


def _off_hours(c, i):
    h = c.local(c.docs[i][2]).hour
    return h < 8 or h > 18


def _near_midnight(c, i):
    inst = c.docs[i][2]
    return c.local(inst).date() != inst.date()


def _boundary_day(c, i):
    d = c.local(c.docs[i][2]).date()
    return d == c.local(c.p1).date() or d == c.local(c.p1 - timedelta(seconds=1)).date()


def in_error_window(inst, p1, sched) -> bool:
    """The exact minute window of the boundary errors (utc_wall_clock invoices, the boundary receipt): with a positive
    offset minutes 5 to offset-11 of the first day after the period, with a negative offset minutes 1440+offset+11
    to 1434 of the period's last day (local time)."""
    off = sched.offset_at(p1)
    if off == 0:
        return False
    local = inst + timedelta(minutes=sched.offset_at(inst))
    minute = local.hour * 60 + local.minute
    if off > 0:
        return local.date() == (p1 + timedelta(minutes=off)).date() and 5 <= minute <= off - 11
    last = p1 - timedelta(seconds=1)
    return local.date() == (last + timedelta(minutes=sched.offset_at(last))).date() and 1440 + off + 11 <= minute <= 1434


def _boundary_window(c, i, kinds=None):
    kind, rec, inst = c.docs[i]
    label = rec["kind"]
    return (kinds is None or label in kinds) and in_error_window(inst, c.p1, c.sched)


def _pair_side(c, i, side):
    return i in c.twins and c.docs[i][1]["kind"] == side


def _pair_usd(c, i):
    rec = c.docs[i][1]
    return usd(rec["total_minor"], rec["currency"])


def _subscription(c, i):
    return any(li["ref"].startswith("SUB-") for li in c.docs[i][1]["line_items"])


def _lag(c, i) -> timedelta:
    return c.lag.get(i, timedelta(0))


def _lag_is_offset(c, i) -> bool:
    lag = _lag(c, i)
    return lag != timedelta(0) and lag == -timedelta(minutes=c.sched.offset_at(c.docs[i][2]))


def _lag_date_change_foreign(c, i) -> bool:
    kind, rec, inst = c.docs[i]
    return (_lag(c, i) != timedelta(0) and rec["currency"] != c.base
            and c.local(inst + _lag(c, i)).date() != c.local(inst).date())


def _credit_on_single_payment(c, i) -> bool:
    """A payment with a 2900 row whose invoice has exactly one payment (the only one)."""
    refs = c.docs[i][1].get("invoice_refs") if c.docs[i][0] == "payment" else None
    return i in c.acct2900 and bool(refs) and c.pay_count[refs[0]] == 1


def _credit_within_invoice(c, i) -> bool:
    """... and the payment is not larger than the invoice total (no overpayment explains the 2900 row)."""
    if not _credit_on_single_payment(c, i):
        return False
    rec = c.docs[i][1]
    inv = c.docs.get(rec["invoice_refs"][0])
    return inv is not None and inv[0] == "invoice" and rec["amount_minor"] <= inv[1]["total_minor"]


def _relieved_and_credited_with_another_receipt(c, i) -> bool:
    """A receipt with a 1100 row and a 2900 row whose invoice another receipt also lists (a part-paid invoice)."""
    kind, rec, _ = c.docs[i]
    if kind != "payment" or rec["kind"] != "receipt" or not rec["invoice_refs"] or i not in c.acct2900 or i not in c.has1100:
        return False
    return any(c.receipt_count[r] > 1 for r in rec["invoice_refs"])


def _receipt_without_relief(c, i) -> bool:
    """A receipt with invoice references and no 1100 row (nothing relieved a receivable)."""
    kind, rec, _ = c.docs[i]
    return kind == "payment" and rec["kind"] == "receipt" and bool(rec["invoice_refs"]) and i not in c.has1100


def _credit_receipt_refs(c, i) -> list:
    """The invoices listed by a receipt with a 2900 row (empty for anything else)."""
    kind, rec, _ = c.docs[i]
    if kind != "payment" or rec["kind"] != "receipt" or i not in c.acct2900:
        return []
    return [r for r in rec["invoice_refs"] or [] if r in c.docs and c.docs[r][0] == "invoice"]


def _day_of_period(c, inv_id) -> int:
    """Local calendar days from the first day of the period to the invoice's local date (negative for an opening item)."""
    return (c.local(c.docs[inv_id][2]).date() - c.local(c.p0).date()).days


def _credit_on_opening_item(c, i) -> bool:
    """A receipt with a 2900 row that lists an opening-item invoice (one carried in at period start against 3900)."""
    return any(r in c.opening for r in _credit_receipt_refs(c, i))


def _credit_after_invoice_off_days(c, i) -> bool:
    """A receipt with a 2900 row dated after its invoice, the invoice not issued on days 0 to 10 of the period."""
    return any(c.docs[i][2] > c.docs[r][2] and not 0 <= _day_of_period(c, r) <= 10 for r in _credit_receipt_refs(c, i))


def _part_paid_invoice(c, i) -> bool:
    """A sales invoice with two or more receipts that sum to less than its total."""
    kind, rec, _ = c.docs[i]
    return kind == "invoice" and rec["kind"] == "sales" and c.receipt_count[i] >= 2 and c.received[i] < rec["total_minor"]


def _over_received_sales(c) -> int:
    """Sales invoices whose receipts sum to more than the invoice total."""
    return sum(1 for i, (k, rec, _t) in c.docs.items() if k == "invoice" and rec["kind"] == "sales" and c.received[i] > rec["total_minor"])


def _round_amount(c, i):
    kind, rec, _ = c.docs[i]
    amount = rec["total_minor"] if kind == "invoice" else rec["amount_minor"]
    ccy = rec["currency"]
    return amount % (10 ** (CURRENCY_EXPONENTS[ccy] + 2)) == 0


RULES = {
    "qty/price outside catalogue": lambda c, i: _inv(c, i) and outside_catalogue(c.docs[i][1]),
    "sales qty above catalogue max": lambda c, i: _inv(c, i) and c.docs[i][1]["kind"] == "sales" and any(
        li["quantity"] > SALES[li["description"]][1][1] for li in c.docs[i][1]["line_items"]),
    "off-hours invoice": lambda c, i: _inv(c, i) and _off_hours(c, i),
    "off-hours payment": lambda c, i: not _inv(c, i) and _off_hours(c, i),
    "off-hours document": lambda c, i: _off_hours(c, i),
    "near-midnight (UTC date differs) invoice": lambda c, i: _inv(c, i) and _near_midnight(c, i),
    "near-midnight (UTC date differs) payment": lambda c, i: not _inv(c, i) and _near_midnight(c, i),
    "within 12 h of period boundary": lambda c, i: c.minutes_from_boundary(c.docs[i][2]) <= 12 * 60,
    "boundary day, off-hours invoice": lambda c, i: _inv(c, i) and _boundary_day(c, i) and _off_hours(c, i),
    "boundary day, off-hours payment": lambda c, i: not _inv(c, i) and _boundary_day(c, i) and _off_hours(c, i),
    "largest foreign purchase": lambda c, i: c.rank_p.get(i) == 1,
    "dominant foreign purchase (>= 1.5x runner-up)": lambda c, i: c.dominant_p == i,
    "top-3 foreign purchase": lambda c, i: c.rank_p.get(i, 99) <= 3,
    "largest foreign sale": lambda c, i: c.rank_s.get(i) == 1,
    "top-3 foreign sale": lambda c, i: c.rank_s.get(i, 99) <= 3,
    "largest invoice": lambda c, i: c.rank_all.get(i) == 1,
    "weekend date": lambda c, i: c.local(c.docs[i][2]).date().weekday() >= 5,
    "weekday date": lambda c, i: c.local(c.docs[i][2]).date().weekday() < 5,
    "terms not 30 days": lambda c, i: _inv(c, i) and c.terms(c.docs[i][1]) != 30,
    "terms 14 or 45 days": lambda c, i: _inv(c, i) and c.terms(c.docs[i][1]) in (14, 45),
    "unpaid twin invoice": lambda c, i: i in c.twins and i not in c.paid,
    "paid twin invoice": lambda c, i: i in c.twins and i in c.paid,
    "invoice with a twin": lambda c, i: i in c.twins,
    "sales invoice with a twin": lambda c, i: _pair_side(c, i, "sales"),
    "purchase invoice with a twin": lambda c, i: _pair_side(c, i, "purchase"),
    "invoice with a later line-identical repeat (2 to 10 days)": lambda c, i: i in c.pair_earlier_of_later,
    "sales invoice with a later line-identical repeat": lambda c, i: i in c.pair_earlier_of_later and c.docs[i][1]["kind"] == "sales",
    "purchase invoice with a later line-identical repeat": lambda c, i: i in c.pair_earlier_of_later and c.docs[i][1]["kind"] == "purchase",
    "later member of a line-identical pair": lambda c, i: i in c.pair_later,
    "line-identical pair in a foreign currency": lambda c, i: i in c.pair_members and c.docs[i][1]["currency"] != c.base,
    "line-identical pair under 300 USD": lambda c, i: i in c.pair_members and _pair_usd(c, i) < 300,
    "same-instant pair of a subscription item": lambda c, i: i in c.pair_members and _subscription(c, i),
    "line-identical pair, earlier member paid": lambda c, i: i in c.pair_earlier_paid,
    "line-identical pair member posted off its issued_at": lambda c, i: i in c.off_posting,
    "same-instant pair with terms != 30": lambda c, i: i in c.odd_terms_pair,
    "same-instant pair, terms != 30 or one copy paid": lambda c, i: i in c.paid_or_odd_pair,
    "sales invoice in the error window": lambda c, i: _boundary_window(c, i, ("sales",)) and _inv(c, i),
    "purchase invoice in the error window": lambda c, i: _boundary_window(c, i, ("purchase",)) and _inv(c, i),
    "receipt in the error window": lambda c, i: _boundary_window(c, i, ("receipt",)) and not _inv(c, i),
    "disbursement in the error window": lambda c, i: _boundary_window(c, i, ("disbursement",)) and not _inv(c, i),
    "document on an FX holiday": lambda c, i: c.local(c.docs[i][2]).date().isoformat() in c.holidays,
    "payment with a 2900 row": lambda c, i: i in c.acct2900,
    "payment with a 2900 row and invoice refs": lambda c, i: i in c.acct2900 and bool(c.docs[i][1]["invoice_refs"]),
    "payment with a 2900 row on an invoice that has no other payment": _credit_on_single_payment,
    "... and the payment is at most the invoice total": _credit_within_invoice,
    "receipt with invoice references and no 1100 row": _receipt_without_relief,
    "receipt with a 1100 row and a 2900 row on an invoice that another receipt also lists": _relieved_and_credited_with_another_receipt,
    "receipt with a 2900 row on an opening-item invoice": _credit_on_opening_item,
    "receipt with a 2900 row dated after its invoice, the invoice not issued on days 0 to 10 of the period": _credit_after_invoice_off_days,
    "sales invoice with two or more receipts that sum to less than its total": _part_paid_invoice,
    "round amount": _round_amount,
    # posting lag: a posting is booked at its own moment inside the document's period (policy posting_rules.posting_timestamp),
    # so another instant is ordinary; only a crossing of the period boundary is an error
    "posting row at a different instant than its document": lambda c, i: _lag(c, i) != timedelta(0),
    "posted later than its document": lambda c, i: _lag(c, i) > timedelta(0),
    "posted earlier than its document": lambda c, i: _lag(c, i) < timedelta(0),
    "lag equals the zone offset": _lag_is_offset,
    "lag of less than one hour": lambda c, i: timedelta(0) < abs(_lag(c, i)) < timedelta(hours=1),
    "lag across a date change on a foreign-currency document": _lag_date_change_foreign,
}


def _count(c, pred):
    return sum(1 for p in c.ep.payments if pred(p))


# episode-level rules: (label predicted, predicate). "error" rules need exactly-perfect precision with 3 episodes,
# "clean" rules precision >= 0.9 with 2 episodes (only 5 of the 20 episodes are clean)
def _all_local_offset(c) -> bool:
    """Public text only: no ledger timestamp is written as UTC and at most two distinct offsets appear (the local one and
    its other side of a clock change)."""
    texts = [r["timestamp"] for r in c.ep.ledger]
    if not texts or any(t.endswith("Z") or t.endswith("+00:00") for t in texts):
        return False
    return len({t[-6:] for t in texts}) <= 2


def _size_max_lags(c) -> int:
    """The largest default posting_lag count of the episode's size, read off the ledger size (a public number)."""
    rows = len(c.ep.ledger)
    return 22 if rows < 500 else (38 if rows < 1250 else 50)


def _differing_postings(c) -> int:
    return sum(1 for v in c.lag.values() if v != timedelta(0))


def _unexplained_2900(c) -> int:
    """Rows on 2900 that no refund (a credit row and a relief row) and no receipt without invoice references explains."""
    refunds = _count(c, lambda p: p["kind"] == "refund")
    nulls = _count(c, lambda p: p["kind"] == "receipt" and not p["invoice_refs"])
    return c.rows2900 - 2 * refunds - nulls


EPISODE_RULES = {
    "any quantity/price outside catalogue -> error": ("error", lambda c: any(outside_catalogue(i) for i in c.ep.invoices)),
    "any off-hours payment on a boundary day -> error": ("error", lambda c: any(
        k == "payment" and _boundary_day(c, i) and _off_hours(c, i) for i, (k, _r, _t) in c.docs.items())),
    "any same-instant pair with terms != 30 -> error": ("error", lambda c: bool(c.odd_terms_pair)),
    "any posting at a different instant than its document -> error": ("error", lambda c: any(v != timedelta(0) for v in c.lag.values())),
    "more postings at another instant than the size's largest default lag count -> error": ("error", lambda c: _differing_postings(c) > _size_max_lags(c)),
    "at most 5 documents posted later than their timestamp -> clean": ("clean", lambda c: sum(1 for v in c.lag.values() if v > timedelta(0)) <= 5),
    "8 or more ledger rows on account 2900 -> error": ("error", lambda c: c.rows2900 >= 8),
    "2900 rows beyond twice the refunds plus the null-ref receipts -> error": ("error", lambda c: _unexplained_2900(c) > 0),
    "any receipt with a 2900 row lists an opening-item invoice -> error": ("error", lambda c: any(_credit_on_opening_item(c, i) for i in c.docs)),
    "any receipt with a 2900 row dated after an invoice not issued on days 0 to 10 -> error": ("error", lambda c: any(
        _credit_after_invoice_off_days(c, i) for i in c.docs)),
    "any sales invoice with two or more receipts below its total -> error": ("error", lambda c: any(_part_paid_invoice(c, i) for i in c.docs)),
    "at most 3 sales invoices whose receipts sum above their total -> error": ("error", lambda c: _over_received_sales(c) <= 3),
    "at most 0.64 payments per invoice -> error": ("error", lambda c: len(c.ep.payments) <= 0.64 * len(c.ep.invoices)),
    "122 or more invoices -> error": ("error", lambda c: len(c.ep.invoices) >= 122),
    "every ledger timestamp in the local offset (no UTC, <= 2 offsets) -> clean": ("clean", _all_local_offset),
    "small ledger (< 500 rows) with >= 2 refunds -> clean": ("clean", lambda c: len(c.ep.ledger) < 500 and _count(
        c, lambda p: p["kind"] == "refund") >= 2),
    "small ledger (< 500 rows) with >= 3 null-ref receipts -> clean": ("clean", lambda c: len(c.ep.ledger) < 500 and _count(
        c, lambda p: p["kind"] == "receipt" and not p["invoice_refs"]) >= 3),
}


# Rules on the number of line-identical pairs, measured by the CLI and by the generated-sample test only: the 20 committed
# episodes hold too few of them per size. The count of an episode never depends on its duplicates (it is drawn per size and
# holds them), so these are expected to stay below the limits; the pair-count document rule still sees the weak prior
# D / T of an episode with few pairs.
PAIR_COUNT_RULES = {
    "pair member in an episode with <= 2 line-identical pairs": lambda c, i: i in c.pair_members and len(c.pairs) <= 2,
}
PAIR_COUNT_EPISODE_RULES = {
    "small ledger (< 500 rows) with >= 3 line-identical pairs -> error": ("error", lambda c: len(c.ep.ledger) < 500 and len(c.pairs) >= 3),
}
DUP_CELLS = ("sales/same", "sales/later", "purchase/same", "purchase/later")


def duplicate_pairs(c) -> set:
    """Pairs (as frozensets of invoice IDs) that are the affected IDs of a duplicate_invoice issue."""
    return {frozenset(i["affected_ids"]) for i in c.ep.truth["issues"] if i["type"] == "duplicate_invoice"}


def measure_episodes(ctxs: list) -> dict:
    out = {}
    for name, (label, rule) in EPISODE_RULES.items():
        flagged = [c for c in ctxs if rule(c)]
        hits = sum(1 for c in flagged if bool(c.ep.truth["issues"]) == (label == "error"))
        out[name] = {"label": label, "predicted": len(flagged), "hits": hits,
                     "precision": hits / len(flagged) if flagged else 0.0}
    return out


# Payments outside business hours (no longer only the boundary receipt), stated as explicit rules so that one
# command reproduces them. The other residual tell, the FX target being the largest foreign purchase, is scored
# against wrong_fx_rate targets only (Tally.add_fx), not against the whole answer key.
RESIDUAL_RULES = {
    "residual: off-hours payment": lambda c, i: not _inv(c, i) and _off_hours(c, i),
    "residual: off-hours payment outside the error window": lambda c, i: (
        not _inv(c, i) and _off_hours(c, i) and not in_error_window(c.docs[i][2], c.p1, c.sched)),
    "residual: off-hours payment inside the error window": lambda c, i: (
        not _inv(c, i) and _off_hours(c, i) and in_error_window(c.docs[i][2], c.p1, c.sched)),
}


class Tally:
    """Pooled counts for the document rules and the episode rules, fed one episode at a time."""

    def __init__(self, rules: dict, pair_counts: bool = False):
        self.main_rules = rules
        self.pair_counts = pair_counts
        self.rules = {**rules, **(PAIR_COUNT_RULES if pair_counts else {})}
        self.episode_rules = {**EPISODE_RULES, **(PAIR_COUNT_EPISODE_RULES if pair_counts else {})}
        self.fired = dict.fromkeys(self.rules, 0)
        self.hit = dict.fromkeys(self.rules, 0)
        self.episodes_firing = dict.fromkeys(self.rules, 0)
        self.ep_flagged = dict.fromkeys(self.episode_rules, 0)
        self.ep_hits = dict.fromkeys(self.episode_rules, 0)
        self.dup_cells = {k: {"pairs": 0, "duplicates": 0} for k in DUP_CELLS}
        self.episodes = self.documents = self.affected = self.error_episodes = 0
        self.fx_eligible = self.fx_hits = 0
        self.fx_chance = 0.0

    def add(self, ep) -> None:
        c = Ctx(ep)
        truth = c.affected()
        self.episodes += 1
        self.documents += len(c.docs)
        self.affected += len(truth)
        self.error_episodes += bool(ep.truth["issues"])
        self.add_fx(c)
        for name, rule in self.rules.items():
            fired = {i for i in c.docs if rule(c, i)}
            self.fired[name] += len(fired)
            self.hit[name] += len(fired & truth)
            self.episodes_firing[name] += bool(fired)
        for name, (label, rule) in self.episode_rules.items():
            if rule(c):
                self.ep_flagged[name] += 1
                self.ep_hits[name] += bool(ep.truth["issues"]) == (label == "error")
        dups = duplicate_pairs(c)
        for ids in c.pairs:
            cell = self.dup_cells[c.docs[ids[0]][1]["kind"] + "/" + c.pair_shape[frozenset(ids)]]
            cell["pairs"] += 1
            cell["duplicates"] += frozenset(ids) in dups

    def add_fx(self, c) -> None:
        """Count one episode for the FX-target tell: eligible when a wrong_fx_rate target is a foreign purchase;
        a hit when the largest foreign purchase is one; chance is the share of foreign purchases that are targets."""
        fx = {i for iss in c.ep.truth["issues"] if iss["type"] == "wrong_fx_rate" for i in iss["affected_ids"]}
        targets = fx & set(c.rank_p)
        if not targets:
            return
        self.fx_eligible += 1
        self.fx_hits += any(c.rank_p[i] == 1 for i in targets)
        self.fx_chance += len(targets) / len(c.rank_p)

    def result(self) -> dict:
        def doc(names):
            return {n: {"predicted": self.fired[n], "hits": self.hit[n],
                        "precision": self.hit[n] / self.fired[n] if self.fired[n] else 0.0,
                        "recall": self.hit[n] / self.affected if self.affected else 0.0,
                        "episodes_firing": self.episodes_firing[n]} for n in names}

        def episode(rules):
            return {n: {"label": label, "predicted": self.ep_flagged[n], "hits": self.ep_hits[n],
                        "precision": self.ep_hits[n] / self.ep_flagged[n] if self.ep_flagged[n] else 0.0}
                    for n, (label, _r) in rules.items()}

        rules = doc(self.main_rules)
        episode_rules = episode(EPISODE_RULES)
        cells = {k: dict(v) for k, v in self.dup_cells.items()}
        cells["pooled"] = {"pairs": sum(v["pairs"] for v in cells.values()), "duplicates": sum(v["duplicates"] for v in cells.values())}
        for v in cells.values():
            v["precision"] = v["duplicates"] / v["pairs"] if v["pairs"] else 0.0
        fx = {"eligible_episodes": self.fx_eligible, "largest_is_target": self.fx_hits,
              "rate": self.fx_hits / self.fx_eligible if self.fx_eligible else 0.0,
              "chance": self.fx_chance / self.fx_eligible if self.fx_eligible else 0.0}
        out = {"rules": rules, "episode_rules": episode_rules, "fx_target": fx, "affected": self.affected,
               "episodes": self.episodes, "documents": self.documents, "error_episodes": self.error_episodes,
               "duplicates_by_side": cells}
        if self.pair_counts:
            out["pair_count_rules"] = doc(PAIR_COUNT_RULES)
            out["pair_count_episode_rules"] = episode(PAIR_COUNT_EPISODE_RULES)
        return out


def measure_episode_objects(episodes) -> dict:
    """Pooled measurement of RULES and EPISODE_RULES over Episode objects."""
    tally = Tally(RULES)
    for ep in episodes:
        tally.add(ep)
    return tally.result()


def sample_entries(n: int, master: str = DEFAULT_MASTER) -> list:
    """n (name, seed, config) entries with the check-set mix: batches of 20 from check_set("<master>/<batch>");
    a short batch takes evenly spread entries, so n=2 still sees one clean and one error episode."""
    from .splits import check_set

    out = []
    for batch in range((n + BATCH - 1) // BATCH):
        take = min(BATCH, n - batch * BATCH)
        entries = check_set(f"{master}/{batch:02d}")
        for j in range(take):
            e = entries[j * BATCH // take]
            out.append((f"b{batch:02d}_{e['name']}", e["seed"], e["config"]))
    return out


def generate_sample(n: int, master: str = DEFAULT_MASTER):
    """Yield the generated episodes of sample_entries(n, master)."""
    from .generator import generate_episode

    for _name, seed, config in sample_entries(n, master):
        yield generate_episode(seed, config).episode


def run(n: int, master: str = DEFAULT_MASTER) -> dict:
    """Generate n episodes and measure RULES, RESIDUAL_RULES and the episode rules over them."""
    tally = Tally({**RULES, **RESIDUAL_RULES}, pair_counts=True)
    for ep in generate_sample(n, master):
        tally.add(ep)
    out = tally.result()
    out["master"] = master
    out["residual"] = sorted(RESIDUAL_RULES)
    return out


def table(m: dict) -> str:
    lines = [f"{m['episodes']} episodes, {m['documents']} documents, {m['affected']} affected documents",
             f"{'rule':44s} {'pred':>5s} {'hits':>5s} {'prec':>6s} {'recall':>6s}"]
    for name, r in sorted(m["rules"].items(), key=lambda kv: -kv[1]["precision"] * (kv[1]["hits"] > 0)):
        lines.append(f"{name:44s} {r['predicted']:5d} {r['hits']:5d} {r['precision']:6.2f} {r['recall']:6.2f}")
    lines.append("episode-level rules (episodes flagged, correct, precision)")
    for name, r in {**m["episode_rules"], **m.get("pair_count_episode_rules", {})}.items():
        lines.append(f"{name:62s} {r['predicted']:3d} {r['hits']:3d} {r['precision']:5.2f}")
    for name, r in m.get("pair_count_rules", {}).items():
        lines.append(f"{name:62s} {r['predicted']:5d} {r['hits']:5d} {r['precision']:5.2f}")
    lines.append("duplicates by side and shape (line-identical pairs, pairs that are duplicates, precision)")
    for name, r in m["duplicates_by_side"].items():
        lines.append(f"{name:62s} {r['pairs']:5d} {r['duplicates']:5d} {r['precision']:5.2f}")
    return "\n".join(lines)


def rounded(m: dict) -> dict:
    """A copy of the measurement with ratios rounded to 4 places, for the committed files."""
    out = json.loads(json.dumps(m))
    for key in ("rate", "chance"):
        out["fx_target"][key] = round(out["fx_target"][key], 4)
    for r in out["duplicates_by_side"].values():
        r["precision"] = round(r["precision"], 4)
    for group in ("rules", "episode_rules", "pair_count_rules", "pair_count_episode_rules"):
        for r in out.get(group, {}).values():
            for key in ("precision", "recall"):
                if key in r:
                    r[key] = round(r[key], 4)
    return out


def to_json(m: dict) -> str:
    return json.dumps(rounded(m), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def to_markdown(m: dict) -> str:
    m = rounded(m)
    lines = ["# Shortcut-tell measurement", "",
             f"Master string `{m['master']}`, {m['episodes']} generated episodes ({m['error_episodes']} with errors), "
             f"{m['documents']} public documents, {m['affected']} affected documents (the answer key).",
             f"Reproduce: `python -m auditgym.tells --n {m['episodes']} --master {m['master']} --out runs/tells`.", "",
             "A rule fires on the documents it selects. True hits are fired documents that are in the answer key; "
             "precision = hits / fires on; recall = hits / affected documents; support = episodes in which the rule "
             "fires at least once.", "",
             "| rule | fires on | true hits | precision | recall | support |", "|---|---:|---:|---:|---:|---:|"]
    for name, r in sorted(m["rules"].items(), key=lambda kv: (-kv[1]["precision"] * (kv[1]["hits"] > 0), kv[0])):
        lines.append(f"| {name} | {r['predicted']} | {r['hits']} | {r['precision']:.4f} | {r['recall']:.4f} | {r['episodes_firing']} |")
    n, n_err = m["episodes"], m["error_episodes"]
    base = {"error": n_err / n if n else 0.0, "clean": (n - n_err) / n if n else 0.0}
    lines += ["", "## Episode-level rules", "",
              f"Base rate: {n_err} of {n} episodes have errors ({base['error']:.4f}) and {n - n_err} are clean "
              f"({base['clean']:.4f}). A rule is a tell only if its precision is well above the base rate of its label.", "",
              "| rule | label | episodes flagged | correct | precision | base rate of the label |",
              "|---|---|---:|---:|---:|---:|"]
    for name, r in m["episode_rules"].items():
        lines.append(f"| {name} | {r['label']} | {r['predicted']} | {r['hits']} | {r['precision']:.4f} | "
                     f"{base.get(r['label'], 0.0):.4f} |")
    if "pair_count_rules" in m:
        lines += ["", "## Pair-count rules", "",
                  "The number of line-identical pairs of an episode is drawn per size and holds the duplicates, so it must not "
                  "separate episodes with a duplicate from clean ones. The rules are measured here and in the generated-sample "
                  "test only: the 20 committed episodes hold too few pairs per size.", "",
                  "| rule | fires on | true hits | precision | recall | support |", "|---|---:|---:|---:|---:|---:|"]
        for name, r in m["pair_count_rules"].items():
            lines.append(f"| {name} | {r['predicted']} | {r['hits']} | {r['precision']:.4f} | {r['recall']:.4f} | {r['episodes_firing']} |")
        lines += ["", "| episode rule | label | episodes flagged | correct | precision | base rate of the label |",
                  "|---|---|---:|---:|---:|---:|"]
        for name, r in m["pair_count_episode_rules"].items():
            lines.append(f"| {name} | {r['label']} | {r['predicted']} | {r['hits']} | {r['precision']:.4f} | "
                         f"{base.get(r['label'], 0.0):.4f} |")
    lines += ["", "## Duplicates by side and shape", "",
              "A line-identical pair is two invoices of one counterparty with the same kind, currency, total and lines "
              "(references ignored) at most 10 days apart. Its shape is `same` when both carry one instant and `later` when "
              "the second is keyed 2 to 9 days after the first. A pair is a duplicate when the answer key lists it. Decoys "
              "and duplicates come from one pair builder, so the precision of a pair is about the same in every cell.", "",
              "| side/shape | pairs | duplicates | precision |", "|---|---:|---:|---:|"]
    for name, r in m["duplicates_by_side"].items():
        lines.append(f"| {name} | {r['pairs']} | {r['duplicates']} | {r['precision']:.4f} |")
    fx = m["fx_target"]
    lines += ["", "## FX target and the largest foreign purchase", "",
              f"Among the {fx['eligible_episodes']} episodes whose answer key has a wrong_fx_rate target that is a foreign "
              f"purchase invoice, the largest foreign purchase is such a target in {fx['largest_is_target']} "
              f"(rate {fx['rate']:.4f}). Chance level, the mean share of foreign purchases that are targets: {fx['chance']:.4f}.",
              "", "## Measured only in the regression test", "",
              "The episode rules on the count of documents in the error window (more or fewer than the typical count, by "
              "size and kind) and the window-by-kind rules scored against utc_wall_clock targets only are measured in "
              "tests/test_tells.py on 100 generated episodes. The window rows above are scored against all affected documents."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m auditgym.tells", description="Measure shortcut tells on generated episodes.")
    ap.add_argument("--n", type=int, default=200, help="number of generated episodes")
    ap.add_argument("--master", default=DEFAULT_MASTER, help="public master string the seeds derive from")
    ap.add_argument("--out", default="runs/tells", help="directory for summary.md and summary.json")
    args = ap.parse_args(argv)
    if args.n < 1:
        ap.error("--n must be at least 1")
    t0 = time.time()
    m = run(args.n, args.master)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(to_json(m), encoding="utf-8", newline="\n")
    (out / "summary.md").write_text(to_markdown(m), encoding="utf-8", newline="\n")
    print(f"{m['episodes']} episodes, {m['documents']} documents, {m['affected']} affected; wrote {out}/summary.md and summary.json")
    print(f"elapsed {time.time() - t0:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
