"""Boundary and rule tests written for the mutants of tools/mutation_smoke.py (recorded in runs/mutation/).

Most of them close a gap the mutation run showed: the other unit tests let that mutant survive. A few pin a mutant that
the other tests already killed (protocol-echo-length, protocol-nan, protocol-surrogate, schemas-evidence-count and,
since the currency cap, schemas-findings-count, schemas-affected-count, schemas-id-length, schemas-explanation-length,
schemas-amount-upper), but only indirectly. Each test names the mutant it was written for. Every one of them passes on the real code and fails
on that mutant. The mutation tool runs these tests last, so the summary tells apart the mutants killed by the other
tests from those killed only here.
"""

import copy
import unittest
from fractions import Fraction
from pathlib import Path

from auditgym import evidence_check, protocol, reward, schemas
from auditgym.episode import load_episode
from auditgym.grader import Grader
from auditgym.matcher import match
from auditgym.timeutil import parse_ts
from auditgym.verify import (LEAK_MARKERS, check_budget, check_ids, check_leaks, check_records_schema, check_surface,
                             compare_with_truth)
from tests.test_env import episode, fresh, oracle_submit

ROOT = Path(__file__).resolve().parent.parent
TRAIN = ROOT / "episodes" / "train"


def finding(type_, ids, amount, currency, evidence, explanation="x"):
    return {"type": type_, "affected_ids": ids, "claimed_amount_minor": amount, "currency": currency,
            "evidence_ids": evidence, "explanation": explanation}


def issue(issue_id, type_="wrong_fx_rate", ids=("INV-9",), amount=3177, currency="EUR", tol=2,
          evidence=(("D9", "L9"),)):
    return {"issue_id": issue_id, "type": type_, "affected_ids": list(ids), "expected_amount_minor": amount,
            "currency": currency, "tolerance_minor": tol, "evidence_sets": [list(e) for e in evidence]}


FX = ("wrong_fx_rate", ["INV-9"], 3177, "EUR", ["D9", "L9"])


class MatcherSurvivors(unittest.TestCase):
    def test_under_claim_beyond_tolerance_does_not_match(self):  # matcher-amount-one-sided
        r = match([finding("wrong_fx_rate", ["INV-9"], 3174, "EUR", ["D9", "L9"])], [issue("iss_01")])
        self.assertEqual((r.tp, r.fp, r.fn), (0, 1, 1))
        self.assertEqual(r.unmatched[0]["reason"], "amount")
        self.assertEqual(match([finding("wrong_fx_rate", ["INV-9"], 3175, "EUR", ["D9", "L9"])], [issue("iss_01")]).tp, 1)

    def test_document_id_in_affected_ids_maps_to_the_invoice_id(self):  # matcher-alias-affected
        r = match([finding(*FX)], [issue("iss_01", ids=("INV-9",))], {"DOC-9": "INV-9"})
        self.assertEqual(r.tp, 1)
        r = match([finding("wrong_fx_rate", ["DOC-9"], 3177, "EUR", ["D9", "L9"])], [issue("iss_01")], {"DOC-9": "INV-9"})
        self.assertEqual(r.tp, 1)

    def test_invoice_id_in_evidence_maps_to_the_document_id(self):  # matcher-alias-evidence
        key = issue("iss_01", evidence=(("DOC-9", "L9"),))
        aliases = {"DOC-9": "INV-9"}
        self.assertEqual(match([finding("wrong_fx_rate", ["INV-9"], 3177, "EUR", ["INV-9", "L9"])], [key], aliases).tp, 1)
        self.assertEqual(match([finding("wrong_fx_rate", ["INV-9"], 3177, "EUR", ["INV-9", "L9"])], [key]).tp, 0)

    def test_identical_issues_are_taken_in_ascending_issue_id_order(self):  # matcher-tiebreak-order
        issues = [issue("iss_02"), issue("iss_01")]
        r = match([finding(*FX)], issues)
        self.assertEqual(r.pairs, [(0, "iss_01")])
        self.assertEqual(r.missed, ["iss_02"])
        r = match([finding(*FX), finding(*FX)], issues)
        self.assertEqual(sorted(i for _, i in r.pairs), ["iss_01", "iss_02"])


