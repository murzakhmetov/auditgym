"""Terminal rewards.

Common reward (the one reported as "return"):
    reward = clip(2 * F1 - 1 - 0.002 * inspection_steps, -1, 1)
inspection_steps counts every step except the final submit (invalid actions
included). Computed with exact fractions, then converted to float once.

Experimental reward (reported separately, never replaces the common one):
soft credit per issue for a finding with the right type and affected_ids:
0.5, plus 0.25 if currency and amount are right, plus 0.25 if a complete
evidence set is cited. softF1 = 2 * S / (n_findings + n_issues), so extra or
repeated partial findings always lower it.
"""

from __future__ import annotations

from fractions import Fraction

from .matcher import f1_fraction, normalize_finding, normalize_issue

STEP_COST = Fraction(2, 1000)
INVALID_REWARD = -1.0


def clip(value: Fraction, lo: int = -1, hi: int = 1) -> Fraction:
    return max(Fraction(lo), min(Fraction(hi), value))


def terminal_reward_from_f1(f1: Fraction, inspection_steps: int) -> float:
    return float(clip(2 * f1 - 1 - STEP_COST * int(inspection_steps)))


def terminal_reward(tp: int, fp: int, fn: int, inspection_steps: int) -> float:
    return terminal_reward_from_f1(f1_fraction(tp, fp, fn), inspection_steps)


def experimental_reward(findings: list[dict], issues: list[dict], inspection_steps: int, aliases: dict | None = None) -> dict:
    nfs = [normalize_finding(i, f, aliases) for i, f in enumerate(findings)]
    nis = sorted((normalize_issue(t) for t in issues), key=lambda t: t.issue_id)
    used: set[int] = set()
    credit_total = Fraction(0)
    per_issue = {}
    for ni in nis:
        best = None
        for nf in nfs:
            if nf.index in used or nf.type != ni.type or nf.ids != ni.ids:
                continue
            credit = Fraction(1, 2)
            if nf.currency == ni.currency and abs(nf.amount - ni.amount) <= ni.tolerance:
                credit += Fraction(1, 4)
            if any(es <= nf.evidence for es in ni.evidence_sets):
                credit += Fraction(1, 4)
            if best is None or credit > best[0]:
                best = (credit, nf.index)
        if best is not None:
            used.add(best[1])
            credit_total += best[0]
            per_issue[ni.issue_id] = float(best[0])
    denom = len(nfs) + len(nis)
    soft_f1 = Fraction(1) if denom == 0 else Fraction(2) * credit_total / denom
    return {
        "soft_f1": float(soft_f1),
        "reward": terminal_reward_from_f1(soft_f1, inspection_steps),
        "credit_per_issue": per_issue,
    }
