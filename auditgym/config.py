"""Generator configuration: schema, defaults, validation, deterministic resolution.

A config only states what is wanted; every unspecified choice is drawn from
the episode RNG during resolution, and the fully resolved config is stored in
provenance.json. Infeasible requests raise ConfigError: the generator never
silently injects fewer errors than requested.
"""

from __future__ import annotations

from datetime import timedelta

from . import CONFIG_VERSION, FINDING_TYPES
from .catalog import BASE_CURRENCIES, FOREIGN_POOL, TZ_FOR_BASE
from .ids import STYLES
from .money import CURRENCY_EXPONENTS
from .rng import Rng
from .timeutil import TZ_RULES, local_date, local_datetime, month_bounds, offset_minutes


class ConfigError(ValueError):
    pass


VARIANTS = {
    "duplicate_invoice": ("same_day_copy", "rekeyed_copy"),
    "unallocated_payment": ("missing", "partial"),
    "wrong_fx_rate": ("utc_date", "posting_date", "stale_rate", "transposed"),
    "wrong_period": ("booked_early", "booked_late", "utc_wall_clock"),
}
INTERACTING = ("boundary_fx_payment", "fx_invoice_partial_allocation")
DISTRACTORS = (
    "legit_repeat",
    "recurring",
    "split_payment",
    "multi_invoice_payment",
    "underpayment",
    "overpayment_refund",
    "null_ref_receipt",
    "boundary_doc",
    "midnight_fx",
    "weekend_fx",
    "posting_lag",
    "credit_receipt",
    "prepaid_receipt",
    "split_remainder",
)
SIZES = {
    "small": {"customers": (6, 9), "suppliers": (5, 7), "sales_invoices": (14, 22), "purchase_invoices": (8, 12),
              "prior_invoices": (3, 5), "target_rows": (220, 420)},
    "medium": {"customers": (10, 15), "suppliers": (7, 10), "sales_invoices": (30, 42), "purchase_invoices": (15, 22),
               "prior_invoices": (5, 8), "target_rows": (600, 1000)},
    "large": {"customers": (14, 20), "suppliers": (9, 13), "sales_invoices": (26, 30), "purchase_invoices": (12, 15),
              "prior_invoices": (5, 8), "target_rows": (1500, 2000)},
}
# The case suggests 20 to 200 documents and 200 to 2,000 ledger rows per episode. The `large` ranges above give 161 to 198 documents
# in 40 default-config seeds (before round 10: 198 to 251). The suggestion is not enforced: more errors and distractors add documents.
DEFAULT_DISTRACTORS = {
    "small": {"recurring": 1, "split_payment": 1, "multi_invoice_payment": 1, "underpayment": 1,
              "midnight_fx": 2, "weekend_fx": 1},
    "medium": {"recurring": 2, "split_payment": 2, "multi_invoice_payment": 1, "underpayment": 2,
               "midnight_fx": 3, "weekend_fx": 2},
    "large": {"recurring": 3, "split_payment": 3, "multi_invoice_payment": 2, "underpayment": 3,
              "midnight_fx": 4, "weekend_fx": 3},
}
# default counts drawn from a range (an explicit count in the config stays exact); a fixed default would let the
# number of boundary documents separate episodes with boundary errors from clean ones
DEFAULT_DISTRACTOR_RANGES = {
    "small": {"boundary_doc": (2, 7), "posting_lag": (12, 22), "overpayment_refund": (1, 3), "null_ref_receipt": (1, 3),
              "split_remainder": (1, 4)},
    "medium": {"boundary_doc": (3, 8), "posting_lag": (24, 38), "overpayment_refund": (1, 3), "null_ref_receipt": (2, 4),
               "split_remainder": (2, 5)},
    "large": {"boundary_doc": (4, 8), "posting_lag": (32, 50), "overpayment_refund": (2, 4), "null_ref_receipt": (2, 4),
              "split_remainder": (2, 6)},
}
# credit_receipt: a receipt that leaves a customer credit in 2900 although it is not an error, in three over-received shapes
# (an overpayment that is not refunded, a second receipt on an invoice that is already settled, a part payment topped up by a
# receipt above the rest; every one is credited to 2900 by policy because no invoice balance is open to relieve), and
# prepaid_receipt, a receipt that names an invoice issued after it. The unallocated_payment errors take the place of
# prepaid receipts, so the number of invoices whose receipts sum above their total, the number of settled and topped-up
# receipts and the rows on 2900 that those explain never depend on how many errors are injected; what an error changes is
# the number of prepaid receipts, which is zero in half of the episodes and otherwise drawn from a range, so that it says little (a fresh unallocated
# receipt names an invoice that was issued before it, like every other 2900 credit that is not prepaid).
CREDIT_OVER_RANGES = {"small": (2, 4), "medium": (3, 5), "large": (3, 6)}
PREPAID_RANGES = {"small": (1, 5), "medium": (1, 6), "large": (1, 7)}
PREPAID_ZERO_SHARE = 0.5  # half of the episodes draw no prepaid receipt at all, so "no receipt dated before its invoice" is common
# share of the fresh unallocated receipts (and of the over-received credit receipts) whose invoice was issued before the
# period (an opening item); the prior invoices an error brings are taken out of counts.prior_invoices
UNALLOCATED_PRIOR_SHARE = 0.35
# The document a standalone wrong_fx_rate or wrong_period error sits on: an invoice, a customer receipt or a supplier
# disbursement (a payment target comes with the invoice it settles). The shares are tuned by measurement (auditgym.tells,
# rules "a receipt" and "a disbursement") so that a receipt, a disbursement and an invoice are in the answer key at about
# the same rate; before 0.4.0 these two errors were always on an invoice, so a policy could skip payments for them.
TARGET_KINDS = ("invoice", "receipt", "disbursement")
TARGET_KIND_SHARES = (0.34, 0.36, 0.30)
TARGETED_TYPES = ("wrong_fx_rate", "wrong_period")
# split_remainder (ranges in DEFAULT_DISTRACTOR_RANGES): a part payment followed by a second receipt that leaves a rest of the invoice open (both relieve 1100 in
# full, nothing goes to 2900); per episode, on a fork, so that an invoice with two receipts below its total is no tell
# posting_lag: the number of documents of the extract whose posting is booked at another instant than the document's (invoices
# and payments of both sides and currencies), the postings that are errors included. It is about a quarter of the documents of
# the period, drawn per episode, and the lags of ordinary documents fill what the errors leave of it, so neither the count nor
# a share of it depends on how many errors are injected. The lagged documents are drawn uniformly from the clean ones, the
# pair members and the documents of error issues alike. (An explicit 0 therefore leaves only the errors' own postings at
# another instant: a diagnostic setting, not for a split or a check set.)
FORKED_RANGES = ("posting_lag", "overpayment_refund", "null_ref_receipt", "split_remainder")
MAX_POSTING_LAG = 64
# Line-identical pairs of one counterparty (the decoys and the sources of duplicate_invoice errors alike). The visible
# count is drawn from this range per size and holds duplicates, so it never depends on how many errors are injected.
DEFAULT_REPEAT_PAIRS = {"small": (2, 4), "medium": (3, 5), "large": (3, 6)}
TOP_KEYS = {
    "config_version", "size", "base_currency", "foreign_currencies", "timezone", "period", "rounding", "id_style",
    "ts_repr", "row_order", "errors", "variants", "interacting", "distractors", "counts", "twin",
}
MAX_ERRORS = 12
TS_REPRS = ("local", "utc", "mixed")
ROW_ORDERS = ("time", "shuffled")
ROUNDINGS = ("half_even", "half_up")


