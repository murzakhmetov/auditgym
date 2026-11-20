"""Grader-side attack battery and replay of recorded actions, used by `check`.

Everything here is offline and deterministic. Nothing is shown to an agent.

reward_battery(ep)   one oracle finding is changed at a time; each probe states
                     the published rule it exercises (never more than 30
                     findings or 10 evidence IDs, the schema limits). It also
                     adds each plausible distractor accusation to the oracle
                     answer, one kind at a time.
clean_battery(ep)    the same distractor accusations on a clean ledger.
distractor_attacks   for every distractor in the grader's provenance, a false
                     finding built from the real records by the published
                     rules (base currency, posted base amount, the evidence
                     the rules ask for). It is false because the records are
                     legitimate, not because it is malformed: the same
                     constructors applied to the records of a real issue are
                     true positives (tests/test_check_battery.py).
replay_records(...)  feeds the recorded actions of each agent run into a fresh
                     AuditEnv and requires JSON-equal observations and the same
                     terminal reward (the case's "identical seeds, config,
                     version and actions reproduce transitions and rewards").
matched_claims(...)  which issues the auditor matched, with the claimed amounts.
"""

from __future__ import annotations

import json
from fractions import Fraction

from . import FINDING_TYPES
from .env import AuditEnv
from .grader import Grader
from .matcher import match
from .money import convert_minor, exponent
from .policies.oracle import OraclePolicy
from .reward import clip
from .schemas import MAX_EVIDENCE_IDS, MAX_FINDINGS
from .task import TOLERANCE_MINOR
from .timeutil import local_date, parse_ts

LADDER = (7, -7, 50, -50)


def _grade(ep, findings, steps: int = 0) -> dict:
    return Grader(ep.truth, ep.episode_id).grade({"episode_id": ep.episode_id, "findings": findings}, steps, "submitted")


def _real_doc_ids(ep) -> list:
    return sorted(d["doc_id"] for t in (ep.invoices, ep.payments) for d in t)


def _used_ids(ep) -> set:
    used = set()
    for t in ep.truth["issues"]:
        used.update(t["affected_ids"])
        for es in t["evidence_sets"]:
            used.update(es)
    return used


def _index(ep) -> dict:
    """{public ID: record} for every invoice and payment, also under its doc_id."""
    idx = {}
    for table, key in ((ep.invoices, "invoice_id"), (ep.payments, "payment_id")):
        for d in table:
            idx[d[key]] = d
            idx[d["doc_id"]] = d
    return idx


def _amount(d: dict) -> int:
    return d["total_minor"] if "total_minor" in d else d["amount_minor"]


def _public_id(d: dict) -> str:
    return d["invoice_id"] if "invoice_id" in d else d["payment_id"]


def _own_rows(ep, d: dict) -> list:
    """Ledger rows that belong to the document itself: an invoice's own journal, every row of a payment."""
    if "invoice_id" in d:
        return [r for r in ep.ledger if r["invoice_id"] == d["invoice_id"] and r["payment_id"] is None]
    return [r for r in ep.ledger if r["payment_id"] == d["payment_id"]]


def _key_row(ep, d: dict):
    """The posting row the published rules measure: receivable/payable for an invoice, bank for a payment."""
    accounts = ("1100", "2000") if "invoice_id" in d else ("1000",)
    return next((r for r in _own_rows(ep, d) if r["account"] in accounts), None)


def _row_amount(row, fallback: int) -> int:
    return max(row["debit_minor"], row["credit_minor"]) if row else fallback


def _posted_base(ep, d: dict) -> int:
    """The base-currency amount posted on the document's key row, else its own amount."""
    return _row_amount(_key_row(ep, d), _amount(d))


def _unallocated_row(ep, pay: dict):
    """The payment's 2900 row when it has one, else its bank row."""
    return next((r for r in _own_rows(ep, pay) if r["account"] == "2900"), None) or _key_row(ep, pay)


def _cite(docs: list, rows: list, extra: tuple = ()) -> list:
    ids = [d["doc_id"] for d in docs] + [r["row_id"] for r in rows if r] + list(extra)
    return list(dict.fromkeys(ids))[:MAX_EVIDENCE_IDS]


def _accusation(ep, ftype: str, docs: list, amount: int, evidence: list, why: str) -> dict:
    return {"type": ftype, "affected_ids": [_public_id(d) for d in docs], "claimed_amount_minor": max(0, int(amount)),
            "currency": ep.manifest["base_currency"], "evidence_ids": evidence, "explanation": why}


