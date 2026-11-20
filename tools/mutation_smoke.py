"""Mutation smoke: how strongly do the unit tests pin the core? A hand-listed set of one-line mutants.

    python tools/mutation_smoke.py OUT_DIR            # run every mutant, write OUT_DIR/summary.md and summary.json
    python tools/mutation_smoke.py OUT_DIR --record   # the same, then copy both files to runs/mutation/
    options: --jobs N (parallel mutants, default 3)  --timeout S (per mutant, default 300)  --only ID[,ID...]

Each mutant is (file, exact source snippet, replacement, test modules, what it breaks). For one mutant the tool copies
the repository into a fresh temporary directory (the working tree is never touched: the process-isolation layer hashes
the package, and the code stamp covers it), checks that the snippet occurs exactly once and that the result still
compiles, applies the single replacement and runs "python -m unittest -f <modules>" there. Failing or crashing tests, or
a timeout, mean the mutant is killed; a green run means it survived. Two phases per mutant: its listed modules first,
then, only if those pass, tests.test_mutation_survivors (written for these very mutants). The summary records which
phase killed it ("listed tests": the modules listed for the mutant, or "survivor tests") and a sha256 of (file,
snippet, replacement); the other test modules are not run against a mutant. A mutant that is listed as equivalent (the change
cannot alter any behavior) is run too, but reported apart: it counts neither as killed nor as survived. A mutant marked
for one platform (its only killing test runs there, such as a Windows-only test) is not run elsewhere and is reported as
"not run here", not counted. The summary names the platform it was recorded on.
Before any mutant the unmutated copy runs all listed modules once; if that fails nothing is reported.

The summary holds no timings, paths or test names, so two runs on the same tree write the same bytes. Standard library
only. tests/test_mutation_smoke.py checks (fast) that every snippet still occurs exactly once at HEAD.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent

# What a copy of the repository needs to run the unit tests (the viewer, docs, other runs and .git stay out).
COPY_DIRS = ("auditgym", "tests", "examples", "configs", "schemas", "episodes", "tools", "runs/train_dev")
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")


class Mutant(NamedTuple):
    id: str
    file: str
    old: str
    new: str
    modules: tuple
    breaks: str
    equivalent: str = ""  # why the change cannot alter behavior; empty for a real mutant
    only_on: str = ""  # os.name where the test that kills it runs ("nt": a Windows-only test); empty: every platform


# The module with the tests written for these very mutants runs as a second phase, after the listed modules.
SURV = "tests.test_mutation_survivors"
MATCH = ("tests.test_matcher", "tests.test_reward", "tests.test_env")
REWARD = ("tests.test_reward", "tests.test_matcher", "tests.test_env")
SCHEMA = ("tests.test_schemas", "tests.test_contract_battery", "tests.test_env", "tests.test_matcher")
ENV = ("tests.test_env", "tests.test_contract_battery")
VERIFY = ("tests.test_verify", "tests.test_generator")
SHIFT = ("tests.test_transform_shift",)
WINHARD = ("tests.test_windows_hardening", "tests.test_redteam", "tests.test_isolation")
PROTO = ("tests.test_isolation", "tests.test_redteam", "tests.test_contract_fuzz")


def M(id, file, old, new, modules, breaks, equivalent="", only_on=""):
    return Mutant(id, file, old, new, tuple(modules), breaks, equivalent, only_on)


MUTANTS = [
    # ---------------------------------------------------------------- matcher: the five criteria
    M("matcher-type", "auditgym/matcher.py", "if nf.type != ni.type:", "if False:", MATCH,
      "criterion type: a finding of another type still matches"),
    M("matcher-ids-subset", "auditgym/matcher.py", "if nf.ids != ni.ids:", "if not set(nf.ids) <= set(ni.ids):", MATCH,
      "criterion affected_ids: a subset of the key's IDs matches"),
    M("matcher-currency", "auditgym/matcher.py", "if nf.currency != ni.currency:", "if False:", MATCH,
      "criterion currency: a wrong currency still matches"),
    M("matcher-amount-boundary", "auditgym/matcher.py", "if abs(nf.amount - ni.amount) > ni.tolerance:",
      "if abs(nf.amount - ni.amount) >= ni.tolerance:", MATCH, "criterion amount: the tolerance boundary is exclusive"),
    M("matcher-amount-one-sided", "auditgym/matcher.py", "if abs(nf.amount - ni.amount) > ni.tolerance:",
      "if nf.amount - ni.amount > ni.tolerance:", MATCH, "criterion amount: an under-claim of any size matches"),
    M("matcher-amount-no-tolerance", "auditgym/matcher.py", "if abs(nf.amount - ni.amount) > ni.tolerance:",
      "if abs(nf.amount - ni.amount) > 0:", MATCH, "criterion amount: the per-issue tolerance is ignored"),
    M("matcher-evidence-overlap", "auditgym/matcher.py", "if not any(es <= nf.evidence for es in ni.evidence_sets):",
      "if not any(es & nf.evidence for es in ni.evidence_sets):", MATCH,
      "criterion evidence: a partial overlap with an evidence set is enough"),
    M("matcher-evidence-all-sets", "auditgym/matcher.py", "if not any(es <= nf.evidence for es in ni.evidence_sets):",
      "if not all(es <= nf.evidence for es in ni.evidence_sets):", MATCH,
      "criterion evidence: every acceptable set must be cited, not one"),
    M("matcher-currency-case", "auditgym/matcher.py", 'currency=str(f["currency"]).strip().upper(),',
      'currency=str(f["currency"]).strip(),', MATCH, "normalization: the finding's currency is no longer upper-cased"),
    M("matcher-id-strip", "auditgym/matcher.py", "{s.strip() for s in ids if isinstance(s, str) and s.strip()}",
      "{s for s in ids if isinstance(s, str) and s.strip()}", MATCH, "normalization: IDs keep surrounding whitespace"),
    M("matcher-alias-affected", "auditgym/matcher.py",
      'ids = normalize_ids(doc_to_key.get(s.strip(), s) for s in f["affected_ids"] if isinstance(s, str))',
      'ids = normalize_ids(s for s in f["affected_ids"] if isinstance(s, str))', MATCH,
      "alias: a doc_id in affected_ids is no longer mapped to its invoice_id/payment_id"),
    M("matcher-alias-evidence", "auditgym/matcher.py",
      'evidence = normalize_ids(key_to_doc.get(s.strip(), s) for s in f["evidence_ids"] if isinstance(s, str))',
      'evidence = normalize_ids(s for s in f["evidence_ids"] if isinstance(s, str))', MATCH,
      "alias: an invoice_id/payment_id in evidence_ids is no longer mapped to its doc_id"),
    # ------------------------------------------------------- matcher: one-to-one matching, tie-break, F1
    M("matcher-one-to-one", "auditgym/matcher.py", "if owner[j] == -1 or augment(owner[j], seen):", "if True:", MATCH,
      "maximum matching: a later finding takes an issue from an earlier one, which is not re-matched"),
    M("matcher-tp-counts-edges", "auditgym/matcher.py", "tp = len(pairs)", "tp = sum(1 for a in adj if a)", MATCH,
      "one-to-one: every finding with a candidate issue is a true positive, so one issue can score several times"),
    M("matcher-no-augmenting-path", "auditgym/matcher.py", "if owner[j] == -1 or augment(owner[j], seen):",
      "if owner[j] == -1:", MATCH, "maximum matching: greedy first-fit instead of augmenting paths"),
    M("matcher-tiebreak-order", "auditgym/matcher.py",
      "nis = sorted((normalize_issue(t) for t in issues), key=lambda t: t.issue_id)",
      "nis = sorted((normalize_issue(t) for t in issues), key=lambda t: t.issue_id, reverse=True)", MATCH,
      "tie-break: issues are tried in descending issue_id order"),
    M("matcher-repeat-not-fp", "auditgym/matcher.py", "fp = len(nfs) - tp",
      'fp = len([u for u in unmatched if u["reason"] != "duplicate"])', MATCH,
      "false positives: an exact repeat of a matched finding is no longer counted"),
    M("matcher-f1-formula", "auditgym/matcher.py", "return Fraction(2 * tp, 2 * tp + fp + fn)",
      "return Fraction(2 * tp, 2 * tp + fp)", MATCH, "F1: false negatives dropped from the denominator"),
    M("matcher-f1-empty", "auditgym/matcher.py", "if tp + fp + fn == 0:\n        return Fraction(1)",
      "if tp + fp + fn == 0:\n        return Fraction(0)", MATCH, "F1: an empty answer on a clean ledger scores 0, not 1"),
    M("matcher-precision-empty", "auditgym/matcher.py", "precision = tp / (tp + fp) if (tp + fp) else 0.0",
      "precision = tp / (tp + fp) if (tp + fp) else 1.0", MATCH, "precision with no findings is 1.0, not 0.0"),
    # ---------------------------------------------------------------------------------------- reward
    M("reward-step-cost-value", "auditgym/reward.py", "STEP_COST = Fraction(2, 1000)", "STEP_COST = Fraction(3, 1000)",
      REWARD, "step cost is 0.003 per inspection step instead of 0.002"),
    M("reward-step-cost-dropped", "auditgym/reward.py",
      "return float(clip(2 * f1 - 1 - STEP_COST * int(inspection_steps)))", "return float(clip(2 * f1 - 1))", REWARD,
      "step cost: inspection steps are free"),
    M("reward-f1-scale", "auditgym/reward.py", "return float(clip(2 * f1 - 1 - STEP_COST * int(inspection_steps)))",
      "return float(clip(f1 - STEP_COST * int(inspection_steps)))", REWARD, "reward: F1 is not mapped to [-1, 1]"),
    M("reward-clip-lower", "auditgym/reward.py", "return max(Fraction(lo), min(Fraction(hi), value))",
      "return min(Fraction(hi), value)", REWARD, "clip: no lower bound, so many steps push the reward below -1"),
    M("reward-clip-upper", "auditgym/reward.py", "return max(Fraction(lo), min(Fraction(hi), value))",
      "return max(Fraction(lo), value)", REWARD, "clip helper: no upper bound (not reachable through the reward: every caller passes a value <= 1)"),
    M("reward-invalid-constant", "auditgym/reward.py", "INVALID_REWARD = -1.0", "INVALID_REWARD = 0.0", REWARD,
      "an invalid submission is not rewarded -1"),
    M("reward-soft-denominator", "auditgym/reward.py", "denom = len(nfs) + len(nis)", "denom = len(nis)", REWARD,
      "experimental reward: extra findings no longer lower soft F1"),
    M("reward-soft-empty", "auditgym/reward.py", "soft_f1 = Fraction(1) if denom == 0 else Fraction(2) * credit_total / denom",
      "soft_f1 = Fraction(0) if denom == 0 else Fraction(2) * credit_total / denom", REWARD,
      "experimental reward: an empty answer on a clean ledger scores 0, not 1"),
    M("reward-soft-credit-scale", "auditgym/reward.py", "credit = Fraction(weights[r][c], 4)",
      "credit = Fraction(weights[r][c], 3)", REWARD, "experimental reward: credit is not in quarters"),
    M("reward-soft-amount-credit", "auditgym/reward.py", "nf.currency == ni.currency and abs(nf.amount - ni.amount) <= ni.tolerance",
      "nf.currency == ni.currency or abs(nf.amount - ni.amount) <= ni.tolerance", REWARD,
      "experimental reward: amount credit needs only the currency or only the amount"),
    M("reward-soft-group-key", "auditgym/reward.py", "cands = [nf for nf in nfs if (nf.type, nf.ids) == key]",
      "cands = [nf for nf in nfs if nf.type == key[0]]", REWARD,
      "experimental reward: findings compete for issues of the same type with other IDs"),
    M("reward-assignment-positive", "auditgym/reward.py", "and weights[p[j] - 1][j - 1] > 0)",
      "and weights[p[j] - 1][j - 1] >= 0)", REWARD, "assignment helper: zero-weight pairs are reported (not reachable through experimental_reward: weights are >= 2)"),
    # ---------------------------------------------------------------------------------------- grader
    M("grader-closed", "auditgym/grader.py", '"closed": result.fp == 0 and result.fn == 0,',
      '"closed": result.fp == 0 or result.fn == 0,', MATCH, "closed: a run with only false positives or only misses counts as closed"),
    M("grader-invalid-fn", "auditgym/grader.py", '"fn": len(self.issues),', '"fn": 0,', MATCH,
      "invalid submission: no issue counts as missed"),
    M("grader-invalid-reward", "auditgym/grader.py", '"reward": INVALID_REWARD,', '"reward": 0.0,', MATCH,
      "invalid submission: the grade's reward is not -1"),
    M("grader-steps-in-reward", "auditgym/grader.py", "reward = terminal_reward_from_f1(result.f1_exact, inspection_steps)",
      "reward = terminal_reward_from_f1(result.f1_exact, 0)", MATCH, "grade: the step cost is not applied"),
    M("grader-aliases", "auditgym/grader.py", 'self.aliases = dict(self.truth.get("id_aliases", {}))', "self.aliases = {}",
      MATCH, "grade: the answer key's id_aliases are not used"),
    M("grader-error-cap", "auditgym/grader.py", '"errors": list(invalid_errors or [])[:20],',
      '"errors": list(invalid_errors or [])[:21],', MATCH, "invalid submission: the error list is capped at 21, not 20"),
    M("grader-missed-issues", "auditgym/grader.py", '"missed_issues": result.missed,', '"missed_issues": [],', MATCH,
      "grade: missed issues are not listed"),
    # --------------------------------------------------------------------------------------- schemas
    M("schemas-findings-count", "auditgym/schemas.py", "if len(findings) > MAX_FINDINGS:", "if len(findings) >= MAX_FINDINGS:",
      SCHEMA, "limit: 30 findings are already too many"),
    M("schemas-evidence-count", "auditgym/schemas.py", "MAX_EVIDENCE_IDS = 10", "MAX_EVIDENCE_IDS = 11", SCHEMA,
      "limit: 11 evidence IDs are accepted"),
    M("schemas-affected-count", "auditgym/schemas.py", "MAX_AFFECTED_IDS = 10", "MAX_AFFECTED_IDS = 11", SCHEMA,
      "limit: 11 affected IDs are accepted"),
    M("schemas-id-length", "auditgym/schemas.py", "elif len(item) > MAX_ID_CHARS:", "elif len(item) >= MAX_ID_CHARS:", SCHEMA,
      "limit: an ID of exactly 64 characters is too long"),
    M("schemas-explanation-length", "auditgym/schemas.py", "elif len(exp) > MAX_EXPLANATION_CHARS:",
      "elif len(exp) >= MAX_EXPLANATION_CHARS:", SCHEMA, "limit: an explanation of exactly 1000 characters is too long"),
    M("schemas-amount-upper", "auditgym/schemas.py", "amt < 0 or amt > MAX_AMOUNT_MINOR", "amt < 0 or amt >= MAX_AMOUNT_MINOR",
      SCHEMA, "limit: the maximum amount itself is rejected"),
    M("schemas-amount-lower", "auditgym/schemas.py", "amt < 0 or amt > MAX_AMOUNT_MINOR", "amt <= 0 or amt > MAX_AMOUNT_MINOR",
      SCHEMA, "limit: an amount of 0 is rejected"),
    M("schemas-surrogate-id", "auditgym/schemas.py", "elif not _utf8(item):", "elif False:", SCHEMA,
      "lone surrogate in an ID is accepted"),
    M("schemas-surrogate-explanation", "auditgym/schemas.py", "elif not _utf8(exp):", "elif False:", SCHEMA,
      "lone surrogate in an explanation is accepted"),
    M("schemas-surrogate-episode-id", "auditgym/schemas.py", 'elif not _utf8(obj["episode_id"]):', "elif False:", SCHEMA,
      "lone surrogate in the episode_id is accepted"),
    M("schemas-bool-amount", "auditgym/schemas.py", "return isinstance(value, int) and not isinstance(value, bool)",
      "return isinstance(value, int)", SCHEMA, "True is accepted as an integer amount"),
    M("schemas-affected-min", "auditgym/schemas.py", "MAX_AFFECTED_IDS, 1, errors, prefix)", "MAX_AFFECTED_IDS, 0, errors, prefix)",
      SCHEMA, "an empty affected_ids list is accepted"),
    M("schemas-blank-id", "auditgym/schemas.py", "if not isinstance(item, str) or not item.strip():",
      "if not isinstance(item, str):", SCHEMA, "a blank ID is accepted"),
    M("schemas-currency-shape", "auditgym/schemas.py", '_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")',
      '_CURRENCY_RE = re.compile(r"^[A-Za-z]{2,3}$")', SCHEMA, "a 2-letter currency is accepted"),
    M("schemas-episode-mismatch", "auditgym/schemas.py", 'elif episode_id is not None and obj["episode_id"] != episode_id:',
      "elif False:", SCHEMA, "a submission for another episode is accepted"),
    M("schemas-unknown-finding-keys", "auditgym/schemas.py", "if extra_f:", "if False:", SCHEMA,
      "unknown keys inside a finding are accepted"),
    M("schemas-coerce-int", "auditgym/schemas.py", "if isinstance(value, float) and value.is_integer():",
      "if isinstance(value, float):", SCHEMA, "a fractional float amount is truncated to an integer"),
    M("schemas-page-size", "auditgym/schemas.py", "MAX_PAGE = 50", "MAX_PAGE = 51", ENV, "page size is 51 instead of 50"),
    # ------------------------------------------------------------------------------------------ env
    M("env-page-limit", "auditgym/env.py", "or not 1 <= limit <= schemas.MAX_PAGE:", "or not 1 <= limit <= schemas.MAX_PAGE + 1:",
      ENV, "page size: limit 51 is accepted"),
    M("env-page-default", "auditgym/env.py", 'limit = schemas.coerce_int(action.get("limit", schemas.MAX_PAGE))',
      'limit = schemas.coerce_int(action.get("limit", 10))', ENV, "page size: the default page is 10 rows, not 50"),
    M("env-step-budget", "auditgym/env.py", "if self._steps >= self.max_steps:", "if self._steps > self.max_steps:", ENV,
      "step budget: one extra step is allowed before truncation"),
    M("env-max-steps-bound", "auditgym/env.py", "if not 1 <= int(max_steps) <= DEFAULT_MAX_STEPS:",
      "if not 1 <= int(max_steps) < DEFAULT_MAX_STEPS:", ENV, "step budget: the default maximum of 100 is rejected"),
    M("env-cursor-end", "auditgym/env.py", "and int(cursor) <= len(rows):", "and int(cursor) < len(rows):", ENV,
      "cursor: the end-of-table offset is a bad cursor"),
    M("env-next-cursor", "auditgym/env.py", '"next_cursor": str(nxt) if nxt < len(rows) else None,',
      '"next_cursor": str(nxt) if nxt <= len(rows) else None,', ENV, "cursor: the last page announces another page"),
    M("env-eval-hides-reward", "auditgym/env.py", 'if not self._done or self.mode != "train":', "if not self._done:", ENV,
      "eval mode: the terminal reward reaches the policy"),
    M("env-eval-hides-info", "auditgym/env.py", 'if self._done and self.mode == "train":', "if self._done:", ENV,
      "eval mode: TP/FP/FN and the reward reach the policy in info"),
    M("env-inspection-steps", "auditgym/env.py",
      'inspection = self._steps - (1 if reason in ("submitted", "invalid_submission") else 0)', "inspection = self._steps",
      ENV, "step cost: the final submit counts as an inspection step"),
    M("env-rows-copy", "auditgym/env.py", '"rows": copy.deepcopy(page),', '"rows": page,', ENV,
      "isolation: the policy receives the environment's own row objects"),
    M("env-time-limit", "auditgym/env.py", "if self._clock() - self._t0 > self.time_limit_s:",
      "if self._clock() - self._t0 >= self.time_limit_s:", ENV, "time limit: the boundary instant already truncates"),
    M("env-finished-noop", "auditgym/env.py", "if self._done:\n            obs = self._obs(None, _err(\"episode_finished\"",
      "if False:\n            obs = self._obs(None, _err(\"episode_finished\"", ENV, "a finished episode accepts more actions"),
    M("env-submit-extra-keys", "auditgym/env.py", 'errors.append("unknown action keys: " + _echo(", ".join(extra)))', "pass",
      ENV, "a submit with unknown action keys is accepted"),
    # -------------------------------------------------------------------------------------- verify
    M("verify-colon-in-id", "auditgym/verify.py", 'if ":" in i:', "if False:", VERIFY, "ids_unique: a ':' inside an ID is allowed"),
    M("verify-duplicate-id", "auditgym/verify.py", "if i in seen and seen[i] != where:", "if False:", VERIFY,
      "ids_unique: one ID used in two tables is allowed"),
    M("verify-record-counts", "auditgym/verify.py", "if counts.get(t) != len(ep.table(t)):", "if False:", VERIFY,
      "records_schema: a wrong manifest record count passes"),
    M("verify-amount-mismatch", "auditgym/verify.py", 'if f["amount"] != t["expected_amount_minor"]:', "if False:", VERIFY,
      "declared_discrepancies: an auditor/key amount mismatch passes"),
    M("verify-evidence-sets", "auditgym/verify.py", 'if {frozenset(s) for s in f["evidence_sets"]} != {frozenset(s) for s in t["evidence_sets"]}:',
      "if False:", VERIFY, "declared_discrepancies: differing evidence sets pass"),
    M("verify-unknown-variant", "auditgym/verify.py", 'if t.get("variant") not in VARIANTS.get(t.get("type"), ()):',
      "if False:", VERIFY, "declared_discrepancies: an unknown issue variant passes"),
    M("verify-budget-bound", "auditgym/verify.py", "pages + 1 <= max_steps", "pages <= max_steps", VERIFY,
      "budget_feasible: the submit step is not counted"),
    M("verify-surface-pattern", "auditgym/verify.py", "if not patterns.get(pat):", "if False:", VERIFY,
      "no_surface_tells: a touched ledger row with a unique pattern passes"),
    M("verify-leak-marker", "auditgym/verify.py", 'LEAK_MARKERS = ("iss_", "duplicate_of", "provenance",',
      'LEAK_MARKERS = ("iss_", "duplicate_of",', VERIFY, "no_leaks: the word provenance is no longer a leak marker"),
    M("verify-final-digest", "auditgym/verify.py", 'elif ep.public_digest() != ep.provenance["final_digest"]:', "elif False:",
      VERIFY, "provenance_roundtrip: a public digest that differs from final_digest passes"),
    M("verify-clean-digest", "auditgym/verify.py", "elif _tables_digest(rec) != want:", "elif False:", VERIFY,
      "provenance_roundtrip: reverted tables with the wrong clean digest pass"),
    M("verify-op-touches", "auditgym/verify.py", 'if not (set(t["affected_ids"]) & touched):', "if False:", VERIFY,
      "provenance_roundtrip: an issue with no op touching its records passes"),
    M("verify-injection-match", "auditgym/verify.py", "if injected != declared:", "if False:", VERIFY,
      "provenance_roundtrip: injections and truth issues may differ"),
    M("verify-retarget", "auditgym/verify.py", 'if isinstance(want, list) and set(values) != set(want):', "if False:", VERIFY,
      "provenance_roundtrip: an injection retargeted to other records passes"),
    # ------------------------------------------------------------------------------ evidence_check
    M("evidence-fx-tolerance", "auditgym/evidence_check.py", "if delta > TOLERANCE_MINOR else None",
      "if delta >= TOLERANCE_MINOR else None", VERIFY, "wrong_fx_rate: a difference exactly at the tolerance counts as an error"),
    M("evidence-uncited-record", "auditgym/evidence_check.py",
      "if len(cited_rows) + len(cited_docs) + len(cited_fx) != len(evidence):\n        return None",
      "if False:\n        return None", VERIFY, "evidence IDs that name no record are ignored"),
    M("evidence-duplicate-account", "auditgym/evidence_check.py", 'or ra[0]["account"] != rb[0]["account"]:', "or False:",
      VERIFY, "duplicate_invoice: rows in different accounts still support it"),
    M("evidence-duplicate-signature", "auditgym/evidence_check.py", "if sig_a is None or sig_a != sig_b:", "if sig_a is None:",
      VERIFY, "duplicate_invoice: two different invoices still support it"),
    M("evidence-unallocated-total", "auditgym/evidence_check.py", 'i["total_minor"] >= p["amount_minor"]',
      'i["total_minor"] > p["amount_minor"]', VERIFY, "unallocated_payment: a payment equal to the invoice total is rejected"),
    M("evidence-unallocated-account", "auditgym/evidence_check.py", 'r["account"] == "2900"', 'r["account"] != ""', VERIFY,
      "unallocated_payment: the row may sit in any account"),
    M("evidence-fx-future-date", "auditgym/evidence_check.py", "if fx_d > local_d or", "if fx_d >= local_d or", VERIFY,
      "wrong_fx_rate: a rate dated on the document's own day is rejected"),
    M("evidence-period-boundary", "auditgym/evidence_check.py", "(p0 <= inst < p1) == (p0 <= post < p1)",
      "(p0 <= inst < p1) == (p0 <= post <= p1)", VERIFY, "wrong_period: the period end instant belongs to the period"),
    M("evidence-offset-start", "auditgym/evidence_check.py", "if start <= inst:", "if start < inst:", VERIFY,
      "local date: the UTC offset change takes effect one instant late"),
    M("evidence-half-even", "auditgym/evidence_check.py", "return floor if floor % 2 == 0 else floor + 1",
      "return floor + 1", VERIFY, "rounding: half_even always rounds the tie up"),
    # ------------------------------------------------------------------------------------- protocol
    M("protocol-max-line", "auditgym/protocol.py", "if len(line) > MAX_LINE:", "if len(line) >= MAX_LINE:", PROTO,
      "bound: a line of exactly MAX_LINE characters is malformed"),
    M("protocol-max-depth", "auditgym/protocol.py", "depth > MAX_DEPTH", "depth >= MAX_DEPTH", PROTO,
      "bound: nesting of exactly MAX_DEPTH is malformed"),
    M("protocol-max-nodes", "auditgym/protocol.py", "nodes > MAX_NODES or", "nodes >= MAX_NODES or", PROTO,
      "bound: exactly MAX_NODES parsed nodes is malformed"),
    M("protocol-separator-count", "auditgym/protocol.py", 'if line.count("[") + line.count("{") + line.count(",") > MAX_NODES:',
      'if line.count("[") + line.count("{") > MAX_NODES:', PROTO, "bound: commas are not counted against the node limit"),
    M("protocol-max-digits", "auditgym/protocol.py", "if len(text) > MAX_NUMBER_CHARS:", "if len(text) >= MAX_NUMBER_CHARS:", PROTO,
      "bound: an integer literal of exactly MAX_NUMBER_CHARS digits is malformed"),
    M("protocol-max-float", "auditgym/protocol.py", "if len(text) > MAX_FLOAT_CHARS:", "if len(text) >= MAX_FLOAT_CHARS:", PROTO,
      "bound: a float literal of exactly MAX_FLOAT_CHARS characters is malformed"),
    M("protocol-nonsubmit-size", "auditgym/protocol.py", "if len(line) > MAX_NONSUBMIT_CHARS and not",
      "if len(line) >= MAX_NONSUBMIT_CHARS and not", PROTO, "bound: a non-submit line of exactly 2048 characters is malformed"),
    M("protocol-nan", "auditgym/protocol.py", 'raise ValueError("NaN and Infinity are not JSON")', "return 0", PROTO,
      "NaN and Infinity are accepted as numbers"),
    M("protocol-echo-length", "auditgym/protocol.py", "echo = line[:ECHO_CHARS].rstrip", "echo = line[:ECHO_CHARS + 1].rstrip", PROTO,
      "echo: a malformed line is echoed 257 characters long"),
    M("protocol-surrogate", "auditgym/protocol.py", 'json.dumps(action, ensure_ascii=False, allow_nan=False).encode("utf-8")',
      "json.dumps(action, ensure_ascii=False, allow_nan=False)", PROTO, "a lone surrogate in an action is accepted"),
    # ---------------------------------------------------------------- round 7: verify, year shift, Windows child
    M("verify-stale-rate-variant", "auditgym/verify.py", 'elif variant in ("utc_date", "posting_date", "stale_rate"):',
      'elif variant in ("utc_date", "posting_date"):', VERIFY,
      "provenance: the stale_rate change.wrong_rate_date is not checked against the fx.csv rate"),
    M("shift-direction-order", "auditgym/transform.py", "for cand in (k, -k):", "for cand in (-k, k):", SHIFT,
      "shift_direction tries -28 before +28"),
    M("check-shift-direction-order", "auditgym/check.py", "for k in (k0, -k0):", "for k in (-k0, k0):", SHIFT,
      "D_paired tries the -28 shift before +28"),
    M("shift-period-lower", "auditgym/transform.py", "not PERIOD_YEARS[0] <= int(text[:4]) + k",
      "not PERIOD_YEARS[0] < int(text[:4]) + k", SHIFT, "shift: a period landing exactly on 2000 is refused"),
    M("policy-path-append", "auditgym/agent.py", "at = sys.path.index(staged) + 1 if staged in sys.path else len(sys.path)",
      "at = len(sys.path)", WINHARD, "Windows child: the policy directory goes last on sys.path, not after the staged code",
      only_on="nt"),
]


# ------------------------------------------------------------------------------------------ mechanics
def read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def occurrences(mutant: Mutant, root: Path = ROOT) -> int:
    return read_text(root / mutant.file).count(mutant.old)


def list_problems(root: Path = ROOT) -> list[str]:
    """Why the list cannot be used on `root`: a duplicate ID, a snippet that is not found exactly once, a replacement
    that equals the snippet or does not compile."""
    problems, seen = [], set()
    for m in MUTANTS:
        if m.id in seen:
            problems.append(f"{m.id}: duplicate id")
        seen.add(m.id)
        text = read_text(root / m.file)
        n = text.count(m.old)
        if n != 1:
            problems.append(f"{m.id}: snippet occurs {n} times in {m.file} (need exactly 1)")
            continue
        if m.new == m.old:
            problems.append(f"{m.id}: replacement equals the snippet")
        try:
            compile(text.replace(m.old, m.new, 1), m.file, "exec")
        except SyntaxError as exc:
            problems.append(f"{m.id}: mutated source does not compile ({exc.msg})")
    return problems


def make_copy(dst: Path) -> None:
    for name in os.listdir(ROOT):
        src = ROOT / name
        if src.is_file():
            shutil.copy2(src, dst / name)
    for rel in COPY_DIRS:
        src = ROOT / rel
        if src.is_dir():
            shutil.copytree(src, dst / rel, ignore=IGNORE)


def kill_tree(proc: subprocess.Popen) -> None:
    """Stop `proc` and everything it started (a grandchild such as `auditgym verify` would otherwise keep the
    temporary copy busy and burn CPU)."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    proc.kill()


