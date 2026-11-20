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
                         and every declared issue has an op touching its affected records. In both modes the
                         provenance structure is cross-checked: every injection type and variant is a known one,
                         every injection has non-empty targets naming existing public invoices (payments for the payment
                         role), every distractor has an ids list of existing invoice or payment IDs and a known kind,
                         and truth issues and injections match one to one by (issue_id, type), and the target values of
                         each injection equal the affected_ids of the truth issue with the same issue_id. A
                         provenance.json that is not an object, ops that are not a list, or a malformed op is a FAIL
                         line of this check (the replay and the clean-books check are then skipped), not a traceback.
                         The semantic record provenance.injections[].change is cross-checked against the public records and
                         the ops, and an unknown, missing or malformed key of a known type is a FAIL line. duplicate_invoice:
                         change is empty. wrong_period: posting_ts is the timestamp that the ledger ops (set after, or added
                         record) record for the target's booking rows. wrong_fx_rate: correct_rate and correct_rate_date are the
                         fx.csv policy rate (latest rate on or before the document's local date); wrong_rate and wrong_rate_date
                         are the fx.csv rate of the date the variant names (utc_date: the UTC date, posting_date: the local date
                         of posting_ts, stale_rate: the day before the period), or for transposed two adjacent digits of
                         correct_rate swapped (at least 0.2 % apart, no date); posting_date adds posting_ts as above; the
                         touched booking row (invoice 1100 or 2000, payment 1000) equals the amount at wrong_rate.
                         unallocated_payment: alloc fits the variant (missing 0, partial more), 2900 holds the converted
                         amount - alloc, and the ledger relieves the invoice by the proportional carrying amount of alloc
  declared_discrepancies the independent auditor reproduces exactly the answer key (types, affected IDs, amounts,
                         evidence sets) and reports no anomaly; truth id_aliases equal {doc_id: invoice_id or
                         payment_id} of the public records (nothing missing or extra) and every issue variant is one
                         of config.VARIANTS[type]
  evidence_sufficient    each acceptable evidence set alone (plus policy and manifest) re-derives type, affected
                         IDs and amount, using evidence_check.py (independent of auditor.py and money.py); and for every
                         unallocated_payment issue no other receipt settled the invoice, checked on all public records: no
                         payment but the issue's lists the invoice in invoice_refs, and no ledger row but the issue's own
                         payment relieves it (credit to 1100 for a sales invoice, debit to 2000 for a purchase invoice)
  budget_feasible        reading every page of every table plus submit fits in 100 steps
  no_surface_tells       every injected or modified ledger row has an untouched twin with the same account and
                         null pattern
  no_leaks               public files contain no answer-key markers

verify DIR does not catch alone: a changed provenance.seed, a removed or shortened distractor list, a distractor
kind swapped for another known one, a wrong_period injection variant, or any truth.json variant (injection variants of
wrong_fx_rate and unallocated_payment are checked through change; verify DIR does not compare truth.json's variant or
manifest.episode_id, which for hidden episodes needs the generation secret, and nothing records the distractor list).
change.alloc is checked only to the resolution of the base-currency 2900 and relief amounts: when the document currency
is finer than the base, several alloc values fit the same ledger and the public records cannot pin it further. An
injection retargeted to another record is caught by the targets-equal-affected_ids rule. "check" catches the seed, distractor and
variant cases above by regenerating every committed episode from its seed and config and comparing the bytes.
"""

from __future__ import annotations

import math
import re
from datetime import date, timedelta
from fractions import Fraction

from .auditor import audit
from .config import DISTRACTORS, VARIANTS
from .episode import Episode
from .evidence_check import _local_date, _round_fraction, convert_fraction
from .evidence_check import derive_from_evidence  # noqa: F401  (re-exported: check.py and tests import it from here)
from .io import canonical_json, sha256_text
from .render import apply_ops
from .timeutil import parse_ts

OP_KEYS = {"ledger": "row_id", "invoices": "doc_id", "payments": "doc_id"}
REPLAY_ERRORS = (KeyError, TypeError, AttributeError, ValueError, IndexError, ArithmeticError)  # ArithmeticError: OverflowError on a 1e400 amount
INVOICE_FIELDS = ("doc_id", "invoice_id", "kind", "entity_id", "issued_at", "due_at", "currency", "total_minor", "line_items")
PAYMENT_FIELDS = ("doc_id", "payment_id", "kind", "entity_id", "timestamp", "currency", "amount_minor", "invoice_refs", "bank_ref")
# the twin episode (inject.py) adds one distractor kind that the config cannot ask for
DISTRACTOR_KINDS = (*DISTRACTORS, "twin_legit_repeat")
LEAK_MARKERS = ("iss_", "duplicate_of", "provenance", "truth.json", "injected", "expected_amount")


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


RATE_SYNTAX = re.compile(r"[0-9]{1,12}(\.[0-9]{1,12})?")  # the fx.csv rate format: no exponent, sign or space reaches Fraction()


def _is_rate(v) -> bool:
    """A positive decimal string in the fx.csv format (checked before any Fraction() call, so 1e99999999 cannot hang)."""
    return isinstance(v, str) and RATE_SYNTAX.fullmatch(v) is not None and Fraction(v) > 0


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


def check_key_consistency(ep: Episode) -> list[str]:
    """Answer-key rules the auditor does not exercise: id_aliases is exactly {doc_id: invoice_id or payment_id}
    over the public invoices and payments, and every issue variant is one the config knows for its type."""
    errs = []
    want = {d["doc_id"]: d["invoice_id"] for d in ep.invoices}
    want.update({d["doc_id"]: d["payment_id"] for d in ep.payments})
    got = ep.truth.get("id_aliases", {})
    for k in sorted(set(want) - set(got))[:5]:
        errs.append(f"id_aliases missing {k}")
    for k in sorted(set(got) - set(want))[:5]:
        errs.append(f"id_aliases has extra {k}")
    for k in sorted(set(want) & set(got)):
        if want[k] != got[k] and len(errs) < 10:
            errs.append(f"id_aliases maps {k} to {got[k]}, public record says {want[k]}")
    for t in ep.truth.get("issues", []):
        if t.get("variant") not in VARIANTS.get(t.get("type"), ()):
            errs.append(f"issue {t.get('issue_id')}: variant {t.get('variant')!r} is not a known variant of {t.get('type')}")
    return errs


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


def _sole_receipt_errors(ep: Episode, issue: dict) -> list[str]:
    """unallocated_payment: the evidence cannot show that no other receipt settled the invoice, so check it on all
    public records. No payment other than the issue's one lists the invoice in invoice_refs, and no ledger row other
    than the issue's own payment relieves the invoice: a credit to 1100 (receivable of a sales invoice) or a debit to
    2000 (payable of a purchase invoice) that carries the invoice ID. The invoice's own booking is a debit to 1100
    (sales) or a credit to 2000 (purchase), so it never counts."""
    ids = set(issue.get("affected_ids", []))
    pays = [d for d in ep.payments if d["payment_id"] in ids]
    invs = [d for d in ep.invoices if d["invoice_id"] in ids]
    if len(pays) != 1 or len(invs) != 1:
        return []  # the evidence check reports the malformed key
    pid, inv = pays[0]["payment_id"], invs[0]
    errs = [f"{issue['issue_id']}: payment {d['payment_id']} also lists invoice {inv['invoice_id']} in invoice_refs"
            for d in ep.payments if d["payment_id"] != pid and inv["invoice_id"] in (d["invoice_refs"] or [])]
    account, side = ("1100", "credit_minor") if inv["kind"] == "sales" else ("2000", "debit_minor")
    errs += [f"{issue['issue_id']}: ledger row {r['row_id']} relieves invoice {inv['invoice_id']} ({account}) besides the issue's payment"
             for r in ep.ledger if r["invoice_id"] == inv["invoice_id"] and r["account"] == account and r[side] > 0
             and r["payment_id"] != pid]
    return errs[:5]


def check_evidence(ep: Episode) -> list[str]:
    errs = []
    for t in ep.truth.get("issues", []):
        if t["type"] == "unallocated_payment":
            errs += _sole_receipt_errors(ep, t)
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
    seed = str(ep.provenance.get("seed", "")) if isinstance(ep.provenance, dict) else ""
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


def _document_ids(ep: Episode) -> tuple[set, set]:
    """Invoice IDs and payment IDs of the public documents (entity, row and doc IDs are not document IDs)."""
    return {d["invoice_id"] for d in ep.invoices}, {d["payment_id"] for d in ep.payments}


def _id_list(value) -> list | None:
    """A string as a one-item list, a list of strings as is, anything else None."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return value
    return None


def _injection_errors(inj, invoice_ids: set, payment_ids: set) -> list[str]:
    """Problems with one injection: shape, known type and variant, non-empty targets of the right record kind."""
    if not isinstance(inj, dict):
        return ["injection must be an object"]
    name, kind, variant, targets = inj.get("issue_id"), inj.get("type"), inj.get("variant"), inj.get("targets")
    if not isinstance(kind, str) or not isinstance(variant, str):
        return [f"injection {name}: type and variant must be strings"]
    errs = []
    if kind not in VARIANTS:
        errs.append(f"injection {name}: unknown type {kind!r}")
    elif variant not in VARIANTS[kind]:
        errs.append(f"injection {name}: unknown variant {variant!r} for {kind}")
    if not isinstance(targets, dict) or not targets:
        return errs + [f"injection {name}: targets must be a non-empty object"]
    for role, ref in targets.items():
        refs = _id_list(ref)
        if refs is None or not refs:
            errs.append(f"injection {name}: target {role} must be a record id or a list of them")
            continue
        known = payment_ids if role == "payment" else invoice_ids
        errs += [f"injection {name}: target {role} {r!r} is not a public {'payment' if role == 'payment' else 'invoice'}"
                 for r in refs if r not in known]
    return errs


def _distractor_errors(dis, document_ids: set) -> list[str]:
    """Problems with one distractor: shape, known kind, an ids list of existing invoice or payment IDs."""
    if not isinstance(dis, dict):
        return ["distractor must be an object"]
    kind, refs = dis.get("kind"), _id_list(dis.get("ids"))
    if not isinstance(kind, str) or kind not in DISTRACTOR_KINDS:
        return [f"distractor kind {kind!r} is not a known kind"]
    if refs is None or not isinstance(dis.get("ids"), list):
        return [f"distractor {kind}: ids must be a list of record ids"]
    return [f"distractor {kind}: id {r!r} is not a public record" for r in refs if r not in document_ids]


def _op_shape_error(op, index: int) -> str | None:
    """Why one provenance op cannot be replayed, or None when it can."""
    if not isinstance(op, dict):
        return f"op {index} must be an object"
    table, kind, rid = op.get("table"), op.get("op"), op.get("id")
    if not isinstance(table, str) or table not in OP_KEYS or kind not in ("add", "remove", "set") or not isinstance(rid, str):
        return f"op {index} needs a known table, an op of add, remove or set, and a string id"
    if kind == "add" and not (isinstance(op.get("record"), dict) and op["record"].get(OP_KEYS[table]) == rid):
        return f"op {index}: add needs a record whose {OP_KEYS[table]} is the op id"
    if kind == "set" and not (isinstance(op.get("field"), str) and "before" in op and "after" in op):
        return f"op {index}: set needs a field, before and after"
    return None


def provenance_shape_errors(ep: Episode) -> list[str]:
    """Reasons why provenance.json cannot be replayed at all: not an object, ops not a list, or a malformed op."""
    prov = ep.provenance
    if not isinstance(prov, dict):
        return ["provenance.json must be an object"]
    ops = prov.get("ops", [])
    if not isinstance(ops, list):
        return ["provenance.ops must be a list"]
    return [e for e in (_op_shape_error(op, i) for i, op in enumerate(ops)) if e][:10]


def _retarget_errors(injections: list, issues) -> list[str]:
    """An injection's target values must be exactly the affected IDs of the truth issue with its issue_id."""
    affected = {t["issue_id"]: t.get("affected_ids") for t in issues if isinstance(t, dict) and isinstance(t.get("issue_id"), str)}
    errs = []
    for inj in injections:
        if not isinstance(inj, dict) or not isinstance(inj.get("targets"), dict):
            continue
        if not isinstance(inj.get("issue_id"), str) or inj["issue_id"] not in affected:
            continue
        values = [r for ref in inj["targets"].values() for r in (_id_list(ref) or [])]
        want = affected[inj["issue_id"]]
        if isinstance(want, list) and set(values) != set(want):
            errs.append(f"injection {inj['issue_id']}: targets {sorted(set(values))} differ from the affected_ids "
                        f"{sorted(set(want))} of the truth issue")
    return errs


# ------------------------------------------------------------------ semantic record: injections[].change
CHANGE_KEYS = {
    "duplicate_invoice": frozenset(),
    "unallocated_payment": frozenset({"alloc"}),
    "wrong_fx_rate": frozenset({"correct_rate", "correct_rate_date", "wrong_rate", "wrong_rate_date"}),
    "wrong_period": frozenset({"posting_ts"}),
}
POLICY_RATE_LOOKBACK_DAYS = 15  # the generator's rule: the latest published rate within 15 days before the date
RATE_TRANSPOSE_MIN = Fraction(2, 1000)  # a transposed rate differs from the right one by at least 0.2 %


class _ChangeIndex:
    """Public records and ops indexed once for the change cross-checks."""

    def __init__(self, ep: Episode):
        pol = ep.policy
        self.base = pol["base_currency"]
        self.exps = pol["currency_exponents"]
        self.mode = pol["rounding"]["mode"]
        self.schedule = pol["utc_offset_schedule"]
        self.p0 = parse_ts(pol["reporting_period"]["start"])
        self.inv = {d["invoice_id"]: d for d in ep.invoices}
        self.pay = {d["payment_id"]: d for d in ep.payments}
        self.fx = {}
        for r in ep.fx:
            self.fx.setdefault((r["source_currency"], r["target_currency"]), {})[r["date"]] = r["rate"]
        self.rows_by_inv, self.rows_by_pay, self.ops = {}, {}, {}
        for r in ep.ledger:
            if r["invoice_id"]:
                self.rows_by_inv.setdefault(r["invoice_id"], []).append(r)
            if r["payment_id"]:
                self.rows_by_pay.setdefault(r["payment_id"], []).append(r)
        for op in ep.provenance.get("ops", []):
            if op["table"] == "ledger":
                self.ops.setdefault(op["id"], []).append(op)
        self.injections = [i for i in ep.provenance.get("injections", []) if isinstance(i, dict)]

    def policy_rate(self, ccy: str, day: date):
        """(rate, date text) of the latest published rate on or before day, within 15 days; None when there is none."""
        if ccy == self.base:
            return "1", day.isoformat()
        table = self.fx.get((ccy, self.base), {})
        for back in range(POLICY_RATE_LOOKBACK_DAYS):
            text = (day - timedelta(days=back)).isoformat()
            if text in table:
                return table[text], text
        return None

    def local_date(self, inst) -> date:
        return _local_date(inst, self.schedule)

    def convert(self, amount: int, rate: str, ccy: str) -> int:
        return convert_fraction(amount, rate, self.exps[ccy], self.exps[self.base], self.mode)


def _is_transposition(correct: str, wrong: str) -> bool:
    """wrong is correct with two adjacent different digits swapped, positive, and at least 0.2 % away."""
    if len(correct) != len(wrong):
        return False
    diff = [k for k, (a, b) in enumerate(zip(correct, wrong)) if a != b]
    if len(diff) != 2 or diff[1] != diff[0] + 1:
        return False
    i, j = diff
    if not (correct[i].isdigit() and correct[j].isdigit() and correct[i] == wrong[j] and correct[j] == wrong[i]):
        return False
    if wrong.startswith("0") and not wrong.startswith("0."):
        return False
    return Fraction(wrong) > 0 and abs(Fraction(wrong) - Fraction(correct)) >= Fraction(correct) * RATE_TRANSPOSE_MIN


def _timestamp_ops_errors(ix: _ChangeIndex, rows: list, posting_ts, name: str) -> list[str]:
    """Every timestamp the ops record for these published rows (a set 'after' or an added record) equals posting_ts,
    and the ops record at least one."""
    seen, errs = 0, []
    for row in rows:
        for op in ix.ops.get(row["row_id"], []):
            if op["op"] == "set" and op["field"] == "timestamp":
                inst = parse_ts(op["after"])
            elif op["op"] == "add":
                inst = parse_ts(op["record"]["timestamp"])
            else:
                continue
            seen += 1
            if inst != posting_ts and len(errs) < 3:
                errs.append(f"injection {name}: change.posting_ts differs from the timestamp {op.get('after') or op['record']['timestamp']} "
                            f"that the ops record for row {row['row_id']}")
    return errs if errs else ([] if seen else [f"injection {name}: no ledger op records the posting timestamp change.posting_ts"])


def _target_of(ix: _ChangeIndex, inj: dict, name: str):
    """(document, rows that belong to its own booking, error list): one invoice or one payment target."""
    t = inj.get("targets")
    if not isinstance(t, dict):
        return None, [], [f"injection {name}: targets must be an object"]
    inv, pay = t.get("invoice"), t.get("payment")
    if isinstance(inv, str) and pay is None and inv in ix.inv:
        return ix.inv[inv], [r for r in ix.rows_by_inv.get(inv, []) if r["payment_id"] is None], []
    if isinstance(pay, str) and inv is None and pay in ix.pay:
        return ix.pay[pay], list(ix.rows_by_pay.get(pay, [])), []
    return None, [], [f"injection {name}: targets must name exactly one public invoice or one public payment"]


def _wrong_period_errors(ix: _ChangeIndex, inj: dict, ch: dict, name: str) -> list[str]:
    doc, rows, errs = _target_of(ix, inj, name)
    if errs:
        return errs
    try:
        posting = parse_ts(ch["posting_ts"])
    except ValueError:
        return [f"injection {name}: change.posting_ts is not a timestamp with an offset"]
    return _timestamp_ops_errors(ix, rows, posting, name)


def _wrong_fx_errors(ix: _ChangeIndex, inj: dict, ch: dict, name: str) -> list[str]:
    doc, rows, errs = _target_of(ix, inj, name)
    if errs:
        return errs
    is_invoice = "invoice_id" in doc
    ccy = doc["currency"]
    if ccy == ix.base:
        return [f"injection {name}: the target is in the base currency, so no exchange rate applies"]
    rates = {}
    for key in ("correct_rate", "wrong_rate"):
        try:
            if not _is_rate(ch[key]):
                raise ValueError
            rates[key] = ch[key]
        except (ValueError, ZeroDivisionError):
            errs.append(f"injection {name}: change.{key} must be a positive decimal string")
    dates = {}
    for key in ("correct_rate_date", "wrong_rate_date"):
        if ch[key] is None and key == "wrong_rate_date":
            dates[key] = None
            continue
        try:
            dates[key] = date.fromisoformat(ch[key]).isoformat()
        except (TypeError, ValueError):
            errs.append(f"injection {name}: change.{key} must be an ISO date" + (" or null" if key == "wrong_rate_date" else ""))
    if errs:
        return errs
    inst = parse_ts(doc["issued_at"] if is_invoice else doc["timestamp"])
    local_d = ix.local_date(inst)
    want = ix.policy_rate(ccy, local_d)
    if want != (rates["correct_rate"], dates["correct_rate_date"]):
        errs.append(f"injection {name}: change.correct_rate {rates['correct_rate']} of {dates['correct_rate_date']} is not the fx.csv policy "
                    f"rate {want} for {ccy} on the document's local date {local_d}")
    if rates["wrong_rate"] == rates["correct_rate"]:
        errs.append(f"injection {name}: change.wrong_rate equals change.correct_rate")
    variant = inj.get("variant")
    if variant == "transposed":
        if dates["wrong_rate_date"] is not None:
            errs.append(f"injection {name}: a transposed rate has no wrong_rate_date")
        if not _is_transposition(rates["correct_rate"], rates["wrong_rate"]):
            errs.append(f"injection {name}: change.wrong_rate is not change.correct_rate with two adjacent digits swapped (at least 0.2 % apart)")
    elif variant in ("utc_date", "posting_date", "stale_rate"):
        if variant == "utc_date":
            day = inst.date()
        elif variant == "posting_date":
            try:
                day = ix.local_date(parse_ts(ch["posting_ts"]))
            except ValueError:
                return errs + [f"injection {name}: change.posting_ts is not a timestamp with an offset"]
        else:
            day = ix.local_date(ix.p0) - timedelta(days=1)
        if ix.policy_rate(ccy, day) != (rates["wrong_rate"], dates["wrong_rate_date"]):
            errs.append(f"injection {name}: change.wrong_rate {rates['wrong_rate']} of {dates['wrong_rate_date']} is not the fx.csv rate "
                        f"that the {variant} variant takes, {ix.policy_rate(ccy, day)} (day {day})")
    if variant == "posting_date" and "posting_ts" in ch:
        try:
            errs += _timestamp_ops_errors(ix, rows, parse_ts(ch["posting_ts"]), name)
        except ValueError:
            errs.append(f"injection {name}: change.posting_ts is not a timestamp with an offset")
    # the booking carries the wrong rate: every touched booking row equals the amount converted at wrong_rate
    amount = doc["total_minor"] if is_invoice else doc["amount_minor"]
    booked = ix.convert(amount, rates["wrong_rate"], ccy)
    account = ("1100" if doc["kind"] == "sales" else "2000") if is_invoice else "1000"
    touched = [r for r in rows if r["account"] == account and ix.ops.get(r["row_id"])]
    if not touched:
        errs.append(f"injection {name}: no ledger op touches the {account} row of the target")
    for r in touched:
        if (r["debit_minor"] or r["credit_minor"]) != booked and len(errs) < 6:
            errs.append(f"injection {name}: row {r['row_id']} is booked at {r['debit_minor'] or r['credit_minor']}, "
                        f"not {booked} (the amount at change.wrong_rate)")
    return errs


def _alloc_errors(ix: _ChangeIndex, inj: dict, ch: dict, name: str) -> list[str]:
    t = inj.get("targets") or {}
    pay, inv = ix.pay.get(t.get("payment")), ix.inv.get(t.get("invoice"))
    if pay is None or inv is None:
        return [f"injection {name}: targets must name a public payment and a public invoice"]
    alloc = ch["alloc"]
    if not _is_int(alloc) or not 0 <= alloc <= pay["amount_minor"]:
        return [f"injection {name}: change.alloc must be an integer between 0 and the payment amount {pay['amount_minor']}"]
    errs = []
    variant = inj.get("variant")
    if (variant == "missing") != (alloc == 0):
        errs.append(f"injection {name}: change.alloc {alloc} does not fit variant {variant} (missing means 0, partial means more than 0)")
    if inv["kind"] != "sales" or inv["currency"] != pay["currency"]:
        return errs + [f"injection {name}: the invoice must be a sales invoice in the currency of the payment"]
    ccy, unalloc = pay["currency"], pay["amount_minor"] - alloc
    # the receipt leaves amount - alloc in 2900, converted at the payment-date rate (or the rate of a rate error on it)
    rates = []
    own = ix.policy_rate(ccy, ix.local_date(parse_ts(pay["timestamp"])))
    if own:
        rates.append(own[0])
    rates += [i["change"]["wrong_rate"] for i in ix.injections if i.get("type") == "wrong_fx_rate" and isinstance(i.get("change"), dict)
              and _is_rate(i["change"].get("wrong_rate")) and (i.get("targets") or {}).get("payment") == pay["payment_id"]]
    credited = sum(r["credit_minor"] for r in ix.rows_by_pay.get(pay["payment_id"], []) if r["account"] == "2900")
    try:
        expected = {0} if unalloc == 0 else {ix.convert(unalloc, rate, ccy) for rate in rates}
    except (ValueError, ZeroDivisionError):
        expected = set()
    if credited not in expected:
        errs.append(f"injection {name}: 2900 holds {credited} of the receipt, but change.alloc {alloc} leaves {unalloc} unallocated "
                    f"({sorted(expected)} at the payment-date rate)")
    # the allocated part relieves the invoice's carrying amount in proportion
    carrying = [r["debit_minor"] for r in ix.rows_by_inv.get(inv["invoice_id"], [])
                if r["payment_id"] is None and r["account"] == "1100" and r["debit_minor"] > 0]
    relieved = sum(r["credit_minor"] for r in ix.rows_by_inv.get(inv["invoice_id"], [])
                   if r["payment_id"] == pay["payment_id"] and r["account"] == "1100")
    if len(carrying) != 1:
        errs.append(f"injection {name}: the invoice has {len(carrying)} receivable booking rows, so its carrying amount is unknown")
    elif inv["total_minor"] > 0:
        base = carrying[0]
        want = base if alloc == inv["total_minor"] else _round_fraction(Fraction(base * alloc, inv["total_minor"]), ix.mode)
        if relieved != want:
            errs.append(f"injection {name}: the ledger relieves {relieved} of the invoice, change.alloc {alloc} relieves {want}")
    return errs


def _change_errors(ix: _ChangeIndex, inj: dict) -> list[str]:
    """The recorded change of one injection, checked against the public records and the ops."""
    name, kind = inj.get("issue_id"), inj.get("type")
    if kind not in CHANGE_KEYS or inj.get("variant") not in VARIANTS.get(kind, ()):
        return []  # reported by _injection_errors
    ch = inj.get("change")
    if not isinstance(ch, dict):
        return [f"injection {name}: change must be an object"]
    want = set(CHANGE_KEYS[kind]) | ({"posting_ts"} if kind == "wrong_fx_rate" and inj["variant"] == "posting_date" else set())
    errs = [f"injection {name}: change lacks {k!r}" for k in sorted(want - set(ch))]
    errs += [f"injection {name}: change has the unknown key {k!r}" for k in sorted(set(ch) - want, key=str)]
    if errs:
        return errs
    if kind == "unallocated_payment":
        return _alloc_errors(ix, inj, ch, name)
    if kind == "wrong_fx_rate":
        return _wrong_fx_errors(ix, inj, ch, name)
    if kind == "wrong_period":
        return _wrong_period_errors(ix, inj, ch, name)
    return []


def change_errors(ep: Episode, injections: list) -> list[str]:
    """provenance.injections[].change against fx.csv, the ledger, the payments and the ops (see the module docstring)."""
    try:
        ix = _ChangeIndex(ep)
        return [e for inj in injections if isinstance(inj, dict) for e in _change_errors(ix, inj)]
    except REPLAY_ERRORS as exc:
        return [f"injection change cannot be cross-checked: {type(exc).__name__}: {exc}"]


def check_provenance_structure(ep: Episode) -> list[str]:
    """Provenance is replayable, injections and distractors are well formed, use known names, point at existing
    public invoices or payments, match the answer key one to one by (issue_id, type), and each injection's target
    values equal the affected_ids of the truth issue with its issue_id."""
    errs = provenance_shape_errors(ep)
    if errs:
        return errs
    injections, distractors = ep.provenance.get("injections", []), ep.provenance.get("distractors", [])
    if not isinstance(injections, list) or not isinstance(distractors, list):
        return ["injections and distractors must be lists"]
    invoice_ids, payment_ids = _document_ids(ep)
    for inj in injections:
        errs += _injection_errors(inj, invoice_ids, payment_ids)
    for dis in distractors:
        errs += _distractor_errors(dis, invoice_ids | payment_ids)
    injected = sorted((str(i.get("issue_id")), str(i.get("type"))) for i in injections if isinstance(i, dict))
    declared = sorted((str(t["issue_id"]), str(t["type"])) for t in ep.truth.get("issues", []))
    if injected != declared:
        errs.append(f"injections {injected} do not match truth issues {declared} by (issue_id, type)")
    errs += _retarget_errors(injections, ep.truth.get("issues", []))
    errs += change_errors(ep, injections)
    return errs[:20]


def check_roundtrip(ep: Episode, clean: Episode | None) -> list[str]:
    errs = check_provenance_structure(ep)
    if provenance_shape_errors(ep):
        return errs
    try:
        return errs + _replay_errors(ep, clean)
    except REPLAY_ERRORS as exc:
        return errs + [f"provenance ops cannot be replayed on the published tables: {type(exc).__name__}: {exc}"]


def _replay_errors(ep: Episode, clean: Episode | None) -> list[str]:
    errs = []
    keys = OP_KEYS
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


def _clean_book_errors(ep: Episode, clean: Episode | None) -> list[str]:
    """Anomalies or findings in the clean books; a failure when the clean books cannot be reconstructed."""
    if clean is None and provenance_shape_errors(ep):
        return ["clean books cannot be reconstructed: provenance is malformed"]
    try:
        clean_ep = clean if clean is not None else clean_episode_from(ep)
        found = audit(clean_ep.manifest, clean_ep.policy, clean_ep.ledger, clean_ep.invoices, clean_ep.payments, clean_ep.fx)
    except REPLAY_ERRORS as exc:
        return [f"clean books cannot be reconstructed: {type(exc).__name__}: {exc}"]
    return [f"clean books: {a}" for a in found["anomalies"][:10]] + [
        f"clean books show {f['type']} on {f['affected_ids']}" for f in found["findings"][:10]]


def verify_generated(ep: Episode, clean: Episode | None = None) -> dict:
    checks = {}
    checks["records_schema"] = check_records_schema(ep)
    checks["ids_unique"] = check_ids(ep)
    checks["clean_equalities"] = _clean_book_errors(ep, clean)
    checks["provenance_roundtrip"] = check_roundtrip(ep, clean)
    found = audit(ep.manifest, ep.policy, ep.ledger, ep.invoices, ep.payments, ep.fx)
    checks["declared_discrepancies"] = compare_with_truth(found, ep.truth) + check_key_consistency(ep)
    checks["evidence_sufficient"] = check_evidence(ep)
    checks["budget_feasible"] = check_budget(ep)
    checks["no_surface_tells"] = (["provenance is malformed, so the surface cannot be checked"]
                                  if provenance_shape_errors(ep) else check_surface(ep, strict=clean is None))
    checks["no_leaks"] = check_leaks(ep)
    failures = [f"{name}: {msg}" for name, msgs in checks.items() for msg in msgs]
    return {
        "ok": not failures,
        "checks": {name: ("pass" if not msgs else msgs) for name, msgs in checks.items()},
        "failures": failures,
        "n_issues": len(ep.truth.get("issues", [])),
    }


_ID_RE = re.compile(r"^[^:\s]{1,64}$")
