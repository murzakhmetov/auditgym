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

    def test_generated_seed_must_be_a_plain_int(self):
        cfg = {"generator": {"size": "small"}}
        for bad in ("1", 1.0, 1.5, True, False, "abc", [1], b"1"):
            with self.subTest(seed=bad):
                with self.assertRaises(TypeError) as cm:
                    AuditEnv().reset(seed=bad, config=cfg)
                self.assertIn(type(bad).__name__, str(cm.exception))

    def test_negative_and_large_int_seeds_stay_valid(self):
        for seed in (-5, 0, 2 ** 80):
            obs, _ = AuditEnv().reset(seed=seed, config={"generator": {"size": "small"}})
            self.assertIn("episode_id", obs["manifest"])

    def test_seed_check_does_not_touch_loaded_episodes(self):
        obs, _ = AuditEnv().reset(seed="ignored", config={"episode": episode()})
        self.assertEqual(obs["manifest"]["episode_id"], episode().episode_id)

    def test_stray_key_next_to_generator_is_rejected(self):
        with self.assertRaises(ValueError) as cm:
            AuditEnv().reset(seed=1, config={"generator": {"size": "small"}, "size": "large", "errors": {}})
        self.assertIn("errors, size", str(cm.exception))

    def test_generator_with_reset_keys_is_fine(self):
        obs, _ = AuditEnv().reset(seed=3, config={"generator": {"size": "small"}, "transform": {"permute_seed": 1}})
        self.assertIn("episode_id", obs["manifest"])

    def test_flat_generator_config_still_works(self):
        a, _ = AuditEnv().reset(seed=3, config={"size": "small"})
        b, _ = AuditEnv().reset(seed=3, config={"generator": {"size": "small"}})
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

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


class ResetConfigTypes(unittest.TestCase):
    def test_episode_must_be_an_episode(self):
        for bad in (None, {}, "ep", 5, episode().manifest):
            with self.subTest(bad=type(bad).__name__):
                with self.assertRaises(TypeError) as cm:
                    AuditEnv().reset(seed=1, config={"episode": bad})
                self.assertIn('"episode"', str(cm.exception))
                self.assertIn("Episode", str(cm.exception))

    def test_generator_must_be_a_dict(self):
        for bad in (None, [], "small", 3):
            with self.subTest(bad=type(bad).__name__):
                with self.assertRaises(TypeError) as cm:
                    AuditEnv().reset(seed=1, config={"generator": bad})
                self.assertIn('"generator"', str(cm.exception))

    def test_valid_forms_keep_working(self):
        obs, _ = AuditEnv().reset(config={"episode": episode()})
        self.assertIn("episode_id", obs["manifest"])
        obs, _ = AuditEnv().reset(seed=3, config={"size": "small"})
        self.assertIn("episode_id", obs["manifest"])
        obs, _ = AuditEnv().reset(seed=3, config={"generator": {"size": "small"}})
        self.assertIn("episode_id", obs["manifest"])
        obs, _ = AuditEnv().reset(seed=3, config={"generator": {}})
        self.assertIn("episode_id", obs["manifest"])


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


class WeakSeedInEvalMode(unittest.TestCase):
    """A small seed without a secret can be recovered from the public episode_id, so eval mode refuses to generate
    from one unless the env was built with allow_weak_seed=True. Train mode is unchanged."""

    CONFIG = {"size": "small"}

    def test_jurors_probe_recover_a_13_bit_seed_from_the_episode_id(self):
        """Juror b's probe: reset an env with examples/config_mixed.json, read info['episode_id'], recover the seed by
        brute force with episode_id_for. In eval mode the reset itself now refuses the small seed."""
        from pathlib import Path

        from auditgym.generator import episode_id_for

        cfg = json.loads((Path(__file__).resolve().parent.parent / "examples" / "config_mixed.json").read_text(encoding="utf-8"))
        hidden = 4242  # 13 bits
        _obs, info = AuditEnv(mode="train").reset(seed=hidden, config=cfg)  # train mode is unchanged
        recovered = next(s for s in range(2 ** 13) if episode_id_for(s, cfg) == info["episode_id"])
        self.assertEqual(recovered, hidden)
        with self.assertRaises(ValueError) as cm:
            AuditEnv(mode="eval").reset(seed=hidden, config=cfg)
        for word in ("eval mode", "13 bits", "secret", "allow_weak_seed"):
            self.assertIn(word, str(cm.exception))
        with self.assertRaises(ValueError):
            AuditEnv(mode="eval").reset(seed=recovered, config=cfg)
        with self.assertRaises(ValueError):
            AuditEnv(mode="eval", secret="").reset(seed=hidden, config=cfg)  # an empty secret is no secret

    def test_boundary_is_two_to_the_40(self):
        env = AuditEnv(mode="eval")
        with self.assertRaises(ValueError):
            env.reset(seed=2 ** 40 - 1, config=self.CONFIG)
        with self.assertRaises(ValueError):
            env.reset(seed=-(2 ** 40 - 1), config=self.CONFIG)
        obs, _ = env.reset(seed=2 ** 40, config=self.CONFIG)
        self.assertIn("episode_id", obs["manifest"])

    def test_a_secret_the_override_and_train_mode_keep_small_seeds_working(self):
        for env in (AuditEnv(mode="eval", secret="host-secret"), AuditEnv(mode="eval", allow_weak_seed=True),
                    AuditEnv(mode="train")):
            obs, _ = env.reset(seed=7, config=self.CONFIG)
            self.assertIn("episode_id", obs["manifest"])

    def test_loaded_episodes_are_not_affected(self):
        obs, _ = AuditEnv(mode="eval").reset(seed=7, config={"episode": episode()})
        self.assertIn("episode_id", obs["manifest"])

    def test_the_limit_matches_the_run_command(self):
        from auditgym import __main__ as cli_mod
        from auditgym import check as check_mod
        from auditgym import env as env_mod

        self.assertEqual(env_mod.MIN_SEED_BITS, cli_mod.MIN_SEED_BITS)
        self.assertEqual(env_mod.MIN_SEED_BITS, check_mod.MIN_SEED_BITS)