def _int_in(value, lo, hi, name):
    if not isinstance(value, int) or isinstance(value, bool) or not lo <= value <= hi:
        raise ConfigError(f"{name} must be an integer in [{lo}, {hi}]")
    return value


def validate(config: dict) -> dict:
    if not isinstance(config, dict):
        raise ConfigError("config must be an object")
    unknown = sorted(set(config) - TOP_KEYS)
    if unknown:
        raise ConfigError(f"unknown config keys: {', '.join(unknown)}")
    cv = str(config.get("config_version", CONFIG_VERSION))
    if cv != CONFIG_VERSION:
        raise ConfigError(f"unsupported config_version {cv!r}; this generator reads {CONFIG_VERSION!r}")
    size = config.get("size", "small")
    if size not in SIZES:
        raise ConfigError(f"size must be one of {', '.join(SIZES)}")
    base = config.get("base_currency")
    if base is not None and base not in CURRENCY_EXPONENTS:
        raise ConfigError(f"unknown base_currency {base!r}")
    foreign = config.get("foreign_currencies")
    if foreign is not None:
        if not isinstance(foreign, list) or any(c not in CURRENCY_EXPONENTS for c in foreign):
            raise ConfigError("foreign_currencies must be a list of known currency codes")
        if base is not None and base in foreign:
            raise ConfigError("foreign_currencies must not contain the base currency")
        if len(set(foreign)) != len(foreign) or len(foreign) > 3:
            raise ConfigError("foreign_currencies: at most 3 distinct codes")
    tz = config.get("timezone")
    if tz is not None and tz not in TZ_RULES:
        raise ConfigError(f"unknown timezone {tz!r}; supported: {', '.join(TZ_RULES)}")
    period = config.get("period")
    if period is not None:
        try:
            y, m = (int(p) for p in str(period).split("-"))
            if not (2000 <= y <= 2100 and 1 <= m <= 12):
                raise ValueError
        except ValueError:
            raise ConfigError("period must look like 'YYYY-MM'") from None
    for key, allowed in (("rounding", ROUNDINGS), ("id_style", STYLES), ("ts_repr", TS_REPRS), ("row_order", ROW_ORDERS)):
        if config.get(key) is not None and config[key] not in allowed:
            raise ConfigError(f"{key} must be one of {', '.join(allowed)}")
    errors = config.get("errors", {}) or {}
    if not isinstance(errors, dict) or any(k not in FINDING_TYPES for k in errors):
        raise ConfigError(f"errors keys must be among {', '.join(FINDING_TYPES)}")
    for k, v in errors.items():
        _int_in(v, 0, MAX_ERRORS, f"errors.{k}")
    variants = config.get("variants", {}) or {}
    if not isinstance(variants, dict):
        raise ConfigError("variants must be an object")
    for k, v in variants.items():
        if k not in VARIANTS or not isinstance(v, list) or not v or any(x not in VARIANTS[k] for x in v):
            raise ConfigError(f"variants.{k} must be a non-empty list from {', '.join(VARIANTS.get(k, ()))}")
    inter = config.get("interacting", []) or []
    if not isinstance(inter, list) or any(x not in INTERACTING for x in inter):
        raise ConfigError(f"interacting must be a list from {', '.join(INTERACTING)}")
    if "fx_invoice_partial_allocation" in inter and "partial" not in (variants.get("unallocated_payment") or ["partial"]):
        raise ConfigError("fx_invoice_partial_allocation needs the 'partial' variant of unallocated_payment")
    total = sum(errors.values()) + 2 * len(inter)
    if total > MAX_ERRORS:
        raise ConfigError(f"at most {MAX_ERRORS} errors per episode (requested {total})")
    distractors = config.get("distractors")
    if distractors is not None:
        if not isinstance(distractors, dict) or any(k not in DISTRACTORS for k in distractors):
            raise ConfigError(f"distractors keys must be among {', '.join(DISTRACTORS)}")
        for k, v in distractors.items():
            _int_in(v, 0, MAX_POSTING_LAG if k == "posting_lag" else 8, f"distractors.{k}")
    if "twin" in config and not isinstance(config["twin"], bool):
        raise ConfigError("twin must be true or false")
    counts = config.get("counts")
    if counts is not None:
        if not isinstance(counts, dict) or any(k not in SIZES["small"] for k in counts):
            raise ConfigError(f"counts keys must be among {', '.join(SIZES['small'])}")
        for k, v in counts.items():
            _int_in(v, 1 if k != "prior_invoices" else 0, 2000, f"counts.{k}")
    return config