def duplicate_attack(ep, first: dict, second: dict, why: str = "two invoices, same supplier and amount") -> dict:
    """Published duplicate_invoice shape: both copies, base amount of one posting, both documents and both key rows."""
    rows = [_key_row(ep, first), _key_row(ep, second)]
    return _accusation(ep, "duplicate_invoice", [first, second], _posted_base(ep, second), _cite([first, second], rows), why)


def unallocated_attack(ep, pay: dict, inv: dict, why: str = "receipt does not relieve the invoice") -> dict:
    """Published unallocated_payment shape: payment and invoice, the 2900 amount, both documents, the 2900 row, the bank row for a foreign-currency invoice and every receivable/payable row of the invoice."""
    row = _unallocated_row(ep, pay)
    acct = "1100" if inv["kind"] == "sales" else "2000"
    inv_rows = [r for r in ep.ledger if r["invoice_id"] == inv["invoice_id"] and r["account"] == acct]
    bank = [r for r in _own_rows(ep, pay) if r["account"] == "1000"] if inv["currency"] != ep.manifest["base_currency"] else []
    return _accusation(ep, "unallocated_payment", [pay, inv], _row_amount(row, _amount(pay)), _cite([pay, inv], [row] + bank + inv_rows), why)


def period_attack(ep, doc: dict, why: str = "document sits at the period boundary") -> dict:
    """Published wrong_period shape: the document, its key row amount, the document and that row."""
    return _accusation(ep, "wrong_period", [doc], _posted_base(ep, doc), _cite([doc], [_key_row(ep, doc)]), why)


def _fx_dates(ep, ccy: str) -> list:
    return sorted(r["date"] for r in ep.fx if r["source_currency"] == ccy and r["target_currency"] == ep.manifest["base_currency"])


def _fx_rate(ep, ccy: str, day: str) -> str:
    return next(r["rate"] for r in ep.fx if r["date"] == day and r["source_currency"] == ccy
                and r["target_currency"] == ep.manifest["base_currency"])


def policy_fx_date(ep, doc: dict):
    """Date of the policy rate (latest published on or before the document's company-local date), or None."""
    if doc["currency"] == ep.manifest["base_currency"]:
        return None
    local = local_date(parse_ts(doc.get("issued_at") or doc["timestamp"]), ep.policy["timezone"]).isoformat()
    return max((d for d in _fx_dates(ep, doc["currency"]) if d <= local), default=None)


def _base_at(ep, doc: dict, day: str) -> int:
    exps = ep.policy["currency_exponents"]
    return convert_minor(_amount(doc), _fx_rate(ep, doc["currency"], day), exponent(doc["currency"], exps),
                         exponent(ep.manifest["base_currency"], exps), ep.policy["rounding"]["mode"])


def policy_base(ep, doc: dict):
    """Base amount at the policy rate, or None for a base-currency document."""
    day = policy_fx_date(ep, doc)
    return None if day is None else _base_at(ep, doc, day)


def fx_attack(ep, doc: dict, believed_base: int, why: str = "conversion date is near midnight or a weekend"):
    """Published wrong_fx_rate shape: the document, |posted - believed base|, the document, its key row and the
    fx record of the policy date. None for a base-currency document."""
    day = policy_fx_date(ep, doc)
    if day is None:
        return None
    record = f"{day}:{doc['currency']}:{ep.manifest['base_currency']}"
    return _accusation(ep, "wrong_fx_rate", [doc], abs(_posted_base(ep, doc) - believed_base),
                       _cite([doc], [_key_row(ep, doc)], (record,)), why)


def _neighbour_fx_attack(ep, doc: dict):
    """An agent who doubts the rate date believes the neighbouring published date's rate was due."""
    day = policy_fx_date(ep, doc)
    if day is None:
        return None
    dates = _fx_dates(ep, doc["currency"])
    i = dates.index(day)
    other = dates[i - 1] if i else (dates[i + 1] if i + 1 < len(dates) else None)
    return None if other is None else fx_attack(ep, doc, _base_at(ep, doc, other))


