"""Error injection.

1. plan_errors() creates target documents inside the (still error-free)
   history with the properties each error needs, using the same builders as
   ordinary documents, and records the planned change.
2. make_overrides() turns the plan into booking overrides once FX rates exist.
3. derive_issues() reads the erroneous books and writes the answer key:
   affected IDs, the real discrepancy amount, and acceptable evidence sets.

Supported errors (each independently configurable through config.errors and
config.variants) and the two interacting scenarios are listed in config.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta

from .books import Books, Overrides, policy_rate
from .config import BOUNDARY_FX_FALLBACK, UNALLOCATED_PRIOR_SHARE, ConfigError, boundary_utc_date_ok, utc_date_days
from .history import (LARGE_PURCHASE_USD, LARGE_SALES_USD, PAIR_SHAPE_OF_VARIANT, PAIR_SIDES, VARIANT_OF_PAIR_SHAPE,
                      HistoryBuilder, Invoice, SampleRetry)
from .money import convert_minor
from .timeutil import in_ambiguous_hour, local_datetime, offset_minutes

MATERIALITY_MIN = 100
TOLERANCE_MINOR = 2
PART_PAID_SHARE = 0.5  # share of unallocated receipts whose invoice was already part paid by an earlier receipt
TYPE_ORDER = {"duplicate_invoice": 0, "unallocated_payment": 1, "wrong_fx_rate": 2, "wrong_period": 3}
SCENARIO_ORDER = {"single": 0, "boundary_fx_payment": 1, "fx_invoice_partial_allocation": 2}


class RetryAttempt(SampleRetry):
    """The sampled targets cannot carry the error cleanly; resample the episode."""


@dataclass
class Item:
    type: str
    variant: str
    scenario: str
    targets: dict
    data: dict = field(default_factory=dict)


@dataclass
class Plan:
    items: list = field(default_factory=list)
    extra_invoices: list = field(default_factory=list)
    protected_dates: set = field(default_factory=set)


# ---------------------------------------------------------------- helpers
def _minute_time(b: HistoryBuilder, d: date, m_lo: int, m_hi: int) -> datetime:
    try:
        return b.minute_time(d, m_lo, m_hi)
    except SampleRetry as exc:
        raise RetryAttempt(str(exc)) from None


def _clear_of_dst(b: HistoryBuilder, d: date, m_lo: int, m_hi: int, off: int) -> int:
    """The latest minute of day `d`, at most m_hi, at which a receipt's UTC-wall-clock posting (receipt minus `off`) stays
    75 minutes clear of a DST change and still under the boundary's offset `off`. Ordinary documents never sit that close
    to a change, so a posting there would be a public tell, and after the change its wall clock would no longer be the
    receipt's UTC wall clock. No DST change near the boundary: m_hi itself, so the draw is unchanged."""
    m = m_hi
    while m >= m_lo:
        posting = local_datetime(b.h.tz, d, m // 60, m % 60, 59) - timedelta(minutes=off)
        if not in_ambiguous_hour(b.h.tz, posting) and offset_minutes(b.h.tz, posting) == off:
            return m
        m -= 1
    raise RetryAttempt("no receipt minute keeps the boundary posting clear of a DST change")


def _offset_on(b: HistoryBuilder, d: date) -> int:
    return b.offset_on(d)


def _new_invoice(b: HistoryBuilder, kind: str, issued: datetime, foreign: bool | None, min_usd: float, tags=None) -> Invoice:
    """A target document drawn like an ordinary one: lines are resampled inside the catalogue quantity and
    price ranges until the invoice clears the materiality floor (never scaled up beyond the ranges)."""
    role = "customer" if kind == "sales" else "supplier"
    ent = b.entity_with(role, foreign=foreign)
    ccy = b.h.entities[ent].currency
    if kind == "sales":
        lines = b.sales_lines(ccy, min_usd_total=min_usd)
    else:
        lines = b.purchase_lines(ccy, issued, entity=ent, min_usd=min_usd)
    return b.add_invoice(kind, ent, issued, lines, tags)


def _near_midnight(b: HistoryBuilder, d: date) -> datetime:
    """Local time on d whose UTC calendar date differs from d."""
    try:
        return b.near_midnight_time(d)
    except SampleRetry:
        raise RetryAttempt("zero UTC offset on this date") from None


def transpose_rate(rate: str, b: HistoryBuilder) -> str:
    """Swap two adjacent digits of the rate so that it changes by at least 0.2 %."""
    from decimal import Decimal

    digits = [i for i, ch in enumerate(rate) if ch.isdigit()]
    cands = []
    for a, c in zip(digits, digits[1:]):
        if c != a + 1 or rate[a] == rate[c]:
            continue
        s = list(rate)
        s[a], s[c] = s[c], s[a]
        cand = "".join(s)
        if cand.startswith("0") and not cand.startswith("0."):
            continue
        if Decimal(cand) > 0 and abs(Decimal(cand) - Decimal(rate)) >= Decimal(rate) * Decimal("0.002"):
            cands.append(cand)
    if not cands:
        raise RetryAttempt("rate has no material transposition")
    return b.rng.choice(cands)


def utc_date_candidates(b: HistoryBuilder, late_limit: int) -> list:
    """utc_date days with a published rate on both sides (no FX holiday on the day or, for negative offsets, after)."""
    h = b.h
    return [d for d in utc_date_days(h.tz, h.year, h.month, late_limit)
            if d not in h.holidays and (b.offset_on(d) >= 0 or d + timedelta(days=1) not in h.holidays)]


def _fx_target_date(b: HistoryBuilder, lo: date, hi: date) -> date:
    """Date of a wrong-rate document: a business day, a weekend day or an FX holiday at the share of ordinary documents
    (the policy rate is then the latest earlier published rate)."""
    return b.loose_date(lo, hi)


def feasible_variants(b: HistoryBuilder, etype: str, allowed: list, late_limit: int = 2) -> list:
    h = b.h
    out = []
    boundary_off = offset_minutes(h.tz, h.p1)
    for v in allowed:
        if etype == "wrong_fx_rate" and not h.foreign:
            continue
        if v == "utc_date" and not utc_date_candidates(b, late_limit):
            continue
        if v == "utc_wall_clock" and boundary_off == 0:
            continue
        out.append(v)
    return out


# ---------------------------------------------------------------- creators
def convert_pair(b: HistoryBuilder, plan: Plan, variants: list) -> None:
    """One duplicate_invoice error from a drawn line-identical pair. The pair is chosen uniformly among the unused pairs of
    an allowed shape, so side, payment status, terms, item and price have the same chance for a duplicate as for a decoy.
    The first invoice stays the original. The second one leaves the history, takes the first one's line items (so its
    references match) and is posted as the copy at its own issued_at and the rate of its own date; it was never paid.
    The variant follows the pair's shape: the same instant is same_day_copy, a later one is rekeyed_copy. With twin=true nothing is converted: the chosen pair
    is relabelled and the twin keeps the whole history, including the choice, with the opposite answer."""
    h = b.h
    shapes = {PAIR_SHAPE_OF_VARIANT[v] for v in variants}
    cands = [p for p in b.pairs if not p.get("used") and p["shape"] in shapes]
    if not cands:  # unreachable for a resolved config (repeat_pairs >= the duplicate count); kept for hand-built ones
        with b.stream(b.dup_rng):
            cands = [b.repeat_pair(b.rng.choice(PAIR_SIDES), b.rng.choice(sorted(shapes)))]
    pair = b.dup_rng.choice(cands)
    pair["used"] = True
    original, second = h.invoices[pair["first"]], h.invoices[pair["second"]]
    if b.cfg.get("twin"):
        pair["entry"]["kind"] = "twin_legit_repeat"
        for inv in (original, second):
            inv.tags = ["legit_repeat", "twin"]
        return
    del h.invoices[second.key]
    h.distractors.remove(pair["entry"])
    copy = Invoice(second.key, original.kind, original.entity, original.currency, second.issued, second.due,
                   [replace(li) for li in original.lines], [], duplicate_of=original.key)
    plan.extra_invoices.append(copy)
    plan.items.append(Item("duplicate_invoice", VARIANT_OF_PAIR_SHAPE[pair["shape"]], "single",
                           {"original": original.key, "copy": copy.key}))


def create_unallocated(b: HistoryBuilder, plan: Plan, variant: str, scenario: str = "single",
                       invoice: Invoice | None = None, after: datetime | None = None) -> None:
    h, rng = b.h, b.rng
    fresh = invoice is None
    if invoice is None:
        prior = b.unallocated_prior.pop() if b.unallocated_prior else rng.random() < UNALLOCATED_PRIOR_SHARE
        invoice = b.open_invoice(prior)
    start = max(after or invoice.issued, invoice.issued, h.p0)
    open_total = invoice.total
    t = None
    if fresh and b.alloc_rng.random() < PART_PAID_SHARE:
        # an earlier part payment already relieved the invoice (on the stream of its own): the receipt below meets a balance
        # that is open but smaller than the invoice total, so a count of the invoice's payments or the total says nothing
        with b.stream(b.alloc_rng):
            t_first = b.pay_time_after(start, 1, 8, in_period=True)
            t = b.pay_time_after(t_first, 1, 10, in_period=True) if t_first else None
            if t:
                part = max(1, int(invoice.total * b.alloc_rng.uniform(0.3, 0.6)))
                b.add_payment("receipt", invoice.entity, invoice.currency, t_first, part, [invoice.key], ["part_paid"])
                open_total = invoice.total - part
    if t is None:
        t = b.pay_time_after(start, 1, 14, in_period=True)
    if t is None:
        raise RetryAttempt("no room for the receipt inside the period")
    amount = open_total if rng.random() < 0.65 else max(1, int(open_total * rng.uniform(0.45, 0.9)))
    p = b.add_payment("receipt", invoice.entity, invoice.currency, t, amount, [invoice.key])
    alloc = 0 if variant == "missing" else max(1, int(amount * rng.uniform(0.2, 0.75)))
    plan.items.append(Item("unallocated_payment", variant, scenario, {"payment": p.key, "invoice": invoice.key}, {"alloc": alloc}))


def create_wrong_fx(b: HistoryBuilder, plan: Plan, variant: str, scenario: str = "single", kind: str | None = None) -> Invoice:
    h, rng = b.h, b.rng
    kind = kind or ("sales" if rng.random() < 0.6 else "purchase")
    data: dict = {}
    late_limit = 9 if scenario != "single" else 2
    if variant == "utc_date":
        cands = utc_date_candidates(b, late_limit)
        if not cands:
            raise RetryAttempt("no date for a UTC-date FX error")
        d = rng.choice(cands)
        issued = _near_midnight(b, d)
    else:
        lo = h.p_first_date + timedelta(days=5 if variant == "stale_rate" else 1)
        hi = h.p_last_date - timedelta(days=9 if variant == "posting_date" else late_limit)
        if hi < lo:
            hi = lo
        d = _fx_target_date(b, lo, hi)
        issued = b.local_time(d, b.doc_hours())
    if variant == "posting_date":
        steps = [k for k in range(1, 7) if (d + timedelta(days=k)).weekday() < 5 and d + timedelta(days=k) <= h.p_last_date
                 and d + timedelta(days=k) not in h.holidays]
        if not steps:
            raise RetryAttempt("no business day to post on")
        post_d = d + timedelta(days=rng.choice(steps))
        data["posting_ts"] = b.local_time(post_d)
        plan.protected_dates.add(post_d)
    inv = _new_invoice(b, kind, issued, True, LARGE_SALES_USD if kind == "sales" else LARGE_PURCHASE_USD)
    plan.protected_dates.add(d)
    plan.items.append(Item("wrong_fx_rate", variant, scenario, {"invoice": inv.key}, data))
    return inv


def create_wrong_period(b: HistoryBuilder, plan: Plan, variant: str, scenario: str = "single") -> None:
    h, rng = b.h, b.rng
    kind = rng.choice(["sales", "purchase"])
    foreign = (rng.random() < 0.4) if h.foreign else False
    if variant == "booked_early":
        d = b.loose_date(h.next_first_date, h.next_first_date + timedelta(days=2))
        issued = b.local_time(d, b.doc_hours())
        posting = b.local_time(b.business_date(h.p_last_date - timedelta(days=1), h.p_last_date))
    elif variant == "booked_late":
        d = b.loose_date(h.p_last_date - timedelta(days=2), h.p_last_date)
        issued = b.local_time(d, b.doc_hours())
        posting = b.local_time(b.business_date(h.next_first_date, h.next_first_date + timedelta(days=3)))
    else:
        off = offset_minutes(h.tz, h.p1)
        if off > 0:
            issued = _minute_time(b, h.next_first_date, 5, off - 11)
        elif off < 0:
            issued = _minute_time(b, h.p_last_date, 1440 + off + 11, 1434)
        else:
            raise ConfigError("utc_wall_clock needs a non-zero UTC offset at the period boundary")
        posting = issued - timedelta(minutes=off)
    inv = _new_invoice(b, kind, issued, foreign, 600)
    plan.items.append(Item("wrong_period", variant, scenario, {"invoice": inv.key}, {"posting_ts": posting}))


def create_boundary_fx_payment(b: HistoryBuilder, plan: Plan, fx_variants: list | None = None) -> None:
    h, rng = b.h, b.rng
    off = offset_minutes(h.tz, h.p1)
    if off == 0 or not h.foreign:
        raise ConfigError("boundary_fx_payment needs a foreign currency and a non-zero UTC offset")
    d0 = b.business_date(h.p_first_date + timedelta(days=2), h.p_last_date - timedelta(days=6))
    inv = _new_invoice(b, "sales", b.local_time(d0), True, 5000)
    amount = int(inv.total * rng.uniform(0.4, 0.9))
    if off > 0:
        ts = _minute_time(b, h.next_first_date, 5, _clear_of_dst(b, h.next_first_date, 5, off - 11, off))
    else:
        ts = _minute_time(b, h.p_last_date, 1440 + off + 11, _clear_of_dst(b, h.p_last_date, 1440 + off + 11, 1434, off))
    posting = ts - timedelta(minutes=off)
    if in_ambiguous_hour(h.tz, posting) or offset_minutes(h.tz, posting) != off:  # guard; _clear_of_dst keeps it unreachable
        raise RetryAttempt("the boundary posting crosses a DST change")
    p = b.add_payment("receipt", inv.entity, inv.currency, ts, amount, [inv.key])
    local_d = b.h.local_date(ts)
    utc_d = ts.date()
    plan.protected_dates.update({local_d, utc_d})
    scen = "boundary_fx_payment"
    plan.items.append(Item("wrong_period", "utc_wall_clock", scen, {"payment": p.key}, {"posting_ts": posting}))
    if boundary_utc_date_ok(f"{h.year:04d}-{h.month:02d}", off):
        plan.items.append(Item("wrong_fx_rate", "utc_date", scen, {"payment": p.key}, {"wrong_rate_date": utc_d}))
        return
    # utc_date needs a published rate on the receipt's local date and a different rate on its UTC date; this boundary
    # lacks one of the two, so the same receipt carries another rate error instead (drawn only here, so every month that
    # could host utc_date is unchanged).
    allowed = BOUNDARY_FX_FALLBACK if fx_variants is None else [v for v in fx_variants if v in BOUNDARY_FX_FALLBACK]
    variants = feasible_variants(b, "wrong_fx_rate", list(allowed))
    if not variants:
        raise ConfigError("boundary_fx_payment in this month needs the stale_rate or transposed variant of wrong_fx_rate")
    plan.items.append(Item("wrong_fx_rate", rng.choice(variants), scen, {"payment": p.key}, {}))


def create_fx_invoice_partial_allocation(b: HistoryBuilder, plan: Plan, fx_variants: list, alloc_variants: list) -> None:
    # the scenario is only real when the receipt is booked partly to 1100 and partly to 2900, so that the wrong
    # carrying amount of the invoice feeds the relief and FX difference of the receipt: always 'partial'
    if "partial" not in alloc_variants:
        raise ConfigError("fx_invoice_partial_allocation needs the 'partial' variant of unallocated_payment")
    variants = feasible_variants(b, "wrong_fx_rate", fx_variants, late_limit=9) or ["posting_date"]
    variant = b.rng.choice(variants)
    scen = "fx_invoice_partial_allocation"
    inv = create_wrong_fx(b, plan, variant, scen, kind="sales")
    after = plan.items[-1].data.get("posting_ts", inv.issued)
    create_unallocated(b, plan, "partial", scen, invoice=inv, after=after)


def plan_errors(b: HistoryBuilder, cfg: dict) -> Plan:
    plan = Plan()
    errors = cfg["errors"]
    for etype in ("duplicate_invoice", "unallocated_payment", "wrong_fx_rate", "wrong_period"):
        n = errors.get(etype, 0)
        if not n:
            continue
        variants = feasible_variants(b, etype, cfg["variants"][etype])
        if not variants:
            raise ConfigError(f"no feasible variant of {etype} for this configuration")
        for _ in range(n):
            if etype == "duplicate_invoice":
                convert_pair(b, plan, variants)  # no main-stream draw: the choice is on the pairs' own stream
                continue
            v = b.rng.choice(variants)
            if etype == "unallocated_payment":
                create_unallocated(b, plan, v)
            elif etype == "wrong_fx_rate":
                create_wrong_fx(b, plan, v)
            else:
                create_wrong_period(b, plan, v)
    for scen in cfg["interacting"]:
        if scen == "boundary_fx_payment":
            create_boundary_fx_payment(b, plan, cfg["variants"]["wrong_fx_rate"])
        else:
            create_fx_invoice_partial_allocation(b, plan, cfg["variants"]["wrong_fx_rate"], cfg["variants"]["unallocated_payment"])
    return plan


def plan_posting_lags(b: HistoryBuilder, plan: Plan) -> None:
    """Posting lags (HistoryBuilder.apply_posting_lags) around the planned errors. A target whose posting moment is the error
    (wrong_period, the posting_date variant, the boundary receipt) never takes one and its moment orders the documents around
    it; the documents of the other issues (the receipt and invoice of an unallocated payment, an invoice with a wrong rate)
    take lags like any clean document, and the issue stays what it is: amounts and rates follow the document."""
    protected, fixed, error_keys = set(), {}, set()
    for it in plan.items:
        for role, key in it.targets.items():
            if it.type == "duplicate_invoice":
                continue  # the pair's own lags (drawn by pair, converted or not)
            own = it.type == "wrong_period" or (it.type == "wrong_fx_rate" and (it.variant == "posting_date" or role == "payment"))
            if own:
                protected.add(key)
                if "posting_ts" in it.data:
                    fixed[key] = it.data["posting_ts"]
            else:
                error_keys.add(key)
    b.apply_posting_lags(plan.extra_invoices, fixed, protected, error_keys - protected)


# ---------------------------------------------------------------- overrides
def make_overrides(b: HistoryBuilder, plan: Plan) -> Overrides:
    h = b.h
    ov = Overrides(extra_invoices=list(plan.extra_invoices))
    for it in plan.items:
        if it.type == "wrong_fx_rate":
            if "invoice" in it.targets:
                doc = h.invoices[it.targets["invoice"]]
                d = h.local_date(doc.issued)
            else:
                doc = h.payments[it.targets["payment"]]
                d = h.local_date(doc.ts)
            correct, cdate = policy_rate(h, doc.currency, d)
            if cdate != d and it.variant == "utc_date":
                raise RetryAttempt("target document date has no published rate")
            if it.variant == "utc_date":
                inst = doc.issued if "invoice" in it.targets else doc.ts
                wrong, wdate = policy_rate(h, doc.currency, inst.date())
            elif it.variant == "posting_date":
                pts = it.data["posting_ts"]
                ov.inv_ts[doc.key] = pts
                wrong, wdate = policy_rate(h, doc.currency, h.local_date(pts))
            elif it.variant == "stale_rate":
                wrong, wdate = policy_rate(h, doc.currency, h.p_first_date - timedelta(days=1))
            else:
                wrong, wdate = transpose_rate(correct, b), None
            if wrong == correct:
                raise RetryAttempt("wrong rate equals the correct rate")
            it.data.update({"correct_rate": correct, "correct_rate_date": cdate, "wrong_rate": wrong, "wrong_rate_date": wdate})
            if "invoice" in it.targets:
                ov.inv_rate[doc.key] = wrong
            else:
                ov.pay_rate[doc.key] = wrong
        elif it.type == "wrong_period":
            if "invoice" in it.targets:
                ov.inv_ts[it.targets["invoice"]] = it.data["posting_ts"]
            else:
                ov.pay_ts[it.targets["payment"]] = it.data["posting_ts"]
        elif it.type == "unallocated_payment":
            ov.pay_alloc[it.targets["payment"]] = it.data["alloc"]
    return ov


# ---------------------------------------------------------------- answer key
def _line_amount(line) -> int:
    return line.debit or line.credit


def derive_issues(b: HistoryBuilder, plan: Plan, books: Books) -> list[dict]:
    h = b.h
    by_ident = {ln.ident: ln for ln in books.lines}

    def inv_row(key, role):
        ln = by_ident.get((("inv", key), role, key))
        if ln is None:
            raise RetryAttempt("expected invoice posting outside the ledger window")
        return ln

    def pay_row(key, role, ref=None):
        ln = by_ident.get((("pay", key), role, ref))
        if ln is None:
            raise RetryAttempt(f"expected payment line {role} missing")
        return ln

    def in_period(inst: datetime) -> bool:
        return h.p0 <= inst < h.p1

    issues = []
    for it in plan.items:
        t = it.targets
        if it.type == "duplicate_invoice":
            o, c = t["original"], t["copy"]
            ap_o, ap_c = inv_row(o, "primary"), inv_row(c, "primary")
            ex_o, ex_c = inv_row(o, "counter"), inv_row(c, "counter")
            amount = _line_amount(ap_c)
            doc = books.invoices[o]
            sales = doc.kind == "sales"
            who, accounts = (("customer", "receivable and revenue") if sales else ("supplier", "payable and expense"))
            if it.variant == "same_day_copy":
                explanation = (f"{'Sales' if sales else 'Purchase'} invoice entered twice: same {who}, date, currency, total and "
                               f"{'delivery' if sales else 'line'} references; both copies are posted to accounts {accounts}.")
            else:
                gap = (h.local_date(books.invoices[c].issued) - h.local_date(doc.issued)).days
                explanation = (f"{'Sales' if sales else 'Purchase'} invoice entered twice: same {who}, currency, total and "
                               f"{'delivery' if sales else 'line'} references; the copy was keyed again {gap} days later and is "
                               f"posted at its own date, so its base amount is the later posting; both copies are posted to "
                               f"accounts {accounts}.")
            issues.append({
                "item": it, "affected": [("invoice", o), ("invoice", c)], "amount": amount,
                "evidence": [[("doc", o), ("doc", c), ("row", ap_o.ident), ("row", ap_c.ident)],
                             [("doc", o), ("doc", c), ("row", ex_o.ident), ("row", ex_c.ident)]],
                "sort": (doc.issued, amount),
                "explanation": explanation,
            })
        elif it.type == "unallocated_payment":
            p, i = t["payment"], t["invoice"]
            row = pay_row(p, "unalloc")
            amount = _line_amount(row)
            if amount < MATERIALITY_MIN:
                raise RetryAttempt("unallocated amount below materiality")
            acct = "1100" if books.invoices[i].kind == "sales" else "2000"
            inv_rows = sorted((ln for ln in books.lines if ln.invoice == i and ln.account == acct), key=lambda ln: ln.order)
            # a foreign-currency invoice also cites the receipt's bank row: it holds the whole receipt at the payment-date
            # rate, the only public record that shows what part of it the 2900 amount is
            bank_rows = [pay_row(p, "bank")] if books.invoices[i].currency != h.base else []
            issues.append({
                "item": it, "affected": [("payment", p), ("invoice", i)], "amount": amount,
                # both documents, the 2900 row (and the bank row in a foreign currency) and every receivable/payable row
                # of the invoice (its posting and any relief): together they show that the invoice was open and that
                # this payment alone relieved it
                "evidence": [[("doc", p), ("doc", i), ("row", row.ident)] + [("row", ln.ident) for ln in bank_rows + inv_rows]],
                "sort": (h.payments[p].ts, amount),
                "explanation": "Receipt references an open invoice whose balance covers it, but part or all of it "
                               "was left in 2900 unallocated receipts instead of relieving receivables.",
            })
        elif it.type == "wrong_fx_rate":
            fx_key = (it.data["correct_rate_date"], None, h.base)
            if "invoice" in t:
                k = t["invoice"]
                inv = books.invoices[k]
                prim, ctr = inv_row(k, "primary"), inv_row(k, "counter")
                correct = convert_minor(inv.total, it.data["correct_rate"], h.exponents[inv.currency], h.exponents[h.base], h.rounding)
                delta = abs(_line_amount(prim) - correct)
                fx_key = (it.data["correct_rate_date"], inv.currency, h.base)
                evidence = [[("doc", k), ("row", prim.ident), ("fx", fx_key)], [("doc", k), ("row", ctr.ident), ("fx", fx_key)]]
                affected = [("invoice", k)]
                sort = (inv.issued, delta)
            else:
                k = t["payment"]
                p = h.payments[k]
                bank = pay_row(k, "bank")
                correct = convert_minor(p.amount, it.data["correct_rate"], h.exponents[p.currency], h.exponents[h.base], h.rounding)
                delta = abs(_line_amount(bank) - correct)
                fx_key = (it.data["correct_rate_date"], p.currency, h.base)
                evidence = [[("doc", k), ("row", bank.ident), ("fx", fx_key)]]
                affected = [("payment", k)]
                sort = (p.ts, delta)
            if delta < MATERIALITY_MIN:
                raise RetryAttempt("FX difference below materiality")
            issues.append({
                "item": it, "affected": affected, "amount": delta, "evidence": evidence, "sort": sort,
                "explanation": f"Converted at {it.data['wrong_rate']} instead of the policy rate "
                               f"{it.data['correct_rate']}: the rate of {it.data['correct_rate_date']}, the latest rate published on or "
                               f"before the document's local date.",
            })
        elif it.type == "wrong_period":
            if "invoice" in t:
                k = t["invoice"]
                inv = books.invoices[k]
                prim, ctr = inv_row(k, "primary"), inv_row(k, "counter")
                doc_ts, post_ts = inv.issued, prim.ts
                evidence = [[("doc", k), ("row", prim.ident)], [("doc", k), ("row", ctr.ident)]]
                affected, amount = [("invoice", k)], _line_amount(prim)
            else:
                k = t["payment"]
                p = h.payments[k]
                bank = pay_row(k, "bank")
                doc_ts, post_ts = p.ts, bank.ts
                evidence = [[("doc", k), ("row", bank.ident)]]
                affected, amount = [("payment", k)], _line_amount(bank)
            if in_period(doc_ts) == in_period(post_ts):
                raise RetryAttempt("period error did not cross the boundary")
            issues.append({
                "item": it, "affected": affected, "amount": amount, "evidence": evidence, "sort": (doc_ts, amount),
                "explanation": "Document belongs to "
                               + ("the reporting period" if in_period(doc_ts) else "another period")
                               + " by its own timestamp in company time, but is posted "
                               + ("outside" if in_period(doc_ts) else "inside") + " the reporting period.",
            })
    issues.sort(key=lambda x: (SCENARIO_ORDER[x["item"].scenario], TYPE_ORDER[x["item"].type], x["sort"]))
    keys = [(x["item"].type, tuple(sorted(x["affected"]))) for x in issues]
    if len(set(keys)) != len(keys):
        raise RetryAttempt("two issues share type and affected records")
    return issues
