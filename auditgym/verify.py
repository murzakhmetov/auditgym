"""Episode verification (data and answer key).

Named checks, each independent of the generator's internal state:

  records_schema         public records have the published fields and types
  ids_unique             IDs are unique across tables and never contain ':'
  clean_equalities       clean books (reconstructed from provenance): every journal and the trial balance
                         balance, and the independent auditor finds no discrepancy and no anomaly
  provenance_roundtrip   with a clean twin (generation): reverting the ops gives the clean books and applying
                         them gives the published books. Directory mode (verify DIR, no twin): revert then
                         re-apply reproduces the published tables, the digest of the reverted tables equals
                         provenance.clean_records_digest (missing = FAIL), public_digest() equals final_digest,
                         and every declared issue has an op touching its affected records
  declared_discrepancies the independent auditor reproduces exactly the answer key (types, affected IDs, amounts,
                         evidence sets) and reports no anomaly
  evidence_sufficient    each acceptable evidence set alone (plus policy and manifest) re-derives type, affected
                         IDs and amount, using evidence_check.py (independent of auditor.py and money.py)
  budget_feasible        reading every page of every table plus submit fits in 100 steps
  no_surface_tells       every injected or modified ledger row has an untouched twin with the same account and
                         null pattern
  no_leaks               public files contain no answer-key markers
"""

from __future__ import annotations

import math
import re
from datetime import date

from .auditor import audit
from .episode import Episode
from .evidence_check import derive_from_evidence  # noqa: F401  (re-exported: check.py and tests import it from here)
from .io import canonical_json, sha256_text
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


# derive_from_evidence lives in evidence_check.py (independent implementation) and is re-exported here.


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


def check_surface(ep: Episode, strict: bool = False) -> list[str]:
    """strict (directory mode): an episode with declared issues must carry ledger ops; none at all is a failure."""
    touched = {op["id"] for op in ep.provenance.get("ops", []) if op["table"] == "ledger" and op["op"] in ("add", "set")}
    if not touched:
        if strict and ep.truth.get("issues"):
            return ["episode declares issues but provenance has no ledger ops, so the surface cannot be checked"]
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


def records_digest(ledger: list, invoices: list, payments: list) -> str:
    """Order-independent sha256 of a set of records (ledger rows, invoices, payments), keyed by their row/doc ID."""
    parts = []
    for name, key, rows in (("ledger", "row_id", ledger), ("invoices", "doc_id", invoices), ("payments", "doc_id", payments)):
        parts.append([name, [canonical_json(r) for r in sorted(rows, key=lambda r: r[key])]])
    return sha256_text(canonical_json(parts))


def _tables_by_id(ep: Episode) -> dict:
    keys = {"ledger": "row_id", "invoices": "doc_id", "payments": "doc_id"}
    return {t: {r[k]: r for r in ep.table(t)} for t, k in keys.items()}


def _tables_digest(tables: dict) -> str:
    return records_digest(list(tables["ledger"].values()), list(tables["invoices"].values()), list(tables["payments"].values()))


def _op_touches(ops: list, published: dict, reverted: dict) -> set:
    """Public identifiers that the ops reach: row/doc IDs plus the invoice and payment IDs those records carry."""
    ids = set()
    for op in ops:
        ids.add(op["id"])
        rec = op.get("record") or published[op["table"]].get(op["id"]) or reverted[op["table"]].get(op["id"]) or {}
        ids.update(rec[k] for k in ("invoice_id", "payment_id") if rec.get(k))
        if op.get("field") in ("invoice_id", "payment_id"):
            ids.update(v for v in (op.get("before"), op.get("after")) if v)
    return ids


def check_roundtrip(ep: Episode, clean: Episode | None) -> list[str]:
    errs = []
    keys = {"ledger": "row_id", "invoices": "doc_id", "payments": "doc_id"}
    ops = ep.provenance.get("ops", [])
    rec = reconstruct_clean(ep)
    if clean is not None:
        for t, k in keys.items():
            if rec[t] != {r[k]: r for r in clean.table(t)}:
                errs.append(f"reverting provenance does not reproduce clean {t}")
        fwd = apply_ops(_tables(clean), ops)
        for t, k in keys.items():
            if fwd[t] != {r[k]: r for r in ep.table(t)}:
                errs.append(f"applying provenance does not reproduce published {t}")
        return errs
    # Directory mode: nothing but the episode itself is available, so check it against the digests stored at generation.
    fwd = apply_ops({t: list(rec[t].values()) for t in keys}, ops)
    for t, k in keys.items():
        if fwd[t] != {r[k]: r for r in ep.table(t)}:
            errs.append(f"reverting then re-applying provenance does not reproduce published {t}")
    want = ep.provenance.get("clean_records_digest")
    if not isinstance(want, str) or not want:
        errs.append("provenance has no clean_records_digest")
    elif _tables_digest(rec) != want:
        errs.append("digest of the reverted tables differs from provenance.clean_records_digest")
    if not ep.provenance.get("final_digest"):
        errs.append("provenance has no final_digest")
    elif ep.public_digest() != ep.provenance["final_digest"]:
        errs.append("public_digest() differs from provenance.final_digest")
    if not ops and ep.provenance.get("clean_digest") != ep.public_digest():
        errs.append("no ops, so provenance.clean_digest must equal public_digest()")
    touched = _op_touches(ops, _tables_by_id(ep), rec)
    for t in ep.truth.get("issues", []):
        if not (set(t["affected_ids"]) & touched):
            errs.append(f"{t['issue_id']}: no provenance op touches its affected records {t['affected_ids']}")
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
    checks["no_surface_tells"] = check_surface(ep, strict=clean is None)
    checks["no_leaks"] = check_leaks(ep)
    failures = [f"{name}: {msg}" for name, msgs in checks.items() for msg in msgs]
    return {
        "ok": not failures,
        "checks": {name: ("pass" if not msgs else msgs) for name, msgs in checks.items()},
        "failures": failures,
        "n_issues": len(ep.truth.get("issues", [])),
    }


_ID_RE = re.compile(r"^[^:\s]{1,64}$")
