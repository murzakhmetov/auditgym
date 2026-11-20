"""Harmless transformations for paired checks.

* permute_seed: shuffles the order of ledger rows, invoices, payments and FX rows;
* remap_seed:   replaces every public ID (rows, documents, invoices, payments,
                entities) by a fresh opaque ID, consistently in records, answer
                key and provenance;
* ts_repr:      re-writes every timestamp as the same instant with another
                offset ("utc", "local" company time, or "mixed");
* rename_seed:  replaces the company name and every invoice line description
                by fresh synthetic wording from a seeded injective mapping,
                consistently in records and provenance. Reference tokens inside
                a description (e.g. "SUB-2025-05-6014") are kept.
* shift_years:  moves every calendar year by K years, K a nonzero multiple of 28 (see the SHIFT_* constants, _check_shift and _shift_deep).

The answer is unchanged up to the ID mapping, so the oracle's reward must not
change. Available as AuditEnv.reset(config={"transform": {...}}) and as
`python -m auditgym transform` (--permute-seed, --remap-seed, --ts-repr, --rename-seed, --shift-years).
Counterparties appear in the public records only as entity IDs, which remap_seed replaces.
"""

from __future__ import annotations

import copy
import hashlib
import re

from . import catalog
from .auditor import OffsetSchedule
from .episode import Episode
from .ids import STYLES, IdFactory
from .rng import Rng, seed_from_text
from .timeutil import format_ts, format_utc, parse_ts
from .verify import reconstruct_clean, records_digest

ALT_OFFSETS = (-420, -180, 0, 60, 345, 480, 660)

# Year shift. The Gregorian weekday and leap-year pattern repeats every 28 years while no non-leap century year
# (1900, 2100) lies between the two dates, so a shift by a multiple of 28 keeps every weekday, every 29 February and
# every n-th-weekday DST rule date (timeutil.TZ_RULES). Both ends must stay inside 1901-03-01 .. 2099-12-31. The date
# patterns below also see years 2100..2199, so a date in 2100 is refused instead of being left behind by a shift.
SHIFT_CYCLE_YEARS = 28
SHIFT_MIN_DATE = (1901, 3, 1)
SHIFT_MAX_DATE = (2099, 12, 31)
PERIOD_YEARS = (2000, 2100)  # the period years config.py accepts
_YEAR_MONTH = re.compile(r"(?<![0-9])((?:19|20|21)[0-9]{2})(?=-(?:0[1-9]|1[0-2])(?![0-9]))")  # 2026-05-.., SUB-2026-05-.., "2026-05"
_FULL_DATE = re.compile(r"(?<![0-9])((?:19|20|21)[0-9]{2})-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])(?![0-9])")
_SLASH_YEAR = re.compile(r"(?<=/)((?:19|20|21)[0-9]{2})(?=/)")  # "slashed" ID style: SI/2026/123456


_TOKEN_TAIL = re.compile(r"^(.*\S) ([A-Z]{2,4}-[0-9][0-9-]*)$")


def _split_description(text: str) -> tuple:
    """(wording, reference token or "") for a line description such as "Freight WB-12345"."""
    m = _TOKEN_TAIL.match(text)
    return (m.group(1), m.group(2)) if m else (text, "")


def _walk(node, visit) -> None:
    """Call visit(dict) on every dict nested in node."""
    if isinstance(node, dict):
        visit(node)
        for v in node.values():
            _walk(v, visit)
    elif isinstance(node, list):
        for v in node:
            _walk(v, visit)


def _name_map(ep: Episode, rename_seed: int) -> dict:
    """Seeded injective maps for the company name and for description wordings."""
    rng = Rng(f"rename:{rename_seed}:{ep.episode_id}")
    old_company = (ep.manifest.get("company") or {}).get("name")
    companies = {}
    if isinstance(old_company, str):
        new_company = old_company
        while new_company == old_company:
            new_company = catalog.company_name(rng, ep.manifest.get("timezone"))
        companies[old_company] = new_company
    wordings = set()

    def collect(d):
        if isinstance(d.get("description"), str):
            wordings.add(_split_description(d["description"])[0])

    for table in (ep.invoices, ep.payments, ep.ledger):
        _walk(table, collect)
    _walk(ep.provenance, collect)
    used = set(wordings)
    words = {}
    for w in sorted(wordings):
        new = w
        while new in used:
            new = f"{catalog.syllable_name(rng)} {catalog.syllable_name(rng)} item"
        used.add(new)
        words[w] = new
    return {"company": companies, "words": words}


