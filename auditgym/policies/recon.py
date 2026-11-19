"""Simple reconciliation algorithm (organizer baseline 2).

Reads all tables, then applies the kind of shortcuts a quick reconciliation
script would use. The environment is designed so that each shortcut fails on
some distractor:
  * duplicates: same supplier, currency, total and calendar date (ignores line
    refs, so legitimate repeats become false positives);
  * unallocated: any 2900 credit of a receipt that carries invoice_refs
    (overpayment excess is legitimate and becomes a false positive);
  * FX: rate of the calendar date as written in the timestamp, exact date only
    (wrong when timestamps are written in UTC or another offset);
  * period: compares the year-month prefix of the timestamps as written
    (wrong around midnight when offsets differ).
"""

from __future__ import annotations

from ..money import convert_minor
from .common import Pager, submission


def _amt(r: dict) -> int:
    return r["debit_minor"] or r["credit_minor"]


class ReconPolicy:
    name = "recon"

    def __init__(self):
        self.pager = Pager()
        self.manifest = None
        self.policy = None

    def act(self, obs: dict, reward: float = 0.0, info: dict | None = None) -> dict:
        if "task" in obs:
            self.pager = Pager()
            self.manifest = obs["manifest"]
            self.policy = obs["policy"]
        else:
            self.pager.feed(obs)
        if self.pager.finished or obs.get("remaining_steps", 0) <= 1:
            return submission(self.manifest["episode_id"], self.findings())
        return self.pager.next_action()

    def findings(self) -> list:
        d = self.pager.data
        base = self.manifest["base_currency"]
        exps = self.policy["currency_exponents"]
        rounding = self.policy["rounding"]["mode"]
        period = self.manifest["period_start"][:7]
        by_inv, by_pay = {}, {}
        for r in d["ledger"]:
            if r["payment_id"]:
                by_pay.setdefault(r["payment_id"], []).append(r)
            elif r["invoice_id"]:
                by_inv.setdefault(r["invoice_id"], []).append(r)
        rates = {(r["date"], r["source_currency"]): r["rate"] for r in d["fx"] if r["target_currency"] == base}
        out = []

        def add(t, ids, amount, evidence):
            out.append({"type": t, "affected_ids": ids, "claimed_amount_minor": int(amount), "currency": base,
                        "evidence_ids": [e for e in evidence if e][:10], "explanation": f"recon rule for {t}"})

        groups = {}
        for doc in d["invoices"]:
            if doc["kind"] == "purchase" and doc["invoice_id"] in by_inv:
                groups.setdefault((doc["entity_id"], doc["currency"], doc["total_minor"], doc["issued_at"][:10]), []).append(doc)
        for docs in groups.values():
            if len(docs) >= 2:
                a, b = docs[0], docs[1]
                ra = [r for r in by_inv[a["invoice_id"]] if r["account"] == "2000"]
                rb = [r for r in by_inv[b["invoice_id"]] if r["account"] == "2000"]
                if ra and rb:
                    add("duplicate_invoice", [a["invoice_id"], b["invoice_id"]], _amt(rb[0]),
                        [a["doc_id"], b["doc_id"], ra[0]["row_id"], rb[0]["row_id"]])
        pays = {p["payment_id"]: p for p in d["payments"]}
        invs = {i["invoice_id"]: i for i in d["invoices"]}
        for pid, rows in by_pay.items():
            p = pays.get(pid)
            if not p or p["kind"] != "receipt" or not p["invoice_refs"]:
                continue
            for r in rows:
                if r["account"] == "2900" and r["credit_minor"] > 0:
                    ref = p["invoice_refs"][0]
                    add("unallocated_payment", [pid, ref], r["credit_minor"],
                        [p["doc_id"], invs[ref]["doc_id"] if ref in invs else None, r["row_id"]])
        for doc in d["invoices"]:
            rows = by_inv.get(doc["invoice_id"], [])
            prim = [r for r in rows if r["account"] in ("1100", "2000") and r["timestamp"] != self.manifest["period_start"]]
            if not prim:
                continue
            prim = prim[0]
            if doc["currency"] != base:
                rate = rates.get((doc["issued_at"][:10], doc["currency"]))
                if rate:
                    expected = convert_minor(doc["total_minor"], rate, exps[doc["currency"]], exps[base], rounding)
                    if abs(expected - _amt(prim)) > 2:
                        add("wrong_fx_rate", [doc["invoice_id"]], abs(expected - _amt(prim)),
                            [doc["doc_id"], prim["row_id"], f"{doc['issued_at'][:10]}:{doc['currency']}:{base}"])
            if (doc["issued_at"][:7] == period) != (prim["timestamp"][:7] == period):
                add("wrong_period", [doc["invoice_id"]], _amt(prim), [doc["doc_id"], prim["row_id"]])
        for pid, rows in by_pay.items():
            p = pays.get(pid)
            bank = [r for r in rows if r["account"] == "1000"]
            if not p or not bank:
                continue
            bank = bank[0]
            if p["currency"] != base:
                rate = rates.get((p["timestamp"][:10], p["currency"]))
                if rate:
                    expected = convert_minor(p["amount_minor"], rate, exps[p["currency"]], exps[base], rounding)
                    if abs(expected - _amt(bank)) > 2:
                        add("wrong_fx_rate", [pid], abs(expected - _amt(bank)),
                            [p["doc_id"], bank["row_id"], f"{p['timestamp'][:10]}:{p['currency']}:{base}"])
            if (p["timestamp"][:7] == period) != (bank["timestamp"][:7] == period):
                add("wrong_period", [pid], _amt(bank), [p["doc_id"], bank["row_id"]])
        return out
