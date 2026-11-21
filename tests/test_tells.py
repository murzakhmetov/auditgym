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
amounts. A rate that differs from the policy rate is not a shortcut: it is the task, so it is not measured here. A posting
at another instant than its document is measured since round 8: before it, the policy said a posting's timestamp equals its
document's, so that rule picked out the answer key (14 of 14 flagged documents of the committed episodes, 54 of 54 on 100
generated ones); now a posting is booked at its own moment inside the document's period (distractor posting_lag, and lags on
documents of error issues at the same rate), and the rules on a different instant, on the sign, the size, the zone offset
and a date change are measured like every other rule.

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
catalogue-range check fail. With the current generator (version 0.3.0 with posting lags) the best document rule reaches precision 0.25 with 4 hits (a
sales invoice in the error window) and the best recall among selective rules is 0.18 at precision 0.17 (a payment with a 2900 row and
invoice refs), far from both limits; a posting at another instant than its document has precision 0.035 (20 hits of 575 flagged
documents) at recall 0.40; the episode-level rules flag nothing (clean labels, catalogue outliers) or reach 0.75 on 15 of 20 episodes
(any posting at another instant, any off-hours payment on a boundary day) and 0.80 on 15 episodes (a same-instant pair with terms other
than 30 days): error labels, whose base rate is 0.75. Line-identical pairs: decoys and the sources of duplicates come
from one builder and a duplicate is a converted pair, so the rules on a pair (a twin by side, a foreign currency, under
300 USD, a subscription item, an earlier member that was paid, a member posted off its issued_at) fire on a pair with
the same precision as on a duplicate; GeneratedDuplicateTests checks that on 100 generated episodes (the precision of a
pair per side and shape stays below 0.5 and within a factor of 3 between the four cells; the pair count of an episode, which holds the
duplicates, does not separate episodes with a duplicate). Run with -v/--verbose (or set AUDITGYM_TELLS_TABLE=1) to print the table.
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
# The smallest duplicate side-and-shape cells need enough observations to compare their rates.
GEN_EPISODES = 200
WINDOW_KINDS = ("sales", "purchase", "receipt", "disbursement")


def generated_sample() -> list:
    """(size, window documents by kind, target ids) for default-config episodes with a boundary offset; about half
    of them carry a utc_wall_clock target and some the boundary receipt."""
    if "gen" in _CACHE:
        return _CACHE["gen"]
    from auditgym.config import ConfigError
    from auditgym.generator import GenerationError, generate_episode

    rng = random.Random(1234)
    pairs_info = []
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
        dups = tells.duplicate_pairs(c)
        pairs_info.append({
            "size": size, "pairs": len(c.pairs), "has_duplicate": bool(dups),
            "cells": [(c.docs[ids[0]][1]["kind"] + "/" + c.pair_shape[frozenset(ids)], frozenset(ids) in dups) for ids in c.pairs],
            "subscription_pairs": sum(1 for i in c.pair_members if tells.RULES["same-instant pair of a subscription item"](c, i)),
            "off_posting": len(c.off_posting), "off_dup": len(c.off_posting & {i for ids in c.pairs if frozenset(ids) in dups for i in ids}),
            "affected": len(c.affected()),
            "lag_flagged": sum(1 for i in c.docs if tells.RULES["posting row at a different instant than its document"](c, i)),
            "lag_hits": len({i for i in c.docs if tells.RULES["posting row at a different instant than its document"](c, i)} & c.affected()),
            "docs": len(c.docs), "error": bool(ep.truth["issues"]), "ep_lag": any(v for v in c.lag.values()),
            "members": len(c.pair_members), "dup_members": sum(len(ids) for ids in c.pairs if frozenset(ids) in dups)})
    _CACHE["gen"] = out
    _CACHE["gen_pairs"] = pairs_info
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
                            # the lower 95 % Wilson bound of the share, not the point estimate: on 8 to 40 flagged episodes the
                            # estimate moves by 5 points with the draw (the receipt count sat at 0.85 on the data before round 8
                            # as well, because the boundary receipt of the scenario is one more receipt in the window)
                            n, k, z = len(flagged), sum(flagged), 1.96
                            lower = (k / n + z * z / (2 * n) - z * ((k / n * (1 - k / n) + z * z / (4 * n)) / n) ** 0.5) / (1 + z * z / n)
                            self.assertLess(lower, 0.85, f"{size} {kind} {rule}: {k} of {n}")


