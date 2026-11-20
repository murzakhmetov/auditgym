"""shift_years: every calendar fact the answer key depends on survives a shift by a multiple of 28 years."""

from __future__ import annotations

import contextlib
import io
import json
import re
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from auditgym import __main__ as cli_mod
from auditgym.check_battery import matched_claims
from auditgym.episode import load_episode
from auditgym.generator import generate_episode
from auditgym.runner import run_one
from auditgym.timeutil import TZ_RULES, dst_window_utc
from auditgym.transform import _shift_text, shift_direction, transform_episode
from auditgym.verify import verify_generated

TRAIN = Path(__file__).resolve().parent.parent / "episodes" / "train"
DEV = Path(__file__).resolve().parent.parent / "episodes" / "dev"
SEED = 6602239917354212077
NAMES = ("t01_clean_small", "t03_duplicate", "t05_fx_rate", "t06_period", "t08_fx_partial_allocation")
FULL_DATE = re.compile(r"(?<![0-9])((?:19|20)[0-9]{2})-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])(?![0-9])")


def _tables(ep) -> dict:
    return {"policy": ep.policy, "ledger": ep.ledger, "invoices": ep.invoices, "payments": ep.payments, "fx": ep.fx}


def _dates(ep) -> list:
    text = "".join(ep.public_texts().values()) + json.dumps(ep.truth, sort_keys=True) + json.dumps(ep.provenance, sort_keys=True)
    return [(int(m.group(1)), int(m.group(2)), int(m.group(3))) for m in FULL_DATE.finditer(text)]