class RewardSurvivors(unittest.TestCase):
    def test_clip_has_both_bounds(self):  # reward-clip-upper
        self.assertEqual(reward.clip(Fraction(5)), 1)
        self.assertEqual(reward.clip(Fraction(-5)), -1)
        self.assertEqual(reward.clip(Fraction(1, 2)), Fraction(1, 2))

    def test_empty_answer_on_a_clean_ledger_has_full_soft_credit(self):  # reward-soft-empty
        out = reward.experimental_reward([], [], 0)
        self.assertEqual((out["soft_f1"], out["reward"]), (1.0, 1.0))

    def test_amount_credit_needs_both_currency_and_amount(self):  # reward-soft-amount-credit
        key = [issue("iss_01")]
        full = reward.experimental_reward([finding(*FX)], key, 0)
        wrong_amount = reward.experimental_reward([finding("wrong_fx_rate", ["INV-9"], 1, "EUR", ["D9", "L9"])], key, 0)
        wrong_currency = reward.experimental_reward([finding("wrong_fx_rate", ["INV-9"], 3177, "USD", ["D9", "L9"])], key, 0)
        self.assertEqual(full["credit_per_issue"], {"iss_01": 1.0})
        self.assertEqual(wrong_amount["credit_per_issue"], {"iss_01": 0.75})
        self.assertEqual(wrong_currency["credit_per_issue"], {"iss_01": 0.75})

    def test_credit_needs_the_same_affected_ids(self):  # reward-soft-group-key
        key = [issue("iss_01", ids=("INV-9",))]
        out = reward.experimental_reward([finding("wrong_fx_rate", ["INV-8"], 3177, "EUR", ["D9", "L9"])], key, 0)
        self.assertEqual((out["soft_f1"], out["credit_per_issue"]), (0.0, {}))

    def test_assignment_never_reports_a_zero_weight_pair(self):  # reward-assignment-positive
        self.assertEqual(reward._max_weight_assignment([[0]]), [])
        self.assertEqual(reward._max_weight_assignment([[0, 0], [0, 0]]), [])
        self.assertEqual(reward._max_weight_assignment([[0, 3], [2, 0]]), [(0, 1), (1, 0)])


class GraderSurvivors(unittest.TestCase):
    def setUp(self):
        self.key = [issue("iss_01"), issue("iss_02", type_="duplicate_invoice", ids=("INV-1", "INV-2"), amount=500,
                                          evidence=(("D1", "D2"),))]
        self.truth = {"issues": self.key, "id_aliases": {"DOC-9": "INV-9"}}
        self.good = [finding(*FX), finding("duplicate_invoice", ["INV-1", "INV-2"], 500, "EUR", ["D1", "D2"])]

    def grade(self, findings, steps=3):
        return Grader(self.truth, "ep").grade({"episode_id": "ep", "findings": findings}, steps, "submitted")

    def test_closed_needs_no_false_positive_and_no_miss(self):  # grader-closed
        self.assertTrue(self.grade(self.good)["closed"])
        extra = self.grade(self.good + [finding("wrong_period", ["INV-5"], 1, "EUR", ["Z"])])
        self.assertEqual((extra["fp"], extra["fn"], extra["closed"]), (1, 0, False))
        missed = self.grade(self.good[:1])
        self.assertEqual((missed["fp"], missed["fn"], missed["closed"]), (0, 1, False))

    def test_invalid_grade_counts_every_issue_as_missed_and_caps_the_errors(self):  # grader-invalid-fn, grader-error-cap
        g = Grader(self.truth, "ep").grade(None, 3, "invalid_submission", invalid_errors=[f"e{i}" for i in range(25)])
        self.assertEqual((g["fn"], g["tp"], g["fp"], g["reward"], g["closed"]), (2, 0, 0, -1.0, False))
        self.assertEqual(g["errors"], [f"e{i}" for i in range(20)])
        self.assertEqual(g["missed_issues"], ["iss_01", "iss_02"])

    def test_the_answer_key_aliases_reach_the_matcher(self):  # grader-aliases
        g = self.grade([finding("wrong_fx_rate", ["DOC-9"], 3177, "EUR", ["D9", "L9"])])
        self.assertEqual(g["tp"], 1)

    def test_missed_issues_are_listed(self):  # grader-missed-issues
        g = self.grade([])
        self.assertEqual((g["missed_issues"], g["fn"], g["pairs"]), (["iss_01", "iss_02"], 2, []))
        self.assertEqual(self.grade(self.good[:1])["missed_issues"], ["iss_02"])


