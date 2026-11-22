"""judge_adapter.py against the check definitions of https://genesis-exe.com/fintech-checks.html.

C01-C20 contract tests, the twenty matcher and reward tests of block 3 and the open examples M01-M12, on fixtures built
here from a generated episode (the closed truth is replaced by the single issue A of the definitions).
"""

import copy
import json
import shutil
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import judge_adapter as ja  # noqa: E402


def reward_for(f1: Fraction, steps: int) -> float:
    return float(max(Fraction(-1), min(Fraction(1), 2 * f1 - 1 - Fraction(2, 1000) * steps)))


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.base = Path(cls._tmp.name) / "base"
        ja.generate_episode(4611686018427387905, {"size": "small", "errors": {"wrong_period": 1}}, str(cls.base))
        cls.truth = json.loads((cls.base / "truth.json").read_text(encoding="utf-8"))
        invoices = [json.loads(ln) for ln in (cls.base / "invoices.jsonl").read_text(encoding="utf-8").splitlines()]
        payments = [json.loads(ln) for ln in (cls.base / "payments.jsonl").read_text(encoding="utf-8").splitlines()]
        cls.D1, cls.D3 = invoices[0]["doc_id"], invoices[1]["doc_id"]
        cls.D2 = payments[0]["doc_id"]
        cls.R = [i["invoice_id"] for i in invoices[:5]]
        cls.U = "ZZZ-NOT-A-RECORD"
        cls.eid = cls.truth["episode_id"]

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def fixture(self, issues, tolerance=None):
        """A copy of the base episode whose truth holds exactly `issues` (list of (type, affected_ids))."""
        out = Path(self._tmp.name) / f"fx{len(list(Path(self._tmp.name).iterdir()))}"
        shutil.copytree(self.base, out)
        truth = copy.deepcopy(self.truth)
        truth["issues"] = []
        for n, (typ, ids) in enumerate(issues, 1):
            issue = {"issue_id": f"iss_{n:02d}", "type": typ, "affected_ids": list(ids), "expected_amount_minor": 10000,
                     "currency": "KZT", "evidence_sets": [[self.D1, self.D2]]}
            if tolerance is not None:
                issue["tolerance_minor"] = tolerance
            truth["issues"].append(issue)
        (out / "truth.json").write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8", newline="\n")
        return str(out)

    def finding(self, typ="wrong_period", ids=None, amount=10000, currency="KZT", evidence=None):
        return {"type": typ, "affected_ids": list(ids if ids is not None else [self.R[0]]), "claimed_amount_minor": amount,
                "currency": currency, "evidence_ids": list(evidence if evidence is not None else [self.D1, self.D2]),
                "explanation": "short"}

    def score(self, directory, findings, steps=10):
        return ja.score_episode(directory, {"episode_id": self.eid, "findings": findings}, steps)

    def assertScore(self, res, tp, fp, fn, f1, steps=10):
        self.assertEqual((res["tp"], res["fp"], res["fn"]), (tp, fp, fn), res)
        self.assertAlmostEqual(res["f1"], float(f1), places=9)
        self.assertAlmostEqual(res["return"], reward_for(Fraction(f1).limit_denominator(10 ** 6), steps), places=9)


