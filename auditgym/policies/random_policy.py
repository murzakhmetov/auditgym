"""Random explorer with a fixed seed (organizer baseline 1).

Picks uniformly among tools with random (sometimes invalid) arguments, reuses
IDs it has seen, and at a random moment submits 0-3 findings assembled from
seen IDs. Deterministic for a given seed and observation sequence.
"""

from __future__ import annotations

import random

from .. import FINDING_TYPES
from ..schemas import TABLES

_ID_FIELDS = ("row_id", "invoice_id", "payment_id", "doc_id")


class RandomPolicy:
    name = "random"

    def __init__(self, seed: int = 0):
        self.seed = int(seed)
        self.rng = random.Random(self.seed)
        self._reset_state()

    def _reset_state(self):
        self.episode_id = None
        self.base = "XXX"
        self.ids: list[str] = []
        self.doc_ids: list[str] = []
        self.totals: dict[str, int] = {}

    def _remember(self, obs: dict) -> None:
        result = obs.get("result") or {}
        rows = list(result.get("rows") or [])
        if result.get("record"):
            rows.append(result["record"])
        if result.get("document"):
            rows.append(result["document"])
        for r in rows:
            for f in _ID_FIELDS:
                v = r.get(f)
                if isinstance(v, str) and v not in self.ids:
                    self.ids.append(v)
                    if f == "doc_id":
                        self.doc_ids.append(v)
            if "date" in r and "source_currency" in r:
                fid = f"{r['date']}:{r['source_currency']}:{r['target_currency']}"
                if fid not in self.ids:
                    self.ids.append(fid)

    def _submit(self) -> dict:
        findings = []
        for _ in range(self.rng.randint(0, 3)):
            if not self.ids:
                break
            findings.append({
                "type": self.rng.choice(FINDING_TYPES),
                "affected_ids": self.rng.sample(self.ids, k=min(len(self.ids), self.rng.randint(1, 2))),
                "claimed_amount_minor": self.rng.randint(0, 500000),
                "currency": self.base,
                "evidence_ids": self.rng.sample(self.ids, k=min(len(self.ids), self.rng.randint(0, 4))),
                "explanation": "random guess",
            })
        return {"action": "submit", "findings": {"episode_id": self.episode_id, "findings": findings}}

    def act(self, obs: dict, reward: float = 0.0, info: dict | None = None) -> dict:
        if "task" in obs:
            self._reset_state()
            self.episode_id = obs["manifest"]["episode_id"]
            self.base = obs["manifest"]["base_currency"]
        self._remember(obs)
        remaining = obs.get("remaining_steps", 0)
        if remaining <= 1 or self.rng.random() < 0.04:
            return self._submit()
        choice = self.rng.randrange(5)
        if choice in (0, 1):
            table = self.rng.choice(TABLES)
            cursor = self.rng.choice([None, "0", str(50 * self.rng.randint(0, 40)), "abc"])
            return {"action": "list_records", "table": table, "cursor": cursor, "limit": self.rng.randint(1, 50)}
        if choice == 2:
            pool = self.ids or ["missing-id"]
            rid = self.rng.choice(pool) if self.rng.random() < 0.8 else f"guess-{self.rng.randint(0, 9999)}"
            return {"action": "get_record", "table": self.rng.choice(TABLES), "id": rid}
        if choice == 3:
            pool = self.doc_ids or ["missing-doc"]
            did = self.rng.choice(pool) if self.rng.random() < 0.8 else f"doc-{self.rng.randint(0, 9999)}"
            return {"action": "get_document", "doc_id": did}
        a, b = self.rng.randint(0, 10**6), self.rng.randint(1, 10**4)
        expr = self.rng.choice([f"{a} / {b}", f"{a} * 1.0842", f"({a} - {b}) * 2", "1/0", "2**8"])
        return {"action": "calculator", "expression": expr}
