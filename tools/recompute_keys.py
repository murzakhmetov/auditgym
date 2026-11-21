"""Recompute every answer-key amount of an episode from the PUBLIC records only, without importing auditgym.

An independent second derivation of the key, next to the scripted auditor and the evidence checker of the package: it reads
only `public/` (policy.json, fx.csv, invoices.jsonl, payments.jsonl, ledger.csv) and the key's own fields in
`grader/truth.json` (type, affected IDs, amount, tolerance, evidence sets), and uses the standard library alone.

  python tools/recompute_keys.py ROOT [ROOT ...] [--record DIR]

ROOT is a folder of episode folders (each with public/ and grader/), for example `episodes/train`. Checks per issue type:
  wrong_fx_rate       |bank or primary row - round(document amount * policy rate * 10^(exp_base - exp_doc))| equals the key amount
  wrong_period        the key amount is the cited row; document and row fall on different sides of the reporting period
  unallocated_payment the key amount is the cited 2900 row of the payment, and the payment lists the invoice
  duplicate_invoice   the two invoices agree in kind, counterparty, currency, total and every line; the key amount is the
                      primary row of the later copy
For a payment target it also checks that nothing of the payment sits on 2900 and that the payment does not exceed its invoice.
Exit code 0 when every issue matches, 1 otherwise. `--record DIR` writes DIR/summary.md and DIR/summary.json.
"""
import csv
import glob
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP


def read_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh if ln.strip()]