def run_tests(cwd: Path, modules, timeout: float) -> tuple[bool, str]:
    """(passed, why). A timeout counts as a failure; the whole process tree is stopped."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    cmd = [sys.executable, "-m", "unittest", "-f", *modules]
    group = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
             else {"start_new_session": True})
    proc = subprocess.Popen(cmd, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", **group)
    try:
        _, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_tree(proc)
        try:
            proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            pass
        return False, "timeout"
    tail = (err or "").strip().splitlines()[-6:]
    return proc.returncode == 0, "\n".join(tail)


def run_mutant(m: Mutant, timeout: float) -> dict:
    if m.only_on and m.only_on != os.name:
        return {"passed": None, "why": f"runs only where os.name is {m.only_on!r}", "killed_by": ""}
    with tempfile.TemporaryDirectory(prefix="auditgym-mut-", ignore_cleanup_errors=True) as tmp:
        work = Path(tmp)
        make_copy(work)
        target = work / m.file
        text = read_text(target)
        if text.count(m.old) != 1:
            raise SystemExit(f"{m.id}: snippet does not occur exactly once in {m.file}")
        target.write_bytes(text.replace(m.old, m.new, 1).encode("utf-8"))
        passed, why = run_tests(work, m.modules, timeout)
        if not passed:
            return {"passed": False, "why": why, "killed_by": "listed tests"}
        passed, why = run_tests(work, (SURV,), timeout)
    return {"passed": passed, "why": why, "killed_by": "" if passed else "survivor tests"}


def baseline(timeout: float) -> None:
    modules = sorted({mod for m in MUTANTS for mod in m.modules} | {SURV})
    with tempfile.TemporaryDirectory(prefix="auditgym-mut-", ignore_cleanup_errors=True) as tmp:
        work = Path(tmp)
        make_copy(work)
        passed, why = run_tests(work, modules, timeout * 3)
    if not passed:
        raise SystemExit("the unmutated copy does not pass its own tests; no mutation result is meaningful:\n" + why)


def classify(m: Mutant, res: dict) -> str:
    if res["passed"] is None:
        return "not run here"
    if m.equivalent:
        return "equivalent"
    return "survived" if res["passed"] else "killed"


def snippet_hash(m: Mutant) -> str:
    return hashlib.sha256(json.dumps([m.file, m.old, m.new]).encode("utf-8")).hexdigest()


def tests_hashes() -> dict:
    """sha256 of every test module a run uses, so a test edit after recording shows up as a stale record."""
    modules = sorted({mod for m in MUTANTS for mod in m.modules} | {SURV})
    return {mod: hashlib.sha256(read_text(ROOT / (mod.replace(".", "/") + ".py")).replace("\r\n", "\n")
                                .encode("utf-8")).hexdigest()
            for mod in modules}


PLATFORM_NAMES = {"nt": "Windows", "posix": "POSIX"}


def build_report(results: list[tuple[Mutant, dict]]) -> dict:
    rows = []
    for m, res in results:
        rows.append({
            "id": m.id,
            "file": m.file,
            "breaks": m.breaks,
            "status": classify(m, res),
            "killed_by": res["killed_by"],
            "tests": list(m.modules),
            "sha256": snippet_hash(m),
            **({"equivalent_because": m.equivalent, "observed": "survived" if res["passed"] else "killed"}
               if m.equivalent and res["passed"] is not None else {}),
        })
    real = [r for r in rows if r["status"] not in ("equivalent", "not run here")]
    killed = sum(1 for r in real if r["status"] == "killed")
    by_existing = sum(1 for r in real if r["killed_by"] == "listed tests")
    not_run = sum(1 for r in rows if r["status"] == "not run here")
    return {"listed": len(rows), "counted": len(real), "killed": killed, "survived": len(real) - killed,
            "equivalent": len(rows) - len(real) - not_run, "not_run_here": not_run,
            "recorded_on": f"{PLATFORM_NAMES.get(os.name, os.name)}, Python {sys.version_info[0]}.{sys.version_info[1]}",
            "platform_only": {m.id: PLATFORM_NAMES.get(m.only_on, m.only_on) for m, _ in results if m.only_on},
            "killed_by_existing": by_existing,
            "killed_by_survivor_tests": killed - by_existing, "test_modules_sha256": tests_hashes(),
            "mutants": rows}


def render_markdown(report: dict) -> str:
    lines = [
        "# Mutation smoke",
        "",
        f"**{report['killed']} of {report['counted']} listed mutants killed** "
        f"({report['survived']} survived, {report['equivalent']} equivalent, not counted"
        + (f"; {report['not_run_here']} not run on this platform" if report["not_run_here"] else "") + ").",
        "",
        f"Recorded on {report['recorded_on']}."
        + ("".join(f" `{k}` is killed only by a test that runs on {v}, so it runs only there."
                   for k, v in report["platform_only"].items())),
        "",
        f"{report['killed_by_existing']} of {report['counted']} are killed by the test modules listed for them. The other "
        f"{report['killed_by_survivor_tests']} pass those modules and are killed by `tests/test_mutation_survivors.py`, "
        "which was written for these mutants; the remaining test modules are not run against a mutant.",
        "",
        "Each mutant is one hand-written change to the core (`auditgym/matcher.py`, `reward.py`, `grader.py`, "
        "`schemas.py`, `env.py`, `verify.py`, `evidence_check.py`, `protocol.py`, `transform.py`, `agent.py`, `check.py`), applied to a fresh copy of the "
        "repository, which then runs the unit-test modules named in the last column, and, if those pass, "
        "`tests/test_mutation_survivors.py`. A mutant is killed when those tests fail. The list is in `tools/mutation_smoke.py`; this file holds no timings.",
        "",
        "Regenerate: `python tools/mutation_smoke.py OUT_DIR --record`.",
        "",
        "| # | mutant | file | what it breaks | result | killed by | tests run |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(report["mutants"], 1):
        tests = ", ".join(t.removeprefix("tests.") for t in r["tests"])
        lines.append(f"| {i} | `{r['id']}` | `{r['file']}` | {r['breaks']} | {r['status']} | {r['killed_by'] or '-'} | {tests} |")
    eq = [r for r in report["mutants"] if r["status"] == "equivalent"]
    if eq:
        lines += ["", "## Equivalent mutants", ""]
        lines += [f"- `{r['id']}`: {r['equivalent_because']}" for r in eq]
    surv = [r for r in report["mutants"] if r["status"] == "survived"]
    if surv:
        lines += ["", "## Survivors", ""]
        lines += [f"- `{r['id']}`: {r['breaks']}" for r in surv]
    return "\n".join(lines) + "\n"


def write_report(report: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_bytes((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    (out_dir / "summary.md").write_bytes(render_markdown(report).encode("utf-8"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="hand-listed mutation smoke over the auditgym core")
    ap.add_argument("out_dir")
    ap.add_argument("--record", action="store_true", help="also copy summary.md and summary.json to runs/mutation/")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--only", default="", help="comma-separated mutant IDs (a partial run is never recorded)")
    args = ap.parse_args(argv)
    problems = list_problems()
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 2
    chosen = MUTANTS
    if args.only:
        wanted = args.only.split(",")
        unknown = [w for w in wanted if w not in {m.id for m in MUTANTS}]
        if unknown:
            print("unknown mutant id(s): " + ", ".join(unknown), file=sys.stderr)
            return 2
        chosen = [m for m in MUTANTS if m.id in wanted]
        if args.record:
            print("--only and --record cannot be combined", file=sys.stderr)
            return 2
    baseline(args.timeout)
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        outcomes = list(pool.map(lambda m: run_mutant(m, args.timeout), chosen))
    report = build_report(list(zip(chosen, outcomes)))
    out_dir = Path(args.out_dir)
    write_report(report, out_dir)
    for r in report["mutants"]:
        print(f"{r['status']:10s} {r['id']}")
    print(f"{report['killed']} of {report['counted']} listed mutants killed; {report['survived']} survived; "
          f"{report['equivalent']} equivalent" + (f"; {report['not_run_here']} not run on this platform"
                                                   if report["not_run_here"] else ""))
    if args.record:
        dest = ROOT / "runs" / "mutation"
        dest.mkdir(parents=True, exist_ok=True)
        for name in ("summary.md", "summary.json"):
            shutil.copyfile(out_dir / name, dest / name)
    return 0 if report["survived"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