def _new_description(text: str, names: dict) -> str:
    wording, token = _split_description(text)
    new = names["words"].get(wording, wording)
    return f"{new} {token}" if token else new


def _rename_deep(node, names: dict):
    """Copy of node with every "description" value and the company name renamed."""
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k == "description" and isinstance(v, str):
                out[k] = _new_description(v, names)
            elif k == "company" and isinstance(v, str):
                out[k] = names["company"].get(v, v)
            elif k == "name" and isinstance(v, str) and v in names["company"]:
                out[k] = names["company"][v]
            else:
                out[k] = _rename_deep(v, names)
        return out
    if isinstance(node, list):
        return [_rename_deep(v, names) for v in node]
    return node


def _shift_text(text: str, k: int) -> str:
    def bump(m):
        return f"{int(m.group(1)) + k:04d}"

    return _SLASH_YEAR.sub(bump, _YEAR_MONTH.sub(bump, text))


def _shift_deep(node, k: int):
    """Copy of node with the year moved by k in every date, timestamp, FX record key, dated reference token and
    year-bearing ID, in string values and dict keys alike. Numbers are never touched."""
    if isinstance(node, dict):
        return {(_shift_text(key, k) if isinstance(key, str) else key): _shift_deep(v, k) for key, v in node.items()}
    if isinstance(node, list):
        return [_shift_deep(v, k) for v in node]
    if isinstance(node, str):
        return _shift_text(node, k)
    return node


def _year_strings(node):
    if isinstance(node, dict):
        for key, v in node.items():
            yield from _year_strings(key)
            yield from _year_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _year_strings(v)
    elif isinstance(node, str):
        yield node


def _check_shift(ep: Episode, k: int) -> None:
    """Refuse a shift that is not a nonzero multiple of 28 or that leaves the range where the 28-year cycle holds."""
    if isinstance(k, bool) or not isinstance(k, int):
        raise ValueError("shift_years must be an integer")
    if k == 0 or k % SHIFT_CYCLE_YEARS:
        raise ValueError(f"shift_years must be a nonzero multiple of {SHIFT_CYCLE_YEARS}, got {k}")
    lo, hi = SHIFT_MIN_DATE, SHIFT_MAX_DATE
    for part in (ep.manifest, ep.policy, ep.ledger, ep.invoices, ep.payments, ep.fx, ep.truth, ep.provenance):
        for text in _year_strings(part):
            for m in _FULL_DATE.finditer(text):
                old = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                new = (old[0] + k, old[1], old[2])
                if not (lo <= old <= hi and lo <= new <= hi):
                    raise ValueError(f"shift_years {k} moves {m.group(0)} outside "
                                     f"{lo[0]}-{lo[1]:02d}-{lo[2]:02d} .. {hi[0]}-{hi[1]:02d}-{hi[2]:02d}")
            for m in _YEAR_MONTH.finditer(text):
                if not (lo[0] <= int(m.group(1)) <= hi[0] and lo[0] <= int(m.group(1)) + k <= hi[0]):
                    raise ValueError(f"shift_years {k} moves year {m.group(1)} outside {lo[0]} .. {hi[0]}")
    for text in (ep.manifest.get("period_start"), (ep.provenance.get("resolved_config") or {}).get("period")):
        if isinstance(text, str) and not PERIOD_YEARS[0] <= int(text[:4]) + k <= PERIOD_YEARS[1]:
            raise ValueError(f"shift_years {k} moves the period outside the accepted years {PERIOD_YEARS[0]}..{PERIOD_YEARS[1]}")


def shift_direction(ep: Episode, k: int = SHIFT_CYCLE_YEARS):
    """k when shifting the episode by k years is allowed, else -k when that is allowed, else None."""
    for cand in (k, -k):
        try:
            _check_shift(ep, cand)
        except ValueError:
            continue
        return cand
    return None


