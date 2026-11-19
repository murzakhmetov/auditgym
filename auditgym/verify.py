"""Episode verification (data and answer key).

Named checks, each independent of the generator's internal state:

  records_schema         public records have the published fields and types
  ids_unique             IDs are unique across tables and never contain ':'
  clean_equalities       clean books (reconstructed from provenance): every journal and the trial balance
                         balance, and the independent auditor finds no discrepancy and no anomaly
  provenance_roundtrip   applying provenance ops to the clean books gives the published books, and reverting
                         them gives the clean books back
  declared_discrepancies the independent auditor reproduces exactly the answer key (types, affected IDs, amounts,
                         evidence sets) and reports no anomaly
  evidence_sufficient    each acceptable evidence set alone (plus policy and manifest) re-derives type, affected
                         IDs and amount, using a third implementation of the rules
  budget_feasible        reading every page of every table plus submit fits in 100 steps
  no_surface_tells       every injected or modified ledger row has an untouched twin with the same account and
                         null pattern
  no_leaks               public files contain no answer-key markers
"""

from __future__ import annotations

import math
import re
from datetime import date, timedelta

from .auditor import OffsetSchedule, audit, doc_signature
from .episode import Episode
from .money import convert_minor
from .render import apply_ops
from .timeutil import parse_ts

INVOICE_FIELDS = ("doc_id", "invoice_id", "kind", "entity_id", "issued_at", "due_at", "currency", "total_minor", "line_items")
PAYMENT_FIELDS = ("doc_id", "payment_id", "kind", "entity_id", "timestamp", "currency", "amount_minor", "invoice_refs", "bank_ref")
LEAK_MARKERS = ("iss_", "duplicate_of", "provenance", "truth.json", "injected", "expected_amount")


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def check_records_schema(ep: Episode) -> list[str]:
    errs = []
    m = ep.manifest
    for k in ("schema_version", "episode_id", "base_currency", "period_start", "period_end", "timezone", "record_counts",
              "document_counts", "rounding"):
        if k not in m:
            errs.append(f"manifest missing {k}")
    counts = m.get("record_counts", {})
    for t in ("ledger", "invoices", "payments", "fx"):
        if counts.get(t) != len(ep.table(t)):
            errs.append(f"manifest record_counts.{t} mismatch")
    for r in ep.ledger:
        if not (_is_int(r["debit_minor"]) and _is_int(r["credit_minor"])):
            errs.append(f"ledger {r['row_id']} amounts not integers")
        try:
            parse_ts(r["timestamp"])
        except ValueError:
            errs.append(f"ledger {r['row_id']} bad timestamp")
    for d in ep.invoices:
        if tuple(d) != INVOICE_FIELDS:
            errs.append(f"invoice {d.get('doc_id')} fields {list(d)}")
        elif not _is_int(d["total_minor"]) or not isinstance(d["line_items"], list):
            errs.append(f"invoice {d['doc_id']} types")
    for d in ep.payments:
        if tuple(d) != PAYMENT_FIELDS:
            errs.append(f"payment {d.get('doc_id')} fields {list(d)}")
        elif d["invoice_refs"] is not None and not isinstance(d["invoice_refs"], list):
            errs.append(f"payment {d['doc_id']} invoice_refs must be a list or null")
    for r in ep.fx:
        try:
            date.fromisoformat(r["date"])
            float(r["rate"])
        except ValueError:
            errs.append(f"fx row {r} malformed")
    return errs[:20]


def check_ids(ep: Episode) -> list[str]:
    seen, errs = {}, []

    def add(i, where):
        if i is None:
            return
        if ":" in i:
            errs.append(f"id {i} contains ':'")
        if i in seen and seen[i] != where:
            errs.append(f"id {i} used in {seen[i]} and {where}")
        seen.setdefault(i, where)

    for r in ep.ledger:
        if r["row_id"] in seen:
            errs.append(f"duplicate row_id {r['row_id']}")
        add(r["row_id"], "ledger")
    for d in ep.invoices:
        add(d["doc_id"], "doc")
        add(d["invoice_id"], "invoice")
    for d in ep.payments:
        add(d["doc_id"], "doc")
        add(d["payment_id"], "payment")
    return errs[:20]


def _issue_key(t: str, ids) -> tuple:
    return t, tuple(sorted(ids))


