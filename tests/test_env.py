"""Environment contract: reset/step, limits, termination, invalid input, bounded errors, modes."""

import json
import unittest

from auditgym.env import AuditEnv
from auditgym.generator import generate_episode
from auditgym.policies.oracle import OraclePolicy

CFG = {"size": "small", "errors": {"duplicate_invoice": 1, "wrong_fx_rate": 1}}
_CACHE = {}


def episode(seed=101, cfg=None):
    key = (seed, json.dumps(cfg or CFG, sort_keys=True))
    if key not in _CACHE:
        _CACHE[key] = generate_episode(seed, cfg or CFG).episode
    return _CACHE[key]


def fresh(mode="train", **kw):
    env = AuditEnv(mode=mode, **kw)
    obs, info = env.reset(config={"episode": episode()})
    return env, obs, info


def oracle_submit(env):
    return OraclePolicy(env.episode.truth).act({"manifest": env.episode.manifest})


class ResetContract(unittest.TestCase):
    def test_reset_observation_fields(self):
        env, obs, info = fresh()
        self.assertEqual(set(obs), {"task", "manifest", "policy", "remaining_steps"})
        self.assertEqual(obs["remaining_steps"], 100)
        self.assertEqual(info["episode_id"], obs["manifest"]["episode_id"])
        text = json.dumps(obs)
        for marker in ("iss_", "evidence_sets", "expected_amount", "id_aliases", "provenance"):
            self.assertNotIn(marker, text)

    def test_reset_from_seed_is_reproducible(self):
        a, b = AuditEnv(), AuditEnv()
        oa, _ = a.reset(seed=77, config={"generator": {"size": "small"}})
        ob, _ = b.reset(seed=77, config={"generator": {"size": "small"}})
        self.assertEqual(json.dumps(oa, sort_keys=True), json.dumps(ob, sort_keys=True))

    def test_reset_isolates_state(self):
        env, _, _ = fresh()
        env.step({"action": "list_records", "table": "ledger"})
        env.step(oracle_submit(env))
        obs, _ = env.reset(config={"episode": episode()})
        self.assertEqual(obs["remaining_steps"], 100)
        o, r, term, trunc, _ = env.step({"action": "list_records", "table": "fx"})
        self.assertFalse(term or trunc)
        self.assertEqual(o["remaining_steps"], 99)

    def test_task_text_is_constant_across_episodes(self):
        e1 = AuditEnv()
        o1, _ = e1.reset(config={"episode": episode()})
        o2, _ = e1.reset(config={"episode": episode(202, {"size": "small"})})
        t1, t2 = dict(o1["task"]), dict(o2["task"])
        t1.pop("episode_id")
        t2.pop("episode_id")
        self.assertEqual(t1, t2)


class StepContract(unittest.TestCase):
    def test_step_tuple_and_observation_fields(self):
        env, _, _ = fresh()
        out = env.step({"action": "list_records", "table": "ledger", "cursor": None, "limit": 50})
        self.assertEqual(len(out), 5)
        obs, reward, term, trunc, info = out
        self.assertEqual(set(obs), {"result", "error", "remaining_steps"})
        self.assertEqual(reward, 0.0)
        self.assertFalse(term or trunc)
        self.assertLessEqual(len(obs["result"]["rows"]), 50)

    def test_pagination_is_stable_and_complete(self):
        env, _, _ = fresh()
        seen, cursor = [], None
        while True:
            obs, *_ = env.step({"action": "list_records", "table": "ledger", "cursor": cursor, "limit": 50})
            seen += [r["row_id"] for r in obs["result"]["rows"]]
            cursor = obs["result"]["next_cursor"]
            if cursor is None:
                break
        self.assertEqual(seen, [r["row_id"] for r in env.episode.ledger])
        a, *_ = env.step({"action": "list_records", "table": "ledger", "cursor": "50", "limit": 7})
        b, *_ = env.step({"action": "list_records", "table": "ledger", "cursor": "50", "limit": 7})
        self.assertEqual(a["result"]["rows"], b["result"]["rows"])

    def test_page_limit_is_50(self):
        env, _, _ = fresh()
        obs, *_ = env.step({"action": "list_records", "table": "ledger", "limit": 51})
        self.assertEqual(obs["error"]["code"], "bad_args")

    def test_get_record_document_and_calculator(self):
        env, _, _ = fresh()
        ep = env.episode
        inv = ep.invoices[0]
        obs, *_ = env.step({"action": "get_record", "table": "invoices", "id": inv["invoice_id"]})
        self.assertEqual(obs["result"]["record"], inv)
        obs, *_ = env.step({"action": "get_document", "doc_id": inv["doc_id"]})
        self.assertEqual(obs["result"]["document"], inv)
        fx = ep.fx[0]
        obs, *_ = env.step({"action": "get_record", "table": "fx", "id": f"{fx['date']}:{fx['source_currency']}:{fx['target_currency']}"})
        self.assertEqual(obs["result"]["record"], fx)
        obs, *_ = env.step({"action": "calculator", "expression": "(125000 - 92234) * 2"})
        self.assertEqual(obs["result"]["value"], "65532")

    def test_errors_are_bounded_and_consume_a_step(self):
        env, _, _ = fresh()
        cases = [
            ({"action": "drop_tables"}, "unknown_action"),
            ({"action": "get_record", "table": "truth", "id": "x"}, "unknown_table"),
            ({"action": "get_record", "table": "ledger", "id": "NOPE" * 100}, "unknown_id"),
            ({"action": "get_document", "doc_id": "../grader/truth.json"}, "unknown_id"),
            ({"action": "list_records", "table": "ledger", "cursor": "-1"}, "bad_cursor"),
            ({"action": "list_records", "table": "ledger", "cursor": "999999999"}, "bad_cursor"),
            ({"action": "calculator", "expression": "__import__('os').system('x')"}, "calc_error"),
            ({"action": "calculator", "expression": "1/0"}, "calc_error"),
            ({"action": "list_records", "table": "ledger", "sql": "select"}, "bad_args"),
            ("not even an object", "bad_args"),
            (None, "bad_args"),
        ]
        for i, (action, code) in enumerate(cases, start=1):
            obs, reward, term, trunc, _ = env.step(action)
            self.assertEqual(obs["error"]["code"], code)
            self.assertLessEqual(len(obs["error"]["message"]), 200)
            self.assertEqual(obs["remaining_steps"], 100 - i)
            self.assertEqual(reward, 0.0)
            self.assertNotIn("Traceback", json.dumps(obs))

    def test_nested_args_alias(self):
        env, _, _ = fresh()
        obs, *_ = env.step({"action": "list_records", "args": {"table": "fx", "cursor": None, "limit": 5}})
        self.assertIsNone(obs["error"])
        self.assertEqual(len(obs["result"]["rows"]), 5)

    def test_exploration_reward_is_zero(self):
        env, _, _ = fresh()
        for _ in range(5):
            _, r, *_ = env.step({"action": "list_records", "table": "invoices"})
            self.assertEqual(r, 0.0)


