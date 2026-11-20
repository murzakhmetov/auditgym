"""Anti-shortcut regression: no single public feature may identify the answer key.

For every committed train/dev episode (20 episodes) this computes simple one-feature rules over the public
records only and measures how well each rule picks out the documents of the answer key (every invoice and
payment id in `affected_ids`), pooled over all episodes. A rule is a shortcut when it is both selective and
useful. Two limits are asserted:

  * spec limit (never both): precision >= 0.5 and recall >= 0.3;
  * strong-tell limit (calibrated on the pre-fix data, see below): precision >= 0.8 with at least 3 hits.

Rules cover every tell found by the data audit of the previous generator: quantity or unit price outside the
catalogue ranges (injected documents were scaled up), payments outside business hours (only the boundary
receipt had one), the largest foreign purchase (FX targets were priced above all ordinary purchases), documents
near local midnight and on boundary days, weekend dates (no target was ever on a weekend), payment terms and
payment status (legit repeats were always 30 days and unpaid), an unpaid twin, account 2900 usage, and round
amounts. Rules that simply apply the published accounting policy (a posting that differs from its document, a
rate that differs from the policy rate) are not shortcuts: they are the task, so they are not measured here.

Episode-level rules (any outlier means errors; a small ledger with extra refunds or null-ref receipts means
clean) are measured on the 20 episodes as well: a rule that always names the error label needs a perfect score
on 3 episodes to fail, a rule naming the clean label 0.9 on 2 episodes.

Calibration. Pooled over the 20 committed episodes of the previous generator (50 affected documents) the
shortcut rules measured (precision, hits, recall): quantity or price outside the catalogue ranges 0.83, 10 hits,
0.20; payment outside business hours 1.00, 3 hits, 0.06 (the same 3 payments are the whole "boundary day,
off-hours payment" rule); sales quantity above the catalogue maximum 0.78, 7 hits, 0.14; a same-instant pair with
payment terms other than 30 days 0.86, 12 hits, 0.24 (legit repeats were always 30 days and unpaid); a paid
twin 0.75, 3 hits. At episode level the old data gave: any catalogue outlier 8 of 8 error episodes, any
boundary-day off-hours payment 3 of 3, a small ledger with 2 refunds 2 of 2 clean, with 3 null-ref receipts 2 of
2 clean. The spec limit alone would not have flagged any document rule (recall below 0.3 for each), so the
second limit (precision 0.8 with 3 hits) is what makes this test fail on that data: run on it, nine rules and the
catalogue-range check fail. With the current generator the best document rule reaches precision 0.25 with 5 hits (a paid twin invoice)
and the best recall among selective rules is 0.28 at precision 0.17 (an invoice with a twin), far from both
limits; the episode-level rules flag nothing (clean labels, catalogue outliers) or reach only 0.75 to 0.78
(error labels, whose base rate is 0.75). Run with -v/--verbose (or set AUDITGYM_TELLS_TABLE=1) to print the table.
"""

import contextlib
import io
import json
import os
import random
import sys
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from auditgym import tells
from auditgym.episode import load_episode
from auditgym.splits import EPISODES_DIR
from auditgym.tells import (EPISODE_RULES, RULES, SPEC_PRECISION, SPEC_RECALL, STRONG_HITS, STRONG_PRECISION, Ctx,
                            in_error_window, outside_catalogue, table)

_CACHE = {}


def episodes() -> list:
    if "eps" not in _CACHE:
        index = json.loads((EPISODES_DIR / "index.json").read_text(encoding="utf-8"))["episodes"]
        _CACHE["eps"] = [(e["name"], load_episode(EPISODES_DIR / e["split"] / e["name"])) for e in index]
    return _CACHE["eps"]


def measure() -> dict:
    return tells.measure_episode_objects(ep for _name, ep in episodes())



class TellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = measure()
        if any(a in ("-v", "--verbose") for a in sys.argv) or os.environ.get("AUDITGYM_TELLS_TABLE"):
            print("\n" + table(cls.m))

    def test_pooled_sample_is_the_whole_open_set(self):
        self.assertEqual(self.m["episodes"], 20)
        self.assertGreaterEqual(self.m["affected"], 40)

    def test_no_single_feature_rule_is_selective_and_useful(self):
        for name, r in self.m["rules"].items():
            with self.subTest(rule=name):
                self.assertFalse(r["precision"] >= SPEC_PRECISION and r["recall"] >= SPEC_RECALL,
                                 f"{name}: precision {r['precision']:.2f}, recall {r['recall']:.2f}")

    def test_no_single_feature_rule_is_a_strong_tell(self):
        for name, r in self.m["rules"].items():
            with self.subTest(rule=name):
                self.assertFalse(r["precision"] >= STRONG_PRECISION and r["hits"] >= STRONG_HITS,
                                 f"{name}: precision {r['precision']:.2f} with {r['hits']} hits")

    def test_no_episode_level_rule_gives_the_label_away(self):
        for name, r in self.m["episode_rules"].items():
            need_precision, need_hits = (1.0, 3) if r["label"] == "error" else (0.9, 2)
            with self.subTest(rule=name):
                self.assertFalse(r["precision"] >= need_precision and r["hits"] >= need_hits,
                                 f"{name}: {r['hits']} of {r['predicted']} episodes")

    def test_catalogue_ranges_hold_for_every_invoice(self):
        for name, ep in episodes():
            for inv in ep.invoices:
                self.assertFalse(outside_catalogue(inv), (name, inv["invoice_id"]))