def compare_with_truth(found: dict, truth: dict) -> list[str]:
    errs = list(f"anomaly: {a}" for a in found["anomalies"][:10])
    want = {_issue_key(t["type"], t["affected_ids"]): t for t in truth.get("issues", [])}
    got = {_issue_key(f["type"], f["affected_ids"]): f for f in found["findings"]}
    for k in sorted(set(want) - set(got)):
        errs.append(f"auditor missed {k}")
    for k in sorted(set(got) - set(want)):
        errs.append(f"auditor found undeclared {k}")
    for k in sorted(set(want) & set(got)):
        t, f = want[k], got[k]
        if f["amount"] != t["expected_amount_minor"]:
            errs.append(f"amount mismatch {k}: auditor {f['amount']} vs key {t['expected_amount_minor']}")
        if f["currency"] != t["currency"]:
            errs.append(f"currency mismatch {k}")
        if {frozenset(s) for s in f["evidence_sets"]} != {frozenset(s) for s in t["evidence_sets"]}:
            errs.append(f"evidence sets differ for {k}")
    return errs


# ------------------------------------------------------------------ evidence-only checker
def derive_from_evidence(issue_type: str, evidence: list, ep: Episode) -> tuple | None:
    """Third implementation: derive (type, affected id set, amount) from the cited records only."""
    pol = ep.policy
    base = pol["base_currency"]
    exps = pol["currency_exponents"]
    rounding = pol["rounding"]["mode"]
    p0, p1 = parse_ts(pol["reporting_period"]["start"]), parse_ts(pol["reporting_period"]["end"])
    sched = OffsetSchedule(pol["utc_offset_schedule"])
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
        if "invoice_id" not in a or "invoice_id" not in b or doc_signature(a) != doc_signature(b):
            return None
        ra = [r for r in cited_rows if r["invoice_id"] == a["invoice_id"]]
        rb = [r for r in cited_rows if r["invoice_id"] == b["invoice_id"]]
        if len(ra) != 1 or len(rb) != 1 or ra[0]["account"] != rb[0]["account"]:
            return None
        amt = ra[0]["debit_minor"] or ra[0]["credit_minor"]
        if amt != (rb[0]["debit_minor"] or rb[0]["credit_minor"]):
            return None
        return issue_type, frozenset({a["invoice_id"], b["invoice_id"]}), amt
    if issue_type == "unallocated_payment":
        pays = [d for d in cited_docs if "payment_id" in d]
        invs = [d for d in cited_docs if "invoice_id" in d]
        if len(pays) != 1 or len(invs) != 1 or len(cited_rows) != 1 or cited_fx:
            return None
        p, i, r = pays[0], invs[0], cited_rows[0]
        ok = (p["kind"] == "receipt" and p["invoice_refs"] and i["invoice_id"] in p["invoice_refs"]
              and i["kind"] == "sales" and i["currency"] == p["currency"] and i["total_minor"] >= p["amount_minor"]
              and r["account"] == "2900" and r["credit_minor"] > 0 and r["payment_id"] == p["payment_id"])
        return (issue_type, frozenset({p["payment_id"], i["invoice_id"]}), r["credit_minor"]) if ok else None
    if issue_type == "wrong_fx_rate":
        if len(cited_docs) != 1 or len(cited_rows) != 1 or len(cited_fx) != 1:
            return None
        doc, row, fx = cited_docs[0], cited_rows[0], cited_fx[0]
        if doc["currency"] == base or not refers(row, doc) or fx["source_currency"] != doc["currency"] or fx["target_currency"] != base:
            return None
        inst = parse_ts(doc["issued_at"] if "invoice_id" in doc else doc["timestamp"])
        local_d = sched.local_date(inst)
        fx_d = date.fromisoformat(fx["date"])
        if fx_d > local_d or any(published(fx_d + timedelta(days=k)) for k in range(1, (local_d - fx_d).days + 1)):
            return None
        amount = doc["total_minor"] if "invoice_id" in doc else doc["amount_minor"]
        expected = convert_minor(amount, fx["rate"], exps[doc["currency"]], exps[base], rounding)
        posted = row["debit_minor"] or row["credit_minor"]
        if "invoice_id" not in doc and row["account"] != "1000":
            return None
        delta = abs(posted - expected)
        return (issue_type, frozenset({key_of(doc)}), delta) if delta > 2 else None
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


def check_evidence(ep: Episode) -> list[str]:
    errs = []
    for t in ep.truth.get("issues", []):
        for es in t["evidence_sets"]:
            got = derive_from_evidence(t["type"], es, ep)
            want = (t["type"], frozenset(t["affected_ids"]), t["expected_amount_minor"])
            if got != want:
                errs.append(f"{t['issue_id']}: evidence set {es} derives {got}")
    return errs


# ------------------------------------------------------------------ other checks
def check_budget(ep: Episode, max_steps: int = 100) -> list[str]:
    pages = sum(math.ceil(len(ep.table(t)) / 50) for t in ("ledger", "invoices", "payments", "fx"))
    return [] if pages + 1 <= max_steps else [f"full read needs {pages} pages + submit > {max_steps}"]