def _id_map(ep: Episode, remap_seed: int) -> dict:
    rng = Rng(f"remap:{remap_seed}:{ep.episode_id}")
    year = int(ep.manifest["period_start"][:4])
    style = STYLES[seed_from_text(f"style:{remap_seed}") % len(STYLES)]
    ids = IdFactory(rng, style, year)
    mapping = {}
    ents = sorted({r["entity_id"] for r in ep.invoices} | {r["entity_id"] for r in ep.payments if r["entity_id"]}
                  | {r["entity_id"] for r in ep.ledger if r["entity_id"]})
    kinds_by_entity = {}
    for d in ep.invoices:
        kinds_by_entity[d["entity_id"]] = "customer" if d["kind"] == "sales" else "supplier"
    for e in ents:
        mapping[e] = ids.new(kinds_by_entity.get(e, "customer"))
    for d in sorted(ep.invoices, key=lambda x: x["doc_id"]):
        mapping[d["invoice_id"]] = ids.new("sales_invoice" if d["kind"] == "sales" else "purchase_invoice")
        mapping[d["doc_id"]] = ids.new("doc")
    for d in sorted(ep.payments, key=lambda x: x["doc_id"]):
        mapping[d["payment_id"]] = ids.new(d["kind"])
        mapping[d["doc_id"]] = ids.new("doc")
    for r in sorted(ep.ledger, key=lambda x: x["row_id"]):
        mapping[r["row_id"]] = ids.new("row")
    for op in sorted(ep.provenance.get("ops", []), key=lambda o: (o["table"], o["id"])):
        if op["id"] not in mapping:
            mapping[op["id"]] = ids.new("row" if op["table"] == "ledger" else "doc")
    return mapping


def _map_record(rec: dict, m: dict) -> dict:
    out = dict(rec)
    for k in ("row_id", "doc_id", "invoice_id", "payment_id", "entity_id"):
        if out.get(k) is not None:
            out[k] = m.get(out[k], out[k])
    if out.get("invoice_refs") is not None:
        out["invoice_refs"] = [m.get(x, x) for x in out["invoice_refs"]]
    return out


