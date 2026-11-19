"""Oracle (organizer baseline 4). Grader-side only.

Submits every answer-key issue with its expected amount and the first
acceptable evidence set, using zero inspection steps. It measures the maximum
attainable reward, not agent ability.
"""

from __future__ import annotations


class OraclePolicy:
    name = "oracle"

    def __init__(self, truth: dict):
        self.truth = truth

    def findings(self) -> list[dict]:
        out = []
        for t in sorted(self.truth.get("issues", []), key=lambda x: x["issue_id"]):
            out.append({
                "type": t["type"],
                "affected_ids": list(t["affected_ids"]),
                "claimed_amount_minor": int(t["expected_amount_minor"]),
                "currency": t["currency"],
                "evidence_ids": list(t["evidence_sets"][0]),
                "explanation": t.get("explanation", "")[:1000],
            })
        return out

    def act(self, obs: dict, reward: float = 0.0, info: dict | None = None) -> dict:
        episode_id = obs["manifest"]["episode_id"] if "manifest" in obs else self.truth.get("episode_id")
        return {"action": "submit", "findings": {"episode_id": episode_id, "findings": self.findings()}}