class MatcherAndRewardTests(Base):
    def test_01_one_correct_finding(self):
        d = self.fixture([("wrong_period", [self.R[0]])])
        r = self.score(d, [self.finding()])
        self.assertScore(r, 1, 0, 0, 1)
        self.assertAlmostEqual(r["return"], 0.98, places=9)

    def test_02_empty_findings_on_one_error(self):
        d = self.fixture([("wrong_period", [self.R[0]])])
        r = self.score(d, [])
        self.assertScore(r, 0, 0, 1, 0)
        self.assertEqual(r["return"], -1)

    def test_03_empty_key_and_empty_findings(self):
        d = self.fixture([])
        r = self.score(d, [])
        self.assertScore(r, 0, 0, 0, 1)
        self.assertAlmostEqual(r["return"], 0.98, places=9)

    def test_04_empty_key_one_false_finding(self):
        r = self.score(self.fixture([]), [self.finding()])
        self.assertScore(r, 0, 1, 0, 0)
        self.assertEqual(r["return"], -1)

    def test_05_duplicated_finding(self):
        d = self.fixture([("wrong_period", [self.R[0]])])
        r = self.score(d, [self.finding(), self.finding()])
        self.assertEqual((r["tp"], r["fp"], r["fn"]), (1, 1, 0))
        self.assertAlmostEqual(r["precision"], 0.5)
        self.assertAlmostEqual(r["return"], 47 / 150, places=9)

    def test_06_to_11_one_wrong_field_is_one_fp_and_one_fn(self):
        d = self.fixture([("wrong_period", [self.R[0]])])
        cases = {
            "type": self.finding(typ="wrong_fx_rate"),
            "other existing record": self.finding(ids=[self.R[1]]),
            "amount 10001 at tolerance 0": self.finding(amount=10001),
            "currency": self.finding(currency="USD"),
            "only D1": self.finding(evidence=[self.D1]),
            "missing evidence id instead of D2": self.finding(evidence=[self.D1, self.U]),
        }
        for name, f in cases.items():
            with self.subTest(name):
                r = self.score(d, [f])
                self.assertScore(r, 0, 1, 1, 0)
                self.assertEqual(r["return"], -1)

    def test_12_flagging_every_record_with_every_type(self):
        d = self.fixture([("wrong_period", [self.R[0]])])
        types = ["duplicate_invoice", "unallocated_payment", "wrong_fx_rate", "wrong_period"]
        findings = [self.finding(typ=t, ids=[r]) for r in self.R for t in types]
        self.assertEqual(len(findings), 20)
        r = self.score(d, findings)
        self.assertEqual((r["tp"], r["fp"], r["fn"]), (1, 19, 0))
        self.assertAlmostEqual(r["return"], -871 / 1050, places=9)

    def test_13_14_two_errors(self):
        d = self.fixture([("wrong_period", [self.R[0]]), ("wrong_fx_rate", [self.R[1]])])
        r = self.score(d, [self.finding()])
        self.assertEqual((r["tp"], r["fp"], r["fn"]), (1, 0, 1))
        self.assertAlmostEqual(r["return"], 47 / 150, places=9)
        r = self.score(d, [self.finding(), self.finding(typ="duplicate_invoice", ids=[self.R[3]])])
        self.assertEqual((r["tp"], r["fp"], r["fn"]), (1, 1, 1))
        self.assertAlmostEqual(r["return"], -0.02, places=9)

    def test_15_to_17_inspection_steps(self):
        d = self.fixture([("wrong_period", [self.R[0]])])
        for steps, want in ((0, 1.0), (50, 0.90), (100, 0.80)):
            with self.subTest(steps=steps):
                self.assertAlmostEqual(self.score(d, [self.finding()], steps)["return"], want, places=9)

    def test_18_to_20_limits_are_a_structural_error(self):
        d = self.fixture([("wrong_period", [self.R[0]])])
        ok = self.finding()
        too_many = [dict(ok) for _ in range(31)]
        many_evidence = dict(ok, evidence_ids=[self.D1, self.D2] + [f"X{i}" for i in range(9)])
        long_text = dict(ok, explanation="a" * 1001)
        for name, findings in (("31 findings", too_many), ("11 evidence ids", [many_evidence]), ("1001 characters", [long_text])):
            with self.subTest(name):
                r = self.score(d, findings)
                self.assertEqual(r["return"], -1)
                self.assertTrue(all(r[k] is None for k in ("tp", "fp", "fn", "precision", "recall", "f1")), r)

    def test_exactly_the_limits_are_valid(self):
        d = self.fixture([("wrong_period", [self.R[0]])])
        r = self.score(d, [dict(self.finding(), evidence_ids=[self.D1, self.D2] + [self.D3] + [self.R[2]] * 0,
                                explanation="a" * 1000)])
        self.assertEqual(r["tp"], 1)

    # ----------------------------------------------------------------------------------- M01-M12
    def test_m01_duplicate_ids_inside_the_list_are_one_set(self):
        d = self.fixture([("wrong_period", [self.R[0], self.R[1]])])
        self.assertEqual(self.score(d, [self.finding(ids=[self.R[1], self.R[0], self.R[0]])])["tp"], 1)

    def test_m02_an_extra_existing_record_is_a_miss(self):
        d = self.fixture([("wrong_period", [self.R[0], self.R[1]])])
        r = self.score(d, [self.finding(ids=[self.R[0], self.R[1], self.R[2]])])
        self.assertEqual((r["tp"], r["fp"], r["fn"]), (0, 1, 1))

    def test_m03_extra_existing_evidence_is_allowed(self):
        d = self.fixture([("wrong_period", [self.R[0]])])
        self.assertEqual(self.score(d, [self.finding(evidence=[self.D2, self.D1, self.D3])])["tp"], 1)

    def test_m04_a_nonexistent_evidence_id_makes_the_finding_unmatched(self):
        d = self.fixture([("wrong_period", [self.R[0]])])
        r = self.score(d, [self.finding(evidence=[self.D1, self.D2, self.U])])
        self.assertEqual((r["tp"], r["fp"], r["fn"]), (0, 1, 1))

    def test_m05_eleven_evidence_ids_with_repeats_is_structural(self):
        d = self.fixture([("wrong_period", [self.R[0]])])
        r = self.score(d, [self.finding(evidence=[self.D1] * 10 + [self.D2])])
        self.assertEqual(r["return"], -1)
        self.assertIsNone(r["tp"])

    def test_m06_currency_is_compared_exactly(self):
        d = self.fixture([("wrong_period", [self.R[0]])])
        for code in ("kzt", "KZT ", " KZT"):
            with self.subTest(code=code):
                r = self.score(d, [self.finding(currency=code)])
                self.assertEqual((r["tp"], r["fp"], r["fn"]), (0, 1, 1))

    def test_m07_m08_tolerance_is_the_fixtures_own(self):
        r = self.score(self.fixture([("wrong_period", [self.R[0]])]), [self.finding(amount=10001)])
        self.assertEqual(r["tp"], 0)
        d = self.fixture([("wrong_period", [self.R[0]])], tolerance=1)
        self.assertEqual(self.score(d, [self.finding(amount=10001)])["tp"], 1)
        self.assertEqual(self.score(d, [self.finding(amount=10002)])["tp"], 0)

    def test_m09_amount_as_string_or_bool_is_structural(self):
        d = self.fixture([("wrong_period", [self.R[0]])])
        for bad in ("10000", True):
            with self.subTest(amount=bad):
                self.assertEqual(self.score(d, [self.finding(amount=bad)])["return"], -1)

    def test_m10_m11_the_matching_is_maximum_and_order_free(self):
        d = self.fixture([("wrong_period", [self.R[0]]), ("wrong_period", [self.R[1]])])
        f_a = self.finding(ids=[self.R[0]])
        f_b = self.finding(ids=[self.R[1]])
        for order in ((f_a, f_b), (f_b, f_a)):
            r = self.score(d, list(order))
            self.assertEqual((r["tp"], r["fp"], r["fn"]), (2, 0, 0))

    def test_m12_two_identical_correct_findings(self):
        d = self.fixture([("wrong_period", [self.R[0]])])
        r = self.score(d, [self.finding(), self.finding()])
        self.assertEqual((r["tp"], r["fp"], r["fn"]), (1, 1, 0))


