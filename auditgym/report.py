"""Aggregate grades into diagnostics: P, R, F1, return, steps, agent time,
share of fully closed episodes, per-type recall, and miss reasons."""

from __future__ import annotations

from collections import Counter, defaultdict

from . import FINDING_TYPES


def _mean(xs):
    xs = list(xs)
    return round(sum(xs) / len(xs), 4) if xs else None


def summarize(grades: list) -> dict:
    groups = defaultdict(list)
    for g in grades:
        groups[(g["split"], g["policy"])].append(g)
    out = {}
    for (split, policy), gs in sorted(groups.items()):
        clean = [g for g in gs if g["n_issues"] == 0]
        dirty = [g for g in gs if g["n_issues"] > 0]
        per_type = {}
        misses = Counter()
        for t in FINDING_TYPES:
            iss = [i for g in gs for i in g.get("issues", []) if i["type"] == t]
            if iss:
                per_type[t] = round(sum(i["found"] for i in iss) / len(iss), 4)
        for g in gs:
            for i in g.get("issues", []):
                if not i["found"]:
                    misses[i["miss_reason"]] += 1
        inter = [g for g in gs if any(i.get("scenario") not in (None, "single") for i in g.get("issues", []))]
        out[f"{split}/{policy}"] = {
            "split": split,
            "policy": policy,
            "episodes": len(gs),
            "return": _mean(g["reward"] for g in gs),
            "return_experimental": _mean(g["reward_experimental"] for g in gs),
            "precision": _mean(g["precision"] for g in gs),
            "recall": _mean(g["recall"] for g in gs),
            "f1": _mean(g["f1"] for g in gs),
            "steps": _mean(g["inspection_steps"] for g in gs),
            "agent_time_s": _mean(g["agent_time_s"] for g in gs),
            "closed_share": _mean(1.0 if g["closed"] else 0.0 for g in gs),
            "invalid": sum(1 for g in gs if not g.get("valid", True)),
            "truncated": sum(1 for g in gs if g["status"] in ("step_limit", "time_limit")),
            "return_clean": _mean(g["reward"] for g in clean),
            "return_with_errors": _mean(g["reward"] for g in dirty),
            "return_interacting": _mean(g["reward"] for g in inter),
            "false_positives_on_clean": sum(g["fp"] for g in clean),
            "recall_by_type": per_type,
            "miss_reasons": dict(sorted(misses.items())),
        }
    return out


def markdown_table(summary: dict) -> str:
    head = "| split | policy | n | return | P | R | F1 | steps | agent s | closed | return clean | return errors | FP on clean |\n"
    head += "|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    rows = []
    for v in summary.values():
        rows.append(
            f"| {v['split']} | {v['policy']} | {v['episodes']} | {v['return']} | {v['precision']} | {v['recall']} | "
            f"{v['f1']} | {v['steps']} | {v['agent_time_s']} | {v['closed_share']} | {v['return_clean']} | "
            f"{v['return_with_errors']} | {v['false_positives_on_clean']} |"
        )
    return head + "\n".join(rows) + "\n"


def miss_table(summary: dict) -> str:
    head = "| split | policy | recall by type | miss reasons |\n|---|---|---|---|\n"
    rows = []
    for v in summary.values():
        rt = ", ".join(f"{k}={val}" for k, val in v["recall_by_type"].items()) or "-"
        mr = ", ".join(f"{k}={val}" for k, val in v["miss_reasons"].items()) or "-"
        rows.append(f"| {v['split']} | {v['policy']} | {rt} | {mr} |")
    return head + "\n".join(rows) + "\n"
