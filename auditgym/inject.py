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

from . import catalog
from .books import Books, Overrides, policy_rate
from .config import ConfigError, utc_date_days
from .history import HistoryBuilder, Invoice, SampleRetry
from .money import convert_minor
from .timeutil import in_ambiguous_hour, local_datetime, offset_minutes

MATERIALITY_MIN = 100
TOLERANCE_MINOR = 2
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
    for _ in range(80):
        m = b.rng.randint(m_lo, m_hi)
        inst = local_datetime(b.h.tz, d, m // 60, m % 60, b.rng.randint(0, 59))
        if not in_ambiguous_hour(b.h.tz, inst) and inst not in b._used_times:
            b._used_times.add(inst)
            return inst
    raise RetryAttempt("no free near-midnight time")


def _offset_on(b: HistoryBuilder, d: date) -> int:
    return offset_minutes(b.h.tz, local_datetime(b.h.tz, d, 12))


def _new_invoice(b: HistoryBuilder, kind: str, issued: datetime, foreign: bool | None, min_usd: float, tags=None) -> Invoice:
    role = "customer" if kind == "sales" else "supplier"
    ent = b.entity_with(role, foreign=foreign)
    ccy = b.h.entities[ent].currency
    if kind == "sales":
        lines = b.sales_lines(ccy, min_usd_total=min_usd)
    else:
        item = b.rng.choice(catalog.PURCHASE_ITEMS)
        unit = b.unit_price_minor(ccy, max(min_usd, item[1][0]), max(min_usd * 3, item[1][1]))
        lines = b.purchase_lines(ccy, issued, item, unit)
    return b.add_invoice(kind, ent, issued, lines, tags)


def _near_midnight(b: HistoryBuilder, d: date) -> datetime:
    """Local time on d whose UTC calendar date differs from d."""
    off = _offset_on(b, d)
    if off > 0:
        return _minute_time(b, d, 5, off - 6)
    if off < 0:
        return _minute_time(b, d, 1440 + off + 6, 1434)
    raise RetryAttempt("zero UTC offset on this date")


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
    return utc_date_days(b.h.tz, b.h.year, b.h.month, late_limit)


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
def create_duplicate(b: HistoryBuilder, plan: Plan) -> None:
    h = b.h
    d = b.business_date(h.p_first_date + timedelta(days=1), h.p_last_date - timedelta(days=3))
    inv = _new_invoice(b, "purchase", b.local_time(d), None, 300)
    if b.rng.random() < 0.5:
        t = b.pay_time_after(inv.issued, 2, 15)
        if t:
            b.add_payment("disbursement", inv.entity, inv.currency, t, inv.total, [inv.key])
    copy = Invoice(b.key("I"), inv.kind, inv.entity, inv.currency, inv.issued, inv.due,
                   [replace(li) for li in inv.lines], [], duplicate_of=inv.key)
    item = next(it for it in catalog.PURCHASE_ITEMS if inv.lines[0].description.startswith(it[0].split("{")[0]))
    twin_ref = b.new_ref(item[2], inv.issued)  # drawn in both modes so the rest of the history is identical
    if b.cfg.get("twin"):
        # paired twin with the opposite answer: the second invoice is a separate supply (different line ref)
        li = copy.lines[0]
        copy.lines = [replace(li, ref=twin_ref, description=item[0].format(ref=twin_ref))]
        copy.duplicate_of = None
        copy.tags = ["legit_repeat", "twin"]
        b.h.invoices[copy.key] = copy
        b.h.distractors.append({"kind": "twin_legit_repeat", "keys": [inv.key, copy.key]})
        return
    plan.extra_invoices.append(copy)
    plan.items.append(Item("duplicate_invoice", "same_day_copy", "single", {"original": inv.key, "copy": copy.key}))


def create_unallocated(b: HistoryBuilder, plan: Plan, variant: str, scenario: str = "single",
                       invoice: Invoice | None = None, after: datetime | None = None) -> None:
    h, rng = b.h, b.rng
    if invoice is None:
        if rng.random() < 0.35:
            d = b.business_date(h.p_first_date - timedelta(days=30), h.p_first_date - timedelta(days=3))
            invoice = _new_invoice(b, "sales", b.local_time(d), None, 900, ["prior"])
        else:
            d = b.business_date(h.p_first_date, h.p_last_date - timedelta(days=8))
            invoice = _new_invoice(b, "sales", b.local_time(d), None, 900)
    start = max(after or invoice.issued, invoice.issued, h.p0)
    t = b.pay_time_after(start, 1, 14, in_period=True)
    if t is None:
        raise RetryAttempt("no room for the receipt inside the period")
    amount = invoice.total if rng.random() < 0.65 else int(invoice.total * rng.uniform(0.45, 0.9))
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
        if _offset_on(b, d) < 0:
            plan.protected_dates.add(d + timedelta(days=1))
    else:
        lo = h.p_first_date + timedelta(days=5 if variant == "stale_rate" else 1)
        hi = h.p_last_date - timedelta(days=9 if variant == "posting_date" else late_limit)
        if hi < lo:
            hi = lo
        d = b.business_date(lo, hi)
        issued = b.local_time(d)
    if variant == "posting_date":
        steps = [k for k in range(1, 7) if (d + timedelta(days=k)).weekday() < 5 and d + timedelta(days=k) <= h.p_last_date]
        if not steps:
            raise RetryAttempt("no business day to post on")
        post_d = d + timedelta(days=rng.choice(steps))
        data["posting_ts"] = b.local_time(post_d)
        plan.protected_dates.add(post_d)
    inv = _new_invoice(b, kind, issued, True, 4000)
    plan.protected_dates.add(d)
    plan.items.append(Item("wrong_fx_rate", variant, scenario, {"invoice": inv.key}, data))
    return inv


def create_wrong_period(b: HistoryBuilder, plan: Plan, variant: str, scenario: str = "single") -> None:
    h, rng = b.h, b.rng
    kind = rng.choice(["sales", "purchase"])
    foreign = (rng.random() < 0.4) if h.foreign else False
    if variant == "booked_early":
        d = b.business_date(h.next_first_date, h.next_first_date + timedelta(days=2))
        issued = b.local_time(d)
        posting = b.local_time(b.business_date(h.p_last_date - timedelta(days=1), h.p_last_date))
    elif variant == "booked_late":
        d = b.business_date(h.p_last_date - timedelta(days=2), h.p_last_date)
        issued = b.local_time(d)
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


def create_boundary_fx_payment(b: HistoryBuilder, plan: Plan) -> None:
    h, rng = b.h, b.rng
    off = offset_minutes(h.tz, h.p1)
    if off == 0 or not h.foreign:
        raise ConfigError("boundary_fx_payment needs a foreign currency and a non-zero UTC offset")
    d0 = b.business_date(h.p_first_date + timedelta(days=2), h.p_last_date - timedelta(days=6))
    inv = _new_invoice(b, "sales", b.local_time(d0), True, 5000)
    amount = int(inv.total * rng.uniform(0.4, 0.9))
    if off > 0:
        ts = _minute_time(b, h.next_first_date, 5, off - 11)
    else:
        ts = _minute_time(b, h.p_last_date, 1440 + off + 11, 1434)
    posting = ts - timedelta(minutes=off)
    p = b.add_payment("receipt", inv.entity, inv.currency, ts, amount, [inv.key])
    local_d = b.h.local_date(ts)
    utc_d = ts.date()
    plan.protected_dates.update({local_d, utc_d})
    scen = "boundary_fx_payment"
    plan.items.append(Item("wrong_period", "utc_wall_clock", scen, {"payment": p.key}, {"posting_ts": posting}))
    plan.items.append(Item("wrong_fx_rate", "utc_date", scen, {"payment": p.key}, {"wrong_rate_date": utc_d}))


def create_fx_invoice_partial_allocation(b: HistoryBuilder, plan: Plan, fx_variants: list, alloc_variants: list) -> None:
    variants = feasible_variants(b, "wrong_fx_rate", fx_variants, late_limit=9) or ["posting_date"]
    variant = b.rng.choice(variants)
    scen = "fx_invoice_partial_allocation"
    inv = create_wrong_fx(b, plan, variant, scen, kind="sales")
    after = plan.items[-1].data.get("posting_ts", inv.issued)
    create_unallocated(b, plan, b.rng.choice(alloc_variants), scen, invoice=inv, after=after)


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
            v = b.rng.choice(variants)
            if etype == "duplicate_invoice":
                create_duplicate(b, plan)
            elif etype == "unallocated_payment":
                create_unallocated(b, plan, v)
            elif etype == "wrong_fx_rate":
                create_wrong_fx(b, plan, v)
            else:
                create_wrong_period(b, plan, v)
    for scen in cfg["interacting"]:
        if scen == "boundary_fx_payment":
            create_boundary_fx_payment(b, plan)
        else:
            create_fx_invoice_partial_allocation(b, plan, cfg["variants"]["wrong_fx_rate"], cfg["variants"]["unallocated_payment"])
    return plan


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
            if cdate != d:
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
            it.data.update({"correct_rate": correct, "correct_rate_date": d, "wrong_rate": wrong, "wrong_rate_date": wdate})
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
            issues.append({
                "item": it, "affected": [("invoice", o), ("invoice", c)], "amount": amount,
                "evidence": [[("doc", o), ("doc", c), ("row", ap_o.ident), ("row", ap_c.ident)],
                             [("doc", o), ("doc", c), ("row", ex_o.ident), ("row", ex_c.ident)]],
                "sort": (doc.issued, amount),
                "explanation": "Purchase invoice entered twice: same supplier, date, currency, total and line "
                               "references; both copies are posted to accounts payable.",
            })
        elif it.type == "unallocated_payment":
            p, i = t["payment"], t["invoice"]
            row = pay_row(p, "unalloc")
            amount = _line_amount(row)
            if amount < MATERIALITY_MIN:
                raise RetryAttempt("unallocated amount below materiality")
            issues.append({
                "item": it, "affected": [("payment", p), ("invoice", i)], "amount": amount,
                "evidence": [[("doc", p), ("doc", i), ("row", row.ident)]],
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
                               f"{it.data['correct_rate']} for the document's local date {it.data['correct_rate_date']}.",
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
