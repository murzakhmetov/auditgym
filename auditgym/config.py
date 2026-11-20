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
    "duplicate_invoice": ("same_day_copy",),
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
)
SIZES = {
    "small": {"customers": (6, 9), "suppliers": (5, 7), "sales_invoices": (14, 22), "purchase_invoices": (8, 12),
              "prior_invoices": (3, 5), "target_rows": (220, 420)},
    "medium": {"customers": (10, 15), "suppliers": (7, 10), "sales_invoices": (30, 42), "purchase_invoices": (15, 22),
               "prior_invoices": (5, 8), "target_rows": (600, 1000)},
    "large": {"customers": (14, 20), "suppliers": (9, 13), "sales_invoices": (40, 50), "purchase_invoices": (18, 24),
              "prior_invoices": (5, 8), "target_rows": (1500, 2000)},
}
DEFAULT_DISTRACTORS = {
    "small": {"legit_repeat": 1, "recurring": 1, "split_payment": 1, "multi_invoice_payment": 1, "underpayment": 1,
              "overpayment_refund": 1, "null_ref_receipt": 1, "midnight_fx": 2, "weekend_fx": 1},
    "medium": {"legit_repeat": 2, "recurring": 2, "split_payment": 2, "multi_invoice_payment": 1, "underpayment": 2,
               "overpayment_refund": 1, "null_ref_receipt": 2, "midnight_fx": 3, "weekend_fx": 2},
    "large": {"legit_repeat": 3, "recurring": 3, "split_payment": 3, "multi_invoice_payment": 2, "underpayment": 3,
              "overpayment_refund": 2, "null_ref_receipt": 2, "midnight_fx": 4, "weekend_fx": 3},
}
# default counts drawn from a range (an explicit count in the config stays exact); a fixed default would let the
# number of boundary documents separate episodes with boundary errors from clean ones
DEFAULT_DISTRACTOR_RANGES = {
    "small": {"boundary_doc": (2, 7)},
    "medium": {"boundary_doc": (3, 8)},
    "large": {"boundary_doc": (4, 8)},
}
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
            _int_in(v, 0, 8, f"distractors.{k}")
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
    floor = min_read_pages(counts)
    if floor + 1 > STEP_BUDGET:
        n = counts["prior_invoices"] + counts["sales_invoices"] + counts["purchase_invoices"]
        raise ConfigError(f"counts too large for the {STEP_BUDGET}-step budget: {n} prior, sales and purchase invoices "
                          f"need at least {floor} pages to read in full, plus the submit; lower those counts")
    distractors = dict(DEFAULT_DISTRACTORS[size])
    for k, (lo, hi) in DEFAULT_DISTRACTOR_RANGES[size].items():
        distractors[k] = rng.randint(lo, hi)
    distractors.update(config.get("distractors") or {})
    errors = {t: int((config.get("errors") or {}).get(t, 0)) for t in FINDING_TYPES}
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
        "counts": counts,
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