def _attack_for(ep, kind: str, docs: list):
    """The most plausible false accusation for one distractor, or None when its records are not all there.
    A payment in the distractor is the document at the boundary or near midnight, so it is the one accused."""
    inv = [d for d in docs if "invoice_id" in d]
    pay = [d for d in docs if "payment_id" in d]
    subject = (pay or inv)[:1]
    if kind in ("legit_repeat", "recurring", "twin_legit_repeat") and len(inv) >= 2:
        return duplicate_attack(ep, inv[0], inv[1])
    if kind in ("split_payment", "multi_invoice_payment", "underpayment", "overpayment_refund") and inv and pay:
        return unallocated_attack(ep, pay[0], inv[0])
    if kind == "null_ref_receipt" and pay:
        row = _unallocated_row(ep, pay[0])
        return _accusation(ep, "unallocated_payment", [pay[0]], _row_amount(row, _amount(pay[0])), _cite([pay[0]], [row]),
                           "receipt names no invoice")
    if kind == "boundary_doc" and subject:
        return period_attack(ep, subject[0])
    if kind in ("midnight_fx", "weekend_fx") and subject:
        return _neighbour_fx_attack(ep, subject[0])
    return None


def distractor_attacks(ep) -> dict:
    """{distractor kind: [false finding, ...]}, one per distractor in the provenance whose records can be found."""
    idx = _index(ep)
    out: dict = {}
    for dis in (ep.provenance or {}).get("distractors", []):
        f = _attack_for(ep, dis["kind"], [idx[i] for i in dis["ids"] if i in idx])
        if f:
            out.setdefault(dis["kind"], []).append(f)
    return out


def _decoy(f: dict, **changes) -> dict:
    """An answer-key issue that the accusation satisfies exactly, with some fields changed."""
    issue = {"issue_id": "decoy", "type": f["type"], "affected_ids": list(f["affected_ids"]),
             "expected_amount_minor": f["claimed_amount_minor"], "currency": f["currency"],
             "tolerance_minor": TOLERANCE_MINOR, "evidence_sets": [list(f["evidence_ids"])]}
    return dict(issue, **changes)


def matcher_problems(ep, f: dict) -> list:
    """The accusation must match a key that states exactly its claim and no key that differs in one criterion.
    A matcher that ignores any single criterion fails here, whatever the episode's own answer key holds."""
    aliases = ep.truth.get("id_aliases")
    other = next((i for i in _index(ep) if i not in f["affected_ids"]), "OTHER-RECORD")
    variants = {
        "exact": ({}, 1),
        "other type": ({"type": next(t for t in FINDING_TYPES if t != f["type"])}, 0),
        "other IDs": ({"affected_ids": [other] + f["affected_ids"][1:]}, 0),
        "other currency": ({"currency": "XXX"}, 0),
        "amount off by 3 tolerances": ({"expected_amount_minor": f["claimed_amount_minor"] + 3 * TOLERANCE_MINOR}, 0),
        "uncited evidence": ({"evidence_sets": [list(f["evidence_ids"]) + ["NOT-CITED"]]}, 0),
    }
    return [f"decoy '{name}' gives tp={got}" for name, (changes, want) in variants.items()
            if (got := match([f], [_decoy(f, **changes)], aliases).tp) != want]


def _is_injected(ep, f: dict) -> bool:
    """True when the accusation names only records of one injected error (provenance), so matching it is correct."""
    return any(set(f["affected_ids"]) <= set(inj.get("targets", {}).values())
               for inj in (ep.provenance or {}).get("injections", []))


def _distractor_lines(ep, oracle: list) -> list:
    """One line per distractor kind. Each accusation graded alone against the full answer key is not a true
    positive (unless it names the records of an injected error); added to the oracle answer it adds exactly one
    false positive and lowers the reward; and each matcher criterion rejects it (matcher_problems)."""
    name, n = ep.episode_id, len(oracle)
    alone = _grade(ep, oracle)["reward"]
    out = []
    for kind, attacks in distractor_attacks(ep).items():
        label = f"{name}: {len(attacks)} {kind} accusation(s) each cost exactly one false positive and match no answer-key issue"
        bad, checked = [], 0
        for f in attacks:
            if _is_injected(ep, f):
                continue
            checked += 1
            if match([f], ep.truth["issues"], ep.truth.get("id_aliases")).tp:
                bad.append(f"{f['affected_ids']}: matches an issue of the answer key")
            elif n + 1 <= MAX_FINDINGS:
                res = _grade(ep, oracle + [f])
                if not (res["tp"] == n and res["fp"] == 1 and res["reward"] < alone):
                    bad.append(f"{f['affected_ids']}: tp={res['tp']} fp={res['fp']} reward={res['reward']}")
            bad.extend(f"{f['affected_ids']}: {p}" for p in matcher_problems(ep, f))
        if not checked:
            out.append((label, True, "every accusation names the records of an injected error", True))
        else:
            out.append((label, not bad, "; ".join(bad[:3]) or f"{checked} checked, answer alone {alone}"))
    if not out:
        out.append((f"{name}: distractor accusations", True, "no distractors in this episode", True))
    return out