STEP_BUDGET = 100  # env.DEFAULT_MAX_STEPS; the generator rejects an episode whose full read does not fit (verify budget_feasible)
PAGE_ROWS = 50  # schemas.MAX_PAGE, the largest list_records page


def min_read_pages(counts: dict) -> int:
    """A lower bound on the list_records pages a full read needs, from the counts alone. Every prior, sales and
    purchase invoice is one invoices row and books at least two ledger rows (a debit and a credit); injected errors
    add or move rows, never remove them (tests/test_generator.py checks both on the committed episodes)."""
    n = counts["prior_invoices"] + counts["sales_invoices"] + counts["purchase_invoices"]
    return -(-n // PAGE_ROWS) + -(-2 * n // PAGE_ROWS)


def draw_target_kinds(rng: Rng, errors: dict) -> dict:
    """{"wrong_fx_rate": [...], "wrong_period": [...]}: the target kind of every standalone error of the two types, in the
    order the errors are planned, drawn with TARGET_KIND_SHARES (on a stream of its own, see resolve)."""
    out = {}
    for etype in TARGETED_TYPES:
        kinds = []
        for _ in range(int(errors.get(etype, 0))):
            r, acc, kind = rng.random(), 0.0, TARGET_KINDS[-1]
            for cand, share in zip(TARGET_KINDS, TARGET_KIND_SHARES):
                acc += share
                if r < acc:
                    kind = cand
                    break
            kinds.append(kind)
        out[etype] = kinds
    return out


def error_invoice_load(config: dict, target_kinds: dict | None = None) -> tuple[int, int]:
    """(sales, purchase) invoices that the requested errors add on top of the ordinary ones: the boundary receipt's invoice (a
    sales invoice) and one invoice for every wrong rate and wrong period: a sales invoice under a receipt target, a purchase
    invoice under a disbursement target and an invoice of either side (split evenly, the side is drawn) for an invoice target
    (without `target_kinds` every target counts as an invoice). An
    unallocated receipt adds an invoice as well, but it takes the place of a credit receipt, whose count (and invoice) shrinks
    by one for it (CREDIT_TOTAL_RANGES), so it needs no deduction here; the fx_invoice_partial_allocation scenario shares the
    invoice of its wrong rate with the receipt and nets out the same way."""
    errors = config.get("errors") or {}
    inter = config.get("interacting") or []
    either = int(errors.get("wrong_fx_rate", 0)) + int(errors.get("wrong_period", 0))
    kinds = [k for ks in (target_kinds or {}).values() for k in ks]
    receipts, disbursements = kinds.count("receipt"), kinds.count("disbursement")
    either -= receipts + disbursements
    return ("boundary_fx_payment" in inter) + receipts + (either + 1) // 2, disbursements + either // 2


def resolve(config: dict, rng: Rng) -> dict:
    """Return a fully specified config. Raises ConfigError when infeasible."""
    validate(config)
    size = config.get("size", "small")
    needs_foreign = bool(config.get("errors", {}).get("wrong_fx_rate")) or bool(config.get("interacting"))
    base = config.get("base_currency") or rng.choice(BASE_CURRENCIES)
    foreign = config.get("foreign_currencies")
    if foreign is None:
        pool = [c for c in FOREIGN_POOL.get(base, ["USD", "EUR"]) if c != base]
        foreign = rng.sample(pool, k=rng.randint(1, min(3, len(pool))))
    if needs_foreign and not foreign:
        raise ConfigError("wrong_fx_rate and interacting scenarios need at least one foreign currency")
    tz_fixed = config.get("timezone") is not None
    period_fixed = config.get("period") is not None
    tz = config.get("timezone")
    if tz is None:
        tz = rng.choice(TZ_FOR_BASE.get(base, ["UTC"])) if rng.random() < 0.7 else rng.choice(sorted(TZ_RULES))
    inter = list(config.get("interacting", []) or [])
    variants = {k: list(v) for k, v in (config.get("variants") or {}).items()}
    needs = _needs(config, inter, variants)
    if tz_fixed and _never_offset(tz) and (needs["boundary_offset"] or needs["utc_date"]):
        raise ConfigError(f"timezone {tz} never has a UTC offset, but the requested errors need one")
    if "boundary_fx_payment" in inter and _never_offset(tz):
        tz = "Asia/Almaty"
    period = config.get("period")
    if period is None:
        period = _pick_period(rng, inter)
    else:
        y, m = (int(p) for p in str(period).split("-"))
        period = f"{y:04d}-{m:02d}"
        # a fixed zone's own offset decides; a fixed zero offset is left to the offset message below
        fixed_off = offset_minutes(tz, month_bounds(tz, y, m)[1]) if tz_fixed else None
        if (needs["boundary_weekdays"] and not needs["boundary_fx_fallback"] and fixed_off != 0
                and not (boundary_utc_date_ok(period, fixed_off) if tz_fixed else _boundary_utc_date_possible(period))):
            near = _nearest_boundary_periods(period, tz if tz_fixed else None)
            raise ConfigError("boundary_fx_payment without the stale_rate or transposed variant of wrong_fx_rate needs the first "
                              "day after the period to be a weekday (and the last day too, unless the UTC offset there is positive); "
                              f"period {period} fails that. Nearest feasible periods: {', '.join(near)}. "
                              "Allow the stale_rate or transposed variant of wrong_fx_rate to use any month")
    # Unspecified time zone or period are redrawn (on a side stream, so feasible draws stay unchanged)
    # until the requested errors can be placed; only a fully fixed infeasible request is an error.
    problems = feasibility_problems(tz, period, needs)
    k = 0
    while problems:
        if tz_fixed and period_fixed:
            raise ConfigError(f"timezone {tz} with period {period} cannot carry the requested errors; they need "
                              + "; ".join(problems))
        k += 1
        if k > 400:
            raise ConfigError("no feasible timezone and period found; the requested errors need " + "; ".join(problems))
        alt = rng.fork(f"feasible:{k}")
        if not tz_fixed and (period_fixed or k % 2 == 1):
            tz = alt.choice(sorted(TZ_RULES))
        if not period_fixed and (tz_fixed or k % 2 == 0):
            period = _pick_period(alt, inter)
        problems = feasibility_problems(tz, period, needs)
    counts = {}
    for k, (lo, hi) in SIZES[size].items():
        counts[k] = (config.get("counts") or {}).get(k, rng.randint(lo, hi))
    # Every wrong_fx_rate and wrong_period error (and the boundary scenario) adds an invoice of its own on top of the ordinary
    # ones; those are taken out of the drawn counts, so the number of invoices of an episode never depends on how many errors
    # it holds (an explicit count stays exact).
    errors = {t: int((config.get("errors") or {}).get(t, 0)) for t in FINDING_TYPES}
    # on a fork: the kinds are known before the history is drawn (a payment target's invoice is a paid one) and no other
    # resolved field moves with them
    target_kinds = draw_target_kinds(rng.fork("target_kinds"), errors)
    sales_red, purchase_red = error_invoice_load(config, target_kinds)
    load = {"sales": 0, "purchase": 0, "sales_paid": 0, "purchase_paid": 0}
    for k, red in (("sales_invoices", sales_red), ("purchase_invoices", purchase_red)):
        if k not in (config.get("counts") or {}):
            before = counts[k]
            counts[k] = max(1, before - red)
            load[k.split("_")[0]] = before - counts[k]
    # the boundary scenario's invoice is paid by its receipt and the invoice of a payment target by that payment; the
    # invoices that are themselves the target of an error are never paid
    n_receipts = sum(ks.count("receipt") for ks in target_kinds.values())
    n_disbursements = sum(ks.count("disbursement") for ks in target_kinds.values())
    load["sales_paid"] = min(load["sales"], ("boundary_fx_payment" in inter) + n_receipts)
    load["purchase_paid"] = min(load["purchase"], n_disbursements)
    # A fresh unallocated receipt sits on an opening item with the share UNALLOCATED_PRIOR_SHARE (drawn here, so the prior
    # invoices it brings can be taken out of counts.prior_invoices: the number of opening items never depends on the errors)
    prior_rng = rng.fork("unallocated_prior")
    prior_hits = sum(prior_rng.random() < UNALLOCATED_PRIOR_SHARE for _ in range(errors["unallocated_payment"]))
    if "prior_invoices" not in (config.get("counts") or {}):
        counts["prior_invoices"] = max(0, counts["prior_invoices"] - prior_hits)
    floor = min_read_pages(counts)
    if floor + 1 > STEP_BUDGET:
        n = counts["prior_invoices"] + counts["sales_invoices"] + counts["purchase_invoices"]
        raise ConfigError(f"counts too large for the {STEP_BUDGET}-step budget: {n} prior, sales and purchase invoices "
                          f"need at least {floor} pages to read in full, plus the submit; lower those counts")
    distractors = dict(DEFAULT_DISTRACTORS[size])
    for k, (lo, hi) in DEFAULT_DISTRACTOR_RANGES[size].items():
        # posting_lag is drawn on its own fork, so the draws that follow (the repeat pairs fork, everything else) stay put
        distractors[k] = (rng.fork(f"distractor:{k}") if k in FORKED_RANGES else rng).randint(lo, hi)
    n_dup = errors["duplicate_invoice"]
    explicit = dict(config.get("distractors") or {})
    n_unalloc = errors["unallocated_payment"] + ("fx_invoice_partial_allocation" in inter)
    distractors["credit_receipt"] = rng.fork("distractor:credit_receipt").randint(*CREDIT_OVER_RANGES[size])
    pre = rng.fork("distractor:prepaid_receipt")
    drawn_prepaid = 0 if pre.random() < PREPAID_ZERO_SHARE else pre.randint(*PREPAID_RANGES[size])
    distractors["prepaid_receipt"] = max(0, drawn_prepaid - n_unalloc)
    lo, hi = DEFAULT_REPEAT_PAIRS[size]
    # drawn on a fork, so every other resolved field keeps its draw order when the range is retuned
    drawn = rng.fork("repeat_pairs").randint(lo, hi)
    # a duplicate count above the range's lower bound would crowd the decoys out (every visible pair a duplicate), so
    # then the decoys are drawn on top of the duplicates; for D at most lo this is the old draw
    pairs = drawn if n_dup <= lo else n_dup + drawn
    if "legit_repeat" in explicit:  # an explicit count keeps its meaning: the number of legitimate repeats
        pairs = explicit["legit_repeat"] + n_dup
    distractors.update(explicit)
    distractors["legit_repeat"] = pairs - n_dup
    return {
        "config_version": CONFIG_VERSION,
        "size": size,
        "base_currency": base,
        "foreign_currencies": list(foreign),
        "timezone": tz,
        "period": period,
        "rounding": config.get("rounding") or rng.choice(ROUNDINGS),
        "id_style": config.get("id_style") or rng.choice(STYLES),
        "ts_repr": config.get("ts_repr") or rng.choice(TS_REPRS),
        "row_order": config.get("row_order") or rng.choice(ROW_ORDERS),
        "errors": errors,
        "variants": {t: variants.get(t, list(VARIANTS[t])) for t in FINDING_TYPES},
        "interacting": inter,
        "distractors": distractors,
        "repeat_pairs": pairs,
        "counts": counts,
        "unallocated_prior": prior_hits,
        "error_invoice_load": load,
        "target_kinds": target_kinds,
        "twin": bool(config.get("twin", False)),
    }


def _never_offset(tz: str) -> bool:
    return TZ_RULES[tz][1] == 0 and TZ_RULES[tz][2] == 0


def _needs(config: dict, inter: list, variants: dict) -> dict:
    errors = config.get("errors") or {}
    period_variants = set(variants.get("wrong_period", VARIANTS["wrong_period"]))
    fx_variants = set(variants.get("wrong_fx_rate", VARIANTS["wrong_fx_rate"]))
    return {
        "boundary_offset": "boundary_fx_payment" in inter or (bool(errors.get("wrong_period")) and period_variants <= {"utc_wall_clock"}),
        "boundary_weekdays": "boundary_fx_payment" in inter,
        # a month whose boundary gives the utc_date error no amount still hosts the scenario with one of these variants
        "boundary_fx_fallback": bool(fx_variants & set(BOUNDARY_FX_FALLBACK)),
        "utc_date": bool(errors.get("wrong_fx_rate")) and fx_variants <= {"utc_date"},
    }


def utc_date_days(tz: str, year: int, month: int, late_limit: int) -> list:
    """Weekdays (not the first or last of the period) whose UTC date differs from
    the local date for some local time, with a published rate on both dates."""
    p0, p1 = month_bounds(tz, year, month)
    first, last = local_date(p0, tz), local_date(p1 - timedelta(seconds=1), tz)
    weekdays = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    weekdays = [d for d in weekdays if d.weekday() < 5][1:-1]
    out = []
    for d in weekdays:
        off = offset_minutes(tz, local_datetime(tz, d, 12))
        if d > last - timedelta(days=late_limit):
            continue
        if off > 0 or (off < 0 and (d + timedelta(days=1)).weekday() < 5):
            out.append(d)
    return out


def feasibility_problems(tz: str, period: str, needs: dict) -> list:
    y, m = (int(p) for p in period.split("-"))
    _p0, p1 = month_bounds(tz, y, m)
    problems = []
    off = offset_minutes(tz, p1)
    if needs["boundary_offset"] and off == 0:
        problems.append("a non-zero UTC offset at the period boundary")
    if (needs["boundary_weekdays"] and not needs.get("boundary_fx_fallback") and off != 0
            and not boundary_utc_date_ok(period, off)):
        problems.append("a period boundary at which the utc_date rate error has an amount (the first day after the period a weekday, and the last day too unless the UTC offset is positive)")
    if needs["utc_date"] and not utc_date_days(tz, y, m, 2):
        problems.append("a weekday whose UTC date differs from the local date (utc_date)")
    return problems


BOUNDARY_FX_FALLBACK = ("stale_rate", "transposed")


def boundary_utc_date_ok(period: str, off: int) -> bool:
    """True when the receipt at the period boundary can carry a utc_date rate error that has an amount.

    Rates are published on weekdays only and a weekend date takes the latest earlier rate. A positive offset puts the
    local date on the first day after the period and the UTC date on the last day: they differ in rate when that first
    day is a weekday. A negative offset puts the local date on the last day, which must itself be a weekday (the
    document's own date carries a published rate), and the UTC date on the first day after, a weekday so that its rate
    differs from the local date's."""
    import datetime as _dt

    y, m = (int(p) for p in period.split("-"))
    first_next = _dt.date(y + (m == 12), m % 12 + 1, 1)
    last = first_next - _dt.timedelta(days=1)
    if off > 0:
        return first_next.weekday() < 5
    return off < 0 and first_next.weekday() < 5 and last.weekday() < 5


def _boundary_utc_date_possible(period: str) -> bool:
    return boundary_utc_date_ok(period, 1) or boundary_utc_date_ok(period, -1)


def _boundary_ok(period: str) -> bool:
    import datetime as _dt

    y, m = (int(p) for p in period.split("-"))
    first_next = _dt.date(y + (m == 12), m % 12 + 1, 1)
    last = first_next - _dt.timedelta(days=1)
    return first_next.weekday() < 5 and last.weekday() < 5


def _nearest_boundary_periods(period: str, tz: str | None = None, count: int = 2) -> list[str]:
    """The months closest to `period` within 2000-2100 that can carry a utc_date rate error at the boundary, nearest first
    (earlier before later on a tie). With a fixed `tz` its own UTC offset decides; without one, any offset sign counts."""
    y, m = (int(p) for p in period.split("-"))
    idx = y * 12 + m - 1
    found = []
    for step in range(1, 25):
        for cand in (idx - step, idx + step):
            cy, cm = divmod(cand, 12)
            if not 2000 <= cy <= 2100:
                continue
            label = f"{cy:04d}-{cm + 1:02d}"
            if tz:
                ok = boundary_utc_date_ok(label, offset_minutes(tz, month_bounds(tz, cy, cm + 1)[1]))
            else:
                ok = _boundary_utc_date_possible(label)
            if ok:
                found.append(label)
        if len(found) >= count:
            break
    return found[:count] or ["none within 24 months"]


def _pick_period(rng: Rng, inter: list) -> str:
    for _ in range(200):
        y = rng.choice([2025, 2026, 2027])
        m = rng.randint(1, 12)
        period = f"{y:04d}-{m:02d}"
        if "boundary_fx_payment" not in inter or _boundary_ok(period):
            return period
    raise ConfigError("could not find a feasible period")