class ContractTests(Base):
    def env(self, closed=True):
        env = ja.make_env()
        obs, info = env.reset(0, {"mode": "closed" if closed else "train", "episode_dir": self.fixture([("wrong_period", [self.R[0]])]),
                                  "team_config": {}})
        return env, obs, info

    def step(self, env, name, **args):
        return env.step({"name": name, "args": args})

    def test_c01_c02_reset_pair_and_first_observation(self):
        env, obs, info = self.env()
        json.dumps([obs, info])
        self.assertEqual(set(obs), {"task", "manifest", "policy", "remaining_steps"})
        self.assertEqual(obs["remaining_steps"], 100)
        self.assertEqual(info, {"episode_id": self.eid})
        text = json.dumps(obs)
        self.assertNotIn("expected_amount_minor", text)
        self.assertNotIn("evidence_sets", text)

    def test_c03_manifest(self):
        _env, obs, _info = self.env()
        m = obs["manifest"]
        for key in ("schema_version", "episode_id", "base_currency", "period_start", "period_end", "timezone", "rounding"):
            self.assertIn(key, m)
        self.assertTrue(any(k in m for k in ("record_counts", "document_counts")))

    def test_c04_step_tuple_types(self):
        env, _o, _i = self.env()
        obs, reward, terminated, truncated, info = self.step(env, "list_records", table="ledger", cursor=None, limit=5)
        self.assertIs(type(terminated), bool)
        self.assertIs(type(truncated), bool)
        self.assertEqual(set(obs), {"result", "error", "remaining_steps"})
        self.assertEqual(set(obs["result"]), {"records", "next_cursor"})
        json.dumps([obs, reward, info])

    def test_c05_c06_pages_cursors_and_stability(self):
        env, _o, _i = self.env()
        seen, cursor, pages = [], None, 0
        while True:
            obs = self.step(env, "list_records", table="ledger", cursor=cursor, limit=50)[0]
            rows = obs["result"]["records"]
            self.assertLessEqual(len(rows), 50)
            seen += [r["row_id"] for r in rows]
            pages += 1
            cursor = obs["result"]["next_cursor"]
            if cursor is None:
                break
        self.assertGreater(pages, 2)
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(len(seen), len((self.base / "ledger.csv").read_text(encoding="utf-8").splitlines()) - 1)
        again = self.step(env, "list_records", table="ledger", cursor="50", limit=50)[0]["result"]["records"]
        twice = self.step(env, "list_records", table="ledger", cursor="50", limit=50)[0]["result"]["records"]
        self.assertEqual(again, twice)

    def test_c07_c08_get_record_and_document(self):
        env, _o, _i = self.env()
        rec = self.step(env, "get_record", table="invoices", id=self.R[0])[0]
        self.assertEqual(rec["result"]["invoice_id"], self.R[0])
        doc = self.step(env, "get_document", doc_id=self.D2)[0]
        self.assertEqual(doc["result"]["doc_id"], self.D2)
        self.assertIsNone(doc["error"])

    def test_c09_c10_calculator(self):
        env, _o, _i = self.env()
        obs = self.step(env, "calculator", expression="0.1+0.2")[0]
        self.assertEqual(obs["result"], "0.3")
        bad = self.step(env, "calculator", expression="open('/etc/passwd').read()")[0]
        self.assertIsNone(bad["result"])
        self.assertIsNotNone(bad["error"])

    def test_c11_to_c14_errors_cost_a_step(self):
        env, _o, _i = self.env()
        left = 100
        for name, args in (("get_record", {"table": "invoices", "id": self.U}), ("get_document", {"doc_id": self.U}),
                           ("no_such_action", {}), ("list_records", {"table": "ledger", "cursor": None, "limit": 3})):
            obs, reward, terminated, truncated, _info = self.step(env, name, **args)
            left -= 1
            self.assertEqual(obs["remaining_steps"], left, name)
            self.assertFalse(terminated or truncated)
        self.assertIsNotNone(self.step(env, "get_record", table="invoices", id=self.U)[0]["error"])

    def test_c15_submit_ends_and_later_actions_change_nothing(self):
        env, _o, info = self.env()
        obs, reward, terminated, truncated, info = self.step(env, "submit", findings={"episode_id": self.eid, "findings": []})
        self.assertEqual(obs["result"], {"accepted": True})
        self.assertTrue(terminated)
        self.assertFalse(truncated)
        later = self.step(env, "list_records", table="ledger", cursor=None, limit=5)
        self.assertTrue(later[2])
        self.assertEqual(later[1], 0)

    def test_c16_submit_as_the_hundredth_action(self):
        env, _o, _i = self.env(closed=False)
        for _ in range(99):
            self.step(env, "calculator", expression="1+1")
        obs, reward, terminated, truncated, info = self.step(env, "submit", findings={"episode_id": self.eid, "findings": []})
        self.assertTrue(terminated)
        self.assertFalse(truncated)
        self.assertEqual(info["final"]["status"], "submitted")
        self.assertAlmostEqual(reward, -1.0)  # one error in the key, empty answer

    def test_c17_hundred_explorations_truncate(self):
        env, _o, _i = self.env(closed=False)
        for _ in range(100):
            obs, reward, terminated, truncated, info = self.step(env, "calculator", expression="1+1")
        self.assertTrue(truncated)
        self.assertFalse(terminated)
        self.assertEqual(info["final"]["tp"], 0)
        self.assertEqual(self.step(env, "calculator", expression="1+1")[3], True)

    def test_c18_time_limit_truncates_with_an_empty_answer(self):
        now = [0.0]
        env = ja.JudgeEnv(clock=lambda: now[0])
        env.reset(0, {"mode": "train", "episode_dir": self.fixture([("wrong_period", [self.R[0]])]), "team_config": {}})
        self.step(env, "calculator", expression="1+1")
        now[0] = 61.0
        obs, reward, terminated, truncated, info = self.step(env, "calculator", expression="1+1")
        self.assertTrue(truncated)
        self.assertFalse(terminated)
        self.assertEqual(info["final"]["tp"], 0)

    def test_c19_closed_mode_keeps_the_reward_with_the_grader(self):
        env, _o, _i = self.env()
        for _ in range(3):
            obs, reward, terminated, truncated, info = self.step(env, "list_records", table="payments", cursor=None, limit=5)
            self.assertEqual(reward, 0)
            self.assertEqual(info, {"episode_id": self.eid})
        obs, reward, terminated, truncated, info = self.step(env, "submit", findings={"episode_id": self.eid, "findings": [self.finding()]})
        self.assertTrue(terminated)
        self.assertIn(type(reward), (int, float))
        self.assertEqual(reward, 0)
        self.assertEqual(info, {"episode_id": self.eid})
        self.assertNotIn("tp", json.dumps(obs))

    def test_c20_no_key_data_in_any_channel(self):
        env, obs0, info0 = self.env()
        blobs = [json.dumps([obs0, info0])]
        for table in ("ledger", "invoices", "payments", "fx"):
            cursor = None
            while True:
                obs, reward, _t, _tr, info = self.step(env, "list_records", table=table, cursor=cursor, limit=50)
                blobs.append(json.dumps([obs, reward, info]))
                cursor = obs["result"]["next_cursor"]
                if cursor is None:
                    break
        blobs.append(json.dumps(self.step(env, "get_record", table="ledger", id="../grader/x")))
        blobs.append(json.dumps(self.step(env, "calculator", expression="__import__('os')")))
        text = "\n".join(blobs)
        prov = json.loads((self.base / "provenance.json").read_text(encoding="utf-8"))
        for needle in ("expected_amount_minor", "evidence_sets", "acceptable", '"injections"', "provenance", prov["seed"]):
            self.assertNotIn(needle, text)

    def test_train_mode_without_episode_dir_generates_from_seed_and_team_config(self):
        env = ja.make_env()
        obs, info = env.reset(5, {"mode": "train", "team_config": {"size": "small", "errors": {}}})
        self.assertEqual(obs["remaining_steps"], 100)
        self.assertIn("episode_id", info)

    def test_flat_and_repository_layouts_score_alike(self):
        from auditgym.episode import load_episode  # noqa: F401  (the repository layout is public/ + grader/)

        src = ROOT / "episodes" / "train" / "t03_duplicate"
        truth = json.loads((src / "grader" / "truth.json").read_text(encoding="utf-8"))
        res = ja.score_episode(str(src), {"episode_id": truth["episode_id"], "findings": []}, 3)
        self.assertEqual(res["fn"], len(truth["issues"]))


