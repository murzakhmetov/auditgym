"""Shared, published matcher between submitted findings and the answer key.

Normalization (applied to findings and to answer-key issues alike):
  * type: exact string from FINDING_TYPES;
  * affected_ids: exact strings (case and surrounding whitespace count), duplicates
    removed, compared as a set;
  * currency: exact string, no case folding and no trimming;
  * amount: |claimed_amount_minor - expected_amount_minor| <= tolerance_minor
    (the issue's own `tolerance_minor`, 0 when absent);
  * evidence: exact strings; a finding is supported when at least one acceptable
    evidence set of the issue is a subset of its evidence_ids. Extra evidence IDs
    that exist in the episode are allowed. An evidence ID that does not exist in the
    episode (when the episode's IDs are known) makes the whole finding unmatchable;
  * aliases: a document may be cited by doc_id or by its invoice_id/payment_id.
    In affected_ids a doc_id is mapped to its invoice_id/payment_id; in
    evidence_ids an invoice_id/payment_id is mapped to its doc_id.

A finding and an issue form a valid pair only when all five criteria hold.
Matching is one-to-one and maximizes the number of true positives (Kuhn's
augmenting-path algorithm). Tie-breaking among maximum matchings: findings are
processed in submission order and, for each finding, issues are tried in
ascending issue_id order. Every finding left unmatched is a false positive,
including exact repeats of a matched finding; every issue left unmatched is a
false negative.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

CRITERIA = ("type", "affected_ids", "currency", "amount", "evidence")


def normalize_ids(ids) -> tuple[str, ...]:
    return tuple(sorted({s for s in ids if isinstance(s, str) and s.strip()}))


@dataclass(frozen=True)
class NormFinding:
    index: int
    type: str
    ids: tuple[str, ...]
    amount: int
    currency: str
    evidence: frozenset
    unknown_evidence: bool = False


@dataclass(frozen=True)
class NormIssue:
    issue_id: str
    type: str
    ids: tuple[str, ...]
    amount: int
    currency: str
    tolerance: int
    evidence_sets: tuple


def normalize_finding(index: int, f: dict, aliases: dict | None = None, known_ids=None) -> NormFinding:
    doc_to_key = aliases or {}
    key_to_doc = {v: k for k, v in doc_to_key.items()}
    ids = normalize_ids(doc_to_key.get(s, s) for s in f["affected_ids"] if isinstance(s, str))
    evidence = normalize_ids(key_to_doc.get(s, s) for s in f["evidence_ids"] if isinstance(s, str))
    unknown = known_ids is not None and any(e not in known_ids and doc_to_key.get(e, e) not in known_ids for e in evidence)
    return NormFinding(
        index=index,
        type=f["type"],
        ids=ids,
        amount=int(f["claimed_amount_minor"]),
        currency=str(f["currency"]),
        evidence=frozenset(evidence),
        unknown_evidence=unknown,
    )


def normalize_issue(t: dict) -> NormIssue:
    return NormIssue(
        issue_id=t["issue_id"],
        type=t["type"],
        ids=normalize_ids(t["affected_ids"]),
        amount=int(t["expected_amount_minor"]),
        currency=str(t["currency"]),
        tolerance=int(t.get("tolerance_minor", 0)),
        evidence_sets=tuple(frozenset(normalize_ids(es)) for es in t["evidence_sets"]),
    )


def failed_criteria(nf: NormFinding, ni: NormIssue) -> list[str]:
    failed = []
    if nf.type != ni.type:
        failed.append("type")
    if nf.ids != ni.ids:
        failed.append("affected_ids")
    if nf.currency != ni.currency:
        failed.append("currency")
    if abs(nf.amount - ni.amount) > ni.tolerance:
        failed.append("amount")
    if nf.unknown_evidence or not any(es <= nf.evidence for es in ni.evidence_sets):
        failed.append("evidence")
    return failed


def metrics(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return {"precision": precision, "recall": recall, "f1": float(f1_fraction(tp, fp, fn))}


def f1_fraction(tp: int, fp: int, fn: int) -> Fraction:
    if tp + fp + fn == 0:
        return Fraction(1)
    return Fraction(2 * tp, 2 * tp + fp + fn)


@dataclass
class MatchResult:
    tp: int
    fp: int
    fn: int
    pairs: list = field(default_factory=list)  # (finding_index, issue_id)
    unmatched: list = field(default_factory=list)  # {"index", "reason", "closest_issue"}
    missed: list = field(default_factory=list)  # issue_id
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    f1_exact: Fraction = Fraction(0)

    def to_dict(self) -> dict:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "pairs": [{"finding_index": i, "issue_id": iid} for i, iid in self.pairs],
            "unmatched_findings": self.unmatched,
            "missed_issues": self.missed,
        }


def match(findings: list[dict], issues: list[dict], aliases: dict | None = None, known_ids=None) -> MatchResult:
    nfs = [normalize_finding(i, f, aliases, known_ids) for i, f in enumerate(findings)]
    nis = sorted((normalize_issue(t) for t in issues), key=lambda t: t.issue_id)
    failures = [[failed_criteria(nf, ni) for ni in nis] for nf in nfs]
    adj = [[j for j in range(len(nis)) if not failures[fi][j]] for fi in range(len(nfs))]
    owner = [-1] * len(nis)

    def augment(fi: int, seen: set) -> bool:
        for j in adj[fi]:
            if j in seen:
                continue
            seen.add(j)
            if owner[j] == -1 or augment(owner[j], seen):
                owner[j] = fi
                return True
        return False

    for fi in range(len(nfs)):
        augment(fi, set())

    matched_findings = {owner[j]: j for j in range(len(nis)) if owner[j] != -1}
    pairs = sorted((fi, nis[j].issue_id) for fi, j in matched_findings.items())
    unmatched = []
    for fi, nf in enumerate(nfs):
        if fi in matched_findings:
            continue
        if adj[fi]:
            reason, closest = "duplicate", nis[adj[fi][0]].issue_id
        elif not nis:
            reason, closest = "no_issue_in_key", None
        else:
            best = min(range(len(nis)), key=lambda j: (len(failures[fi][j]), [CRITERIA.index(c) for c in failures[fi][j]], j))
            reason, closest = failures[fi][best][0], nis[best].issue_id
        unmatched.append({"index": fi, "reason": reason, "closest_issue": closest})
    missed = [nis[j].issue_id for j in range(len(nis)) if owner[j] == -1]
    tp = len(pairs)
    fp = len(nfs) - tp
    fn = len(nis) - tp
    m = metrics(tp, fp, fn)
    return MatchResult(
        tp=tp,
        fp=fp,
        fn=fn,
        pairs=pairs,
        unmatched=unmatched,
        missed=missed,
        precision=m["precision"],
        recall=m["recall"],
        f1=m["f1"],
        f1_exact=f1_fraction(tp, fp, fn),
    )
