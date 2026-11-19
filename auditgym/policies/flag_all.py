"""'Flag everything' attack (organizer baseline 3).

Reads the first page of invoices and payments, then submits the maximum of 30
findings: every seen document under every plausible type, with the document's
own amount and every ID it has seen as evidence. The reward must punish this.
"""

from __future__ import annotations

from .. import FINDING_TYPES
from ..schemas import MAX_EVIDENCE_IDS, MAX_FINDINGS


class FlagAllPolicy:
    name = "flag_all"

    def __init__(self):
        self.plan = []
        self.docs = []
        self.rows = []
        self.episode_id = None
        self.base = "XXX"

    def act(self, obs: dict, reward: float = 0.0, info: dict | None = None) -> dict:
        if "task" in obs:
            self.episode_id = obs["manifest"]["episode_id"]
            self.base = obs["manifest"]["base_currency"]
            self.docs, self.rows = [], []
            self.plan = [
                {"action": "list_records", "table": "invoices", "cursor": None, "limit": 50},
                {"action": "list_records", "table": "payments", "cursor": None, "limit": 50},
                {"action": "list_records", "table": "ledger", "cursor": None, "limit": 50},
            ]
        result = obs.get("result") or {}
        for r in result.get("rows") or []:
            if "doc_id" in r:
                self.docs.append(r)
            elif "row_id" in r:
                self.rows.append(r)
        if self.plan:
            return self.plan.pop(0)
        return {"action": "submit", "findings": {"episode_id": self.episode_id, "findings": self._spam()}}

    def _spam(self) -> list[dict]:
        evidence_pool = [d["doc_id"] for d in self.docs] + [r["row_id"] for r in self.rows]
        findings = []
        for i, doc in enumerate(self.docs):
            doc_key = doc.get("invoice_id") or doc.get("payment_id")
            amount = int(doc.get("total_minor", doc.get("amount_minor", 0)) or 0)
            for t in FINDING_TYPES:
                ids = [doc_key]
                if t == "duplicate_invoice" and i + 1 < len(self.docs):
                    ids = [doc_key, self.docs[i + 1].get("invoice_id") or self.docs[i + 1].get("payment_id")]
                if t == "unallocated_payment" and doc.get("invoice_refs"):
                    ids = [doc_key] + list(doc["invoice_refs"])[:1]
                ev = [doc["doc_id"]] + [e for e in evidence_pool if e != doc["doc_id"]][: MAX_EVIDENCE_IDS - 1]
                findings.append({
                    "type": t,
                    "affected_ids": ids,
                    "claimed_amount_minor": amount,
                    "currency": self.base,
                    "evidence_ids": ev,
                    "explanation": "flagged everything",
                })
                if len(findings) >= MAX_FINDINGS:
                    return findings
        return findings