def valid_finding(**over):
    f = finding("duplicate_invoice", ["INV-1"], 100, "EUR", ["D1"])
    f.update(over)
    return f


def errors(findings, episode_id="ep"):
    return schemas.validate_submission({"episode_id": "ep", "findings": findings}, episode_id)


class SchemaLimitSurvivors(unittest.TestCase):
    def test_finding_count_limit(self):  # schemas-findings-count
        self.assertEqual(errors([valid_finding()] * schemas.MAX_FINDINGS), [])
        self.assertTrue(errors([valid_finding()] * (schemas.MAX_FINDINGS + 1)))

    def test_id_list_limits(self):  # schemas-evidence-count, schemas-affected-count
        ids = [f"X{i}" for i in range(11)]
        self.assertEqual(errors([valid_finding(affected_ids=ids[:10])]), [])
        self.assertTrue(errors([valid_finding(affected_ids=ids)]))
        self.assertEqual(errors([valid_finding(evidence_ids=ids[:10])]), [])
        self.assertTrue(errors([valid_finding(evidence_ids=ids)]))

    def test_id_length_limit(self):  # schemas-id-length
        self.assertEqual(errors([valid_finding(affected_ids=["a" * 64], evidence_ids=["b" * 64])]), [])
        self.assertTrue(errors([valid_finding(affected_ids=["a" * 65])]))
        self.assertTrue(errors([valid_finding(evidence_ids=["b" * 65])]))

    def test_explanation_length_limit(self):  # schemas-explanation-length
        self.assertEqual(errors([valid_finding(explanation="e" * 1000)]), [])
        self.assertTrue(errors([valid_finding(explanation="e" * 1001)]))

    def test_amount_range(self):  # schemas-amount-upper, schemas-amount-lower
        self.assertEqual(errors([valid_finding(claimed_amount_minor=0)]), [])
        self.assertEqual(errors([valid_finding(claimed_amount_minor=10 ** 15)]), [])
        self.assertTrue(errors([valid_finding(claimed_amount_minor=-1)]))
        self.assertTrue(errors([valid_finding(claimed_amount_minor=10 ** 15 + 1)]))

    def test_a_blank_id_is_invalid_in_both_lists(self):  # schemas-blank-id
        self.assertTrue(errors([valid_finding(affected_ids=["  "])]))
        self.assertTrue(errors([valid_finding(evidence_ids=["", "D1"])]))

    def test_currency_is_three_letters(self):  # schemas-currency-shape
        self.assertEqual(errors([valid_finding(currency=" eur ")]), [])
        for bad in ("EU", "EURO", "E1R", "", 5):
            self.assertTrue(errors([valid_finding(currency=bad)]), bad)

    def test_only_integral_floats_are_coerced(self):  # schemas-coerce-int
        self.assertEqual(schemas.coerce_int(5.5), 5.5)
        self.assertIsInstance(schemas.coerce_int(5.0), int)
        self.assertEqual(schemas.coerce_int(1e3), 1000)
        self.assertTrue(errors([valid_finding(claimed_amount_minor=5.5)]))


