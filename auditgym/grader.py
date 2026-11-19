"""Grader: structural validation result + matcher + rewards -> grade report.

The report is grader-only. In eval mode nothing from it reaches the policy
before the run ends.
"""

from __future__ import annotations

from .matcher import match
from .reward import INVALID_REWARD, experimental_reward, terminal_reward_from_f1

GRADE_VERSION = "1"


class Grader:
    def __init__(self, truth: dict | None, episode_id: str):
        self.truth = truth or {}
        self.issues = list(self.truth.get("issues", []))
        self.aliases = dict(self.truth.get("id_aliases", {}))
        self.episode_id = episode_id

    def grade(self, submission, inspection_steps: int, status: str, invalid_errors=None, elapsed_s: float = 0.0) -> dict:
        base = {
            "grade_version": GRADE_VERSION,
            "episode_id": self.episode_id,
            "status": status,
            "inspection_steps": int(inspection_steps),
            "elapsed_s": round(float(elapsed_s), 6),
            "n_issues": len(self.issues),
        }
        if status == "invalid_submission":
            return {
                **base,
                "valid": False,
                "errors": list(invalid_errors or [])[:20],
                "n_findings": None,
                "tp": 0,
                "fp": 0,
                "fn": len(self.issues),
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "reward": INVALID_REWARD,
                "reward_experimental": INVALID_REWARD,
                "closed": False,
                "pairs": [],
                "unmatched_findings": [],
                "missed_issues": [t["issue_id"] for t in self.issues],
            }
        findings = list(submission["findings"]) if submission else []
        result = match(findings, self.issues, self.aliases)
        reward = terminal_reward_from_f1(result.f1_exact, inspection_steps)
        exp = experimental_reward(findings, self.issues, inspection_steps, self.aliases)
        return {
            **base,
            "valid": True,
            "errors": [],
            "n_findings": len(findings),
            "tp": result.tp,
            "fp": result.fp,
            "fn": result.fn,
            "precision": result.precision,
            "recall": result.recall,
            "f1": result.f1,
            "reward": reward,
            "reward_experimental": exp["reward"],
            "soft_f1": exp["soft_f1"],
            "closed": result.fp == 0 and result.fn == 0,
            "pairs": [{"finding_index": i, "issue_id": iid} for i, iid in result.pairs],
            "unmatched_findings": result.unmatched,
            "missed_issues": result.missed,
        }
