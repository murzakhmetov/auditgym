"""The in-process contract battery passes on a committed episode and fails on a broken environment."""

import time
import unittest
from unittest import mock

from auditgym import env as env_module
from auditgym.contract_battery import contract_battery
from auditgym.episode import load_episode
from auditgym.policies import SilentPolicy, make_policy
from auditgym.splits import EPISODES_DIR

EP_DIR = EPISODES_DIR / "dev" / "d03_duplicates_gbp"


class ContractBattery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ep = load_episode(EP_DIR)

    def test_passes_on_a_committed_episode_and_is_fast(self):
        t0 = time.monotonic()
        results = contract_battery(self.ep)
        self.assertLess(time.monotonic() - t0, 3.0)
        self.assertGreaterEqual(len(results), 18)
        self.assertEqual([r for r in results if not r[1]], [])
        self.assertEqual(len({label for label, _ok, _d in results}), len(results))

    def test_an_episode_with_an_empty_table_passes_every_check(self):
        from auditgym.generator import generate_episode

        ep = generate_episode(6602239917354212077, {"foreign_currencies": []}).episode
        self.assertEqual(ep.table("fx"), [])
        results = contract_battery(ep)
        self.assertEqual(len(results), 20)
        self.assertEqual([r for r in results if not r[1]], [])

    def test_the_fuzz_calls_the_empty_fx_table(self):
        from auditgym.generator import generate_episode

        ep = generate_episode(6602239917354212077, {"foreign_currencies": []}).episode
        sent = []
        real = env_module.AuditEnv.step

        def spy(self, action):
            if isinstance(action, dict):
                sent.append(action)
            return real(self, action)

        with mock.patch.object(env_module.AuditEnv, "step", spy):
            results = contract_battery(ep)
        self.assertEqual([r for r in results if not r[1]], [])
        fuzz = [r for r in results if "contract fuzz" in r[0]]
        self.assertEqual(len(fuzz), 1)
        for kind in ("list_records", "get_record"):
            hits = [a for a in sent if a.get("action") == kind and a.get("table") == "fx"]
            self.assertGreater(len(hits), 3, f"fuzz never sent {kind} for the empty fx table")

    def test_an_empty_sample_of_observations_does_not_validate_vacuously(self):
        with mock.patch("auditgym.contract_battery._observations", return_value=[]):
            failed = [label for label, ok, _d in contract_battery(self.ep) if not ok]
        self.assertTrue(any("sampled observations" in label for label in failed), failed)

    def test_a_broken_page_size_fails_a_named_check(self):
        def greedy(self, action):
            rows = self._episode.table(action["table"])
            return {"table": action["table"], "rows": rows, "next_cursor": None, "total": len(rows)}, None

        with mock.patch.object(env_module.AuditEnv, "_list_records", greedy):
            failed = [label for label, ok, _d in contract_battery(self.ep) if not ok]
        self.assertTrue(any("page" in label for label in failed), failed)

    def test_an_environment_that_leaks_reward_fails(self):
        real = env_module.AuditEnv._reward_out
        with mock.patch.object(env_module.AuditEnv, "_reward_out", lambda self: self._final["reward"] if self._done else real(self)):
            failed = [label for label, ok, _d in contract_battery(self.ep) if not ok]
        self.assertTrue(any("eval mode" in label for label in failed), failed)

    def test_an_environment_that_raises_fails_instead_of_crashing(self):
        with mock.patch.object(env_module.AuditEnv, "step", side_effect=TypeError("boom")):
            results = contract_battery(self.ep)
        failed = [label for label, ok, _d in results if not ok]
        self.assertTrue(any("ran to the end" in label for label in failed), failed)

    def test_a_cursor_that_ignores_its_value_fails(self):
        state = {"n": 0}
        real = env_module.AuditEnv._list_records

        def drifting(self, action):
            if action.get("cursor") is not None:
                state["n"] += 1
                action = {**action, "cursor": str(state["n"] * 50)}
            return real(self, action)

        with mock.patch.object(env_module.AuditEnv, "_list_records", drifting):
            failed = [label for label, ok, _d in contract_battery(self.ep) if not ok]
        self.assertTrue(any("cursor is stable" in label for label in failed), failed)

    def test_pages_with_duplicates_and_gaps_fail(self):
        real = env_module.AuditEnv._list_records

        def shuffled(self, action):
            res, err = real(self, action)
            if res and res["rows"] and action.get("cursor") is not None:
                res = {**res, "rows": res["rows"][:-1] + res["rows"][:1]}
            return res, err

        with mock.patch.object(env_module.AuditEnv, "_list_records", shuffled):
            failed = [label for label, ok, _d in contract_battery(self.ep) if not ok]
        self.assertTrue(any("paging reaches every row" in label for label in failed), failed)

    def test_truncation_one_step_early_fails(self):
        real = env_module.AuditEnv.step

        def early(self, action):
            out = real(self, action)
            if self._steps == self.max_steps - 1 and not self._done:
                self._finish(submission=None, truncated=True, reason="step_limit")
            return out

        with mock.patch.object(env_module.AuditEnv, "step", early):
            failed = [label for label, ok, _d in contract_battery(self.ep) if not ok]
        self.assertTrue(any("(not before)" in label for label in failed), failed)


