"""Hidden company history: entities, documents, payments, journals, FX rates.

The history is error-free by construction. Errors are introduced later by
inject.py as booking overrides, so the bookkeeping engine (books.py) derives
both the clean books and the erroneous books from the same history.
All times are UTC-aware datetimes; local wall-clock times are derived through
the company time zone rules.
"""

from __future__ import annotations

import contextlib
import random
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from decimal import Decimal

from . import catalog
from .config import UNALLOCATED_PRIOR_SHARE
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
    posted: datetime | None = None  # posting moment when it differs from issued (a posting lag); None = booked at issued

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
    posted: datetime | None = None  # posting moment when it differs from ts (a posting lag); None = booked at ts


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
WEEKEND_SHARE = 0.10  # share of ordinary documents (and non-FX targets) dated on a weekend
OFF_HOURS_DOC_SHARE = 0.05  # share of ordinary invoices issued outside 08:00-18:59 local time
OFF_HOURS_PAY_SHARE = 0.14  # share of ordinary payments made outside 08:00-18:59 local time
SIZE_TRIES = 400
# Error targets are drawn among ordinary-looking documents that clear a size floor (so that an injected FX error
# is material). To keep targets from being the largest documents, this share of ordinary invoices is drawn with
# the same floors.
LARGE_SHARE = 0.5
LARGE_SALES_USD = 4000.0
LARGE_PURCHASE_USD = 2000.0
# boundary distractors draw their kind (invoices and payments, sales and purchase side alike) and the side of the
# boundary at random, so neither the kind nor the number of documents in the error window gives a target away
BOUNDARY_KINDS = ("sales", "purchase", "receipt", "disbursement")
BOUNDARY_ERROR_SIDE_SHARE = 0.6
# Shapes of a line-identical pair of invoices: "same" is two copies of one instant (the same_day_copy variant of
# duplicate_invoice when converted); "later" is the second invoice keyed again 2 to 9 local days later, at its own date and
# hour (the rekeyed_copy variant). Decoys and duplicate sources are drawn by one builder, from the shapes of the allowed
# duplicate variants only.
PAIR_SHAPE_OF_VARIANT = {"same_day_copy": "same", "rekeyed_copy": "later"}
LATER_GAP_DAYS = (2, 9)
OPEN_INVOICE_USD = 900.0  # size floor of the invoice of a 2900 credit, error or not
VARIANT_OF_PAIR_SHAPE = {s: v for v, s in PAIR_SHAPE_OF_VARIANT.items()}
PAIR_SIDES = ("sales", "purchase")
# Posting lags: a posting is booked at its own moment inside the document's period. Four shapes, mirroring the error shapes
# in size and sign: booked later (minutes, hours or 1 to 5 business days, like booked_late and posting_date), booked
# earlier (up to a day or two, like booked_early), at the UTC wall clock of the local time (like utc_wall_clock) and, on a
# foreign-currency document, across a date change with another published rate (booked at the document-date rate).
LAG_SHAPES = ("later", "earlier", "utc_wall_clock", "date_change")
LAG_TRIES = 8


