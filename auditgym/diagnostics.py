"""Host-side diagnostics computed per run and written to grades.jsonl only.

Nothing here is ever shown to a policy. Two measurements:

  * cited_unobserved: IDs a submitted finding cites (affected_ids and
    evidence_ids) that never appeared in any observation of the run. A correct
    citation the agent was never shown is the measurable sign of a leak (or of
    a lucky guess). Limits: a zero does not prove there was no leak, because an
    agent holding leaked IDs can fetch each with get_record/get_document and
    then every ID counts as observed; and made-up IDs that exist nowhere count
    as unobserved just like leaked ones. The oracle sees nothing, so its observed set is empty and
    every ID it cites is unobserved (share 1.0): that is the alarm's own
    positive control.
  * false-positive causes: why a finding that matched no issue was wrong.
    The distractor kind when the finding's IDs intersect a provenance
    distractor, otherwise "near_issue" when they intersect an issue's
    affected IDs, otherwise "unrelated".
"""

from __future__ import annotations

from .matcher import normalize_finding

NEAR_ISSUE = "near_issue"
UNRELATED = "unrelated"


def observed_with_refs(obs: dict) -> set:
    """IDs shown by one observation: row, doc, invoice and payment IDs, the IDs
    inside invoice_refs, and fx IDs (date:source:target) of returned fx rows."""
    out = set()
    result = (obs or {}).get("result") or {}
    if not isinstance(result, dict):
        return out
    recs = list(result.get("rows") or [])
    for k in ("record", "document"):
        if result.get(k):
            recs.append(result[k])
    for r in recs:
        if not isinstance(r, dict):
            continue
        for f in ("row_id", "doc_id", "invoice_id", "payment_id"):
            if isinstance(r.get(f), str):
                out.add(r[f])
        refs = r.get("invoice_refs")
        if isinstance(refs, list):
            out.update(x for x in refs if isinstance(x, str))
        if "date" in r and "source_currency" in r and "target_currency" in r:
            out.add(f"{r['date']}:{r['source_currency']}:{r['target_currency']}")
    return out


def observed_closure(observations: list | None, aliases: dict | None) -> set:
    """Union over all observations, closed under doc_id -> invoice/payment_id (one direction only)."""
    seen = set()
    for obs in observations or []:
        seen |= observed_with_refs(obs)
    aliases = aliases or {}
    for s in list(seen):
        if s in aliases:  # a shown doc_id also shows its invoice/payment id (never the reverse: it would hide leaks)
            seen.add(aliases[s])
    return seen


def cited_ids(findings: list | None) -> set:
    out = set()
    for f in findings or []:
        for k in ("affected_ids", "evidence_ids"):
            for s in f.get(k) or []:
                if isinstance(s, str) and s.strip():
                    out.add(s.strip())
    return out


def citation_report(findings: list | None, observations: list | None, aliases: dict | None) -> dict:
    """observations=None means nothing was observed (the oracle)."""
    seen = observed_closure(observations, aliases)
    cited = cited_ids(findings)
    missing = sorted(cited - seen)
    return {"n_cited": len(cited), "n_cited_unobserved": len(missing), "cited_unobserved": missing}


def fp_causes(findings: list | None, unmatched: list, truth: dict, provenance: dict | None) -> list:
    """One record per unmatched finding: {"finding_index", "cause"}."""
    aliases = (truth or {}).get("id_aliases", {})
    issue_ids = set()
    for t in (truth or {}).get("issues", []):
        issue_ids |= set(t["affected_ids"])
    distractors = (provenance or {}).get("distractors") or []
    out = []
    for u in unmatched or []:
        idx = u["index"]
        nf = normalize_finding(idx, findings[idx], aliases)
        ids = set(nf.ids)
        kinds = sorted({d["kind"] for d in distractors if ids & {x for x in d["ids"] if x}})
        if kinds:
            cause = kinds[0]
        elif ids & issue_ids:
            cause = NEAR_ISSUE
        else:
            cause = UNRELATED
        out.append({"finding_index": idx, "cause": cause})
    return out


def run_diagnostics(grade: dict, truth: dict, provenance: dict | None, submission: list | None,
                    observations: list | None) -> dict:
    """Extra grade keys. submission is None when no valid submission exists."""
    findings = submission or []
    d = citation_report(findings, observations, (truth or {}).get("id_aliases", {}))
    d["fp_details"] = fp_causes(findings, grade.get("unmatched_findings") or [], truth, provenance) if findings else []
    return d
