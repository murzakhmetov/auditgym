"""Generator: configuration, verification, determinism, paired variants, transforms."""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from auditgym.config import ConfigError
from auditgym.generator import generate_episode
from auditgym.rng import Rng
from auditgym.runner import run_one
from auditgym.transform import transform_episode
from auditgym.verify import derive_from_evidence, verify_generated

ROOT = Path(__file__).resolve().parent.parent


class ConfigTests(unittest.TestCase):
    def test_rejects_unknown_and_infeasible_configs(self):
        bad = [
            {"size": "huge"},
            {"errors": {"made_up": 1}},
            {"errors": {"wrong_fx_rate": 13}},
            {"interacting": ["boundary_fx_payment"], "timezone": "UTC"},
            {"errors": {"wrong_fx_rate": 1}, "foreign_currencies": []},
            {"variants": {"wrong_fx_rate": ["utc_date"]}, "errors": {"wrong_fx_rate": 1}, "timezone": "UTC"},
            {"config_version": "99"},
            {"unexpected": True},
            {"errors": {"duplicate_invoice": 6, "wrong_period": 6}, "interacting": ["boundary_fx_payment"]},
        ]
        for cfg in bad:
            with self.subTest(cfg=cfg):
                with self.assertRaises(ConfigError):
                    generate_episode(1, cfg)

    def test_feasible_requests_never_fail_on_an_unlucky_draw(self):
        from auditgym.config import feasibility_problems, resolve
        from auditgym.generator import _base_text

        cases = [
            {"size": "small", "interacting": ["boundary_fx_payment"]},
            {"size": "small", "base_currency": "GBP", "interacting": ["boundary_fx_payment"]},
            {"size": "small", "timezone": "Europe/London", "interacting": ["boundary_fx_payment"]},
            {"size": "small", "errors": {"wrong_fx_rate": 1}, "variants": {"wrong_fx_rate": ["utc_date"]}},
            {"size": "small", "errors": {"wrong_period": 1}, "variants": {"wrong_period": ["utc_wall_clock"]}},
            {"size": "small", "period": "2025-12", "interacting": ["boundary_fx_payment"]},
        ]
        for cfg in cases:
            for seed in range(80):
                with self.subTest(cfg=cfg, seed=seed):
                    r = resolve(cfg, Rng(_base_text(seed, cfg, None)).fork("config"))
                    needs = {"boundary_offset": True, "boundary_weekdays": "interacting" in cfg,
                             "utc_date": "wrong_fx_rate" in cfg.get("errors", {})}
                    if "wrong_period" in cfg.get("errors", {}):
                        needs["boundary_weekdays"] = False
                    if "wrong_fx_rate" in cfg.get("errors", {}):
                        needs["boundary_offset"] = False
                    self.assertEqual(feasibility_problems(r["timezone"], r["period"], needs), [])
        gen = generate_episode(38, cases[0])
        self.assertEqual(len(gen.episode.truth["issues"]), 2)

    def test_fully_fixed_infeasible_request_is_a_clear_error(self):
        with self.assertRaises(ConfigError) as ctx:
            generate_episode(1, {"timezone": "Europe/London", "period": "2025-12", "interacting": ["boundary_fx_payment"]})
        self.assertIn("non-zero UTC offset", str(ctx.exception))

    def test_each_error_type_is_independently_configurable(self):
        for t in ("duplicate_invoice", "unallocated_payment", "wrong_fx_rate", "wrong_period"):
            ep = generate_episode(31, {"size": "small", "errors": {t: 2}}).episode
            self.assertEqual([i["type"] for i in ep.truth["issues"]], [t, t])

    def test_every_variant_and_scenario_verifies(self):
        cases = [
            {"errors": {"wrong_fx_rate": 1}, "variants": {"wrong_fx_rate": [v]}} for v in ("utc_date", "posting_date", "stale_rate", "transposed")
        ] + [
            {"errors": {"wrong_period": 1}, "variants": {"wrong_period": [v]}} for v in ("booked_early", "booked_late", "utc_wall_clock")
        ] + [
            {"errors": {"unallocated_payment": 1}, "variants": {"unallocated_payment": [v]}} for v in ("missing", "partial")
        ] + [{"interacting": ["boundary_fx_payment"]}, {"interacting": ["fx_invoice_partial_allocation"]},
             {"interacting": ["boundary_fx_payment"], "timezone": "America/New_York"}]
        for i, extra in enumerate(cases):
            cfg = {"size": "small", "timezone": "Asia/Almaty", **extra}
            with self.subTest(cfg=cfg):
                gen = generate_episode(400 + i, cfg)
                self.assertTrue(gen.verification["ok"], gen.verification["failures"][:3])
                self.assertTrue(gen.episode.truth["issues"])