def reward_battery(ep) -> list:
    """[(check name, ok, detail)] for an episode with at least one issue."""
    name = ep.episode_id
    oracle = OraclePolicy(ep.truth).findings()
    n = len(oracle)
    f0 = oracle[0]
    out = []

    def add(label, ok, detail=""):
        out.append((f"{name}: {label}", bool(ok), detail))

    # Type shotgun: the same finding under every other type.
    others = [t for t in FINDING_TYPES if t != f0["type"]]
    res = _grade(ep, oracle + [dict(f0, type=t) for t in others])
    add(f"type shotgun (copies under {len(others)} other types) costs exactly {len(others)} false positives",
        res["tp"] == n and res["fp"] == len(others) and res["reward"] < 1.0, f"tp={res['tp']} fp={res['fp']}")

    # Amount ladder: neighbouring amounts, de-duplicated and clamped at 0.
    amounts = []
    for d in LADDER:
        a = max(0, f0["claimed_amount_minor"] + d)
        if a != f0["claimed_amount_minor"] and a not in amounts:
            amounts.append(a)
    res = _grade(ep, oracle + [dict(f0, claimed_amount_minor=a) for a in amounts])
    add(f"amount ladder ({len(amounts)} neighbouring amounts) costs exactly {len(amounts)} false positives",
        res["tp"] == n and res["fp"] == len(amounts) and res["reward"] < 1.0, f"tp={res['tp']} fp={res['fp']}")

    # Junk: pad the oracle answer with unmatched findings up to the 30-finding cap.
    j = MAX_FINDINGS - n
    junk = [{"type": FINDING_TYPES[i % len(FINDING_TYPES)], "affected_ids": [f"JUNK-{i}"], "claimed_amount_minor": 1 + i,
             "currency": f0["currency"], "evidence_ids": [f"JUNK-DOC-{i}"], "explanation": "x"} for i in range(j)]
    res = _grade(ep, oracle + junk)
    exact = float(clip(2 * Fraction(2 * n, 2 * n + j) - 1))
    add(f"{j} junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone",
        len(oracle + junk) == MAX_FINDINGS and res["tp"] == n and res["fp"] == j and res["reward"] == exact
        and res["reward"] < _grade(ep, oracle)["reward"], f"reward={res['reward']} expected={exact}")

    # Evidence stuffing: padding the evidence with other real documents is allowed and changes nothing.
    pad = [d for d in _real_doc_ids(ep) if d not in f0["evidence_ids"]]
    stuffed = list(f0["evidence_ids"]) + pad[:max(0, MAX_EVIDENCE_IDS - len(f0["evidence_ids"]))]
    res = _grade(ep, [dict(f0, evidence_ids=stuffed)] + oracle[1:])
    add(f"evidence padded to {len(stuffed)} IDs stays a true positive (published rule)",
        len(stuffed) <= MAX_EVIDENCE_IDS and res["tp"] == n and res["fp"] == 0 and res["reward"] == _grade(ep, oracle)["reward"],
        f"tp={res['tp']} fp={res['fp']}")

    # Right amount, wrong IDs: an unrelated but real invoice.
    used = _used_ids(ep)
    unrelated = [d["invoice_id"] for d in ep.invoices if d["invoice_id"] not in used and d["doc_id"] not in used]
    if unrelated:
        res = _grade(ep, [dict(f0, affected_ids=[unrelated[0]])] + oracle[1:])
        add("right amount with the ID of an unrelated real invoice is not a true positive",
            res["tp"] == n - 1 and res["fp"] == 1, f"tp={res['tp']} fp={res['fp']}")
    else:
        out.append((f"{name}: right amount with the ID of an unrelated real invoice is not a true positive",
                    True, "no unrelated invoice in this episode", True))
    out.extend(_distractor_lines(ep, oracle))
    return out


