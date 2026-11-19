"""Strong scripted auditor (demo policy, not one of the four organizer baselines).

Reads every page of every table through list_records, then runs the
independent auditor (auditgym.auditor) on exactly what it has seen and submits
its findings with the first evidence set. It shows that every scenario is
solvable inside the 100-step budget using only the tool interface.
"""

from __future__ import annotations

from ..auditor import audit
from .common import Pager, submission


class AuditorPolicy:
    name = "auditor"

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
        remaining = obs.get("remaining_steps", 0)
        if self.pager.finished or remaining <= 1:
            return submission(self.manifest["episode_id"], self.findings())
        return self.pager.next_action()

    def findings(self) -> list:
        d = self.pager.data
        try:
            result = audit(self.manifest, self.policy, d["ledger"], d["invoices"], d["payments"], d["fx"])
        except Exception:
            return []
        out = []
        for f in result["findings"]:
            out.append({
                "type": f["type"],
                "affected_ids": f["affected_ids"],
                "claimed_amount_minor": int(f["amount"]),
                "currency": f["currency"],
                "evidence_ids": [e for e in f["evidence_sets"][0] if e][:10],
                "explanation": f"Recomputed from records and policy: {f['type']} of {f['amount']} minor units.",
            })
        return out
