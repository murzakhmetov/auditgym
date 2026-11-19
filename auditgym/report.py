"""Aggregate grades into diagnostics: P, R (macro and micro), F1, return, soft
return, steps, agent time, share of fully closed episodes, per-type recall,
miss reasons, false-positive causes and the unobserved-citation alarm."""

from __future__ import annotations

from collections import Counter, defaultdict

from . import FINDING_TYPES


def _mean(xs):
    xs = list(xs)
    return round(sum(xs) / len(xs), 4) if xs else None


def _ratio(num, den):
    return round(num / den, 4) if den else None


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
        fp_causes = Counter(d["cause"] for g in gs for d in g.get("fp_details", []))
        firsts = [i["first_full_evidence_step"] for g in gs for i in g.get("issues", [])
                  if i.get("first_full_evidence_step") is not None]
        n_issues = sum(len(g.get("issues", [])) for g in gs)
        seen_not_flagged = sum(1 for g in gs for i in g.get("issues", [])
                               if not i["found"] and i.get("first_full_evidence_step") is not None
                               and i["miss_reason"] == "not_flagged")
        n_cited = sum(g.get("n_cited", 0) for g in gs)
        n_unobs = sum(g.get("n_cited_unobserved", 0) for g in gs)
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
            "soft_f1": _mean(g.get("soft_f1", 0.0) for g in gs),
            "tp": sum(g["tp"] for g in gs),
            "fp": sum(g["fp"] for g in gs),
            "fn": sum(g["fn"] for g in gs),
            "micro_precision": _ratio(sum(g["tp"] for g in gs), sum(g["tp"] + g["fp"] for g in gs)),
            "micro_recall": _ratio(sum(g["tp"] for g in gs), sum(g["tp"] + g["fn"] for g in gs)),
            "n_cited": n_cited,
            "n_cited_unobserved": n_unobs,
            "unobserved_citation_share": _ratio(n_unobs, n_cited),
            "fp_causes": dict(sorted(fp_causes.items())),
            "mean_first_full_evidence_step": _mean(firsts),
            "issues_total": n_issues,
            "issues_seen_not_flagged": seen_not_flagged,
            "seen_not_flagged_share": _ratio(seen_not_flagged, n_issues),
            "recall_by_type": per_type,
            "miss_reasons": dict(sorted(misses.items())),
        }
    return out


MACRO_NOTE = ("P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer "
              "scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) "
              "and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. "
              "soft return is the experimental reward (see the reward table).")


def markdown_table(summary: dict) -> str:
    head = ("| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed "
            "| return clean | return errors | FP on clean | unobserved citations |\n")
    head += "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    rows = []
    for v in summary.values():
        rows.append(
            f"| {v['split']} | {v['policy']} | {v['episodes']} | {v['return']} | {v['return_experimental']} | "
            f"{v['precision']} | {v['recall']} | {v['micro_precision']} | {v['micro_recall']} | {v['f1']} | {v['soft_f1']} | "
            f"{v['steps']} | {v['agent_time_s']} | {v['closed_share']} | {v['return_clean']} | "
            f"{v['return_with_errors']} | {v['false_positives_on_clean']} | {v['unobserved_citation_share']} |"
        )
    has_clean = any(v.get("return_clean") is not None for v in summary.values())
    return head + "\n".join(rows) + "\n" + (("\n" + MACRO_NOTE + "\n") if has_clean else "")


def reward_table(summary: dict) -> str:
    """Common vs experimental reward per policy and split."""
    head = ("| split | policy | common return | experimental (soft) return | difference | F1 | soft F1 |\n"
            "|---|---|---|---|---|---|---|\n")
    rows = []
    for v in summary.values():
        a, b = v["return"], v["return_experimental"]
        diff = round(b - a, 4) if a is not None and b is not None else None
        rows.append(f"| {v['split']} | {v['policy']} | {a} | {b} | {diff} | {v['f1']} | {v['soft_f1']} |")
    return head + "\n".join(rows) + "\n"


def fp_table(summary: dict) -> str:
    """False-positive causes, first-full-evidence step and seen-but-not-flagged share per policy."""
    head = ("| split | policy | FP | FP causes | mean first full evidence step | issues seen, not flagged "
            "| unobserved citations (n / cited) |\n|---|---|---|---|---|---|---|\n")
    rows = []
    for v in summary.values():
        causes = ", ".join(f"{k}={n}" for k, n in v["fp_causes"].items()) or "-"
        first = v["mean_first_full_evidence_step"]
        observes = first is not None or v["policy"] != "oracle"
        seen = (f"{v['issues_seen_not_flagged']} / {v['issues_total']} ({v['seen_not_flagged_share']})"
                if v["issues_total"] and observes else "-")
        rows.append(f"| {v['split']} | {v['policy']} | {v['fp']} | {causes} | {first if first is not None else '-'} | "
                    f"{seen} | {v['n_cited_unobserved']} / {v['n_cited']} |")
    return head + "\n".join(rows) + "\n"


def miss_table(summary: dict) -> str:
    head = "| split | policy | recall by type | miss reasons |\n|---|---|---|---|\n"
    rows = []
    for v in summary.values():
        rt = ", ".join(f"{k}={val}" for k, val in v["recall_by_type"].items()) or "-"
        mr = ", ".join(f"{k}={val}" for k, val in v["miss_reasons"].items()) or "-"
        rows.append(f"| {v['split']} | {v['policy']} | {rt} | {mr} |")
    out = head + "\n".join(rows) + "\n"
    # the two diagnostics tables ride along, so every caller of miss_table (run, check) emits them
    return (out + "\n**Common vs experimental reward**\n\n" + reward_table(summary)
            + "\n**False positives, evidence timing, unobserved citations**\n\n" + fp_table(summary))