class GeneratedDuplicateTests(unittest.TestCase):
    """A duplicate is a converted line-identical pair, so a pair must be a duplicate with the same chance whatever its side
    and whatever the pair count of its episode (the visible count is drawn per size and holds the duplicates)."""

    @classmethod
    def setUpClass(cls):
        generated_sample()
        cls.info = _CACHE["gen_pairs"]

    def test_pairs_exist_in_every_side_and_shape_cell_and_are_balanced(self):
        cells = defaultdict(lambda: [0, 0])
        for e in self.info:
            for cell, dup in e["cells"]:
                cells[cell][0] += 1
                cells[cell][1] += dup
        self.assertEqual(set(cells), set(tells.DUP_CELLS))
        rates = {}
        for cell, (pairs, dups) in cells.items():
            with self.subTest(cell=cell):
                self.assertGreaterEqual(dups, 3, f"{cell}: {dups} duplicates in {pairs} pairs")
                rates[cell] = dups / pairs
                self.assertLess(rates[cell], SPEC_PRECISION)
        if all(cells[s][0] >= 15 for s in cells):
            self.assertLessEqual(max(rates.values()) / min(rates.values()), 3.0, str(dict(cells)))

    def test_pair_count_does_not_separate_duplicate_episodes(self):
        for size in ("small", "medium"):
            eps = [e for e in self.info if e["size"] == size]
            counts = [e["pairs"] for e in eps]
            typical = max(set(counts), key=counts.count)
            for rule, flagged in (("more pairs than typical", [e["has_duplicate"] for e in eps if e["pairs"] > typical]),
                                  ("fewer pairs than typical", [e["has_duplicate"] for e in eps if e["pairs"] < typical])):
                with self.subTest(size=size, rule=rule):
                    if len(flagged) >= 8:
                        self.assertLess(sum(flagged) / len(flagged), 0.85, f"{size} {rule}: {sum(flagged)} of {len(flagged)}")

    def test_bottom_of_the_range_pair_members_are_not_a_tell(self):
        from auditgym.config import DEFAULT_REPEAT_PAIRS

        members = hits = affected = 0
        for e in self.info:
            affected += e["affected"]
            if e["pairs"] <= DEFAULT_REPEAT_PAIRS[e["size"]][0]:
                members += e["members"]
                hits += e["dup_members"]
        self.assertGreater(members, 0)
        precision, recall = hits / members, hits / affected
        self.assertFalse(precision >= SPEC_PRECISION and recall >= SPEC_RECALL, f"precision {precision:.2f}, recall {recall:.2f}")
        self.assertLess(precision, STRONG_PRECISION)

    def test_no_subscription_pairs(self):
        self.assertEqual(sum(e["subscription_pairs"] for e in self.info), 0)

    def test_a_pair_member_posted_off_its_instant_is_a_duplicate_no_more_often_than_any_member(self):
        # posting lags (round 8): decoys and duplicates take them at the rate of every other document, so the rule is no tell
        off = sum(e["off_posting"] for e in self.info)
        off_dup = sum(e["off_dup"] for e in self.info)
        members = sum(e["members"] for e in self.info)
        dup_members = sum(e["dup_members"] for e in self.info)
        self.assertGreater(off, 40)
        self.assertLess(off_dup / off, SPEC_PRECISION, f"{off_dup} of {off} members posted off their instant are duplicates")
        self.assertLessEqual(off_dup / off, 1.5 * dup_members / members, (off_dup, off, dup_members, members))


class GeneratedLagTests(unittest.TestCase):
    """A posting at another instant than its document says almost nothing about the answer key (round 8): the document rule
    stays far below the spec limit and the episode rule does not exceed the error base rate by more than a few points."""

    @classmethod
    def setUpClass(cls):
        generated_sample()
        cls.info = _CACHE["gen_pairs"]

    def test_the_document_rule_is_not_a_tell(self):
        flagged = sum(e["lag_flagged"] for e in self.info)
        hits = sum(e["lag_hits"] for e in self.info)
        base = sum(e["affected"] for e in self.info) / sum(e["docs"] for e in self.info)
        self.assertGreater(flagged, 500)
        self.assertLess(hits / flagged, 0.15, f"{hits} of {flagged} flagged documents are in the key")
        self.assertLess(hits / flagged, 4 * base + 0.03, (hits / flagged, base))

    def test_the_episode_rule_stays_at_the_error_base_rate(self):
        flagged = [e for e in self.info if e["ep_lag"]]
        base = sum(e["error"] for e in self.info) / len(self.info)
        precision = sum(e["error"] for e in flagged) / len(flagged)
        self.assertGreater(len(flagged), 0.9 * len(self.info))  # clean episodes have lags too
        self.assertLessEqual(precision, base + 0.05, (precision, base))


