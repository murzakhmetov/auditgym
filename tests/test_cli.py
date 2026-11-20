"""CLI robustness: bad input exits 2 with one `error:` line, closed-run warnings, run metadata,
per-episode random seeding, and the stress helpers. Most cases call main() in-process (fast);
one case runs the real command line to check there is no traceback."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from auditgym import __main__ as cli_mod
from auditgym import config as cfgmod
from auditgym import protocol
from auditgym import stress
from auditgym.episode import load_episode
from auditgym.runner import run_one
from auditgym.splits import load_split_episodes

ROOT = Path(__file__).resolve().parent.parent


def cli(*args, env_extra=None):
    """In-process main(); returns (rc, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    env = dict(env_extra or {})
    with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = cli_mod.main(list(args))
    return rc, out.getvalue(), err.getvalue()


class BadInput(unittest.TestCase):
    def assert_clean_error(self, res):
        rc, _out, err = res
        self.assertEqual(rc, 2, err)
        self.assertNotIn("Traceback", err)
        lines = [ln for ln in err.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, err)
        self.assertTrue(lines[0].startswith("error:"), lines[0])
        return lines[0]

    def gen(self, d, *extra, cfg=None):
        args = ["generate", "--seed", "1", "--out", str(Path(d) / "x"), *extra]
        if cfg is not None:
            args += ["--config", cfg]
        return cli(*args)

    def test_real_command_line_has_no_traceback(self):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, "-m", "auditgym", "generate", "--seed", "1", "--config",
                                json.dumps({"period": "2025-10", "interacting": ["boundary_fx_payment"]}),
                                "--out", str(Path(d) / "x")], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                               env=env, timeout=120)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(len([ln for ln in r.stderr.splitlines() if ln.strip()]), 1, r.stderr)
        self.assertTrue(r.stderr.startswith("error:"), r.stderr)

    def test_infeasible_config(self):
        with tempfile.TemporaryDirectory() as d:
            self.assert_clean_error(self.gen(d, cfg=json.dumps({"period": "2025-10", "interacting": ["boundary_fx_payment"]})))

    def test_config_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            self.assert_clean_error(self.gen(d, cfg="{not json"))
            self.assert_clean_error(self.gen(d, cfg='{"colour": 1}'))
            for bad in ("5", "[]", "null", '"x"', "examples/config_no_such.json"):  # not inline JSON objects: read as paths
                self.assertIn("config file", self.assert_clean_error(self.gen(d, cfg=bad)), bad)
            f = Path(d) / "c.json"
            f.write_text("[]", encoding="utf-8")
            self.assertIn("JSON object", self.assert_clean_error(self.gen(d, cfg=str(f))))
            self.assertEqual(cli_mod._load_config('{"k": "' + "a" * 400 + '"}'), {"k": "a" * 400})  # long inline JSON is not a path

    def test_missing_directories_and_files(self):
        self.assert_clean_error(cli("verify", str(ROOT / "no_such_episode_dir")))
        with tempfile.TemporaryDirectory() as d:
            self.assert_clean_error(cli("transform", "--in", str(Path(d) / "nope"), "--out", str(Path(d) / "o")))
            self.assert_clean_error(cli("grade", "--episode", str(Path(d) / "nope"), "--findings", str(Path(d) / "f.json")))
            self.assert_clean_error(cli("run", "--episodes", str(Path(d) / "nope"), "--out", str(Path(d) / "o")))

    def test_unset_secret_variable_is_an_error(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ):
            os.environ.pop("AUDITGYM_TEST_NO_SUCH_SECRET", None)
            self.assert_clean_error(self.gen(d, "--secret-env", "AUDITGYM_TEST_NO_SUCH_SECRET"))

    def test_bad_numbers(self):
        self.assert_clean_error(cli("stress", "--n", "-1"))
        self.assert_clean_error(cli("budget", "--budgets", "20,x"))
        self.assert_clean_error(cli("budget", "--budgets", "0"))
        self.assert_clean_error(cli("budget", "--budgets", "1000"))

    def test_max_steps_out_of_range_is_an_error(self):
        ep = str(ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy")
        with tempfile.TemporaryDirectory() as d:
            for bad in ("0", "1000", "-5"):
                with self.subTest(bad):
                    line = self.assert_clean_error(cli("run", "--episodes", ep, "--policies", "random", "--max-steps", bad,
                                                       "--out", str(Path(d) / "o")))
                    self.assertIn("--max-steps", line)
            self.assertFalse((Path(d) / "o").exists())

    def test_grade_with_a_huge_integer_is_an_invalid_submission(self):
        ep = ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy"
        eid = load_episode(ep).episode_id
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "f.json"
            f.write_text('{"episode_id": "%s", "findings": [{"type": "duplicate_payment", "affected_ids": ["x"], '
                         '"claimed_amount_minor": %s, "currency": "JPY"}]}' % (eid, "9" * 5000), encoding="utf-8")
            rc, out, err = cli("grade", "--episode", str(ep), "--findings", str(f))
        self.assertEqual(rc, 0, err)
        self.assertEqual(err, "")
        rep = json.loads(out)
        self.assertEqual(rep["reward"], -1)
        self.assertNotEqual(rep["status"], "submitted")

    def test_grade_with_deep_nesting_is_an_invalid_submission(self):
        ep = ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy"
        eid = load_episode(ep).episode_id
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "f.json"
            f.write_text('{"episode_id": "%s", "findings": %s%s}' % (eid, "[" * 100000, "]" * 100000), encoding="utf-8")
            rc, out, err = cli("grade", "--episode", str(ep), "--findings", str(f))
        self.assertEqual(rc, 0, err)
        self.assertEqual(json.loads(out)["reward"], -1)

    def test_seed_must_be_an_integer(self):
        err = io.StringIO()
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            cli_mod.main(["generate", "--seed", "foo", "--out", str(Path(d) / "x")])
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("--seed", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_bad_seeds_files(self):
        cases = {"no seed": {"episodes": [{"name": "no seed"}]},
                 "string seed": {"episodes": [{"seed": "closed-01"}]},
                 "bool seed": {"episodes": [{"seed": True}]},
                 "float seed": {"episodes": [{"seed": 1.5}]},
                 "list seed": {"episodes": [{"seed": [1, 2]}]},
                 "config not object": {"episodes": [{"seed": 1, "config": 5}]},
                 "duplicate names": {"episodes": [{"seed": 1, "name": "a"}, {"seed": 2, "name": "a"}]},
                 "empty": {"episodes": []}}
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "s.json"
            for label, spec in cases.items():
                f.write_text(json.dumps(spec), encoding="utf-8")
                with self.subTest(label):
                    self.assert_clean_error(cli("run", "--seeds-file", str(f), "--policies", "flag_all", "--out", str(Path(d) / "o")))

    def test_secret_env_needs_seeds_file(self):
        with tempfile.TemporaryDirectory() as d:
            res = cli("run", "--episodes", str(ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy"), "--policies", "flag_all",
                      "--secret-env", "AUDITGYM_TEST_SECRET", "--out", str(Path(d) / "o"), env_extra={"AUDITGYM_TEST_SECRET": "x"})
            self.assertIn("--seeds-file", self.assert_clean_error(res))

    def test_internal_errors_keep_their_traceback(self):
        """Only input errors become exit 2: a ValueError raised inside a run is a bug and propagates."""
        with tempfile.TemporaryDirectory() as d, mock.patch("auditgym.runner.run_many", side_effect=ValueError("boom")):
            with self.assertRaises(ValueError):
                cli("run", "--episodes", str(ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy"), "--policies", "flag_all",
                    "--out", str(Path(d) / "o"))


class StrictAgentUser(unittest.TestCase):
    """AUDITGYM_REQUIRE_AGENT_USER=1 with no separate policy user possible (forced by an empty AUDITGYM_AGENT_USER,
    so the result is the same on Windows, macOS, CI and inside the image)."""

    ENV = {"AUDITGYM_REQUIRE_AGENT_USER": "1", "AUDITGYM_AGENT_USER": ""}

    def assert_strict_error(self, rc, err):
        self.assertEqual(rc, 2, err)
        self.assertNotIn("Traceback", err)
        lines = [ln for ln in err.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, err)
        self.assertTrue(lines[0].startswith("error: AUDITGYM_REQUIRE_AGENT_USER=1"), lines[0])
        self.assertIn("AUDITGYM_AGENT_USER is not set", lines[0])

    def test_check_run_and_demo_exit_2_before_any_report(self):
        ep = str(ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy")
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o"
            cases = (["check", "--out", str(out)],
                     ["run", "--episodes", ep, "--policies", "random,oracle", "--out", str(out)],
                     ["demo"],
                     ["budget", "--out", str(out)],
                     ["viewer", "--out", str(out)])
            for argv in cases:
                with self.subTest(argv[0]):
                    rc, stdout, err = cli(*argv, env_extra=self.ENV)
                    self.assert_strict_error(rc, err)
                    self.assertEqual(stdout, "")
                    self.assertFalse(out.exists())

    def test_in_process_and_oracle_runs_need_no_child(self):
        ep = str(ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy")
        with tempfile.TemporaryDirectory() as d:
            for extra in (["--policies", "oracle"], ["--policies", "random", "--in-process"]):
                with self.subTest(extra):
                    rc, _out, err = cli("run", "--episodes", ep, "--out", str(Path(d) / "o"), *extra, env_extra=self.ENV)
                    self.assertEqual(rc, 0, err)

    def test_only_the_value_1_turns_strict_mode_on(self):
        for value, expected in (("1", True), (" 1 ", True), ("", False), ("0", False), ("true", False)):
            with self.subTest(value), mock.patch.dict(os.environ, {"AUDITGYM_REQUIRE_AGENT_USER": value}):
                self.assertEqual(protocol.require_agent_user(), expected)

    def test_agent_process_raises_a_dedicated_exception(self):
        with mock.patch.dict(os.environ, self.ENV), self.assertRaises(protocol.AgentUserRequired):
            protocol.AgentProcess("recon", 0)
        self.assertFalse(issubclass(protocol.AgentUserRequired, OSError))


class ClosedRun(unittest.TestCase):
    def run_seeds(self, d, seeds, env_extra=None, *extra):
        f = Path(d) / "s.json"
        f.write_text(json.dumps({"split": "t", "episodes": [{"name": f"e{s}", "seed": s, "config": {"size": "small"}}
                                                             for s in seeds]}), encoding="utf-8")
        out = Path(d) / "out"
        res = cli("run", "--seeds-file", str(f), "--policies", "flag_all", "--in-process", "--out", str(out), *extra,
                  env_extra=env_extra)
        return res, out

    def test_small_seed_warns_and_runs(self):
        with tempfile.TemporaryDirectory() as d:
            (rc, _o, err), out = self.run_seeds(d, [7])
            self.assertEqual(rc, 0, err)
            self.assertIn("WARNING", err)
            meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
            self.assertIs(meta["secret_used"], False)
            self.assertEqual(meta["min_seed_bits"], 3)
            for key in ("auditgym_version", "generator_version", "config_version", "schema_version", "grade_version",
                        "python", "platform", "mode", "isolated", "policy_seed", "max_steps", "command"):
                self.assertIn(key, meta)
            first = json.loads((out / "trajectories.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(sorted(first), sorted(["run_id", "split", "policy", "episode_id", "step", "action",
                                                    "observation", "reward", "terminated", "truncated"]))

    def test_secret_and_large_seed_no_warning_and_secret_not_recorded(self):
        secret = "s3cret-value-for-test-9f2c"
        with tempfile.TemporaryDirectory() as d:
            (rc, _o, err), out = self.run_seeds(d, [6602239917354212077], {"AUDITGYM_TEST_SECRET": secret},
                                                "--secret-env", "AUDITGYM_TEST_SECRET")
            self.assertEqual(rc, 0, err)
            self.assertNotIn("WARNING", err)
            text = (out / "meta.json").read_text(encoding="utf-8")
            self.assertNotIn(secret, text)
            meta = json.loads(text)
            self.assertIs(meta["secret_used"], True)
            self.assertGreaterEqual(meta["min_seed_bits"], 40)

    def test_warning_boundary_is_two_to_the_40(self):
        warn = cli_mod._small_seed_warning
        self.assertIsNotNone(warn(cli_mod._seed_bits(2 ** 40 - 1), None))
        self.assertIsNone(warn(cli_mod._seed_bits(2 ** 40), None))
        self.assertIsNone(warn(cli_mod._seed_bits(2 ** 62 + 1), None))
        self.assertIsNone(warn(cli_mod._seed_bits(7), "a-secret"))  # a host secret makes small seeds safe


class RandomPolicySeeding(unittest.TestCase):
    def test_one_stream_per_episode(self):
        eps = load_split_episodes(("dev",))
        steps = []
        for _split, _name, ep in eps:
            traj, g = run_one(ep, "random", split="dev", mode="eval", isolated=False, policy_seed=0)
            steps.append(g["inspection_steps"])
        self.assertGreaterEqual(len(set(steps)), 3, steps)

    def test_deterministic_for_same_episode(self):
        ep = load_episode(ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy")
        a = run_one(ep, "random", isolated=False)[0]
        b = run_one(ep, "random", isolated=False)[0]
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        c = run_one(ep, "random", isolated=False, policy_seed=1)[0]
        self.assertNotEqual(json.dumps(a, sort_keys=True), json.dumps(c, sort_keys=True))


class StressHelpers(unittest.TestCase):
    def test_seventeen_valid_extremes(self):
        ex = stress.extreme_configs()
        self.assertEqual(len(ex), 17)
        for _name, _seed, cfg in ex:
            cfgmod.validate(cfg)

    def test_random_configs_valid_and_reproducible(self):
        a = stress.random_configs(40)
        self.assertEqual(a, stress.random_configs(40))
        for _name, _seed, cfg in a:
            cfgmod.validate(cfg)

    def test_tiny_stress_run_writes_report(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(stress, "extreme_configs", lambda: []):
            self.assertEqual(stress.run_stress(1, Path(d), quiet=True, trace=False), 0)
            text = (Path(d) / "report.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# auditgym stress run"))
            self.assertIn("verify failed", text)


if __name__ == "__main__":
    unittest.main()
