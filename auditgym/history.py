"""Hidden company history: entities, documents, payments, journals, FX rates.

The history is error-free by construction. Errors are introduced later by
inject.py as booking overrides, so the bookkeeping engine (books.py) derives
both the clean books and the erroneous books from the same history.
All times are UTC-aware datetimes; local wall-clock times are derived through
the company time zone rules.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from . import catalog
from .money import CURRENCY_EXPONENTS, quantize_rate
from .timeutil import TZ_RULES, in_ambiguous_hour, local_date, local_datetime, month_bounds, offset_minutes


@dataclass
class Entity:
    key: str
    role: str  # customer | supplier
    name: str
    currency: str


@dataclass
class LineItem:
    description: str
    quantity: int
    unit_price_minor: int
    amount_minor: int
    ref: str


@dataclass
class Invoice:
    key: str
    kind: str  # sales | purchase
    entity: str
    currency: str
    issued: datetime
    due: datetime
    lines: list
    tags: list = field(default_factory=list)
    duplicate_of: str | None = None

    @property
    def total(self) -> int:
        return sum(li.amount_minor for li in self.lines)


@dataclass
class Payment:
    key: str
    kind: str  # receipt | disbursement | refund
    entity: str | None
    currency: str
    ts: datetime
    amount: int
    refs: list | None
    bank_ref: str
    tags: list = field(default_factory=list)


@dataclass
class MiscJournal:
    key: str
    ts: datetime
    label: str
    lines: list  # (account, debit_minor, credit_minor)


@dataclass
class History:
    company: str
    base: str
    foreign: list
    tz: str
    year: int
    month: int
    p0: datetime
    p1: datetime
    cutoff_end: datetime
    lookback_start: datetime
    rounding: str
    exponents: dict
    entities: dict = field(default_factory=dict)
    invoices: dict = field(default_factory=dict)
    payments: dict = field(default_factory=dict)
    misc: dict = field(default_factory=dict)
    fx: dict = field(default_factory=dict)  # (date, src, tgt) -> rate string
    fx_noise: dict = field(default_factory=dict)
    holidays: list = field(default_factory=list)
    opening_bank: int = 0
    distractors: list = field(default_factory=list)  # {"kind", "keys"}

    def local_date(self, inst: datetime) -> date:
        return local_date(inst, self.tz)

    @property
    def p_last_date(self) -> date:
        return self.local_date(self.p1 - timedelta(seconds=1))

    @property
    def p_first_date(self) -> date:
        return self.local_date(self.p0)

    @property
    def next_first_date(self) -> date:
        return self.local_date(self.p1)


class SampleRetry(RuntimeError):
    """A random draw could not satisfy its constraints; the generator resamples the attempt."""


CUTOFF_DAYS = 7
LOOKBACK_DAYS = 40
FX_MARGIN_DAYS = 7


class HistoryBuilder:
    """Builds a consistent, error-free history. Deterministic for a given RNG."""

    def __init__(self, rng: random.Random, cfg: dict):
        self.rng = rng
        self.cfg = cfg
        year, month = (int(p) for p in cfg["period"].split("-"))
        tz = cfg["timezone"]
        p0, p1 = month_bounds(tz, year, month)
        next_first = local_date(p1, tz)
        cutoff_end = local_datetime(tz, next_first + timedelta(days=CUTOFF_DAYS))
        lookback_start = local_datetime(tz, local_date(p0, tz) - timedelta(days=LOOKBACK_DAYS))
        self.h = History(
            company=catalog.company_name(rng, tz),
            base=cfg["base_currency"],
            foreign=list(cfg["foreign_currencies"]),
            tz=tz,
            year=year,
            month=month,
            p0=p0,
            p1=p1,
            cutoff_end=cutoff_end,
            lookback_start=lookback_start,
            rounding=cfg["rounding"],
            exponents={c: CURRENCY_EXPONENTS[c] for c in [cfg["base_currency"], *cfg["foreign_currencies"]]},
        )
        self._counters: dict[str, int] = {}
        self.customers: list[str] = []
        self.suppliers: list[str] = []
        self.protected_dates: set[date] = set()
        self._used_refs: set[str] = set()
        self._used_times: set[datetime] = set()

    # ------------------------------------------------------------ helpers
    def key(self, prefix: str) -> str:
        n = self._counters.get(prefix, 0) + 1
        self._counters[prefix] = n
        return f"{prefix}{n:04d}"

    def period_dates(self, weekday_only: bool = False) -> list[date]:
        h = self.h
        d, out = h.p_first_date, []
        while d <= h.p_last_date:
            if not weekday_only or d.weekday() < 5:
                out.append(d)
            d += timedelta(days=1)
        return out

    def local_time(self, d: date, hour_range=(8, 18), minute=None) -> datetime:
        for _ in range(50):
            hour = self.rng.randint(*hour_range)
            mm = self.rng.randint(0, 59) if minute is None else minute
            ss = self.rng.randint(0, 59)
            inst = local_datetime(self.h.tz, d, hour, mm, ss)
            if not in_ambiguous_hour(self.h.tz, inst) and inst not in self._used_times:
                self._used_times.add(inst)
                return inst
        raise SampleRetry("could not find a free timestamp")

    def business_date(self, start: date, end: date) -> date:
        days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
        weekdays = [d for d in days if d.weekday() < 5]
        return self.rng.choice(weekdays or days)

    def unit_price_minor(self, ccy: str, usd_lo: float, usd_hi: float) -> int:
        exp = CURRENCY_EXPONENTS[ccy]
        usd = Decimal(str(round(self.rng.uniform(usd_lo, usd_hi), 2)))
        value = usd / Decimal(catalog.USD_VALUE[ccy]) * (Decimal(10) ** exp)
        grain = {0: 10, 2: 5, 3: 50}.get(exp, 1)
        minor = int(value / grain) * grain
        return max(grain, minor)

    def new_ref(self, pattern: str, issued: datetime) -> str:
        ym = f"{self.h.local_date(issued).year:04d}-{self.h.local_date(issued).month:02d}"
        for _ in range(1000):
            ref = pattern.format(n4=self.rng.randint(1000, 9999), n5=self.rng.randint(10000, 99999), ym=ym)
            if "{ym}" in pattern or ref not in self._used_refs:
                if "{ym}" not in pattern:
                    self._used_refs.add(ref)
                return ref
        raise SampleRetry("ref space exhausted")

    def bank_ref(self) -> str:
        return f"BT{self.rng.randint(10**9, 10**10 - 1)}"

    # ------------------------------------------------------------ entities
    def build_entities(self) -> None:
        h, cfg = self.h, self.cfg
        for role, count, base_share in (("customer", cfg["counts"]["customers"], 0.6), ("supplier", cfg["counts"]["suppliers"], 0.7)):
            for _ in range(count):
                k = self.key("C" if role == "customer" else "S")
                ccy = h.base if (self.rng.random() < base_share or not h.foreign) else self.rng.choice(h.foreign)
                h.entities[k] = Entity(k, role, catalog.counterparty_name(self.rng), ccy)
                (self.customers if role == "customer" else self.suppliers).append(k)
        # make sure every foreign currency has at least one customer and one supplier
        for ccy in h.foreign:
            for role, pool in (("customer", self.customers), ("supplier", self.suppliers)):
                if not any(h.entities[k].currency == ccy for k in pool):
                    k = self.key("C" if role == "customer" else "S")
                    h.entities[k] = Entity(k, role, catalog.counterparty_name(self.rng), ccy)
                    pool.append(k)

    def entity_with(self, role: str, currency: str | None = None, foreign: bool | None = None) -> str:
        pool = self.customers if role == "customer" else self.suppliers
        cands = [k for k in pool if (currency is None or self.h.entities[k].currency == currency)
                 and (foreign is None or (self.h.entities[k].currency != self.h.base) == foreign)]
        if not cands:
            ccy = currency or (self.rng.choice(self.h.foreign) if foreign else self.h.base)
            k = self.key("C" if role == "customer" else "S")
            self.h.entities[k] = Entity(k, role, catalog.counterparty_name(self.rng), ccy)
            pool.append(k)
            return k
        return self.rng.choice(cands)

    # ------------------------------------------------------------ documents
    def sales_lines(self, ccy: str, n_lines: int | None = None, min_usd_total: float = 0.0) -> list:
        lines = []
        for i in range(n_lines or self.rng.randint(1, 4)):
            desc, (lo, hi), (qlo, qhi) = self.rng.choice(catalog.SALES_ITEMS)
            qty = self.rng.randint(qlo, qhi)
            unit = self.unit_price_minor(ccy, lo, hi)
            lines.append(LineItem(desc, qty, unit, qty * unit, ""))
        while min_usd_total and self._usd(sum(li.amount_minor for li in lines), ccy) < min_usd_total:
            li = lines[0]
            li.quantity += max(1, li.quantity)
            li.amount_minor = li.quantity * li.unit_price_minor
        for idx, li in enumerate(lines):
            li.ref = f"L{idx + 1}"
        return lines

    def purchase_lines(self, ccy: str, issued: datetime, item=None, unit_override=None) -> list:
        desc_t, (lo, hi), pattern = item or self.rng.choice(catalog.PURCHASE_ITEMS)
        ref = self.new_ref(pattern, issued)
        unit = unit_override if unit_override is not None else self.unit_price_minor(ccy, lo, hi)
        return [LineItem(desc_t.format(ref=ref), 1, unit, unit, ref)]

    def _usd(self, minor: int, ccy: str) -> float:
        return float(Decimal(minor) / (Decimal(10) ** CURRENCY_EXPONENTS[ccy]) * Decimal(catalog.USD_VALUE[ccy]))

    def add_invoice(self, kind: str, entity: str, issued: datetime, lines: list, tags=None, terms_days=None) -> Invoice:
        k = self.key("I")
        terms = terms_days if terms_days is not None else self.rng.choice([14, 30, 45])
        due = local_datetime(self.h.tz, self.h.local_date(issued) + timedelta(days=terms), 23, 59, 59)
        inv = Invoice(k, kind, entity, self.h.entities[entity].currency, issued, due, lines, list(tags or []))
        self.h.invoices[k] = inv
        return inv

    def add_payment(self, kind: str, entity: str | None, currency: str, ts: datetime, amount: int, refs, tags=None) -> Payment:
        k = self.key("P")
        p = Payment(k, kind, entity, currency, ts, int(amount), list(refs) if refs is not None else None, self.bank_ref(), list(tags or []))
        self.h.payments[k] = p
        return p

    def random_sales_invoice(self, d: date | None = None, foreign: bool | None = None, tags=None, hours=(8, 18), min_usd=0.0) -> Invoice:
        cust = self.entity_with("customer", foreign=foreign)
        d = d or self.business_date(self.h.p_first_date, self.h.p_last_date)
        issued = self.local_time(d, hours)
        return self.add_invoice("sales", cust, issued, self.sales_lines(self.h.entities[cust].currency, min_usd_total=min_usd), tags)

    def random_purchase_invoice(self, d: date | None = None, foreign: bool | None = None, tags=None, hours=(8, 18)) -> Invoice:
        sup = self.entity_with("supplier", foreign=foreign)
        d = d or self.business_date(self.h.p_first_date, self.h.p_last_date)
        issued = self.local_time(d, hours)
        return self.add_invoice("purchase", sup, issued, self.purchase_lines(self.h.entities[sup].currency, issued), tags)

    def pay_time_after(self, after: datetime, min_days=1, max_days=20, latest: datetime | None = None, in_period=False) -> datetime | None:
        h = self.h
        latest = latest or (h.p1 - timedelta(hours=1) if in_period else h.cutoff_end - timedelta(hours=1))
        start = max(self.h.local_date(after) + timedelta(days=min_days), h.p_first_date)
        end = min(self.h.local_date(after) + timedelta(days=max_days), self.h.local_date(latest))
        if end < start:
            return None
        for _ in range(20):
            d = self.business_date(start, end)
            t = self.local_time(d)
            if after < t < latest:
                return t
        return None

    # ------------------------------------------------------------ regular flow
    def build_regular(self) -> None:
        h, cfg, rng = self.h, self.cfg, self.rng
        counts = cfg["counts"]
        # prior-period sales and purchase invoices, open at period start
        for _ in range(counts["prior_invoices"]):
            d = self.business_date(h.local_date(h.lookback_start) + timedelta(days=2), h.p_first_date - timedelta(days=2))
            kind = "sales" if rng.random() < 0.65 else "purchase"
            inv = (self.random_sales_invoice(d, tags=["prior"]) if kind == "sales" else self.random_purchase_invoice(d, tags=["prior"]))
            if rng.random() < 0.6:
                t = self.pay_time_after(max(inv.issued, h.p0), min_days=1, max_days=25)
                if t:
                    self.add_payment("receipt" if kind == "sales" else "disbursement", inv.entity, inv.currency, t, inv.total, [inv.key])
        # in-period sales
        for _ in range(counts["sales_invoices"]):
            inv = self.random_sales_invoice()
            if rng.random() < 0.7:
                t = self.pay_time_after(inv.issued, 2, 25)
                if t:
                    self.add_payment("receipt", inv.entity, inv.currency, t, inv.total, [inv.key])
        # in-period purchases
        for _ in range(counts["purchase_invoices"]):
            inv = self.random_purchase_invoice()
            if rng.random() < 0.6:
                t = self.pay_time_after(inv.issued, 3, 20)
                if t:
                    self.add_payment("disbursement", inv.entity, inv.currency, t, inv.total, [inv.key])
        # a few documents dated in the cut-off window (correctly booked there)
        for _ in range(rng.randint(2, 4)):
            d = self.business_date(h.next_first_date, h.next_first_date + timedelta(days=CUTOFF_DAYS - 2))
            if rng.random() < 0.6:
                self.random_sales_invoice(d, tags=["cutoff"])
            else:
                self.random_purchase_invoice(d, tags=["cutoff"])
        # one receipt from a known payer without an invoice reference (credited to 2900 by policy);
        # every episode has it, so a 2900 credit row from a receipt is never a tell by itself
        cust = self.entity_with("customer")
        ccy = h.entities[cust].currency
        d = self.business_date(h.p_first_date + timedelta(days=2), h.p_last_date - timedelta(days=2))
        self.add_payment("receipt", cust, ccy, self.local_time(d), self.unit_price_minor(ccy, 150, 2500), None, ["null_ref"])
        h.opening_bank = self.unit_price_minor(h.base, 40000, 250000) * 3

    # ------------------------------------------------------------ distractors
    def build_distractors(self) -> None:
        h, rng = self.h, self.rng
        dcounts = self.cfg["distractors"]
        for _ in range(dcounts.get("legit_repeat", 0)):
            sup = self.entity_with("supplier")
            d = self.business_date(h.p_first_date + timedelta(days=1), h.p_last_date - timedelta(days=3))
            issued = self.local_time(d)
            item = rng.choice([it for it in catalog.PURCHASE_ITEMS if "{ym}" not in it[2]])
            unit = self.unit_price_minor(h.entities[sup].currency, item[1][0], item[1][1])
            a = self.add_invoice("purchase", sup, issued, self.purchase_lines(h.entities[sup].currency, issued, item, unit), ["legit_repeat"], 30)
            b = self.add_invoice("purchase", sup, issued, self.purchase_lines(h.entities[sup].currency, issued, item, unit), ["legit_repeat"], 30)
            h.distractors.append({"kind": "legit_repeat", "keys": [a.key, b.key]})
        for _ in range(dcounts.get("recurring", 0)):
            sup = self.entity_with("supplier")
            item = rng.choice([it for it in catalog.PURCHASE_ITEMS if "{ym}" in it[2]] or catalog.PURCHASE_ITEMS)
            unit = self.unit_price_minor(h.entities[sup].currency, item[1][0], item[1][1])
            keys = []
            prior_d = self.business_date(h.p_first_date - timedelta(days=28), h.p_first_date - timedelta(days=20))
            cur_d = self.business_date(h.p_first_date + timedelta(days=2), h.p_first_date + timedelta(days=9))
            for d, tags in ((prior_d, ["recurring", "prior"]), (cur_d, ["recurring"])):
                issued = self.local_time(d)
                keys.append(self.add_invoice("purchase", sup, issued, self.purchase_lines(h.entities[sup].currency, issued, item, unit), tags, 30).key)
            h.distractors.append({"kind": "recurring", "keys": keys})
        for _ in range(dcounts.get("split_payment", 0)):
            inv = self.random_sales_invoice(self.business_date(h.p_first_date, h.p_first_date + timedelta(days=12)))
            t1 = self.pay_time_after(inv.issued, 1, 8, in_period=True)
            t2 = self.pay_time_after(t1 or inv.issued, 1, 10) if t1 else None
            if t1 and t2:
                part = int(inv.total * rng.uniform(0.3, 0.7))
                p1 = self.add_payment("receipt", inv.entity, inv.currency, t1, part, [inv.key], ["split"])
                p2 = self.add_payment("receipt", inv.entity, inv.currency, t2, inv.total - part, [inv.key], ["split"])
                h.distractors.append({"kind": "split_payment", "keys": [inv.key, p1.key, p2.key]})
        for _ in range(dcounts.get("multi_invoice_payment", 0)):
            cust = self.entity_with("customer")
            d1 = self.business_date(h.p_first_date, h.p_first_date + timedelta(days=10))
            i1 = self.add_invoice("sales", cust, self.local_time(d1), self.sales_lines(h.entities[cust].currency))
            i2 = self.add_invoice("sales", cust, self.local_time(d1 + timedelta(days=rng.randint(1, 4))), self.sales_lines(h.entities[cust].currency))
            t = self.pay_time_after(max(i1.issued, i2.issued), 2, 12)
            if t:
                p = self.add_payment("receipt", cust, i1.currency, t, i1.total + i2.total, [i1.key, i2.key], ["multi"])
                h.distractors.append({"kind": "multi_invoice_payment", "keys": [i1.key, i2.key, p.key]})
        for _ in range(dcounts.get("underpayment", 0)):
            inv = self.random_sales_invoice()
            t = self.pay_time_after(inv.issued, 2, 15)
            if t:
                p = self.add_payment("receipt", inv.entity, inv.currency, t, int(inv.total * rng.uniform(0.5, 0.95)), [inv.key], ["underpaid"])
                h.distractors.append({"kind": "underpayment", "keys": [inv.key, p.key]})
        for _ in range(dcounts.get("overpayment_refund", 0)):
            inv = self.random_sales_invoice(self.business_date(h.p_first_date, h.p_first_date + timedelta(days=10)))
            t = self.pay_time_after(inv.issued, 1, 8, in_period=True)
            if not t:
                continue
            excess = max(1, int(inv.total * rng.uniform(0.03, 0.2)))
            p = self.add_payment("receipt", inv.entity, inv.currency, t, inv.total + excess, [inv.key], ["overpaid"])
            keys = [inv.key, p.key]
            t2 = self.pay_time_after(t, 2, 12)
            if t2:
                r = self.add_payment("refund", inv.entity, inv.currency, t2, excess, [inv.key], ["refund"])
                keys.append(r.key)
            h.distractors.append({"kind": "overpayment_refund", "keys": keys})
        for _ in range(dcounts.get("null_ref_receipt", 0)):
            cust = self.entity_with("customer")
            ccy = h.entities[cust].currency
            sample = [i for i in h.invoices.values() if i.kind == "sales" and i.currency == ccy]
            amount = rng.choice(sample).total if sample and rng.random() < 0.6 else self.unit_price_minor(ccy, 200, 3000)
            d = self.business_date(h.p_first_date, h.p_last_date)
            p = self.add_payment("receipt", cust if rng.random() < 0.6 else None, ccy, self.local_time(d), amount, None, ["null_ref"])
            h.distractors.append({"kind": "null_ref_receipt", "keys": [p.key]})
        for i in range(dcounts.get("boundary_doc", 0)):
            if i % 2 == 0:
                inv = self.random_sales_invoice(h.p_last_date, hours=(23, 23))
            else:
                inv = (self.random_purchase_invoice if i % 4 == 1 else self.random_sales_invoice)(h.next_first_date, hours=(0, 0))
            inv.tags.append("boundary")
            h.distractors.append({"kind": "boundary_doc", "keys": [inv.key]})
        if h.foreign:
            for _ in range(dcounts.get("midnight_fx", 0)):
                inv = self.near_midnight_invoice(foreign=True)
                if inv:
                    h.distractors.append({"kind": "midnight_fx", "keys": [inv.key]})
            for _ in range(dcounts.get("weekend_fx", 0)):
                weekend = [d for d in self.period_dates() if d.weekday() >= 5]
                if not weekend:
                    continue
                inv = self.random_sales_invoice(rng.choice(weekend), foreign=True, tags=["weekend"])
                h.distractors.append({"kind": "weekend_fx", "keys": [inv.key]})

    def near_midnight_invoice(self, foreign: bool, kind: str | None = None, tags=None) -> Invoice | None:
        """Invoice whose local date differs from its UTC date (needs a non-zero offset)."""
        h = self.h
        if offset_minutes(h.tz, h.p0) == 0 and offset_minutes(h.tz, h.p1) == 0:
            return None
        for _ in range(60):
            d = self.business_date(h.p_first_date + timedelta(days=1), h.p_last_date - timedelta(days=1))
            inst0 = local_datetime(h.tz, d, 12)
            off = offset_minutes(h.tz, inst0)
            if off > 0:
                hours = (0, max(0, off // 60 - 1))
            else:
                hours = (min(23, 24 + off // 60 + 1), 23)
            try:
                issued = self.local_time(d, hours)
            except SampleRetry:
                continue
            if issued.date() != d:
                kind = kind or ("sales" if self.rng.random() < 0.6 else "purchase")
                ent = self.entity_with("customer" if kind == "sales" else "supplier", foreign=foreign)
                ccy = h.entities[ent].currency
                lines = self.sales_lines(ccy, min_usd_total=400) if kind == "sales" else self.purchase_lines(ccy, issued)
                return self.add_invoice(kind, ent, issued, lines, list(tags or ["midnight"]))
        return None

    # ------------------------------------------------------------ FX
    def build_fx(self) -> None:
        h, rng = self.h, self.rng
        start = h.local_date(h.lookback_start) - timedelta(days=FX_MARGIN_DAYS)
        end = h.local_date(h.cutoff_end) + timedelta(days=1)
        candidates = [d for d in self.period_dates(weekday_only=True) if d not in self.protected_dates and d.day not in (1,)]
        n_hol = rng.randint(0, 2)
        h.holidays = sorted(rng.sample(candidates, k=min(n_hol, len(candidates))))
        days = []
        d = start
        while d <= end:
            if d.weekday() < 5 and d not in h.holidays:
                days.append(d)
            d += timedelta(days=1)
        for ccy in h.foreign:
            level = Decimal(catalog.USD_VALUE[ccy]) / Decimal(catalog.USD_VALUE[h.base])
            level *= Decimal(str(round(rng.uniform(0.97, 1.03), 4)))
            places = max(2, 6 - len(str(int(level))) if level >= 1 else 6 + _leading_zeros(level))
            prev = None
            for day in days:
                for _ in range(20):
                    step = Decimal(str(round(rng.gauss(0, 0.003), 6)))
                    cand = level * (Decimal(1) + step)
                    text = quantize_rate(cand, places)
                    if prev is None or abs(Decimal(text) - Decimal(prev)) >= Decimal(prev) * Decimal("0.0005"):
                        break
                level = Decimal(text)
                h.fx[(day, ccy, h.base)] = text
                prev = text
        # unrelated cross rates the agent must ignore
        others = [c for c in catalog.USD_VALUE if c not in (h.base, *h.foreign)]
        if len(h.foreign) >= 1 and others:
            src = rng.choice(others)
            tgt = h.foreign[0]
            lvl = Decimal(catalog.USD_VALUE[src]) / Decimal(catalog.USD_VALUE[tgt])
            places = max(2, 6 - len(str(int(lvl))) if lvl >= 1 else 6 + _leading_zeros(lvl))
            for day in days[:: rng.randint(2, 3)]:
                h.fx_noise[(day, src, tgt)] = quantize_rate(lvl * Decimal(str(round(rng.uniform(0.99, 1.01), 4))), places)

    def rate_on(self, ccy: str, d: date) -> tuple[str, date] | None:
        """Policy rate: rate of local date d, else the latest earlier date."""
        if ccy == self.h.base:
            return "1", d
        for back in range(0, 15):
            day = d - timedelta(days=back)
            r = self.h.fx.get((day, ccy, self.h.base))
            if r is not None:
                return r, day
        return None

    # ------------------------------------------------------------ misc journals
    def fill_misc(self, rows_needed: int) -> None:
        h, rng = self.h, self.rng
        templates = [
            ("payroll", [("6100", "D"), ("1000", "C")]),
            ("payroll taxes", [("6110", "D"), ("2200", "C")]),
            ("rent", [("6200", "D"), ("1000", "C")]),
            ("utilities", [("6300", "D"), ("1000", "C")]),
            ("travel", [("6400", "D"), ("1000", "C")]),
            ("depreciation", [("6500", "D"), ("1500", "C")]),
            ("bank charges", [("6900", "D"), ("1000", "C")]),
            ("accrual", [("6300", "D"), ("2100", "C")]),
            ("card settlement", [("6400", "D"), ("6300", "D"), ("1000", "C")]),
        ]
        dates = self.period_dates()
        rows = 0
        while rows < rows_needed:
            label, shape = rng.choice(templates)
            d = rng.choice(dates)
            ts = self.local_time(d, (7, 20))
            if ts == h.p0:
                continue
            amounts = [self.unit_price_minor(h.base, 15, 2500) for _ in shape if _[1] == "D"]
            total = sum(amounts)
            lines, di = [], 0
            for acct, side in shape:
                if side == "D":
                    lines.append((acct, amounts[di], 0))
                    di += 1
                else:
                    lines.append((acct, 0, total))
            k = self.key("M")
            h.misc[k] = MiscJournal(k, ts, label, lines)
            rows += len(lines)


def _leading_zeros(value: Decimal) -> int:
    s = format(value, "f")
    if "." not in s:
        return 0
    frac = s.split(".")[1]
    return len(frac) - len(frac.lstrip("0"))