class GeneratedCreditTests(unittest.TestCase):
    """What a row on 2900, the number of invoices and the number of late postings say about the answer key (round 8): before it a
    payment with a 2900 row on an invoice with one payment was in the key every time, an episode with 8 or more rows on 2900 was
    an error episode, and the invoice count grew with the errors."""

    @classmethod
    def setUpClass(cls):
        cls.m = tells.run(80)
        n, e = cls.m["episodes"], cls.m["error_episodes"]
        cls.base = {"error": e / n, "clean": (n - e) / n}

    def test_the_single_payment_rules_on_2900_are_not_tells(self):
        for name in ("payment with a 2900 row on an invoice that has no other payment", "... and the payment is at most the invoice total",
                     "receipt with invoice references and no 1100 row",
                     "receipt with a 1100 row and a 2900 row on an invoice that another receipt also lists",
                     "receipt with a 2900 row on an opening-item invoice",
                     "receipt with a 2900 row dated after its invoice, the invoice not issued on days 0 to 10 of the period",
                     "sales invoice with two or more receipts that sum to less than its total"):
            r = self.m["rules"][name]
            with self.subTest(rule=name):
                self.assertGreater(r["predicted"], 50)
                self.assertLess(r["precision"], 0.5, f"{name}: {r['hits']} of {r['predicted']}")

    def test_the_episode_rules_on_counts_stay_near_the_base_rate(self):
        for name in ("8 or more ledger rows on account 2900 -> error", "2900 rows beyond twice the refunds plus the null-ref receipts -> error",
                     "122 or more invoices -> error", "more postings at another instant than the size's largest default lag count -> error",
                     "at most 5 documents posted later than their timestamp -> clean",
                     "any receipt with a 2900 row lists an opening-item invoice -> error",
                     "any receipt with a 2900 row dated after an invoice not issued on days 0 to 10 -> error",
                     "any sales invoice with two or more receipts below its total -> error",
                     "at most 3 sales invoices whose receipts sum above their total -> error",
                     "at most 0.64 payments per invoice -> error"):
            r = self.m["episode_rules"][name]
            with self.subTest(rule=name):
                if r["predicted"] >= 12:
                    self.assertLessEqual(r["precision"], self.base[r["label"]] + 0.2, f"{name}: {r['hits']} of {r['predicted']}")


class PairGroupTests(unittest.TestCase):
    def test_an_ordinary_invoice_of_the_same_price_far_away_does_not_hide_a_pair(self):
        import copy
        from datetime import timedelta

        from auditgym.generator import generate_episode
        from auditgym.timeutil import format_ts, parse_ts

        ep = generate_episode(5, {"size": "small", "errors": {}, "distractors": {"legit_repeat": 2}}).episode
        before = tells.Ctx(ep).pairs
        self.assertEqual(len(before), 2)
        by_id = {i["invoice_id"]: i for i in ep.invoices}
        extra = copy.deepcopy(by_id[before[0][0]])
        extra["invoice_id"] = "ZZ-EXTRA-1"
        extra["issued_at"] = format_ts(parse_ts(extra["issued_at"]) + timedelta(days=45), 0)
        ep.invoices.append(extra)
        self.assertEqual(sorted(tells.Ctx(ep).pairs), sorted(before))


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
        self.assertEqual(set(m["pair_count_rules"]), set(tells.PAIR_COUNT_RULES))
        self.assertEqual(set(m["pair_count_episode_rules"]), set(tells.PAIR_COUNT_EPISODE_RULES))
        self.assertEqual(set(m["duplicates_by_side"]), {"sales/same", "sales/later", "purchase/same", "purchase/later", "pooled"})
        cells = m["duplicates_by_side"]
        parts = [v for k, v in cells.items() if k != "pooled"]
        self.assertEqual(cells["pooled"]["pairs"], sum(v["pairs"] for v in parts))
        self.assertEqual(cells["pooled"]["duplicates"], sum(v["duplicates"] for v in parts))
        self.assertLessEqual(cells["pooled"]["duplicates"], cells["pooled"]["pairs"])
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