class SkipsAndRejections(unittest.TestCase):
    def test_skip_note_text(self):
        from auditgym.check import skip_note

        self.assertEqual(skip_note([{"ok": True}, {"ok": True, "skipped": True}, {"skipped": True}]), " (2 skipped)")
        self.assertEqual(skip_note([{"ok": True}]), "")
        self.assertEqual(skip_note(n=7), " (7 skipped)")
        self.assertEqual(skip_note(n=0), "")

    def test_section_header_and_summary_line_carry_the_skip_note(self):
        import tempfile
        from pathlib import Path

        from auditgym import check

        rep = check.Report()
        with mock.patch("builtins.print"):
            rep.add("C_data", "a verifies", True)
            rep.skip("C_data", "rate stays rare", "too few episodes")
        self.assertEqual(check.section_header("C_data", rep.sections["C_data"]), "#### C_data (1/1) (1 skipped)\n")
        self.assertTrue(check.summary_line(rep).startswith("summary: C_data 1/1 (1 skipped) ("))
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(check, "isolation_line", return_value="x"), \
                mock.patch.object(check, "markdown_table", return_value=""), mock.patch.object(check, "miss_table", return_value=""):
            check._write_report(Path(tmp), rep, {}, [], [], 1.0, "src", "dev", 1, keep_runs=False)
            text = (Path(tmp) / "report.md").read_text(encoding="utf-8")
        self.assertIn("#### C_data (1/1) (1 skipped)", text)
        self.assertEqual(rep.counts()["C_data"], {"passed": 2, "total": 2, "skipped": 1, "applicable": 1, "applicable_passed": 1})

    def test_a_failed_check_is_not_hidden_by_a_skip(self):
        from auditgym import check

        rep = check.Report()
        with mock.patch("builtins.print"):
            rep.add("C_data", "a", True)
            rep.add("C_data", "b", False)
            rep.skip("C_data", "c", "n/a")
        self.assertTrue(check.summary_line(rep).startswith("summary: C_data 1/2 (1 skipped) ("))

    def test_a_section_without_skips_reads_as_before(self):
        from auditgym import check

        rep = check.Report()
        with mock.patch("builtins.print"):
            rep.add("A", "x", True)
            rep.add("A", "y", True)
        self.assertTrue(check.summary_line(rep).startswith("summary: A 2/2 ("))
        self.assertEqual(check.section_header("A", rep.sections["A"]), "#### A (2/2)\n")

    def test_report_carries_a_code_stamp_equal_across_two_writes(self):
        import json
        import platform
        import tempfile
        from pathlib import Path

        from auditgym import check

        rep = check.Report()
        with mock.patch("builtins.print"):
            rep.add("A", "x", True)
        docs = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as tmp, mock.patch.object(check, "isolation_line", return_value="x"), \
                    mock.patch.object(check, "markdown_table", return_value=""), mock.patch.object(check, "miss_table", return_value=""):
                check._write_report(Path(tmp), rep, {}, [], [], 1.0, "src", "dev", 1, keep_runs=False)
                docs.append((json.loads((Path(tmp) / "report.json").read_text(encoding="utf-8")),
                             (Path(tmp) / "report.md").read_text(encoding="utf-8")))
        code = docs[0][0]["code"]
        self.assertEqual(code, docs[1][0]["code"])
        self.assertRegex(code["code_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual((code["python"], code["platform"]), (platform.python_version(), platform.platform()))
        self.assertIn(f"Code: {check.stamp_line(code)}.", docs[0][1])
        self.assertEqual(docs[0][1], docs[1][1])

    def test_code_stamp_ignores_bytecode_but_not_sources(self):
        from auditgym import check, protocol

        real = protocol.code_digest()
        base = check.code_stamp()
        with_bytecode = dict(real, **{"auditgym/__pycache__/x.cpython-311.pyc": "a" * 64, "auditgym/x.pyo": "b" * 64,
                                      "auditgym/y.pyc": "c" * 64})
        with mock.patch.object(protocol, "code_digest", return_value=with_bytecode):
            self.assertEqual(check.code_stamp(), base)
        some_source = next(k for k in real if k.endswith(".py"))
        changed = dict(real, **{some_source: "0" * 64})
        with mock.patch.object(protocol, "code_digest", return_value=changed):
            self.assertNotEqual(check.code_stamp()["code_sha256"], base["code_sha256"])

    def test_check_main_maps_a_broken_episode_to_one_error_line_and_exit_2(self):
        import contextlib
        import io

        from auditgym import check
        from auditgym.episode import EpisodeFormatError

        err = io.StringIO()
        with mock.patch.object(check, "_main", side_effect=EpisodeFormatError("x/grader/truth.json is not valid JSON")), \
                contextlib.redirect_stderr(err):
            rc = check.main([])
        self.assertEqual(rc, 2)
        self.assertEqual(err.getvalue(), "error: x/grader/truth.json is not valid JSON\n")

    def test_correctness_rejection_check_verdict_and_label(self):
        from auditgym.check import correctness_rejection_check

        none = {"exception": 0, "sampling_check": 0, "correctness": 0}
        label, ok, _d = correctness_rejection_check(0, none)
        self.assertEqual((label, ok), ("no candidate episode was rejected by a correctness check (0 resampled)", True))
        label, ok, _d = correctness_rejection_check(2, {"exception": 1, "sampling_check": 1, "correctness": 0})
        self.assertEqual((label, ok), ("no candidate episode was rejected by a correctness check (2 resampled, all for sampling reasons)", True))
        label, ok, detail = correctness_rejection_check(3, {"exception": 1, "sampling_check": 1, "correctness": 1})
        self.assertEqual((label, ok), ("no candidate episode was rejected by a correctness check (3 resampled, 1 by a correctness check)", False))
        self.assertIn("2 sampling", detail)

    def test_rejections_are_classified_by_check_name(self):
        from types import SimpleNamespace as NS

        from auditgym.check import rejection_classes

        gens = [NS(rejected_checks=[{"attempt": 0, "failed_checks": []}, {"attempt": 1, "failed_checks": ["budget_feasible"]}]),
                NS(rejected_checks=[{"attempt": 0, "failed_checks": ["no_surface_tells", "budget_feasible"]},
                                    {"attempt": 1, "failed_checks": ["no_surface_tells", "evidence_sufficient"]},
                                    {"attempt": 2, "failed_checks": ["declared_discrepancies"]}])]
        self.assertEqual(rejection_classes(gens), {"exception": 1, "sampling_check": 2, "correctness": 2})

    def test_generator_carries_the_failing_check_names_and_provenance_is_unchanged(self):
        from auditgym import generator

        calls = {"n": 0}
        real = generator.build_once

        def flaky(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise generator.SampleRetry("forced")
            return real(*a, **k)

        with mock.patch.object(generator, "build_once", flaky):
            gen = generator.generate_episode(1, {})
        self.assertEqual(gen.rejected_checks, [{"attempt": 0, "failed_checks": []}])
        self.assertEqual(gen.episode.provenance["rejected_attempts"], [{"attempt": 0, "reason": "forced"}])

        bad = {"ok": False, "failures": ["x: y"], "checks": {"no_leaks": ["y"], "budget_feasible": ["z"], "ids_unique": "pass"}}
        from auditgym import verify

        real_verify = verify.verify_generated
        seen = {"n": 0}

        def verdict(ep, clean=None):
            seen["n"] += 1
            return bad if seen["n"] == 1 else real_verify(ep, clean)

        with mock.patch.object(verify, "verify_generated", verdict):
            gen = generator.generate_episode(1, {})
        self.assertEqual(gen.rejected_checks, [{"attempt": 0, "failed_checks": ["no_leaks", "budget_feasible"]}])


class SilentBaseline(unittest.TestCase):
    def test_submits_nothing_on_the_first_action(self):
        policy = make_policy("silent")
        self.assertIsInstance(policy, SilentPolicy)
        action = policy.act({"manifest": {"episode_id": "ep_x"}, "task": {}, "policy": {}, "remaining_steps": 100})
        self.assertEqual(action, {"action": "submit", "findings": {"episode_id": "ep_x", "findings": []}})


class CoverageLine(unittest.TestCase):
    """The report's 'N named checks of K kinds' must not count an organizer's episode names as kinds."""

    def test_episode_names_of_the_run_are_not_kinds(self):
        from auditgym.check import check_kind

        names = ["tz_Asia/Kathmandu", "tz_UTC", "large_twelve"]
        labels = [f"{n} verifies (12 issues, 1 attempt(s))" for n in names]
        labels += [f"{n}: same seed and config regenerate identical records and answer key" for n in names]
        self.assertEqual(len({check_kind(x, names) for x in labels}), 2)
        self.assertEqual(len({check_kind(x) for x in labels}), 6)  # without the names every episode looks new

    def test_public_names_and_ids_are_generalised(self):
        from auditgym.check import check_kind

        self.assertEqual(check_kind("ep_99b4722e2dd40466: an unknown ID gives a bounded error"),
                         check_kind("ep_0123456789abcdef: an unknown ID gives a bounded error"))
        self.assertEqual(check_kind("h02_dupes {'permute_seed': 11}: oracle answer and reward preserved"),
                         check_kind("h13_fx {'remap_seed': 3}: oracle answer and reward preserved"))
        self.assertNotEqual(check_kind("x: amount ladder"), check_kind("x: type shotgun"))


if __name__ == "__main__":
    unittest.main()