class VerificationTests(unittest.TestCase):
    def test_random_configs_verify(self):
        rng = Rng("test-random-configs")
        types = ["duplicate_invoice", "unallocated_payment", "wrong_fx_rate", "wrong_period"]
        for n in range(12):
            cfg = {"size": rng.choice(["small", "medium"]), "errors": {t: rng.randint(0, 2) for t in types}}
            if rng.random() < 0.4:
                cfg["interacting"] = [rng.choice(["boundary_fx_payment", "fx_invoice_partial_allocation"])]
            gen = generate_episode(rng.next_u64() >> 1, cfg)
            rep = verify_generated(gen.episode, gen.clean)
            self.assertTrue(rep["ok"], rep["failures"][:3])
            self.assertLessEqual(len(gen.episode.truth["issues"]), 12)

    def test_clean_company_has_empty_key(self):
        gen = generate_episode(55, {"size": "small"})
        self.assertEqual(gen.episode.truth["issues"], [])
        self.assertTrue(verify_generated(gen.episode, gen.clean)["ok"])

    def test_removing_a_decisive_record_breaks_the_evidence(self):
        ep = generate_episode(61, {"size": "small", "errors": {"wrong_fx_rate": 1, "duplicate_invoice": 1}}).episode
        for issue in ep.truth["issues"]:
            for es in issue["evidence_sets"]:
                for drop in range(len(es)):
                    reduced = es[:drop] + es[drop + 1:]
                    self.assertIsNone(derive_from_evidence(issue["type"], reduced, ep))

    def test_twin_pair_has_opposite_answers(self):
        a = generate_episode(5520017338842210093, {"size": "small", "errors": {"duplicate_invoice": 1}}).episode
        b = generate_episode(5520017338842210093, {"size": "small", "errors": {"duplicate_invoice": 1}, "twin": True}).episode
        self.assertEqual(len(a.truth["issues"]), 1)
        self.assertEqual(len(b.truth["issues"]), 0)
        self.assertEqual(len(a.ledger), len(b.ledger))
        self.assertNotEqual(a.episode_id, b.episode_id)


class DeterminismTests(unittest.TestCase):
    def test_same_seed_same_bytes(self):
        a = generate_episode(77, {"size": "small", "errors": {"wrong_period": 1}}).episode
        b = generate_episode(77, {"size": "small", "errors": {"wrong_period": 1}}).episode
        self.assertEqual(a.public_digest(), b.public_digest())
        self.assertEqual(a.grader_texts(), b.grader_texts())

    def test_independent_of_hash_seed(self):
        code = ("from auditgym.generator import generate_episode;"
                "print(generate_episode(88, {'size':'small','errors':{'duplicate_invoice':1,'wrong_fx_rate':1}}).episode.public_digest())")
        outs = set()
        for hs in ("0", "12345"):
            env = dict(os.environ, PYTHONHASHSEED=hs, PYTHONPATH=str(ROOT))
            outs.add(subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True).stdout.strip())
        self.assertEqual(len(outs), 1)

    def test_secret_changes_the_episode(self):
        a = generate_episode(99, {"size": "small"}).episode
        b = generate_episode(99, {"size": "small"}, secret="host-only").episode
        self.assertNotEqual(a.public_digest(), b.public_digest())


class TransformTests(unittest.TestCase):
    def test_transforms_preserve_answer_and_oracle_reward(self):
        ep = generate_episode(71, {"size": "small", "interacting": ["boundary_fx_payment"], "errors": {"duplicate_invoice": 1}}).episode
        for tf in ({"permute_seed": 1}, {"remap_seed": 2}, {"ts_repr": "utc"}, {"ts_repr": "mixed", "remap_seed": 3, "permute_seed": 4}):
            t = transform_episode(ep, **tf)
            self.assertTrue(verify_generated(t)["ok"], tf)
            self.assertEqual([i["expected_amount_minor"] for i in t.truth["issues"]], [i["expected_amount_minor"] for i in ep.truth["issues"]])
            _, g = run_one(t, "oracle")
            self.assertEqual(g["reward"], 1.0)
            _, ga = run_one(ep, "auditor", isolated=False)
            _, gb = run_one(t, "auditor", isolated=False)
            self.assertEqual(ga["reward"], gb["reward"], tf)
        r = transform_episode(ep, remap_seed=2)
        old_ids = {x["row_id"] for x in ep.ledger}
        self.assertFalse(old_ids & {x["row_id"] for x in r.ledger})


if __name__ == "__main__":
    unittest.main()