# ---- generated sample: the committed set is too small for kind-by-kind window and count rules
GEN_EPISODES = 100
WINDOW_KINDS = ("sales", "purchase", "receipt", "disbursement")


def generated_sample() -> list:
    """(size, window documents by kind, target ids) for default-config episodes with a boundary offset; about half
    of them carry a utc_wall_clock target and some the boundary receipt."""
    if "gen" in _CACHE:
        return _CACHE["gen"]
    from auditgym.config import ConfigError
    from auditgym.generator import GenerationError, generate_episode

    rng = random.Random(1234)
    types = ("duplicate_invoice", "unallocated_payment", "wrong_fx_rate", "wrong_period")
    out = []
    while len(out) < GEN_EPISODES:
        size = rng.choice(["small", "small", "medium"])
        cfg = {"size": size, "errors": {t: rng.randint(0, 1) for t in types}}
        if rng.random() < 0.4:
            cfg["interacting"] = ["boundary_fx_payment"]
        if rng.random() < 0.5:
            cfg["variants"] = {"wrong_period": ["utc_wall_clock"]}
        try:
            g = generate_episode(rng.getrandbits(62), cfg)
        except (ConfigError, GenerationError):
            continue
        ep = g.episode
        c = Ctx(ep)
        if c.sched.offset_at(c.p1) == 0:
            continue
        variant = {i["issue_id"]: i["variant"] for i in ep.provenance["injections"]}
        targets = {d for iss in ep.truth["issues"] if variant[iss["issue_id"]] == "utc_wall_clock" for d in iss["affected_ids"]}
        window = defaultdict(set)
        for i, (_k, rec, inst) in c.docs.items():
            if in_error_window(inst, c.p1, c.sched):
                window[rec["kind"]].add(i)
        out.append((size, window, targets))
    _CACHE["gen"] = out
    return out


class GeneratedBoundaryTests(unittest.TestCase):
    def test_window_rule_by_kind_is_not_a_tell(self):
        sample = generated_sample()
        for kind in WINDOW_KINDS:
            predicted = sum(len(w[kind]) for _s, w, _t in sample)
            hits = sum(len(w[kind] & t) for _s, w, t in sample)
            with self.subTest(kind=kind):
                self.assertGreaterEqual(predicted, 20)
                self.assertLess(hits / predicted, STRONG_PRECISION, f"{kind} in the error window: {hits} of {predicted}")

    def test_window_count_by_kind_does_not_separate_target_episodes(self):
        sample = generated_sample()
        for size in ("small", "medium"):
            eps = [(w, t) for s, w, t in sample if s == size]
            for kind in WINDOW_KINDS:
                counts = [len(w[kind]) for w, _t in eps]
                typical = max(set(counts), key=counts.count)
                for rule, flagged in (("more than the typical count", [bool(t) for w, t in eps if len(w[kind]) > typical]),
                                      ("fewer than the typical count", [bool(t) for w, t in eps if len(w[kind]) < typical])):
                    with self.subTest(size=size, kind=kind, rule=rule):
                        if len(flagged) >= 8:
                            self.assertLess(sum(flagged) / len(flagged), 0.85, f"{size} {kind} {rule}: {sum(flagged)} of {len(flagged)}")


class GeneratedSmokeTests(unittest.TestCase):
    def test_module_runs_on_two_generated_episodes(self):
        m = tells.run(2)
        self.assertEqual((m["episodes"], m["master"]), (2, tells.DEFAULT_MASTER))
        self.assertGreater(m["documents"], 0)
        self.assertEqual(m["error_episodes"], 1)
        self.assertGreater(m["affected"], 0)
        self.assertEqual(m["rules"]["weekday date"]["hits"] + m["rules"]["weekend date"]["hits"], m["affected"])
        self.assertLessEqual(m["fx_target"]["largest_is_target"], m["fx_target"]["eligible_episodes"])
        self.assertEqual(set(m["rules"]), set(RULES) | set(tells.RESIDUAL_RULES))
        self.assertEqual(set(m["episode_rules"]), set(EPISODE_RULES))
        for r in m["rules"].values():
            self.assertEqual(set(r), {"predicted", "hits", "precision", "recall", "episodes_firing"})
            self.assertLessEqual(r["hits"], r["predicted"])
            self.assertTrue(0.0 <= r["precision"] <= 1.0 and 0.0 <= r["recall"] <= 1.0)

    def test_cli_writes_identical_files_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            texts = []
            for run in ("a", "b"):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = tells.main(["--n", "2", "--out", str(Path(tmp) / run)])
                self.assertEqual(code, 0)
                texts.append([(Path(tmp) / run / f).read_bytes() for f in ("summary.md", "summary.json")])
            self.assertEqual(texts[0], texts[1])
            self.assertEqual(json.loads(texts[0][1])["episodes"], 2)
            self.assertIn(b"--master auditgym-tells-v1", texts[0][0])
            self.assertIn(b"| rule | fires on | true hits | precision | recall | support |", texts[0][0])


if __name__ == "__main__":
    unittest.main()