class EnvSurvivors(unittest.TestCase):
    def test_a_list_without_limit_returns_a_full_page(self):  # env-page-default
        env, _, _ = fresh()
        obs, *_ = env.step({"action": "list_records", "table": "ledger"})
        self.assertGreater(obs["result"]["total"], 50)
        self.assertEqual(len(obs["result"]["rows"]), 50)
        self.assertEqual(obs["result"]["next_cursor"], "50")

    def test_the_end_of_table_cursor_is_valid(self):  # env-cursor-end
        env, _, _ = fresh()
        total = env.step({"action": "list_records", "table": "fx"})[0]["result"]["total"]
        obs, *_ = env.step({"action": "list_records", "table": "fx", "cursor": str(total)})
        self.assertIsNone(obs["error"])
        self.assertEqual((obs["result"]["rows"], obs["result"]["next_cursor"]), ([], None))
        obs, *_ = env.step({"action": "list_records", "table": "fx", "cursor": str(total + 1)})
        self.assertEqual(obs["error"]["code"], "bad_cursor")

    def test_returned_rows_are_copies(self):  # env-rows-copy
        env, _, _ = fresh()
        first = env.step({"action": "list_records", "table": "ledger", "limit": 1})[0]["result"]["rows"]
        before = copy.deepcopy(first)
        first[0]["debit_minor"] = 987654321
        again = env.step({"action": "list_records", "table": "ledger", "limit": 1})[0]["result"]["rows"]
        self.assertEqual(again, before)

    def test_the_time_limit_is_exceeded_only_after_it_passes(self):  # env-time-limit
        from auditgym.env import AuditEnv

        clock = [0.0]
        env = AuditEnv(mode="train", time_limit_s=60, clock=lambda: clock[0])
        env.reset(config={"episode": episode()})
        clock[0] = 60.0
        obs, _, _, trunc, _ = env.step({"action": "calculator", "expression": "1+1"})
        self.assertFalse(trunc)
        self.assertIsNone(obs["error"])
        clock[0] = 60.5
        obs, _, _, trunc, _ = env.step({"action": "calculator", "expression": "1+1"})
        self.assertTrue(trunc)
        self.assertEqual(obs["error"]["code"], "time_limit")

    def test_a_submit_with_an_unknown_action_key_is_invalid(self):  # env-submit-extra-keys
        env, _, _ = fresh()
        action = dict(oracle_submit(env), note="hello")
        obs, reward_out, terminated, _, _ = env.step(action)
        self.assertTrue(terminated)
        self.assertEqual(obs["error"]["code"], "invalid_submission")
        self.assertEqual(reward_out, -1.0)
        self.assertEqual(env.grader_report()["status"], "invalid_submission")
        self.assertTrue(any("unknown action keys" in e for e in env.grader_report()["errors"]))


def load(name):
    return load_episode(TRAIN / name)