class PairedTests(Base):
    def test_oracle_result_is_the_same_on_a_file_transformed_copy(self):
        """The judge transforms a copy of the files (order, IDs); the oracle's findings, mapped to the new IDs, score alike."""
        d = self.fixture([("wrong_period", [self.R[0]])])
        before = self.score(d, [self.finding()], 4)
        # a remap of every ID by the same prefix in all files and in the closed truth, as a judge-side copy would do
        suffix = "-X"
        new = Path(self._tmp.name) / "remapped"
        shutil.copytree(d, new)
        old_ids = {self.R[0], self.D1, self.D2}
        for name in ("invoices.jsonl", "payments.jsonl", "ledger.csv", "truth.json", "provenance.json"):
            p = new / name
            text = p.read_text(encoding="utf-8")
            for i in sorted(old_ids, key=len, reverse=True):
                text = text.replace(f'"{i}"', f'"{i}{suffix}"') if name.endswith("json") or name.endswith("jsonl") else text.replace(i, i + suffix)
            p.write_text(text, encoding="utf-8", newline="\n")
        mapped = self.finding(ids=[self.R[0] + suffix], evidence=[self.D1 + suffix, self.D2 + suffix])
        after = ja.score_episode(str(new), {"episode_id": self.eid, "findings": [mapped]}, 4)
        self.assertEqual({k: before[k] for k in ("tp", "fp", "fn", "f1", "return")}, {k: after[k] for k in ("tp", "fp", "fn", "f1", "return")})


if __name__ == "__main__":
    unittest.main()