class HistoryBuilder:
    """Builds a consistent, error-free history. Deterministic for a given RNG."""

    def __init__(self, rng: random.Random, cfg: dict):
        # Named streams for the draws of the sales references, the line-identical pairs and the choice of the pairs that
        # become duplicates. They are forked first, before any draw, so none depends on the main stream.
        self.ref_rng = rng.fork("refs")
        self.pair_rng = rng.fork("repeats")
        self.dup_rng = rng.fork("duplicates")
        self.lag_rng = rng.fork("posting_lag")  # every posting-lag draw: unrelated draws never move
        self.credit_rng = rng.fork("credit_receipts")  # the credit_receipt distractors (invoices, times, amounts)
        self.alloc_rng = rng.fork("earlier_payment")  # the earlier part payment of an unallocated receipt's invoice
        # which fresh unallocated receipts sit on an opening item: the resolved count of them, in a shuffled order of its own
        n_fresh = int((cfg.get("errors") or {}).get("unallocated_payment", 0))
        self.unallocated_prior = [True] * int(cfg.get("unallocated_prior", 0)) + [False] * (n_fresh - int(cfg.get("unallocated_prior", 0)))
        rng.fork("unallocated_prior_order").shuffle(self.unallocated_prior)
        # the target kind (invoice, receipt, disbursement) of each standalone wrong_fx_rate and wrong_period error, resolved
        # in the config so that the paid slots of build_regular know them; a hand-built config without them targets invoices
        self.target_kinds = {t: list(ks) for t, ks in (cfg.get("target_kinds") or {}).items()}
        self.lag_log: list[dict] = []  # {"key", "shape", "role"} of every lagged document; role distractor, pair or error
        self.rng = rng
        self.cfg = cfg
        self.pairs: list[dict] = []  # drawn line-identical pairs; inject.convert_pair turns some into duplicates
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
    @contextlib.contextmanager
    def stream(self, rng):
        """Draw every helper below from `rng` instead of the main stream inside the block."""
        saved, self.rng = self.rng, rng
        try:
            yield
        finally:
            self.rng = saved

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

    def loose_date(self, start: date, end: date, weekend_share: float = WEEKEND_SHARE) -> date:
        """Mostly a business day; a small share of ordinary documents fall on a weekend."""
        if self.rng.random() < weekend_share:
            days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
            weekend = [d for d in days if d.weekday() >= 5]
            if weekend:
                return self.rng.choice(weekend)
        return self.business_date(start, end)

    def doc_hours(self) -> tuple:
        """Local hour range of an ordinary invoice: mostly business hours, sometimes late evening or early morning."""
        r = self.rng.random()
        return (8, 18) if r >= OFF_HOURS_DOC_SHARE else ((19, 23) if r < OFF_HOURS_DOC_SHARE / 2 else (0, 7))

    def payment_hours(self) -> tuple:
        r = self.rng.random()
        return (8, 18) if r >= OFF_HOURS_PAY_SHARE else ((19, 23) if r < OFF_HOURS_PAY_SHARE / 2 else (0, 7))

    def minute_time(self, d: date, m_lo: int, m_hi: int) -> datetime:
        """Local time on d between minute m_lo and m_hi of the day (random seconds), free and unambiguous."""
        for _ in range(80):
            m = self.rng.randint(m_lo, m_hi)
            inst = local_datetime(self.h.tz, d, m // 60, m % 60, self.rng.randint(0, 59))
            if not in_ambiguous_hour(self.h.tz, inst) and inst not in self._used_times:
                self._used_times.add(inst)
                return inst
        raise SampleRetry("no free near-midnight time")

    def offset_on(self, d: date) -> int:
        return offset_minutes(self.h.tz, local_datetime(self.h.tz, d, 12))

    def near_midnight_time(self, d: date) -> datetime:
        """Local time on d whose UTC calendar date differs from d (the utc_date error window)."""
        off = self.offset_on(d)
        if off > 0:
            return self.minute_time(d, 5, off - 6)
        if off < 0:
            return self.minute_time(d, 1440 + off + 6, 1434)
        raise SampleRetry("zero UTC offset on this date")

    def boundary_time(self, error_side: bool) -> datetime:
        """A time right at the period boundary. error_side=True uses exactly the window in which the
        utc_wall_clock error documents and the boundary receipt are placed (just after local midnight after the
        period for positive offsets, shortly before the period's last midnight for negative ones)."""
        h = self.h
        off = offset_minutes(h.tz, h.p1)
        if off > 0:
            return (self.minute_time(h.next_first_date, 5, off - 11) if error_side
                    else self.minute_time(h.p_last_date, 1380, 1434))
        if off < 0:
            return (self.minute_time(h.p_last_date, 1440 + off + 11, 1434) if error_side
                    else self.minute_time(h.next_first_date, 0, 59))
        return self.local_time(h.p_last_date, (23, 23)) if error_side else self.local_time(h.next_first_date, (0, 0))

    def unit_price_minor(self, ccy: str, usd_lo: float, usd_hi: float) -> int:
        exp = CURRENCY_EXPONENTS[ccy]
        usd = Decimal(str(round(self.rng.uniform(usd_lo, usd_hi), 2)))
        value = usd / Decimal(catalog.USD_VALUE[ccy]) * (Decimal(10) ** exp)
        grain = {0: 10, 2: 5, 3: 50}.get(exp, 1)
        minor = int(value / grain) * grain
        return max(grain, minor)

    def new_ref(self, pattern: str, issued: datetime | None = None, entity: str | None = None, rng=None) -> str:
        """Line reference, unique per episode. Every pattern has a random part, so uniqueness never needs a
        sequence suffix that would reveal the creation order of documents."""
        rng = rng or self.rng
        ym = ""
        if "{ym}" in pattern:
            local = self.h.local_date(issued)
            ym = f"{local.year:04d}-{local.month:02d}"
        for _ in range(1000):
            ref = pattern.format(n4=rng.randint(1000, 9999), n5=rng.randint(10000, 99999), ym=ym)
            if ref not in self._used_refs:
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
        """Ordinary sales lines. With min_usd_total the draw is repeated (rejection sampling) until the
        invoice clears the floor, so every quantity and unit price stays inside the catalogue ranges."""
        for _ in range(SIZE_TRIES):
            lines = []
            for _i in range(n_lines or self.rng.randint(1, 4)):
                desc, (lo, hi), (qlo, qhi) = self.rng.choice(catalog.SALES_ITEMS)
                qty = self.rng.randint(qlo, qhi)
                unit = self.unit_price_minor(ccy, lo, hi)
                lines.append(LineItem(desc, qty, unit, qty * unit, ""))
            if not min_usd_total or self._usd(sum(li.amount_minor for li in lines), ccy) >= min_usd_total:
                break
        else:
            raise SampleRetry("no ordinary-looking sales invoice reaches the size floor")
        return self.number_sales_lines(lines, self.new_ref(catalog.SALES_REF, rng=self.ref_rng))

    @staticmethod
    def number_sales_lines(lines: list, ref: str) -> list:
        """One delivery reference per sales invoice; its lines carry "<reference>-<line_no>"."""
        for idx, li in enumerate(lines):
            li.ref = f"{ref}-{idx + 1}"
        return lines

    def purchase_lines(self, ccy: str, issued: datetime, item=None, unit_override=None, entity: str | None = None,
                       min_usd: float = 0.0) -> list:
        """One purchase line. With min_usd the item and price are redrawn inside the catalogue ranges until
        the line clears the floor."""
        if item is None:
            for _ in range(SIZE_TRIES):
                cand = self.rng.choice(catalog.PURCHASE_ITEMS)
                price = self.unit_price_minor(ccy, cand[1][0], cand[1][1])
                if not min_usd or self._usd(price, ccy) >= min_usd:
                    item, unit_override = cand, price
                    break
            else:
                raise SampleRetry("no ordinary-looking purchase reaches the size floor")
        desc_t, (lo, hi), pattern = item
        ref = self.new_ref(pattern, issued, entity)
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

    def random_sales_invoice(self, d: date | None = None, foreign: bool | None = None, tags=None, hours=None, min_usd=0.0) -> Invoice:
        cust = self.entity_with("customer", foreign=foreign)
        d = d or self.loose_date(self.h.p_first_date, self.h.p_last_date)
        issued = self.local_time(d, hours or self.doc_hours())
        if not min_usd and self.rng.random() < LARGE_SHARE:
            min_usd = LARGE_SALES_USD
        return self.add_invoice("sales", cust, issued, self.sales_lines(self.h.entities[cust].currency, min_usd_total=min_usd), tags)

    def random_purchase_invoice(self, d: date | None = None, foreign: bool | None = None, tags=None, hours=None, min_usd=0.0) -> Invoice:
        sup = self.entity_with("supplier", foreign=foreign)
        d = d or self.loose_date(self.h.p_first_date, self.h.p_last_date)
        issued = self.local_time(d, hours or self.doc_hours())
        if not min_usd and self.rng.random() < LARGE_SHARE:
            min_usd = LARGE_PURCHASE_USD
        return self.add_invoice("purchase", sup, issued, self.purchase_lines(self.h.entities[sup].currency, issued, entity=sup, min_usd=min_usd), tags)

    def pay_time_after(self, after: datetime, min_days=1, max_days=20, latest: datetime | None = None, in_period=False) -> datetime | None:
        h = self.h
        latest = latest or (h.p1 - timedelta(hours=1) if in_period else h.cutoff_end - timedelta(hours=1))
        start = max(self.h.local_date(after) + timedelta(days=min_days), h.p_first_date)
        end = min(self.h.local_date(after) + timedelta(days=max_days), self.h.local_date(latest))
        if end < start:
            return None
        for _ in range(20):
            d = self.loose_date(start, end)
            t = self.local_time(d, self.payment_hours())
            if after < t < latest:
                return t
        return None

    def open_invoice(self, prior: bool, min_usd: float = OPEN_INVOICE_USD) -> Invoice:
        """The sales invoice of a 2900 credit that is not a refund, drawn the same way for the unallocated_payment errors and
        for the clean credits (credit_receipt shapes, overpayment_refund): an opening item (issued 3 to 30 days before the
        period) with the share UNALLOCATED_PRIOR_SHARE, otherwise an invoice of the period up to 8 days before its end; dates
        are loose (weekends included), the hour an ordinary document hour, the size at least `min_usd`."""
        h = self.h
        if prior:
            d = self.loose_date(h.p_first_date - timedelta(days=30), h.p_first_date - timedelta(days=3))
            tags = ["prior"]
        else:
            d = self.loose_date(h.p_first_date, h.p_last_date - timedelta(days=8))
            tags = None
        issued = self.local_time(d, self.doc_hours())
        ent = self.entity_with("customer", foreign=None)
        return self.add_invoice("sales", ent, issued, self.sales_lines(h.entities[ent].currency, min_usd_total=min_usd), tags)

    def paid_slots(self, n: int, removed: int, removed_paid: int, share: float) -> list:
        """Paid or unpaid for each of the n + removed nominal invoices, each paid with probability `share`; then the slots of
        the invoices that an error brought are dropped (unpaid ones first, `removed_paid` of them paid ones). What is left
        are the n ordinary invoices."""
        coins = [self.rng.random() < share for _ in range(n + removed)]
        for want, drop in ((True, removed_paid), (False, removed - removed_paid)):
            while drop > 0 and want in coins:
                coins.remove(want)
                drop -= 1
        while len(coins) > n:  # not enough slots of the wanted kind: drop whatever is left over
            coins.pop(0)
        return coins

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
        # in-period sales and purchases. An invoice that an error adds (wrong rate, wrong period) is never paid and was taken
        # out of the drawn count, so its slot is taken out of the unpaid ones: the payments per invoice of an episode never
        # depend on how many errors it holds (the boundary scenario's invoice is paid by its receipt: a paid slot goes)
        load = cfg.get("error_invoice_load") or {}
        for kind, share, lo_d, hi_d in (("sales", 0.7, 2, 25), ("purchase", 0.6, 3, 20)):
            n = counts[f"{kind}_invoices"]
            slots = self.paid_slots(n, int(load.get(kind, 0)), int(load.get(f"{kind}_paid", 0)), share)
            for paid in slots:
                inv = self.random_sales_invoice() if kind == "sales" else self.random_purchase_invoice()
                if paid:
                    t = self.pay_time_after(inv.issued, lo_d, hi_d)
                    if t:
                        self.add_payment("receipt" if kind == "sales" else "disbursement", inv.entity, inv.currency, t, inv.total, [inv.key])
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
        self.add_payment("receipt", cust, ccy, self.local_time(d, self.payment_hours()), self.unit_price_minor(ccy, 150, 2500), None, ["null_ref"])
        h.opening_bank = self.unit_price_minor(h.base, 40000, 250000) * 3

    # ------------------------------------------------------------ distractors
    def build_distractors(self) -> None:
        h, rng = self.h, self.rng
        dcounts = self.cfg["distractors"]
        self.build_repeat_pairs(self.cfg.get("repeat_pairs", dcounts.get("legit_repeat", 0)))
        for _ in range(dcounts.get("recurring", 0)):
            sup = self.entity_with("supplier")
            item = rng.choice([it for it in catalog.PURCHASE_ITEMS if "{ym}" in it[2]] or catalog.PURCHASE_ITEMS)
            unit = self.unit_price_minor(h.entities[sup].currency, item[1][0], item[1][1])
            keys = []
            prior_d = self.business_date(h.p_first_date - timedelta(days=28), h.p_first_date - timedelta(days=20))
            cur_d = self.business_date(h.p_first_date + timedelta(days=2), h.p_first_date + timedelta(days=9))
            for d, tags in ((prior_d, ["recurring", "prior"]), (cur_d, ["recurring"])):
                issued = self.local_time(d, self.doc_hours())
                keys.append(self.add_invoice("purchase", sup, issued, self.purchase_lines(h.entities[sup].currency, issued, item, unit, sup), tags, 30).key)
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
        self.build_split_remainders(dcounts.get("split_remainder", 0))
        for _ in range(dcounts.get("multi_invoice_payment", 0)):
            cust = self.entity_with("customer")
            d1 = self.business_date(h.p_first_date, h.p_first_date + timedelta(days=10))
            i1 = self.add_invoice("sales", cust, self.local_time(d1, self.doc_hours()), self.sales_lines(h.entities[cust].currency))
            i2 = self.add_invoice("sales", cust, self.local_time(d1 + timedelta(days=rng.randint(1, 4)), self.doc_hours()), self.sales_lines(h.entities[cust].currency))
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
            prior = rng.random() < UNALLOCATED_PRIOR_SHARE
            for _try in range(8):
                inv = self.open_invoice(prior)
                t = self.pay_time_after(max(inv.issued, h.p0), 1, 8, in_period=True)
                if not t:
                    del h.invoices[inv.key]
                    continue
                excess = max(1, int(inv.total * rng.uniform(0.03, 0.2)))
                p = self.add_payment("receipt", inv.entity, inv.currency, t, inv.total + excess, [inv.key], ["overpaid"])
                keys = [inv.key, p.key]
                t2 = self.pay_time_after(t, 2, 12)
                if t2:
                    r = self.add_payment("refund", inv.entity, inv.currency, t2, excess, [inv.key], ["refund"])
                    keys.append(r.key)
                h.distractors.append({"kind": "overpayment_refund", "keys": keys})
                break
        for _ in range(dcounts.get("null_ref_receipt", 0)):
            cust = self.entity_with("customer")
            ccy = h.entities[cust].currency
            sample = [i for i in h.invoices.values() if i.kind == "sales" and i.currency == ccy]
            amount = rng.choice(sample).total if sample and rng.random() < 0.6 else self.unit_price_minor(ccy, 200, 3000)
            d = self.business_date(h.p_first_date, h.p_last_date)
            p = self.add_payment("receipt", cust if rng.random() < 0.6 else None, ccy, self.local_time(d, self.payment_hours()), amount, None, ["null_ref"])
            h.distractors.append({"kind": "null_ref_receipt", "keys": [p.key]})
        for _ in range(dcounts.get("boundary_doc", 0)):
            kind = rng.choice(BOUNDARY_KINDS)
            error_side = rng.random() < BOUNDARY_ERROR_SIDE_SHARE
            keys = self.boundary_document(kind, error_side)
            h.distractors.append({"kind": "boundary_doc", "keys": keys})
        self.build_credit_receipts(dcounts.get("credit_receipt", 0), dcounts.get("prepaid_receipt", 0))
        if h.foreign:
            for j in range(dcounts.get("midnight_fx", 0)):
                keys = self.near_midnight_documents(payment=(j % 2 == 1))
                if keys:
                    h.distractors.append({"kind": "midnight_fx", "keys": keys})
            for _ in range(dcounts.get("weekend_fx", 0)):
                weekend = [d for d in self.period_dates() if d.weekday() >= 5]
                if not weekend:
                    continue
                inv = self.random_sales_invoice(rng.choice(weekend), foreign=True, tags=["weekend"])
                h.distractors.append({"kind": "weekend_fx", "keys": [inv.key]})

    def build_split_remainders(self, count: int) -> None:
        """`count` split payments that leave a rest open, on the stream of the credit receipts, on an invoice drawn like the one of an
        unallocated receipt (open_invoice: an opening item with the share UNALLOCATED_PRIOR_SHARE, loose dates over the period,
        size floor): a part payment (30 to 70 %), then
        a second receipt of 45 to 90 % of what is left. Both receipts relieve 1100 in full and nothing goes to 2900, so an
        invoice whose receipts sum to less than its total is ordinary; the part-paid unallocated_payment errors are the only
        other invoices of that kind. Recorded as a split_payment distractor of shape "remainder". A shortfall raises
        SampleRetry (the count is exact)."""
        h = self.h
        with self.stream(self.credit_rng):
            rng = self.rng
            for _ in range(count):
                prior = rng.random() < UNALLOCATED_PRIOR_SHARE  # decided before the tries, like every other credit invoice
                for _try in range(8):
                    inv = self.open_invoice(prior)
                    start = max(inv.issued, h.p0)
                    t1 = self.pay_time_after(start, 1, 8, in_period=True)
                    t2 = self.pay_time_after(t1, 1, 10, in_period=True) if t1 else None
                    if not t2:
                        del h.invoices[inv.key]
                        continue
                    part = max(1, int(inv.total * rng.uniform(0.3, 0.7)))
                    second = max(1, int((inv.total - part) * rng.uniform(0.45, 0.9)))
                    p1 = self.add_payment("receipt", inv.entity, inv.currency, t1, part, [inv.key], ["split"])
                    p2 = self.add_payment("receipt", inv.entity, inv.currency, t2, second, [inv.key], ["split", "remainder"])
                    h.distractors.append({"kind": "split_payment", "keys": [inv.key, p1.key, p2.key], "shape": "remainder"})
                    break
                else:
                    raise SampleRetry("no room for a split payment that leaves a rest")

    def build_credit_receipts(self, count: int, prepaid: int = 0) -> None:
        """`count` receipts that leave a credit in 2900 without being an error, and `prepaid` more of the prepaid shape, on
        their own stream. Over-received shapes (an invoice drawn like the one of an unallocated receipt: an opening item with
        the share UNALLOCATED_PRIOR_SHARE, loose dates over the period, size floor OPEN_INVOICE_USD): "overpaid", an overpayment
        that is never refunded (one payment, amount above the invoice total); "settled", a second receipt on an invoice that an
        earlier receipt settled in full; "topped_up", a part payment (30 to 60 % of the invoice) followed by a receipt that is
        more than what was left but at most the invoice total, so it relieves the rest and credits the excess to 2900 (a 1100
        row and a 2900 row on an invoice with another receipt, which would otherwise mark the part-paid unallocated_payment
        errors). "prepaid": a receipt that names an invoice issued 1 to 8 days after it (one payment, amount at most the
        total, so the 2900 row says nothing about the amount or the payment count). All credited to 2900 by policy because no
        invoice balance is open to relieve. A shortfall (no room for a shape after 8 tries) raises SampleRetry."""
        h = self.h
        with self.stream(self.credit_rng):
            # the share of the over-received credits that follow an earlier receipt (settled, topped_up) is drawn per episode,
            # so the number of 2900 receipts that are dated after their invoice and within its total (what an error adds one
            # of) varies from episode to episode and says little about the errors
            second_share = self.credit_second_share = self.rng.uniform(0.2, 0.9)
            for i in range(count + prepaid):
                rng = self.rng
                if i < count:
                    prior = rng.random() < UNALLOCATED_PRIOR_SHARE
                    r = rng.random()
                    shape = "overpaid" if r >= second_share else ("settled" if r < second_share / 2 else "topped_up")
                else:
                    prior, shape = False, "prepaid"
                for _try in range(8):
                    if shape == "prepaid":
                        d = self.business_date(h.p_first_date + timedelta(days=1), h.p_last_date - timedelta(days=3))
                        t = self.local_time(d, self.payment_hours())
                        d_inv = self.loose_date(d + timedelta(days=1), min(d + timedelta(days=8), h.p_last_date))
                        ent = self.entity_with("customer", foreign=None)
                        inv = self.add_invoice("sales", ent, self.local_time(d_inv, self.doc_hours()),
                                               self.sales_lines(h.entities[ent].currency, min_usd_total=OPEN_INVOICE_USD))
                        if inv.issued <= t:
                            del h.invoices[inv.key]
                            continue
                        amount = inv.total if rng.random() < 0.6 else max(1, int(inv.total * rng.uniform(0.4, 0.95)))
                        p = self.add_payment("receipt", inv.entity, inv.currency, t, amount, [inv.key], ["prepaid"])
                        keys = [inv.key, p.key]
                    else:
                        inv = self.open_invoice(prior)
                        start = max(inv.issued, h.p0)
                        if shape == "overpaid":
                            t, t2 = self.pay_time_after(start, 1, 14, in_period=True), True
                        else:
                            t = self.pay_time_after(start, 1, 8, in_period=True)
                            t2 = self.pay_time_after(t, 1, 10, in_period=True) if t else None
                        if not t or not t2:
                            del h.invoices[inv.key]
                            continue
                        if shape == "overpaid":
                            excess = max(1, int(inv.total * rng.uniform(0.03, 0.2)))
                            p = self.add_payment("receipt", inv.entity, inv.currency, t, inv.total + excess, [inv.key], ["overpaid"])
                            keys = [inv.key, p.key]
                        elif shape == "topped_up":
                            part = max(1, int(inv.total * rng.uniform(0.3, 0.6)))
                            excess = max(1, int(part * rng.uniform(0.05, 0.8)))
                            p1 = self.add_payment("receipt", inv.entity, inv.currency, t, part, [inv.key], ["part_paid"])
                            p2 = self.add_payment("receipt", inv.entity, inv.currency, t2, inv.total - part + excess, [inv.key], ["topped_up"])
                            keys = [inv.key, p1.key, p2.key]
                        else:
                            p1 = self.add_payment("receipt", inv.entity, inv.currency, t, inv.total, [inv.key], ["settled"])
                            p2 = self.add_payment("receipt", inv.entity, inv.currency, t2, max(1, int(inv.total * rng.uniform(0.3, 1.0))),
                                                  [inv.key], ["repaid"])
                            keys = [inv.key, p1.key, p2.key]
                    h.distractors.append({"kind": "credit_receipt", "keys": keys, "shape": shape})
                    break
                else:
                    raise SampleRetry(f"no room for a {shape} credit receipt")

    def build_repeat_pairs(self, count: int) -> None:
        """Draw `count` line-identical pairs on their own stream. Side and shape are uniform (shapes: those of the allowed
        duplicate variants), so that a pair that inject.convert_pair later turns into a duplicate was drawn like every
        other pair. Each pair is recorded as a legit_repeat distractor until then."""
        shapes = sorted({PAIR_SHAPE_OF_VARIANT[v] for v in self.cfg["variants"]["duplicate_invoice"]})
        with self.stream(self.pair_rng):
            for _ in range(count):
                self.repeat_pair(self.rng.choice(PAIR_SIDES), self.rng.choice(shapes))

    def repeat_pair(self, side: str, shape: str) -> dict:
        """One pair of invoices of one counterparty with identical kind, currency, terms, total and lines except for the
        line reference, which is fresh (a supplier reference inside the description of a purchase, a delivery reference
        on a sales invoice). Shape "same": both carry one instant. The first invoice is paid with probability 1/2 and the
        second never. Shape "later": the second invoice is dated 2 to 9 local days after the first (never after the period's
        last day), at an ordinary document hour, with its own due date (its date plus the shared terms). No size floor
        and no subscription item: the pool does not depend on what the pair becomes."""
        if shape not in ("same", "later"):
            raise ValueError(f"unknown pair shape {shape!r}")
        h, rng = self.h, self.rng
        sup = self.entity_with("customer" if side == "sales" else "supplier")
        ccy = h.entities[sup].currency
        d = self.loose_date(h.p_first_date + timedelta(days=1), h.p_last_date - timedelta(days=3))
        issued = self.local_time(d, self.doc_hours())
        terms = rng.choice([14, 30, 45])
        issued_b = issued
        if shape == "later":
            d2 = self.loose_date(d + timedelta(days=LATER_GAP_DAYS[0]), min(d + timedelta(days=LATER_GAP_DAYS[1]), h.p_last_date))
            issued_b = self.local_time(d2, self.doc_hours())
        if side == "purchase":
            item = rng.choice([it for it in catalog.PURCHASE_ITEMS if "{ym}" not in it[2]])
            unit = self.unit_price_minor(ccy, item[1][0], item[1][1])
            lines_a = self.purchase_lines(ccy, issued, item, unit, sup)
            lines_b = self.purchase_lines(ccy, issued_b, item, unit, sup)
        else:
            lines_a = self.sales_lines(ccy)
            lines_b = self.number_sales_lines([replace(li) for li in lines_a], self.new_ref(catalog.SALES_REF, rng=self.ref_rng))
        a = self.add_invoice(side, sup, issued, lines_a, ["legit_repeat"], terms)
        b = self.add_invoice(side, sup, issued_b, lines_b, ["legit_repeat"], terms)
        keys = [a.key, b.key]
        if rng.random() < 0.5:
            t = self.pay_time_after(a.issued, 2, 15)
            if t:
                keys.append(self.add_payment("receipt" if side == "sales" else "disbursement", sup, a.currency, t, a.total, [a.key]).key)
        entry = {"kind": "legit_repeat", "keys": keys}
        h.distractors.append(entry)
        pair = {"side": side, "shape": shape, "first": a.key, "second": b.key, "entry": entry}
        self.pairs.append(pair)
        return pair

    def floor_usd(self, kind: str, minimum: float = 0.0) -> float:
        """Size floor of an ordinary invoice: half of them clear the same floor as the error targets."""
        if self.rng.random() < LARGE_SHARE:
            return LARGE_SALES_USD if kind == "sales" else LARGE_PURCHASE_USD
        return minimum

    def boundary_document(self, kind: str, error_side: bool) -> list:
        """A correctly booked document or payment right at the period boundary, placed in the same time window
        as the injected boundary errors (utc_wall_clock invoices and the boundary_fx_payment receipt). On the
        error side a payment is drawn like the boundary receipt: foreign, partial, on a large invoice."""
        h = self.h
        if kind in ("sales", "purchase"):
            ts = self.boundary_time(error_side)
            ent = self.entity_with("customer" if kind == "sales" else "supplier")
            ccy = h.entities[ent].currency
            floor = self.floor_usd(kind, 600.0)
            lines = (self.sales_lines(ccy, min_usd_total=floor) if kind == "sales"
                     else self.purchase_lines(ccy, ts, entity=ent, min_usd=floor))
            inv = self.add_invoice(kind, ent, ts, lines, ["boundary"])
            return [inv.key]
        d_inv = self.business_date(h.p_first_date + (timedelta(days=2) if error_side else timedelta(0)),
                                   h.p_last_date - timedelta(days=6 if error_side else 3))
        make = self.random_sales_invoice if kind == "receipt" else self.random_purchase_invoice
        if error_side and h.foreign:
            inv = make(d_inv, foreign=True, min_usd=5000.0)
            amount = int(inv.total * self.rng.uniform(0.4, 0.9))
        else:
            inv = make(d_inv, foreign=bool(h.foreign) and self.rng.random() < 0.6)
            amount = inv.total if self.rng.random() < 0.5 else int(inv.total * self.rng.uniform(0.4, 0.9))
        ts = self.boundary_time(error_side)
        p = self.add_payment(kind, inv.entity, inv.currency, ts, max(1, amount), [inv.key], ["boundary"])
        return [inv.key, p.key]

    def near_midnight_documents(self, payment: bool) -> list | None:
        """A foreign invoice, or a payment on an ordinary invoice, whose local date differs from its UTC date
        (needs a non-zero offset), placed in the same time window as the utc_date FX error documents."""
        h = self.h
        if offset_minutes(h.tz, h.p0) == 0 and offset_minutes(h.tz, h.p1) == 0:
            return None
        for _ in range(60):
            d = self.business_date(h.p_first_date + timedelta(days=3 if payment else 1), h.p_last_date - timedelta(days=1))
            try:
                ts = self.near_midnight_time(d)
            except SampleRetry:
                continue
            kind = "sales" if self.rng.random() < 0.6 else "purchase"
            if payment:
                inv = (self.random_sales_invoice if kind == "sales" else self.random_purchase_invoice)(
                    self.business_date(h.p_first_date, d - timedelta(days=2)), foreign=True)
                amount = inv.total if self.rng.random() < 0.5 else max(1, int(inv.total * self.rng.uniform(0.4, 0.9)))
                p = self.add_payment("receipt" if kind == "sales" else "disbursement", inv.entity, inv.currency, ts, amount, [inv.key], ["midnight"])
                return [inv.key, p.key]
            ent = self.entity_with("customer" if kind == "sales" else "supplier", foreign=True)
            ccy = h.entities[ent].currency
            floor = self.floor_usd(kind)
            lines = (self.sales_lines(ccy, min_usd_total=floor) if kind == "sales"
                     else self.purchase_lines(ccy, ts, entity=ent, min_usd=floor))
            return [self.add_invoice(kind, ent, ts, lines, ["midnight"]).key]
        return None

    # ------------------------------------------------------------ posting lags
    @staticmethod
    def _shift_business(d: date, k: int) -> date:
        """The k-th weekday after d (before d for a negative k)."""
        step, n = (1 if k > 0 else -1), abs(k)
        while n:
            d += timedelta(days=step)
            if d.weekday() < 5:
                n -= 1
        return d

    def _lag_clock(self, d: date, lo: int, hi: int) -> datetime:
        rng = self.lag_rng
        return local_datetime(self.h.tz, d, rng.randint(lo, hi), rng.randint(0, 59), rng.randint(0, 59))

    def _lag_candidate(self, shape: str, ts: datetime) -> datetime | None:
        h, rng = self.h, self.lag_rng
        d0 = h.local_date(ts)
        if shape == "later":
            r = rng.random()
            if r < 0.12:  # under an hour
                return ts + timedelta(minutes=rng.randint(5, 59), seconds=rng.randint(0, 59))
            if r < 0.5:  # hours
                return ts + timedelta(minutes=rng.randint(60, 23 * 60 + 59), seconds=rng.randint(0, 59))
            return self._lag_clock(self._shift_business(d0, rng.randint(1, 5)), 8, 18)
        if shape == "earlier":
            r = rng.random()
            if r < 0.1:
                return ts - timedelta(minutes=rng.randint(5, 59), seconds=rng.randint(0, 59))
            if r < 0.5:
                return ts - timedelta(minutes=rng.randint(60, 30 * 60), seconds=rng.randint(0, 59))
            return self._lag_clock(self._shift_business(d0, -rng.randint(1, 2)), 8, 18)
        if shape == "utc_wall_clock":
            off = offset_minutes(h.tz, ts)
            return ts - timedelta(minutes=off) if off else None
        later = rng.random() < 0.7  # date_change
        days = rng.randint(1, 3) if later else -rng.randint(1, 2)
        return self._lag_clock(d0 + timedelta(days=days), 8, 18)

    def apply_posting_lags(self, extra_invoices: list, fixed: dict, protected: set, error_keys: set) -> None:
        """Give documents a posting moment other than their timestamp (Invoice.posted, Payment.posted).

        Eligible are the documents inside the period and the cut-off documents after it; the posting stays in the same
        period (never crosses the period's end or start, never leaves the extract) and keeps its place in the posting
        order against the documents it interacts with (an invoice and the payments that settle it, payments of one
        invoice), so no allocation or relief changes: a lag moves timestamps only, never an amount or a rate.
        `fixed` holds the posting moments that errors set (wrong_period, posting_date, the boundary receipt) and
        `protected` the documents whose posting moment is the error itself.
        distractors.posting_lag is the number of documents of the extract whose posting is at another instant than the
        document's, the postings that are errors included: the lags of ordinary documents fill what the errors leave of
        it, so the visible count of postings at another instant is drawn per episode and never depends on how many
        errors are injected. The lagged documents are drawn uniformly from all the eligible ones, clean documents,
        members of line-identical pairs (decoys and duplicates alike, converted or not, so a twin keeps the same lags) and
        documents of error issues alike, so a lag says nothing about an answer-key document; only the clean ones are
        recorded as posting_lag distractors. A count that cannot be placed resamples the attempt (an explicit count is
        never silently lowered)."""
        h, rng = self.h, self.lag_rng
        n_lag = int(self.cfg["distractors"].get("posting_lag", 0))
        self.lag_log = []
        if n_lag <= 0:
            return
        docs = {}  # key -> (document, instant, currency)
        for k, inv in h.invoices.items():
            docs[k] = (inv, inv.issued, inv.currency)
        for inv in extra_invoices:
            docs[inv.key] = (inv, inv.issued, inv.currency)
        for k, p in h.payments.items():
            docs[k] = (p, p.ts, p.currency)

        def window(ts):
            if h.p0 <= ts < h.p1:
                return h.p0, h.p1
            if h.p1 <= ts < h.cutoff_end:
                return h.p1 - timedelta(seconds=1), h.cutoff_end
            return None

        def eff(k):
            doc, ts, _c = docs[k]
            return fixed[k] if k in fixed else (doc.posted or ts)

        def moments(k):
            """Every moment at which document k is booked: its own, and for a posting that an error moved also the moment
            of the clean books (the document's), so a lag keeps its place in the posting order in both sets of books."""
            return {eff(k), docs[k][1]} if k in fixed else {eff(k)}

        eligible = {k for k, (_d, ts, _c) in docs.items() if k not in protected and window(ts)}
        pair_set = {k for pair in self.pairs for k in (pair["first"], pair["second"]) if k in eligible}
        # postings that are errors already sit at another instant; they count toward the episode's total
        budget = n_lag - sum(1 for k, v in fixed.items() if k in docs and v != docs[k][1])
        # Draw the direction mix before selecting documents. Postings moved by errors
        # use slots of their own direction, including when they already fill a quota.
        directions = rng.fork("directions")
        target_later = sum(directions.random() < 0.45 for _ in range(n_lag))
        fixed_later = sum(1 for k, v in fixed.items() if k in docs and v > docs[k][1])
        later_slots = max(0, min(budget, target_later - fixed_later))
        direction_slots = {True: later_slots, False: budget - later_slots}
        by_invoice = defaultdict(list)
        for p in h.payments.values():
            for ref in p.refs or []:
                if ref in docs:
                    by_invoice[ref].append(p.key)
        related = defaultdict(set)
        for ref, pays in by_invoice.items():
            for a in pays:
                related[a].add(ref)
                related[ref].add(a)
                related[a].update(x for x in pays if x != a)
        taken = {eff(k) for k in docs} | set(self._used_times)

        def place(key, role) -> bool:
            doc, ts, ccy = docs[key]
            lo_w, hi_w = window(ts)
            cur = eff(key)
            before = [m for x in related[key] if x in docs for m in moments(x) if m <= cur]
            after = [m for x in related[key] if x in docs for m in moments(x) if m > cur]
            lo = max([lo_w] + before)
            hi = min([hi_w] + after)
            d0 = h.local_date(ts)
            off = offset_minutes(h.tz, ts)
            shapes = list(LAG_SHAPES if ccy != h.base else LAG_SHAPES[:3])
            rng.shuffle(shapes)
            for shape in shapes:
                for _ in range(1 if shape == "utc_wall_clock" else LAG_TRIES):
                    cand = self._lag_candidate(shape, ts)
                    if cand is None:
                        break
                    if not (lo < cand < hi) or cand in taken or in_ambiguous_hour(h.tz, cand):
                        continue
                    if (shape == "later" and cand <= ts) or (shape == "earlier" and cand >= ts):
                        continue
                    if shape == "utc_wall_clock" and offset_minutes(h.tz, cand) != off:
                        continue
                    if shape == "date_change":
                        day = h.local_date(cand)
                        r_doc, r_post = self.rate_on(ccy, d0), self.rate_on(ccy, day)
                        if day == d0 or r_doc is None or r_post is None or r_doc[0] == r_post[0]:
                            continue
                    later = cand > ts
                    if direction_slots[later] == 0:
                        continue
                    direction_slots[later] -= 1
                    doc.posted = cand
                    taken.add(cand)
                    self.lag_log.append({"key": key, "shape": shape, "role": role})
                    return True
            return False

        placed = 0
        for key in rng.sample(sorted(eligible), len(eligible)):
            if placed >= budget:
                break
            role = "pair" if key in pair_set else ("error" if key in error_keys else "distractor")
            if place(key, role):
                placed += 1
                if role == "distractor":
                    h.distractors.append({"kind": "posting_lag", "keys": [key], "shape": self.lag_log[-1]["shape"]})
        if placed < budget:
            raise SampleRetry(f"only {placed} of {budget} posting lags could be placed")

    # ------------------------------------------------------------ FX
    def choose_holidays(self) -> None:
        """Days without a published rate. Drawn before the errors are planned, so an error target can fall on
        a holiday like any ordinary document; the period boundary days stay business days."""
        h, rng = self.h, self.rng
        candidates = [d for d in self.period_dates(weekday_only=True) if d not in (h.p_first_date, h.p_last_date)]
        h.holidays = sorted(rng.sample(candidates, k=min(rng.randint(0, 2), len(candidates))))

    def build_fx(self) -> None:
        h, rng = self.h, self.rng
        start = h.local_date(h.lookback_start) - timedelta(days=FX_MARGIN_DAYS)
        end = h.local_date(h.cutoff_end) + timedelta(days=1)
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

    def lift_opening_bank(self, lines: list) -> bool:
        """Raise the opening bank balance (deterministically, no RNG draw) so that the running bank balance of
        the clean books never goes negative; a margin of 2 % of all bank outflows also covers the small
        differences the injected errors make. Returns True when the balance changed."""
        bal, low, outflow = 0, None, 0
        for ln in lines:  # lines are in posting order
            if ln.account == "1000":
                bal += ln.debit - ln.credit
                outflow += ln.credit
                low = bal if low is None else min(low, bal)
        floor_balance = outflow // 50
        if low is None or low >= floor_balance:
            return False
        grain = 10 ** (self.h.exponents[self.h.base] + 3)
        self.h.opening_bank += -(-(floor_balance - low) // grain) * grain
        return True

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