class Termination(unittest.TestCase):
    def test_submit_terminates_with_terminal_reward_in_train_mode(self):
        env, _, _ = fresh("train")
        env.step({"action": "list_records", "table": "invoices"})
        obs, r, term, trunc, info = env.step(oracle_submit(env))
        self.assertTrue(term)
        self.assertFalse(trunc)
        self.assertAlmostEqual(r, 1.0 - 0.002 * 1)
        self.assertEqual(info["final"]["tp"], len(env.episode.truth["issues"]))

    def test_eval_mode_returns_nothing_until_the_grader_is_asked(self):
        env, _, _ = fresh("eval")
        env.step({"action": "list_records", "table": "invoices"})
        obs, r, term, trunc, info = env.step(oracle_submit(env))
        self.assertTrue(term)
        self.assertEqual(r, 0.0)
        self.assertNotIn("final", info)
        self.assertEqual(env.grader_report()["reward"], 1.0 - 0.002)

    def test_step_limit_truncates_with_empty_answer(self):
        env, _, _ = fresh("train", max_steps=100)
        for i in range(99):
            _, _, term, trunc, _ = env.step({"action": "calculator", "expression": "1+1"})
            self.assertFalse(term or trunc)
        obs, r, term, trunc, info = env.step({"action": "calculator", "expression": "1+1"})
        self.assertTrue(trunc)
        self.assertFalse(term)
        self.assertEqual(obs["remaining_steps"], 0)
        g = env.grader_report()
        self.assertEqual(g["status"], "step_limit")
        self.assertEqual(g["n_findings"], 0)
        self.assertEqual(r, -1.0)

    def test_submit_as_the_100th_step_counts(self):
        env, _, _ = fresh("train")
        for _ in range(99):
            env.step({"action": "calculator", "expression": "2*2"})
        obs, r, term, trunc, _ = env.step(oracle_submit(env))
        self.assertTrue(term)
        self.assertFalse(trunc)
        self.assertAlmostEqual(r, 1.0 - 0.002 * 99)

    def test_time_limit_truncates(self):
        clock = [0.0]
        env = AuditEnv(mode="train", time_limit_s=60, clock=lambda: clock[0])
        env.reset(config={"episode": episode()})
        env.step({"action": "list_records", "table": "invoices"})
        clock[0] = 61.0
        obs, r, term, trunc, _ = env.step(oracle_submit(env))
        self.assertTrue(trunc)
        self.assertEqual(obs["error"]["code"], "time_limit")
        self.assertEqual(env.grader_report()["status"], "time_limit")
        self.assertEqual(env.grader_report()["n_findings"], 0)

    def test_invalid_submission_ends_with_minus_one(self):
        env, _, _ = fresh("train")
        obs, r, term, trunc, _ = env.step({"action": "submit", "findings": {"episode_id": "wrong", "findings": []}})
        self.assertTrue(term)
        self.assertEqual(r, -1.0)
        self.assertEqual(obs["error"]["code"], "invalid_submission")
        self.assertFalse(env.grader_report()["valid"])

    def test_resubmission_is_ignored(self):
        env, _, _ = fresh("train")
        env.step(oracle_submit(env))
        first = env.grader_report()
        obs, r, term, trunc, _ = env.step({"action": "submit", "findings": {"episode_id": env.episode.episode_id, "findings": []}})
        self.assertEqual(obs["error"]["code"], "episode_finished")
        self.assertEqual(r, 0.0)
        self.assertEqual(env.grader_report(), first)

    def test_empty_answer_on_clean_episode_is_rewarded(self):
        env = AuditEnv(mode="train")
        env.reset(config={"episode": episode(202, {"size": "small"})})
        _, r, term, _, _ = env.step({"action": "submit", "findings": {"episode_id": env.episode.episode_id, "findings": []}})
        self.assertTrue(term)
        self.assertEqual(r, 1.0)


if __name__ == "__main__":
    unittest.main()
