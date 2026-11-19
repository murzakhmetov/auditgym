"""Build viewer/index.html: one self-contained offline file (no CDN, no server).

The page is a human demo of the open train/dev episodes. It shows grader-side
information (answer key, matches, failure analysis) explicitly labelled as a
post-run grader view; it is never shown to an agent.

Bundle schema (window.AUDITGYM_DATA):
{
  "version": str, "built_from": str,
  "episodes": [{
      "split", "name", "episode_id", "manifest", "policy",
      "ledger": [...], "invoices": [...], "payments": [...], "fx": [...],
      "truth": {"issues": [...], "id_aliases": {...}},          # grader view
      "provenance": {"injections": [...], "distractors": [...], "ops": [...], "resolved_config": {...}}
  }],
  "runs": [{
      "run_id", "split", "episode_name", "episode_id", "policy", "reward", "reward_experimental",
      "tp", "fp", "fn", "precision", "recall", "f1", "inspection_steps", "agent_time_s", "status", "closed",
      "isolated" (agent in its own process), "mode",
      "pairs": [{"finding_index", "issue_id"}], "unmatched_findings": [{"index", "reason", "closest_issue"}],
      "missed_issues": [...], "issues": [{"issue_id", "type", "found", "first_full_evidence_step", "miss_reason"}],
      "n_cited", "n_cited_unobserved", "cited_unobserved", "fp_details": [{"finding_index", "cause"}],
      "submission": [findings] | null,
      "steps": [{"step", "action", "error", "ids", "n_rows", "value", "remaining_steps"}] | null   # null for the oracle
  }],
  "summary": {"<split>/<policy>": {...report.summarize fields...}},
  "check": {"ok", "counts", "elapsed_s", "summary", "section_seconds", "sections": {section: [{"check", "ok", "skipped"}]}} | null,
  "rubric": [{"label", "n", "name", "weight", "sections": [section keys]}]   # check.RUBRIC, the jury rubric lines
  "budget": {"split", "episodes", "budgets": [int], "f1": {policy: [float]}, "return": {policy: [float]}} | null
}

The graph engine (forcegraph.js) is inlined into the page at build time, so the
output stays a single file with no external scripts.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .. import __version__
from .. import io as aio
from ..report import summarize
from ..runner import observed_ids, run_one
from ..splits import EPISODES_DIR, ROOT, load_split_episodes

TEMPLATE = Path(__file__).with_name("template.html")
ENGINE = Path(__file__).with_name("forcegraph.js")
PLACEHOLDER = "/*__AUDITGYM_DATA__*/null"
ENGINE_PLACEHOLDER = "/*__FORCEGRAPH_JS__*/"
POLICIES = ("random", "recon", "flag_all", "oracle", "auditor")
BUDGETS = (10, 20, 30, 50, 100)
BUDGET_POLICIES = ("auditor", "recon")


def _flatten_action(a) -> dict:
    """Same alias flattening as env.step and runner.run_one: {"action", "args": {...}} becomes one flat dict."""
    if isinstance(a, dict) and set(a) == {"action", "args"} and isinstance(a["args"], dict) and "action" not in a["args"]:
        return {"action": a["action"], **a["args"]}
    return a if isinstance(a, dict) else {}


def _compact_steps(traj: list) -> list:
    out = []
    for rec in traj:
        obs = rec["observation"]
        res = obs.get("result") or {}
        err = obs.get("error")
        out.append({
            "step": rec["step"],
            "action": _flatten_action(rec["action"]) or rec["action"],
            "error": err["code"] if err else None,
            "ids": sorted(observed_ids(obs)),
            "n_rows": len(res.get("rows") or []) if isinstance(res, dict) else 0,
            "value": res.get("value") if isinstance(res, dict) else None,
            "remaining_steps": obs.get("remaining_steps"),
        })
    return out


def _budget_sweep(episodes: list) -> dict | None:
    """Mean F1 and return on dev when the step budget is cut (in-process, eval mode)."""
    dev = [(split, ep) for split, _, ep in episodes if split == "dev"]
    if not dev:
        return None
    f1: dict = {}
    ret: dict = {}
    for pol in BUDGET_POLICIES:
        f1[pol], ret[pol] = [], []
        for budget in BUDGETS:
            grades = [run_one(ep, pol, split=split, mode="eval", isolated=False, max_steps=budget)[1] for split, ep in dev]
            f1[pol].append(round(sum(g["f1"] for g in grades) / len(grades), 4))
            ret[pol].append(round(sum(g["reward"] for g in grades) / len(grades), 4))
    return {"split": "dev", "episodes": len(dev), "budgets": list(BUDGETS), "f1": f1, "return": ret}


def _rubric() -> list:
    """The jury rubric lines exactly as check.py groups the sections for report.md."""
    from ..check import RUBRIC

    out = []
    for label, sections in RUBRIC:
        m = re.match(r"^(\d+)\.\s*(.*?)\s*\((\d+)\)\s*$", label)
        out.append({"label": label, "n": int(m.group(1)) if m else len(out) + 1, "name": m.group(2) if m else label,
                    "weight": int(m.group(3)) if m else None, "sections": list(sections)})
    return out


def make_bundle() -> dict:
    episodes = list(load_split_episodes(("train", "dev"), EPISODES_DIR))
    eps_out, runs, grades = [], [], []
    for split, name, ep in episodes:
        eps_out.append({
            "split": split,
            "name": name,
            "episode_id": ep.episode_id,
            "manifest": ep.manifest,
            "policy": ep.policy,
            "ledger": ep.ledger,
            "invoices": ep.invoices,
            "payments": ep.payments,
            "fx": ep.fx,
            "truth": {"issues": ep.truth.get("issues", []), "id_aliases": ep.truth.get("id_aliases", {})},
            "provenance": {k: ep.provenance.get(k) for k in ("injections", "distractors", "ops", "resolved_config")},
        })
        for pol in POLICIES:
            traj, g = run_one(ep, pol, split=split, mode="eval", isolated=True)
            g["episode_name"] = name
            grades.append(g)
            submission = None
            if traj:
                for rec in traj:
                    a = _flatten_action(rec.get("action"))
                    f = a.get("findings") if a.get("action") == "submit" else None
                    if isinstance(f, dict) and isinstance(f.get("findings"), list) and g.get("status") == "submitted":
                        submission = f["findings"]
            elif pol == "oracle":
                from ..policies.oracle import OraclePolicy

                submission = OraclePolicy(ep.truth).findings()
            runs.append({
                "run_id": g["run_id"], "split": split, "episode_name": name, "episode_id": ep.episode_id, "policy": pol,
                **{k: g.get(k) for k in ("reward", "reward_experimental", "tp", "fp", "fn", "precision", "recall", "f1",
                                         "inspection_steps", "agent_time_s", "status", "closed", "isolated", "mode", "pairs",
                                         "unmatched_findings", "missed_issues", "issues",
                                         "n_cited", "n_cited_unobserved", "cited_unobserved", "fp_details")},
                "submission": submission,
                "steps": _compact_steps(traj) if traj else None,
            })
    check = None
    rep = ROOT / "runs" / "check" / "report.json"
    if rep.exists():
        r = aio.read_json(rep)
        check = {"ok": r.get("ok"), "counts": r.get("counts"), "elapsed_s": r.get("elapsed_s"),
                 "summary": r.get("summary"), "section_seconds": r.get("section_seconds"),
                 # named checks per section (the detail text is kept only for a failing or skipped check)
                 "sections": {sec: [{"check": c["check"], "ok": bool(c["ok"]), "skipped": bool(c.get("skipped")),
                                     **({} if c["ok"] and not c.get("skipped") else {"detail": str(c.get("detail", ""))[:300]})} for c in cs]
                              for sec, cs in (r.get("sections") or {}).items()}}
    return {
        "version": __version__,
        "built_from": "episodes/train, episodes/dev, runs/check/report.json",
        "episodes": eps_out,
        "runs": runs,
        "summary": summarize(grades),
        "check": check,
        "rubric": _rubric(),
        "budget": _budget_sweep(episodes),
    }


def build(out: Path, template: Path = TEMPLATE, bundle_out: Path | None = None) -> Path:
    bundle = make_bundle()
    data = json.dumps(bundle, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    if bundle_out:
        aio.write_text(Path(bundle_out), json.dumps(bundle, ensure_ascii=False, indent=1))
    html = template.read_text(encoding="utf-8")
    if PLACEHOLDER not in html:
        raise ValueError("template.html lacks the data placeholder")
    if ENGINE_PLACEHOLDER not in html:
        raise ValueError("template.html lacks the graph engine placeholder")
    engine = ENGINE.read_text(encoding="utf-8")
    if "</script" in engine.lower():
        raise ValueError("forcegraph.js must not contain a closing script tag")
    html = html.replace(ENGINE_PLACEHOLDER, engine, 1)
    html = html.replace(PLACEHOLDER, data, 1)
    out = Path(out)
    aio.write_text(out, html)
    return out


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "viewer" / "index.html"
    print(build(target, bundle_out=ROOT / "viewer" / "sample_bundle.json"))