class VerifySurvivors(unittest.TestCase):
    def setUp(self):
        self.ep = load("t03_duplicate")

    def test_a_colon_in_an_id_is_an_error(self):  # verify-colon-in-id
        ep = copy.deepcopy(self.ep)
        self.assertEqual(check_ids(ep), [])
        ep.invoices[0]["invoice_id"] = "BILL:1"
        self.assertTrue(any("contains ':'" in e for e in check_ids(ep)))

    def test_one_id_in_two_tables_is_an_error(self):  # verify-duplicate-id
        ep = copy.deepcopy(self.ep)
        ep.payments[0]["payment_id"] = ep.invoices[0]["invoice_id"]
        self.assertTrue(any("used in" in e for e in check_ids(ep)))

    def test_manifest_record_counts_must_match(self):  # verify-record-counts
        ep = copy.deepcopy(self.ep)
        self.assertEqual(check_records_schema(ep), [])
        ep.manifest["record_counts"]["ledger"] += 1
        self.assertIn("manifest record_counts.ledger mismatch", check_records_schema(ep))

    def found(self, **over):
        f = {"type": "wrong_fx_rate", "affected_ids": ["INV-9"], "amount": 3177, "currency": "EUR",
             "evidence_sets": [["D9", "L9"]]}
        f.update(over)
        return {"anomalies": [], "findings": [f]}

    def test_auditor_and_key_must_agree_on_amount_currency_and_evidence(self):  # verify-amount-mismatch, verify-evidence-sets
        key = {"issues": [issue("iss_01")]}
        self.assertEqual(compare_with_truth(self.found(), key), [])
        self.assertTrue(any(e.startswith("amount mismatch") for e in compare_with_truth(self.found(amount=3178), key)))
        self.assertTrue(any(e.startswith("currency mismatch") for e in compare_with_truth(self.found(currency="USD"), key)))
        self.assertTrue(any(e.startswith("evidence sets differ")
                            for e in compare_with_truth(self.found(evidence_sets=[["D9", "L8"]]), key)))
        # the same sets in another order are the same sets
        self.assertEqual(compare_with_truth(self.found(evidence_sets=[["L9", "D9"]]), key), [])

    def test_the_budget_counts_the_submit_step(self):  # verify-budget-bound
        pages = sum(-(-len(self.ep.table(t)) // 50) for t in ("ledger", "invoices", "payments", "fx"))
        self.assertEqual(check_budget(self.ep, pages + 1), [])
        self.assertTrue(check_budget(self.ep, pages))

    def test_a_touched_ledger_row_needs_an_untouched_twin(self):  # verify-surface-pattern
        ep = copy.deepcopy(self.ep)
        row = ep.ledger[0]
        ep.provenance = {"ops": [{"table": "ledger", "op": "set", "id": row["row_id"]}]}
        self.assertEqual(check_surface(ep), [])
        row["account"] = "9999"
        self.assertTrue(any("has a pattern no untouched row has" in e for e in check_surface(ep)))

    def test_every_leak_marker_is_caught(self):  # verify-leak-marker
        self.assertEqual(check_leaks(self.ep), [])
        published = ("iss_", "duplicate_of", "provenance", "truth.json", "injected", "expected_amount")
        self.assertEqual(LEAK_MARKERS, published)
        for marker in published:
            ep = copy.deepcopy(self.ep)
            ep.manifest["note"] = f"text with {marker.upper()} inside"
            self.assertTrue(any(repr(marker) in e for e in check_leaks(ep)), marker)


def evidence_case(name, issue_index=0, set_index=0):
    ep = load(name)
    t = ep.truth["issues"][issue_index]
    return copy.deepcopy(ep), t["type"], list(t["evidence_sets"][set_index])


def derive(ep, type_, es):
    return evidence_check.derive_from_evidence(type_, es, ep)


class EvidenceSurvivors(unittest.TestCase):
    def test_the_derivation_baseline(self):
        for name in ("t03_duplicate", "t04_unallocated", "t05_fx_rate", "t06_period"):
            ep, type_, es = evidence_case(name)
            self.assertIsNotNone(derive(ep, type_, es), name)

    def test_the_fx_tolerance_is_two_minor_units_inclusive(self):  # evidence-fx-tolerance
        ep, type_, es = evidence_case("t05_fx_rate")
        row = next(r for r in ep.ledger if r["row_id"] in es)
        column = "debit_minor" if row["debit_minor"] else "credit_minor"
        posted = row[column]
        delta = derive(ep, type_, es)[2]
        self.assertGreater(delta, 10)
        silent = []
        for base in (posted - delta, posted + delta):  # one of the two is the expected amount
            for v in range(base - 4, base + 5):
                row[column] = v
                got = derive(ep, type_, es)
                if got is None:
                    silent.append(v)
                else:
                    self.assertEqual(got[2], abs(got[2]))
        self.assertEqual(len(silent), 5, silent)
        self.assertEqual(max(silent) - min(silent), 4, silent)

    def test_an_evidence_id_that_names_no_record_derives_nothing(self):  # evidence-uncited-record
        ep, type_, es = evidence_case("t03_duplicate")
        self.assertIsNone(derive(ep, type_, es + ["NO-SUCH-RECORD"]))

    def test_duplicate_rows_must_share_the_account(self):  # evidence-duplicate-account
        ep, type_, es = evidence_case("t03_duplicate")
        rows = [r for r in ep.ledger if r["row_id"] in es]
        self.assertEqual(len(rows), 2)
        rows[1]["account"] = "9999"
        self.assertIsNone(derive(ep, type_, es))

    def test_duplicate_invoices_must_share_the_signature(self):  # evidence-duplicate-signature
        ep, type_, es = evidence_case("t03_duplicate")
        docs = [d for d in ep.invoices if d["doc_id"] in es]
        self.assertEqual(len(docs), 2)
        docs[1]["total_minor"] += 1
        self.assertIsNone(derive(ep, type_, es))

    def test_an_unallocated_payment_row_sits_in_account_2900(self):  # evidence-unallocated-account
        ep, type_, es = evidence_case("t04_unallocated")
        row = next(r for r in ep.ledger if r["row_id"] in es)
        self.assertEqual(row["account"], "2900")
        row["account"] = "1000"
        self.assertIsNone(derive(ep, type_, es))

    def test_a_posting_at_the_period_end_instant_is_outside_the_period(self):  # evidence-period-boundary
        ep, type_, es = evidence_case("t06_period")
        period = ep.policy["reporting_period"]
        doc = next(d for d in ep.invoices if d["doc_id"] in es)
        row = next(r for r in ep.ledger if r["row_id"] in es)
        doc["issued_at"], row["timestamp"] = period["start"], period["end"]
        self.assertEqual(derive(ep, type_, es)[0], "wrong_period")
        row["timestamp"] = period["start"]  # same period on both sides: nothing wrong
        self.assertIsNone(derive(ep, type_, es))

    def test_an_offset_change_applies_at_its_own_instant(self):  # evidence-offset-start
        schedule = [{"from_utc": "2027-01-01T00:00:00Z", "offset": "+00:00"},
                    {"from_utc": "2027-03-01T22:30:00Z", "offset": "+02:00"}]
        before = parse_ts("2027-03-01T22:29:59Z")
        at = parse_ts("2027-03-01T22:30:00Z")
        self.assertEqual(evidence_check._local_date(before, schedule).isoformat(), "2027-03-01")
        self.assertEqual(evidence_check._local_date(at, schedule).isoformat(), "2027-03-02")


def action_line(action_json: str) -> str:
    return '{"type":"action","action":' + action_json + "}"


def submit_line(extra: str = "") -> str:
    return action_line('{"action":"submit"' + extra + "}")


class ProtocolBoundSurvivors(unittest.TestCase):
    def kind(self, line):
        return protocol.parse_agent_line(line)[0]

    def test_a_line_of_exactly_max_line_characters(self):  # protocol-max-line
        line = submit_line()
        self.assertEqual(self.kind(line + " " * (protocol.MAX_LINE - len(line))), "action")
        self.assertEqual(self.kind(line + " " * (protocol.MAX_LINE + 1 - len(line))), "malformed")

    def test_nesting_of_exactly_max_depth(self):  # protocol-max-depth
        def nested(levels):
            return action_line("[" * levels + "]" * levels)
        self.assertEqual(self.kind(nested(protocol.MAX_DEPTH - 1)), "action")
        self.assertEqual(self.kind(nested(protocol.MAX_DEPTH)), "malformed")

    def test_exactly_max_nodes_values(self):  # protocol-max-nodes
        def with_values(n):  # five nodes of the envelope and the submit, then n zeros
            return submit_line(',"pad":[' + ",".join("0" * n) + "]")
        self.assertEqual(self.kind(with_values(protocol.MAX_NODES - 5)), "action")
        self.assertEqual(self.kind(with_values(protocol.MAX_NODES - 4)), "malformed")

    def test_separators_inside_a_string_count_against_the_node_limit(self):  # protocol-separator-count
        self.assertEqual(self.kind(submit_line(',"s":"' + "," * (protocol.MAX_NODES - 10) + '"')), "action")
        self.assertEqual(self.kind(submit_line(',"s":"' + "," * (protocol.MAX_NODES + 1) + '"')), "malformed")

    def test_an_integer_literal_of_exactly_max_digits(self):  # protocol-max-digits
        n = protocol.MAX_NUMBER_CHARS
        self.assertEqual(self.kind(submit_line(',"n":' + "9" * n)), "action")
        self.assertEqual(self.kind(submit_line(',"n":' + "9" * (n + 1))), "malformed")

    def test_a_float_literal_of_exactly_max_characters(self):  # protocol-max-float
        n = protocol.MAX_FLOAT_CHARS
        self.assertEqual(self.kind(submit_line(',"x":0.' + "0" * (n - 2))), "action")
        self.assertEqual(self.kind(submit_line(',"x":0.' + "0" * (n - 1))), "malformed")

    def test_a_non_submit_line_of_exactly_the_size_limit(self):  # protocol-nonsubmit-size
        line = action_line('{"action":"calculator","expression":"1"}')
        limit = protocol.MAX_NONSUBMIT_CHARS
        self.assertEqual(self.kind(line + " " * (limit - len(line))), "action")
        self.assertEqual(self.kind(line + " " * (limit + 1 - len(line))), "malformed")
        big_submit = submit_line()
        self.assertEqual(self.kind(big_submit + " " * (limit + 1 - len(big_submit))), "action")

    def test_nan_and_infinity_are_not_numbers(self):  # protocol-nan
        for token in ("NaN", "Infinity", "-Infinity"):
            self.assertEqual(self.kind(action_line('{"action":"calculator","expression":' + token + "}")), "malformed", token)

    def test_the_echo_of_a_malformed_line_is_bounded(self):  # protocol-echo-length
        kind, echo = protocol.parse_agent_line("x" * 1000)
        self.assertEqual((kind, len(echo)), ("malformed", protocol.ECHO_CHARS))

    def test_a_lone_surrogate_in_an_action_is_malformed(self):  # protocol-surrogate
        line = action_line('{"action":"calculator","expression":"\\ud800"}')
        self.assertEqual(self.kind(line), "malformed")


if __name__ == "__main__":
    unittest.main()