def clean_battery(ep) -> list:
    """One line per distractor kind on a clean ledger. The empty key makes any finding score -1, which alone says
    nothing about the accusation. So the line also requires that the accusation satisfies a key stating exactly its
    claim and no key that differs in one criterion (matcher_problems). That the constructors build well-formed
    accusations (the same constructors on the records of real issues are true positives) is pinned by
    tests/test_check_battery.py."""
    name = ep.episode_id
    silent = _grade(ep, [])["reward"]
    out = []
    for kind, attacks in distractor_attacks(ep).items():
        bad = []
        for f in attacks:
            res = _grade(ep, [f])
            if not (res["tp"] == 0 and res["fp"] == 1 and res["reward"] == -1.0 and res["reward"] < silent):
                bad.append(f"{f['affected_ids']}: fp={res['fp']} reward={res['reward']}")
            bad.extend(f"{f['affected_ids']}: {p}" for p in matcher_problems(ep, f))
        out.append((f"{name}: {len(attacks)} {kind} accusation(s) each score -1, below silence, and satisfy no key but their own",
                    not bad, "; ".join(bad[:3]) or f"silence {silent}"))
    if not out:
        out.append((f"{name}: distractor accusations", True, "no distractors in this episode", True))
    return out


def matched_claims(traj: list, grade: dict) -> frozenset:
    """{(issue_id, claimed amount)} for the issues a run matched (needs the run's own submit action)."""
    findings = []
    for rec in traj or []:
        a = rec.get("action")
        if isinstance(a, dict) and a.get("action") == "submit" and isinstance(a.get("findings"), dict):
            findings = a["findings"].get("findings") or []
    return frozenset((p["issue_id"], findings[p["finding_index"]]["claimed_amount_minor"]) for p in grade.get("pairs", []))


def _j(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def infer_mode(first_obs: dict) -> str:
    text = ((first_obs.get("task") or {}).get("reward") or {}).get("returned_to_policy", "")
    return "train" if text.startswith("terminal reward") else "eval"


def replay_run(records: list, episode) -> list:
    """Replay one recorded run (list of trajectory records, step order). Returns a list of problems (empty = identical)."""
    first = records[0]["observation"]
    mode = infer_mode(first)
    # Replay with the time limit the run published, on a frozen clock: the reset observation (which states the
    # limit) must match byte for byte, and wall-clock time can never truncate a replay.
    limit = (((first.get("task") or {}).get("limits") or {}).get("time_limit_s")) or 60
    env = AuditEnv(mode=mode, max_steps=int(first["remaining_steps"]), time_limit_s=limit, clock=lambda: 0.0)
    obs, _info = env.reset(config={"episode": episode})
    problems = []
    if _j(obs) != _j(first):
        problems.append("reset observation differs")
    last = records[0]
    for rec in records[1:]:
        last = rec
        obs, reward, terminated, truncated, _info = env.step(rec["action"])
        if _j(obs) != _j(rec["observation"]):
            problems.append(f"observation differs at step {rec['step']}")
            break
        if (terminated, truncated) != (rec["terminated"], rec["truncated"]):
            problems.append(f"termination flags differ at step {rec['step']}")
            break
        if not (terminated or truncated) and reward != rec["reward"]:
            problems.append(f"reward differs at step {rec['step']}")
            break
    else:
        if not (last["terminated"] or last["truncated"]):
            problems.append("recorded run does not end")
        elif env.grader_report()["reward"] != last["reward"]:
            problems.append(f"terminal reward {env.grader_report()['reward']} != recorded {last['reward']}")
    return problems


def replay_records(records: list, episodes: dict) -> dict:
    """records: trajectory records (agent policies only); episodes: {(split, episode_id): Episode}.
    Returns {(split, policy): {"runs": n, "bad": [description, ...], "episodes": {episode_id, ...}}}."""
    # A new run starts at every step-0 record (file order), so a seed listed twice is two runs.
    open_runs: dict = {}
    runs: list = []
    for rec in records:
        key = (rec["run_id"], rec["episode_id"], rec["split"], rec["policy"])
        if rec["step"] == 0 or key not in open_runs:
            open_runs[key] = []
            runs.append((key, open_runs[key]))
        open_runs[key].append(rec)
    out: dict = {}
    for (run_id, eid, split, policy), recs in runs:
        slot = out.setdefault((split, policy), {"runs": 0, "bad": [], "episodes": set()})
        slot["runs"] += 1
        slot["episodes"].add(eid)
        ep = episodes.get((split, eid))
        if ep is None:
            slot["bad"].append(f"{eid}: episode not available")
            continue
        problems = replay_run(recs, ep)
        if problems:
            slot["bad"].append(f"{eid}: {problems[0]}")
    return out