def check_surface(ep: Episode) -> list[str]:
    touched = {op["id"] for op in ep.provenance.get("ops", []) if op["table"] == "ledger" and op["op"] in ("add", "set")}
    if not touched:
        return []
    patterns = {}
    for r in ep.ledger:
        if r["row_id"] in touched:
            continue
        pat = (r["account"], r["entity_id"] is None, r["invoice_id"] is None, r["payment_id"] is None,
               r["debit_minor"] > 0)
        patterns[pat] = patterns.get(pat, 0) + 1
    errs = []
    for r in ep.ledger:
        if r["row_id"] in touched:
            pat = (r["account"], r["entity_id"] is None, r["invoice_id"] is None, r["payment_id"] is None, r["debit_minor"] > 0)
            if not patterns.get(pat):
                errs.append(f"row {r['row_id']} has a pattern no untouched row has: {pat}")
    return errs


def check_leaks(ep: Episode) -> list[str]:
    texts = ep.public_texts()
    errs = []
    for name, text in texts.items():
        low = text.lower()
        for marker in LEAK_MARKERS:
            if marker in low:
                errs.append(f"{name} contains marker {marker!r}")
    seed = str(ep.provenance.get("seed", ""))
    if len(seed) >= 8 and any(seed in t for t in texts.values()):
        errs.append("seed appears in public files")
    return errs


def _tables(ep: Episode) -> dict:
    return {"ledger": ep.ledger, "invoices": ep.invoices, "payments": ep.payments}


def reconstruct_clean(ep: Episode) -> dict:
    return apply_ops(_tables(ep), ep.provenance.get("ops", []), reverse=True)


def check_roundtrip(ep: Episode, clean: Episode | None) -> list[str]:
    errs = []
    keys = {"ledger": "row_id", "invoices": "doc_id", "payments": "doc_id"}
    rec = reconstruct_clean(ep)
    if clean is not None:
        for t, k in keys.items():
            if rec[t] != {r[k]: r for r in clean.table(t)}:
                errs.append(f"reverting provenance does not reproduce clean {t}")
        fwd = apply_ops(_tables(clean), ep.provenance.get("ops", []))
        for t, k in keys.items():
            if fwd[t] != {r[k]: r for r in ep.table(t)}:
                errs.append(f"applying provenance does not reproduce published {t}")
    return errs


def clean_episode_from(ep: Episode) -> Episode:
    rec = reconstruct_clean(ep)

    def ordered(t, key):
        published = [r[key] for r in ep.table(t)]
        extra = sorted(set(rec[t]) - set(published))
        return [rec[t][i] for i in published if i in rec[t]] + [rec[t][i] for i in extra]

    return Episode(manifest=ep.manifest, policy=ep.policy, ledger=ordered("ledger", "row_id"),
                   invoices=ordered("invoices", "doc_id"), payments=ordered("payments", "doc_id"), fx=ep.fx,
                   truth={"issues": []}, provenance={})


def verify_generated(ep: Episode, clean: Episode | None = None) -> dict:
    checks = {}
    checks["records_schema"] = check_records_schema(ep)
    checks["ids_unique"] = check_ids(ep)
    clean_ep = clean if clean is not None else clean_episode_from(ep)
    clean_found = audit(clean_ep.manifest, clean_ep.policy, clean_ep.ledger, clean_ep.invoices, clean_ep.payments, clean_ep.fx)
    checks["clean_equalities"] = [f"clean books: {a}" for a in clean_found["anomalies"][:10]] + [
        f"clean books show {f['type']} on {f['affected_ids']}" for f in clean_found["findings"][:10]]
    checks["provenance_roundtrip"] = check_roundtrip(ep, clean)
    found = audit(ep.manifest, ep.policy, ep.ledger, ep.invoices, ep.payments, ep.fx)
    checks["declared_discrepancies"] = compare_with_truth(found, ep.truth)
    checks["evidence_sufficient"] = check_evidence(ep)
    checks["budget_feasible"] = check_budget(ep)
    checks["no_surface_tells"] = check_surface(ep)
    checks["no_leaks"] = check_leaks(ep)
    failures = [f"{name}: {msg}" for name, msgs in checks.items() for msg in msgs]
    return {
        "ok": not failures,
        "checks": {name: ("pass" if not msgs else msgs) for name, msgs in checks.items()},
        "failures": failures,
        "n_issues": len(ep.truth.get("issues", [])),
    }


_ID_RE = re.compile(r"^[^:\s]{1,64}$")