def _ts_function(ep: Episode, mode: str):
    sched = OffsetSchedule(ep.policy["utc_offset_schedule"])

    def fmt(text: str, key: str) -> str:
        inst = parse_ts(text)
        if mode == "utc":
            return format_utc(inst)
        if mode == "local":
            return format_ts(inst, sched.offset_at(inst))
        h = seed_from_text(f"tsrepr:{key}")
        if h % 3 == 0:
            return format_utc(inst)
        if h % 3 == 1:
            return format_ts(inst, sched.offset_at(inst))
        return format_ts(inst, ALT_OFFSETS[(h // 3) % len(ALT_OFFSETS)])

    return fmt


def _retime(rec: dict, fmt, key_field: str) -> dict:
    out = dict(rec)
    key = str(out.get(key_field))
    for f in ("timestamp", "issued_at", "due_at"):
        if f in out and isinstance(out[f], str):
            out[f] = fmt(out[f], key)
    return out


def transform_episode(ep: Episode, permute_seed=None, remap_seed=None, ts_repr=None, rename_seed=None,
                      shift_years=None) -> Episode:
    if ts_repr is not None and ts_repr not in ("utc", "local", "mixed"):
        raise ValueError("ts_repr must be utc, local or mixed")
    if shift_years is not None:
        _check_shift(ep, shift_years)
    new = Episode(
        manifest=copy.deepcopy(ep.manifest),
        policy=copy.deepcopy(ep.policy),
        ledger=[dict(r) for r in ep.ledger],
        invoices=copy.deepcopy(ep.invoices),
        payments=copy.deepcopy(ep.payments),
        fx=[dict(r) for r in ep.fx],
        truth=copy.deepcopy(ep.truth),
        provenance=copy.deepcopy(ep.provenance),
    )
    if remap_seed is not None:
        m = _id_map(ep, int(remap_seed))
        new.ledger = [_map_record(r, m) for r in new.ledger]
        new.invoices = [_map_record(r, m) for r in new.invoices]
        new.payments = [_map_record(r, m) for r in new.payments]
        for t in new.truth.get("issues", []):
            t["affected_ids"] = [m.get(x, x) for x in t["affected_ids"]]
            t["evidence_sets"] = [[m.get(x, x) for x in es] for es in t["evidence_sets"]]
        if "id_aliases" in new.truth:
            new.truth["id_aliases"] = {m.get(k, k): m.get(v, v) for k, v in new.truth["id_aliases"].items()}
        for op in new.provenance.get("ops", []):
            op["id"] = m.get(op["id"], op["id"])
            if "record" in op:
                op["record"] = _map_record(op["record"], m)
            if op.get("field") in ("entity_id", "invoice_id", "payment_id", "row_id", "doc_id"):
                op["before"] = m.get(op["before"], op["before"]) if op["before"] is not None else None
                op["after"] = m.get(op["after"], op["after"]) if op["after"] is not None else None
            if op.get("field") == "invoice_refs":
                op["before"] = [m.get(x, x) for x in op["before"]] if op["before"] is not None else None
                op["after"] = [m.get(x, x) for x in op["after"]] if op["after"] is not None else None
        for inj in new.provenance.get("injections", []):
            inj["targets"] = {k: m.get(v, v) for k, v in inj.get("targets", {}).items()}
        for d in new.provenance.get("distractors", []):
            d["ids"] = [m.get(x, x) for x in d.get("ids", [])]
    if rename_seed is not None:
        names = _name_map(ep, int(rename_seed))
        new.manifest = _rename_deep(new.manifest, names)
        new.invoices = _rename_deep(new.invoices, names)
        new.payments = _rename_deep(new.payments, names)
        for key in ("ops", "injections", "distractors", "history"):
            if key in new.provenance:
                new.provenance[key] = _rename_deep(new.provenance[key], names)
    if ts_repr is not None:
        fmt = _ts_function(ep, ts_repr)
        new.ledger = [_retime(r, fmt, "row_id") for r in new.ledger]
        new.invoices = [_retime(r, fmt, "doc_id") for r in new.invoices]
        new.payments = [_retime(r, fmt, "doc_id") for r in new.payments]
        for op in new.provenance.get("ops", []):
            if "record" in op:
                op["record"] = _retime(op["record"], fmt, "row_id" if op["table"] == "ledger" else "doc_id")
            if op.get("field") in ("timestamp", "issued_at", "due_at"):
                op["before"] = fmt(op["before"], op["id"])
                op["after"] = fmt(op["after"], op["id"])
    if shift_years is not None:  # last of the value rewrites: ts_repr and remap read the source calendar
        _check_shift(new, shift_years)  # the re-rendered values (ts_repr utc) can sit on another date than the source text
        new.manifest = _shift_deep(new.manifest, shift_years)
        new.policy = _shift_deep(new.policy, shift_years)
        new.ledger = _shift_deep(new.ledger, shift_years)
        new.invoices = _shift_deep(new.invoices, shift_years)
        new.payments = _shift_deep(new.payments, shift_years)
        new.fx = _shift_deep(new.fx, shift_years)
        new.truth = _shift_deep(new.truth, shift_years)
        new.provenance = _shift_deep(new.provenance, shift_years)
    if permute_seed is not None:
        rng = Rng(f"permute:{permute_seed}:{ep.episode_id}")
        for table in ("ledger", "invoices", "payments", "fx"):
            rows = new.table(table)
            rng.fork(table).shuffle(rows)
    tag = f"{ep.episode_id}|{permute_seed}|{remap_seed}|{ts_repr}" + ("" if rename_seed is None else f"|{rename_seed}")
    tag += "" if shift_years is None else f"|shift{shift_years}"
    new_id = "ep_" + hashlib.sha256(tag.encode("utf-8")).hexdigest()[:16]
    new.manifest["episode_id"] = new_id
    if new.truth:
        new.truth["episode_id"] = new_id
    new.provenance["transformed_from"] = {"episode_id": ep.episode_id, "permute_seed": permute_seed,
                                          "remap_seed": remap_seed, "ts_repr": ts_repr,
                                          "rename_seed": rename_seed, "shift_years": shift_years}
    # The clean-records digest comes from the SOURCE episode's reverted clean tables pushed through the same ID map and
    # timestamp rewrite, never from the transformed tables it will later be checked against.
    clean_src = reconstruct_clean(ep)
    src_digest = records_digest(list(clean_src["ledger"].values()), list(clean_src["invoices"].values()),
                                list(clean_src["payments"].values()))
    # Fresh digests only vouch for a source that was itself intact; a tampered source gets none (verify then FAILs).
    # No raise: env.reset calls transform on every episode.
    src_ok = (ep.provenance.get("clean_records_digest") == src_digest
              and ep.provenance.get("final_digest") == ep.public_digest())
    if not src_ok:
        new.provenance.pop("clean_records_digest", None)
        new.provenance.pop("final_digest", None)
        return new
    clean_new = {}
    for table, key_field in (("ledger", "row_id"), ("invoices", "doc_id"), ("payments", "doc_id")):
        recs = list(clean_src[table].values())
        if remap_seed is not None:
            recs = [_map_record(r, m) for r in recs]
        if rename_seed is not None:
            recs = _rename_deep(recs, names)
        if ts_repr is not None:
            recs = [_retime(r, fmt, key_field) for r in recs]
        if shift_years is not None:
            recs = _shift_deep(recs, shift_years)
        clean_new[table] = recs
    new.provenance["clean_records_digest"] = records_digest(clean_new["ledger"], clean_new["invoices"], clean_new["payments"])
    new.provenance["final_digest"] = new.public_digest()
    if not new.provenance.get("ops"):
        new.provenance["clean_digest"] = new.provenance["final_digest"]  # no ops: the clean twin is the published books
    return new
