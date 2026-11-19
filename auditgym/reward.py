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


def _max_weight_assignment(weights: list[list[int]]) -> list[tuple[int, int]]:
    """Rows x columns of non-negative integer weights -> (row, col) pairs with positive weight that maximise
    the total (Hungarian algorithm on a square padded cost matrix; deterministic for a given input order)."""
    n_rows = len(weights)
    n_cols = len(weights[0]) if n_rows else 0
    n = max(n_rows, n_cols)
    if n == 0:
        return []
    top = max(max(row) for row in weights) if n_cols else 0
    cost = [[top - (weights[i][j] if i < n_rows and j < n_cols else 0) for j in range(n)] for i in range(n)]
    inf = float("inf")
    u, v, p, way = [0] * (n + 1), [0] * (n + 1), [0] * (n + 1), [0] * (n + 1)
    for i in range(1, n + 1):
        p[0], j0 = i, 0
        minv, used = [inf] * (n + 1), [False] * (n + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], inf, 0
            for j in range(1, n + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    return sorted((p[j] - 1, j - 1) for j in range(1, n + 1)
                  if p[j] and p[j] - 1 < n_rows and j - 1 < n_cols and weights[p[j] - 1][j - 1] > 0)


def experimental_reward(findings: list[dict], issues: list[dict], inspection_steps: int, aliases: dict | None = None) -> dict:
    nfs = [normalize_finding(i, f, aliases) for i, f in enumerate(findings)]
    nis = sorted((normalize_issue(t) for t in issues), key=lambda t: t.issue_id)
    # credit in quarters: 2 for the right type and affected_ids, +1 amount and currency, +1 complete evidence set.
    # Findings only compete for issues with the same (type, affected_ids); within such a group the credit is
    # assigned one-to-one by maximum total weight, so finding order never lowers an exact answer below 1.
    groups: dict = {}
    for ni in nis:
        groups.setdefault((ni.type, ni.ids), []).append(ni)
    credit_total = Fraction(0)
    per_issue = {}
    for key, group in groups.items():
        cands = [nf for nf in nfs if (nf.type, nf.ids) == key]
        if not cands:
            continue
        weights = [[2 + (nf.currency == ni.currency and abs(nf.amount - ni.amount) <= ni.tolerance)
                    + any(es <= nf.evidence for es in ni.evidence_sets) for nf in cands] for ni in group]
        for r, c in _max_weight_assignment(weights):
            credit = Fraction(weights[r][c], 4)
            credit_total += credit
            per_issue[group[r].issue_id] = float(credit)
    denom = len(nfs) + len(nis)
    soft_f1 = Fraction(1) if denom == 0 else Fraction(2) * credit_total / denom
    return {
        "soft_f1": float(soft_f1),
        "reward": terminal_reward_from_f1(soft_f1, inspection_steps),
        "credit_per_issue": per_issue,
    }
