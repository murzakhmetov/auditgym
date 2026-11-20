"""rename_seed: names and wording change, everything the grader and auditor read stays equal."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from auditgym.check_battery import matched_claims
from auditgym.env import AuditEnv
from auditgym.episode import load_episode
from auditgym.runner import run_one
from auditgym.transform import _split_description, transform_episode
from auditgym.verify import verify_generated

TRAIN = Path(__file__).resolve().parent.parent / "episodes" / "train"
NAMES = ("t03_duplicate", "t05_fx_rate", "t10_duplicate_twin_legit", "t08_fx_partial_allocation")


def _descriptions(ep) -> list:
    return [li["description"] for d in ep.invoices for li in d["line_items"]]


def _public_and_provenance_text(ep) -> str:
    return "".join(ep.public_texts().values()) + json.dumps(ep.provenance, sort_keys=True)


class RenameTransformTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.eps = {n: load_episode(TRAIN / n) for n in NAMES}

    def test_invariance_of_reward_and_matched_claims(self):
        for name, ep in self.eps.items():
            t = transform_episode(ep, rename_seed=7)
            self.assertTrue(verify_generated(t)["ok"], name)
            _, g0 = run_one(ep, "oracle")
            _, g1 = run_one(t, "oracle")
            self.assertEqual((g0["reward"], g1["reward"]), (1.0, 1.0), name)
            t0, a0 = run_one(ep, "auditor", isolated=False)
            t1, a1 = run_one(t, "auditor", isolated=False)
            self.assertEqual(a0["reward"], a1["reward"], name)
            self.assertEqual(matched_claims(t0, a0), matched_claims(t1, a1), name)

    def test_ids_amounts_timestamps_and_key_unchanged(self):
        ep = self.eps["t03_duplicate"]
        t = transform_episode(ep, rename_seed=3)
        strip = lambda recs: [{k: v for k, v in r.items() if k != "line_items"} for r in recs]
        self.assertEqual(strip(ep.invoices), strip(t.invoices))
        self.assertEqual(ep.ledger, t.ledger)
        self.assertEqual(ep.payments, t.payments)
        self.assertEqual(ep.truth["issues"], t.truth["issues"])
        for a, b in zip(ep.invoices, t.invoices):
            for x, y in zip(a["line_items"], b["line_items"]):
                self.assertEqual({k: v for k, v in x.items() if k != "description"}, {k: v for k, v in y.items() if k != "description"})

    def test_mapping_is_injective_and_keeps_reference_tokens(self):
        for name, ep in self.eps.items():
            t = transform_episode(ep, rename_seed=5)
            pairs = set(zip(_descriptions(ep), _descriptions(t)))
            olds = [o for o, _n in pairs]
            news = [n for _o, n in pairs]
            self.assertEqual(len(set(olds)), len(pairs), name)
            self.assertEqual(len(set(news)), len(pairs), name)
            for o, n in pairs:
                self.assertEqual(_split_description(o)[1], _split_description(n)[1], name)

    def test_no_original_name_survives(self):
        for name, ep in self.eps.items():
            t = transform_episode(ep, rename_seed=11)
            text = _public_and_provenance_text(t)
            self.assertNotIn(ep.manifest["company"]["name"], text, name)
            for o in {_split_description(d)[0] for d in _descriptions(ep)}:
                self.assertNotIn(o, text, f"{name}: {o}")
            self.assertNotEqual(t.manifest["company"]["name"], ep.manifest["company"]["name"])

    def test_deterministic_and_seed_dependent(self):
        ep = self.eps["t05_fx_rate"]
        a, b = transform_episode(ep, rename_seed=9), transform_episode(ep, rename_seed=9)
        self.assertEqual(a.public_texts(), b.public_texts())
        self.assertEqual(a.grader_texts(), b.grader_texts())
        b = transform_episode(ep, rename_seed=10)
        self.assertNotEqual(_descriptions(a), _descriptions(b))
        self.assertNotEqual(a.manifest["company"]["name"], b.manifest["company"]["name"])

    def test_manifest_without_company(self):
        ep = copy.deepcopy(self.eps["t03_duplicate"])
        ep.manifest.pop("company")
        t = transform_episode(ep, rename_seed=2)
        self.assertNotIn("company", t.manifest)
        self.assertNotEqual(_descriptions(ep), _descriptions(t))

    def test_combines_with_other_transforms(self):
        ep = self.eps["t10_duplicate_twin_legit"]
        t = transform_episode(ep, permute_seed=2, remap_seed=4, ts_repr="mixed", rename_seed=6)
        self.assertTrue(verify_generated(t)["ok"])

    def test_env_reset_accepts_rename_seed(self):
        ep = self.eps["t03_duplicate"]
        obs, _ = AuditEnv().reset(config={"episode": ep, "transform": {"rename_seed": 2}})
        self.assertNotEqual(obs["manifest"]["company"]["name"], ep.manifest["company"]["name"])