def instant(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


class Episode:
    def __init__(self, folder):
        pub = os.path.join(folder, "public")
        self.name = os.path.basename(folder.rstrip("/\\"))
        self.policy = json.load(open(os.path.join(pub, "policy.json"), encoding="utf-8"))
        self.invoices = {r["invoice_id"]: r for r in read_jsonl(os.path.join(pub, "invoices.jsonl"))}
        self.payments = {r["payment_id"]: r for r in read_jsonl(os.path.join(pub, "payments.jsonl"))}
        with open(os.path.join(pub, "ledger.csv"), encoding="utf-8", newline="") as fh:
            self.ledger = list(csv.DictReader(fh))
        self.rows = {r["row_id"]: r for r in self.ledger}
        self.fx = {}
        with open(os.path.join(pub, "fx.csv"), encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                self.fx[(r["date"], r["source_currency"], r["target_currency"])] = Decimal(r["rate"])
        self.truth = json.load(open(os.path.join(folder, "grader", "truth.json"), encoding="utf-8"))
        rp = self.policy["reporting_period"]
        self.p0, self.p1 = instant(rp["start"]), instant(rp["end"])

    def in_period(self, ts):
        return self.p0 <= instant(ts) < self.p1


def amount(row):
    return int(row["debit_minor"]) or int(row["credit_minor"])


def converted(ep, value, ccy, rate):
    ex = ep.policy["currency_exponents"]
    raw = Decimal(value) * rate * (Decimal(10) ** (ex[ep.policy["base_currency"]] - ex[ccy]))
    return (int(raw.quantize(Decimal(1), rounding=ROUND_HALF_EVEN)), int(raw.quantize(Decimal(1), rounding=ROUND_HALF_UP)))


def cited_rows(ep, issue):
    return [x for s in issue["evidence_sets"] for x in s if x in ep.rows]


def check_issue(ep, issue):
    """Return (side, problem or None); side is invoice, receipt, disbursement or pair."""
    typ, ids, key_amt, tol = issue["type"], issue["affected_ids"], issue["expected_amount_minor"], issue["tolerance_minor"]
    if typ == "duplicate_invoice":
        a, b = (ep.invoices.get(i) for i in ids)
        if a is None or b is None:
            return "pair", "affected invoice missing"
        for f in ("kind", "entity_id", "currency", "total_minor"):
            if a[f] != b[f]:
                return "pair", f"the two invoices differ in {f}"
        lines = lambda r: [(x["description"], x["quantity"], x["unit_price_minor"], x["amount_minor"], x["ref"]) for x in r["line_items"]]
        if lines(a) != lines(b):
            return "pair", "the two invoices differ in a line"
        later = a if instant(a["issued_at"]) >= instant(b["issued_at"]) else b
        acct = "1100" if later["kind"] == "sales" else "2000"
        prim = [r for r in ep.ledger if r["invoice_id"] == later["invoice_id"] and not r["payment_id"] and r["account"] == acct]
        if not prim or abs(amount(prim[0]) - key_amt) > tol:
            return "pair", f"key amount {key_amt} is not the later copy's primary row"
        return "pair", None
    if typ == "unallocated_payment":
        pid = [i for i in ids if i in ep.payments]
        iid = [i for i in ids if i in ep.invoices]
        if len(pid) != 1 or len(iid) != 1:
            return "receipt", "affected ids are not one payment and one invoice"
        rows = [ep.rows[r] for r in cited_rows(ep, issue) if ep.rows[r]["account"] == "2900" and ep.rows[r]["payment_id"] == pid[0]]
        if len(rows) != 1 or abs(amount(rows[0]) - key_amt) > tol:
            return "receipt", "the cited 2900 row of the payment does not carry the key amount"
        if iid[0] not in (ep.payments[pid[0]]["invoice_refs"] or []):
            return "receipt", "the payment does not list the invoice"
        return ("receipt" if ep.payments[pid[0]]["kind"] == "receipt" else "disbursement"), None
    # wrong_fx_rate and wrong_period: the target is an invoice or a payment
    pays = [i for i in ids if i in ep.payments]
    if pays:
        p = ep.payments[pays[0]]
        side = p["kind"]
        if any(r["account"] == "2900" and r["payment_id"] == p["payment_id"] for r in ep.ledger):
            return side, "a payment target has a row on 2900"
        refs = p["invoice_refs"] or []
        if not refs or any(r not in ep.invoices for r in refs):
            return side, "a payment target has no invoice"
        if len(refs) == 1 and p["amount_minor"] > ep.invoices[refs[0]]["total_minor"]:
            return side, "a payment target exceeds its invoice"
        doc_ts, doc_amt, doc_ccy = p["timestamp"], p["amount_minor"], p["currency"]
        want = [r for r in cited_rows(ep, issue) if ep.rows[r]["payment_id"] == p["payment_id"]]
    else:
        inv = ep.invoices[ids[0]]
        side = "invoice"
        doc_ts, doc_amt, doc_ccy = inv["issued_at"], inv["total_minor"], inv["currency"]
        want = [r for r in cited_rows(ep, issue) if ep.rows[r]["invoice_id"] == inv["invoice_id"]]
    if not want:
        return side, "no cited row of the target"
    row = ep.rows[want[0]]
    if typ == "wrong_period":
        if abs(amount(row) - key_amt) > tol:
            return side, "key amount is not the cited row"
        if ep.in_period(doc_ts) == ep.in_period(row["timestamp"]):
            return side, "document and row fall on the same side of the period"
        return side, None
    fxk = [x for s in issue["evidence_sets"] for x in s if x.count(":") == 2]
    if not fxk:
        return side, "no fx row cited"
    d, src, dst = fxk[0].split(":")
    rate = ep.fx.get((d, src, dst))
    if rate is None:
        return side, "no direct fx rate for the cited row"
    best = min(abs(abs(amount(row) - c) - key_amt) for c in converted(ep, doc_amt, doc_ccy, rate))
    return side, (None if best <= tol else f"key amount {key_amt} differs from the recomputed difference")


def main(argv):
    record = None
    roots = []
    it = iter(argv)
    for a in it:
        if a == "--record":
            record = next(it)
        else:
            roots.append(a)
    if not roots:
        print(__doc__)
        return 2
    counts, problems, episodes = {}, [], 0
    for root in roots:
        for tf in sorted(glob.glob(os.path.join(root, "*", "grader", "truth.json"))):
            ep = Episode(os.path.dirname(os.path.dirname(tf)))
            episodes += 1
            for issue in ep.truth["issues"]:
                side, problem = check_issue(ep, issue)
                key = f"{issue['type']} / {side}"
                counts.setdefault(key, [0, 0])[0] += 1
                if problem:
                    problems.append(f"{ep.name} {issue['issue_id']} {key}: {problem}")
                else:
                    counts[key][1] += 1
    total = sum(c[0] for c in counts.values())
    ok = sum(c[1] for c in counts.values())
    print(f"{episodes} episodes, {total} issues, {ok} recomputed from the public records alone, {total - ok} differ")
    for p in problems:
        print("DIFF", p)
    if record:
        os.makedirs(record, exist_ok=True)
        rows = "\n".join(f"| {k} | {v[0]} | {v[1]} |" for k, v in sorted(counts.items()))
        md = ("# Independent key recompute\n\n"
              "`tools/recompute_keys.py`: every answer-key amount recomputed from the public records alone "
              "(policy, FX table, invoices, payments, ledger), standard library only, no import of `auditgym` (see the docstring of the tool for the checks).\n\n"
              f"- episodes: {episodes}\n- issues: {total}\n- recomputed and equal to the key: {ok}\n- differing: {total - ok}\n\n"
              "| type / side of the target | issues | recomputed |\n|---|---|---|\n" + rows + "\n")
        open(os.path.join(record, "summary.md"), "w", encoding="utf-8", newline="").write(md)
        js = {"episodes": episodes, "issues": total, "recomputed": ok, "differing": total - ok,
              "by_type_and_side": {k: {"issues": v[0], "recomputed": v[1]} for k, v in sorted(counts.items())}}
        open(os.path.join(record, "summary.json"), "w", encoding="utf-8", newline="").write(json.dumps(js, indent=2, sort_keys=True) + "\n")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