def _cli(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = cli_mod.main(list(args))
    return rc, out.getvalue(), err.getvalue()


class ShiftTransformTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.eps = {n: load_episode(TRAIN / n) for n in NAMES}

    def test_reward_matched_claims_and_verify_survive(self):
        for name, ep in self.eps.items():
            t = transform_episode(ep, shift_years=28)
            self.assertTrue(verify_generated(t)["ok"], (name, verify_generated(t)["failures"][:2]))
            _, g0 = run_one(ep, "oracle")
            _, g1 = run_one(t, "oracle")
            self.assertEqual((g0["reward"], g1["reward"]), (1.0, 1.0), name)
            t0, a0 = run_one(ep, "auditor", isolated=False)
            t1, a1 = run_one(t, "auditor", isolated=False)
            self.assertEqual(a0["reward"], a1["reward"], name)
            self.assertEqual(matched_claims(t0, a0), matched_claims(t1, a1), name)
            key = lambda e: [(x["issue_id"], x["type"], x["expected_amount_minor"]) for x in e.truth["issues"]]
            self.assertEqual(key(ep), key(t), name)

    def test_combined_with_other_transforms(self):
        ep = self.eps["t03_duplicate"]
        t = transform_episode(ep, shift_years=28, permute_seed=4, remap_seed=6, ts_repr="mixed", rename_seed=8)
        self.assertTrue(verify_generated(t)["ok"], verify_generated(t)["failures"][:2])
        _, g1 = run_one(t, "oracle")
        self.assertEqual(g1["reward"], 1.0)

    def test_round_trip_through_plus_28_and_minus_28(self):
        for name, ep in self.eps.items():
            there = transform_episode(ep, shift_years=28)
            self.assertNotEqual(there.public_texts()["ledger.csv"], ep.public_texts()["ledger.csv"], name)
            back = transform_episode(transform_episode(there, shift_years=28), shift_years=-28)
            texts_a, texts_b = there.public_texts(), back.public_texts()
            for fname in ("ledger.csv", "invoices.jsonl", "payments.jsonl", "fx.csv", "policy.json"):
                self.assertEqual(texts_a[fname], texts_b[fname], (name, fname))
            self.assertEqual(there.truth["issues"], back.truth["issues"], name)

    def test_minus_28_restores_original_records(self):
        for name, ep in self.eps.items():
            there = transform_episode(ep, shift_years=28)
            back = transform_episode(there, shift_years=-28)  # period 2054 -> 2026 is inside 2000..2100
            for table, rows in _tables(ep).items():
                self.assertEqual(rows, _tables(back)[table], (name, table))
            for fname, text in ep.public_texts().items():
                if fname != "manifest.json":
                    self.assertEqual(text, back.public_texts()[fname], (name, fname))
            strip = lambda m: {k: v for k, v in m.items() if k != "episode_id"}
            self.assertEqual(strip(ep.manifest), strip(back.manifest), name)
            self.assertEqual(ep.truth["issues"], back.truth["issues"], name)

    def test_invalid_shifts_raise(self):
        ep = self.eps["t01_clean_small"]
        for bad in (0, 1, 4, 8, 12, 14, 20, 27, 29, -14, 56.0, "28", True, None.__class__):
            with self.assertRaises(ValueError, msg=repr(bad)):
                transform_episode(ep, shift_years=bad)
        with self.assertRaisesRegex(ValueError, "accepted years"):  # period 2026 - 28 = 1998; every date stays above 1901
            transform_episode(ep, shift_years=-28)
        with self.assertRaisesRegex(ValueError, "outside 1901-03-01"):  # 2026 + 84 = 2110 is past 2099-12-31
            transform_episode(ep, shift_years=84)
        far = transform_episode(ep, shift_years=56)  # 2082: fine
        with self.assertRaisesRegex(ValueError, "outside 1901-03-01"):  # 2082 + 28 = 2110
            transform_episode(far, shift_years=28)

    def test_date_range_rule_alone(self):
        # period 2071-12 + 28 = 2099-12 passes the period rule, but 2072-01-01 + 28 = 2100-01-01 is past 2099-12-31
        ep = generate_episode(SEED, {"size": "small", "period": "2071-12"}).episode
        with self.assertRaisesRegex(ValueError, "outside 1901-03-01"):
            transform_episode(ep, shift_years=28)
        back = transform_episode(ep, shift_years=-28)
        self.assertEqual(back.provenance["resolved_config"]["period"], "2043-12")
        self.assertTrue(verify_generated(back)["ok"])
        self.assertEqual(shift_direction(ep), -28)

    def test_dates_in_2100_are_refused_both_ways(self):
        for period in ("2099-12", "2100-01"):
            ep = generate_episode(SEED, {"size": "small", "period": period}).episode
            for k in (28, -28):
                with self.assertRaisesRegex(ValueError, "outside 1901-03-01", msg=(period, k)):
                    transform_episode(ep, shift_years=k)
            self.assertIsNone(shift_direction(ep), period)
        self.assertEqual(_shift_text("2100-01-01 2100-01", 0), "2100-01-01 2100-01")

    def test_episode_id_carries_the_shift(self):
        ep = self.eps["t01_clean_small"]
        ids = {transform_episode(ep).episode_id, transform_episode(ep, shift_years=28).episode_id,
               transform_episode(ep, shift_years=56).episode_id}
        self.assertEqual(len(ids), 3)
        self.assertEqual(transform_episode(ep, remap_seed=5).episode_id, "ep_" + __import__("hashlib").sha256(
            f"{ep.episode_id}|None|5|None".encode()).hexdigest()[:16])

    def test_weekday_of_every_date_is_kept(self):
        for name, ep in self.eps.items():
            t = transform_episode(ep, shift_years=28)
            before, after = _dates(ep), _dates(t)
            self.assertEqual(len(before), len(after), name)
            self.assertTrue(before, name)
            for (y, m, d), (y2, m2, d2) in zip(before, after):
                self.assertEqual((y + 28, m, d), (y2, m2, d2), name)
                self.assertEqual(date(y, m, d).weekday(), date(y2, m2, d2).weekday(), name)

    def test_no_old_year_left(self):
        ep = self.eps["t06_period"]
        t = transform_episode(ep, shift_years=28)
        olds = {y for y, _m, _d in _dates(ep)}
        self.assertTrue(olds)
        self.assertFalse(olds & {y for y, _m, _d in _dates(t)})
        self.assertEqual(t.provenance["resolved_config"]["period"][:4], str(int(ep.provenance["resolved_config"]["period"][:4]) + 28))
        self.assertEqual(t.provenance["transformed_from"]["shift_years"], 28)
        self.assertNotEqual(t.episode_id, ep.episode_id)

    def test_leap_days_and_dated_tokens(self):
        self.assertEqual(_shift_text("2028-02-29T10:00:00+05:45", 28), "2056-02-29T10:00:00+05:45")
        self.assertEqual(_shift_text("2096-02-29", -28), "2068-02-29")
        self.assertEqual(_shift_text("SUB-2025-05-6014 SI/2026/123456 2026-06-05:EUR:GBP 2026-06", 28),
                         "SUB-2053-05-6014 SI/2054/123456 2054-06-05:EUR:GBP 2054-06")
        self.assertEqual(_shift_text("gl_2026a667 INV-202605 TS-2056 1202", 28), "gl_2026a667 INV-202605 TS-2056 1202")
        for y in range(1904, 2072, 4):
            if y % 100:
                self.assertEqual(date(y, 2, 29).weekday(), date(y + 28, 2, 29).weekday())

    def test_dst_rule_dates_shift_by_exactly_28_years(self):
        checked = 0
        for tz, (rule, _std, _dst) in TZ_RULES.items():
            if rule == "fixed":
                self.assertIsNone(dst_window_utc(tz, 2026))
                continue
            for year in range(1902, 2072):
                a = dst_window_utc(tz, year)
                b = dst_window_utc(tz, year + 28)
                for x, y in zip(a, b):
                    self.assertEqual((x.year + 28, x.month, x.day, x.hour), (y.year, y.month, y.day, y.hour), (tz, year))
                    self.assertEqual(x.weekday(), y.weekday(), (tz, year))
                    checked += 1
        self.assertGreater(checked, 1000)

    def test_dst_schedule_in_policy_follows_the_weekday_calendar(self):
        ep = load_episode(DEV / "d06_period_dst_march")
        t = transform_episode(ep, shift_years=28)
        old, new = ep.policy["utc_offset_schedule"], t.policy["utc_offset_schedule"]
        self.assertEqual(len(old), 2)  # a real DST transition inside the window
        self.assertEqual([(e["from_utc"], e["offset"]) for e in old],
                         [("2026-01-12T00:00:00Z", "+01:00"), ("2026-03-29T01:00:00Z", "+02:00")])
        self.assertEqual([(e["from_utc"], e["offset"]) for e in new],
                         [("2054-01-12T00:00:00Z", "+01:00"), ("2054-03-29T01:00:00Z", "+02:00")])
        self.assertEqual(date(2026, 3, 29).weekday(), date(2054, 3, 29).weekday())  # last Sunday of March both years
        self.assertTrue(verify_generated(t)["ok"])


class ShiftCliTest(unittest.TestCase):
    def test_cli_writes_shifted_episode_and_rejects_invalid_shift(self):
        src = str(TRAIN / "t03_duplicate")
        with tempfile.TemporaryDirectory() as tmp:
            rc, out, err = _cli("transform", "--in", src, "--out", str(Path(tmp) / "s"), "--shift-years", "28")
            self.assertEqual(rc, 0, err)
            shifted = load_episode(Path(tmp) / "s")
            self.assertTrue(verify_generated(shifted)["ok"])
            self.assertEqual(json.loads(out)["to"], shifted.episode_id)
            for flag in ("27", "0", "-28", "84", "28.0", "abc"):
                rc, out, err = _cli("transform", "--in", src, "--out", str(Path(tmp) / "bad"), "--shift-years", flag)
                self.assertEqual(rc, 2, flag)
                self.assertEqual(out, "")
                self.assertEqual(len(err.strip().splitlines()), 1, err)
                self.assertTrue(err.startswith("error: "), err)
            self.assertFalse((Path(tmp) / "bad").exists())


class ShiftClosedPathTest(unittest.TestCase):
    def test_check_with_a_late_period_skips_or_flips_the_shift(self):
        seeds = {"split": "closed_late_period", "episodes": [
            {"name": "c01", "seed": SEED, "config": {"size": "small", "period": "2080-05"}}]}
        from auditgym import check as check_mod

        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "seeds.json"
            f.write_text(json.dumps(seeds), encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = check_mod.main(["--seeds-file", str(f), "--out", str(Path(tmp) / "o")])
            self.assertEqual(rc, 0, out.getvalue()[-1500:] + err.getvalue())
            self.assertIn("'shift_years': -28", out.getvalue())


if __name__ == "__main__":
    unittest.main()
