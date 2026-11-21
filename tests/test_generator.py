"""Generator: configuration, verification, determinism, paired variants, transforms."""

import csv
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



def _blank_refs(inv: dict) -> dict:
    """An invoice with its line references (and their copies inside the descriptions) replaced by a placeholder."""
    inv = json.loads(json.dumps(inv))
    for li in inv["line_items"]:
        li["description"] = li["description"].replace(li["ref"], "#")
        li["ref"] = "#"
    return inv


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

    def test_counts_that_cannot_fit_the_step_budget_are_a_config_error_at_once(self):
        import time

        for key in ("sales_invoices", "purchase_invoices", "prior_invoices"):
            with self.subTest(key=key):
                t0 = time.monotonic()
                with self.assertRaises(ConfigError) as ctx:
                    generate_episode(7, {"counts": {key: 2000}})
                self.assertLess(time.monotonic() - t0, 1.0)  # before any attempt is built
                self.assertIn("100-step budget", str(ctx.exception))
        gen = generate_episode(7, {"counts": {"sales_invoices": 500}})  # large but readable in 100 steps
        self.assertTrue(gen.verification["ok"])

    def test_the_page_floor_holds_on_every_committed_episode(self):
        # the bound config.min_read_pages relies on: one invoices row per counted invoice, two ledger rows per invoice
        from collections import Counter

        from auditgym.config import PAGE_ROWS, min_read_pages
        from auditgym.episode import load_episode
        from auditgym.splits import EPISODES_DIR

        dirs = sorted(d for d in EPISODES_DIR.glob("*/*") if (d / "public").exists())
        self.assertEqual(len(dirs), 20)
        for d in dirs:
            with self.subTest(d.name):
                ep = load_episode(d)
                counts = ep.provenance["resolved_config"]["counts"]
                n = counts["prior_invoices"] + counts["sales_invoices"] + counts["purchase_invoices"]
                invoices, ledger = ep.table("invoices"), ep.table("ledger")
                self.assertGreaterEqual(len(invoices), n)
                per = Counter(r.get("invoice_id") for r in ledger if r.get("invoice_id"))
                self.assertGreaterEqual(min(per.get(i["invoice_id"], 0) for i in invoices), 2)
                pages = -(-len(invoices) // PAGE_ROWS) + -(-len(ledger) // PAGE_ROWS)
                self.assertGreaterEqual(pages, min_read_pages(counts))

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
        ] + [
            {"errors": {"duplicate_invoice": 1}, "variants": {"duplicate_invoice": [v]}} for v in ("same_day_copy", "rekeyed_copy")
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

    def test_generated_episode_records_clean_records_digest_and_verifies_as_a_directory(self):
        gen = generate_episode(61, {"size": "small", "errors": {"wrong_fx_rate": 1, "duplicate_invoice": 1}})
        self.assertEqual(len(gen.episode.provenance["clean_records_digest"]), 64)
        self.assertTrue(verify_generated(gen.episode)["ok"], verify_generated(gen.episode)["failures"][:2])

    def test_fixed_period_boundary_error_names_nearest_feasible_months(self):
        with self.assertRaises(ConfigError) as cm:
            generate_episode(1, {"interacting": ["boundary_fx_payment"], "period": "2025-02",
                                 "variants": {"wrong_fx_rate": ["utc_date"]}})
        self.assertIn("Nearest feasible periods: ", str(cm.exception))

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


class DataRealismTests(unittest.TestCase):
    def test_twin_keeps_the_whole_history_for_every_seed(self):
        # A duplicate is a drawn pair converted; a twin relabels the same pair and keeps the whole history, whichever side
        # and shape (same instant, or the second invoice keyed again later) the pair has. Find seeds of every side x variant
        # cell (they move whenever generation changes).
        base_cfg = {"size": "small", "errors": {"duplicate_invoice": 1}}
        by_side = {}
        for variant in ("same_day_copy", "rekeyed_copy"):
            cfg = {**base_cfg, "variants": {"duplicate_invoice": [variant]}}
            found = {"sales": [], "purchase": []}
            for seed in range(80):
                ep = generate_episode(seed, cfg, verify=False).episode
                orig = {i["invoice_id"]: i for i in ep.invoices}[ep.provenance["injections"][0]["targets"]["original"]]
                found[orig["kind"]].append(seed)
                if all(len(v) >= 2 for v in found.values()):
                    break
            for side, seeds in found.items():
                self.assertGreaterEqual(len(seeds), 2, f"no seed duplicates a {side} invoice as {variant}")
                by_side[(side, variant)] = (cfg, seeds)
        for (side, variant), (cfg, seeds) in by_side.items():
            for seed in seeds[:2]:
                a = generate_episode(seed, cfg)
                b = generate_episode(seed, {**cfg, "twin": True})
                with self.subTest(seed=seed, side=side, variant=variant):
                    self.assertEqual(b.rejected, [])
                    self.assertEqual(len(b.episode.truth["issues"]), 0)
                    # file order, row ids and full contents: the copy has no positional or id-style tell
                    self.assertEqual(a.episode.ledger, b.episode.ledger)
                    self.assertEqual(a.episode.payments, b.episode.payments)
                    self.assertEqual(a.episode.fx, b.episode.fx)
                    self.assertEqual(len(a.episode.invoices), len(b.episode.invoices))
                    self.assertEqual([_blank_refs(i) for i in a.episode.invoices], [_blank_refs(i) for i in b.episode.invoices])
                    by_id = {i["invoice_id"]: i for i in b.episode.invoices}
                    pair = [i for i in next(d["ids"] for d in b.episode.provenance["distractors"] if d["kind"] == "twin_legit_repeat")
                            if i in by_id]  # the ids of the pair may also hold the payment of its first invoice
                    refs = lambda inv: [li["ref"] for li in inv["line_items"]]
                    self.assertEqual(by_id[pair[0]]["kind"], side)
                    self.assertNotEqual(refs(by_id[pair[0]]), refs(by_id[pair[1]]))
                    # the same two invoices are the duplicate of the error episode, with equal references
                    dup_ids = a.episode.truth["issues"][0]["affected_ids"]
                    self.assertEqual(sorted(dup_ids), sorted(pair))
                    a_by_id = {i["invoice_id"]: i for i in a.episode.invoices}
                    self.assertEqual(refs(a_by_id[dup_ids[0]]), refs(a_by_id[dup_ids[1]]))
                    # and the two episodes draw the same number of line-identical pairs
                    self.assertEqual(a.episode.provenance["resolved_config"]["repeat_pairs"],
                                     b.episode.provenance["resolved_config"]["repeat_pairs"])

    def test_fx_invoice_partial_allocation_is_always_partial(self):
        for seed in range(6):
            ep = generate_episode(seed, {"size": "small", "interacting": ["fx_invoice_partial_allocation"]}).episode
            variants = [i["variant"] for i in ep.provenance["injections"] if i["type"] == "unallocated_payment"]
            self.assertEqual(variants, ["partial"])
        with self.assertRaises(ConfigError):
            generate_episode(1, {"interacting": ["fx_invoice_partial_allocation"], "variants": {"unallocated_payment": ["missing"]}})

    def test_clean_books_never_overdraw_the_bank(self):
        from auditgym.timeutil import parse_ts

        for seed in (11, 12, 13):
            for size in ("small", "large"):
                g = generate_episode(seed, {"size": size})
                bal = 0
                for r in sorted(g.episode.ledger, key=lambda r: parse_ts(r["timestamp"])):
                    if r["account"] == "1000":
                        bal += r["debit_minor"] - r["credit_minor"]
                        self.assertGreaterEqual(bal, 0, (seed, size))

    def test_provenance_config_is_canonical(self):
        a = generate_episode(42, {"size": "small", "errors": {"wrong_fx_rate": 1}})
        b = generate_episode(42, {"errors": {"wrong_fx_rate": 1}, "size": "small"})
        self.assertEqual(a.episode.grader_texts(), b.episode.grader_texts())

    def test_subscription_refs_are_unique_per_supplier_month(self):
        for seed in range(8):
            ep = generate_episode(seed, {"size": "medium"}).episode
            seen = set()
            for inv in ep.invoices:
                if inv["kind"] == "purchase":
                    key = (inv["entity_id"], inv["line_items"][0]["ref"])
                    self.assertNotIn(key, seen)
                    seen.add(key)


def _by_id(ep):
    return {i["invoice_id"]: i for i in ep.invoices}


def _own_rows(ep, invoice_id):
    return [r for r in ep.ledger if r["invoice_id"] == invoice_id and not r["payment_id"]]


class DuplicateSidesTests(unittest.TestCase):
    """duplicate_invoice is injected on sales and purchase invoices alike, from a drawn line-identical pair, in two variants:
    the copy of one instant (same_day_copy) or keyed again 2 to 9 local days later (rekeyed_copy)."""

    CFG = {"size": "small", "errors": {"duplicate_invoice": 1}}
    VARIANTS = ("same_day_copy", "rekeyed_copy")
    _cache: dict = {}

    def episodes(self, per_cell=2):
        """{(side, variant): [episode, ...]}: generated episodes with one duplicate each, per_cell for each of the 4 cells."""
        if per_cell not in self._cache:
            found = {(s, v): [] for s in ("sales", "purchase") for v in self.VARIANTS}
            for variant in self.VARIANTS:
                for seed in range(120):
                    if all(len(found[(s, variant)]) >= per_cell for s in ("sales", "purchase")):
                        break
                    ep = generate_episode(seed, {**self.CFG, "variants": {"duplicate_invoice": [variant]}}).episode
                    kind = _by_id(ep)[ep.truth["issues"][0]["affected_ids"][0]]["kind"]
                    found[(kind, variant)].append(ep)
            self.assertTrue(all(len(v) >= per_cell for v in found.values()), {k: len(v) for k, v in found.items()})
            self._cache[per_cell] = found
        return self._cache[per_cell]

    def test_duplicates_cover_both_sides_and_both_variants_and_post_in_their_own_period(self):
        from datetime import timedelta

        from auditgym.timeutil import local_date, parse_ts

        for (side, variant), eps in self.episodes().items():
            for ep in eps:
                with self.subTest(side=side, variant=variant, episode=ep.episode_id):
                    issue = ep.truth["issues"][0]
                    a, b = (_by_id(ep)[i] for i in issue["affected_ids"])  # the original, then the copy
                    keys = ("kind", "entity_id", "currency", "total_minor", "line_items")
                    self.assertEqual([a[k] for k in keys], [b[k] for k in keys])  # line refs included
                    tz = ep.manifest["timezone"]
                    da, db = (local_date(parse_ts(x["issued_at"]), tz) for x in (a, b))
                    terms = (local_date(parse_ts(a["due_at"]), tz) - da).days
                    self.assertIn(terms, (14, 30, 45))
                    self.assertEqual(local_date(parse_ts(b["due_at"]), tz) - db, timedelta(days=terms))  # the copy's own due date
                    if variant == "same_day_copy":
                        for k in ("issued_at", "due_at"):
                            self.assertEqual(parse_ts(a[k]), parse_ts(b[k]))  # one instant, whatever offset each is written with
                    else:
                        self.assertTrue(2 <= (db - da).days <= 9, (da, db))
                        self.assertGreater(parse_ts(b["issued_at"]), parse_ts(a["issued_at"]))
                        p0, p1 = (parse_ts(ep.policy["reporting_period"][k]) for k in ("start", "end"))
                        self.assertTrue(p0 <= parse_ts(a["issued_at"]) < parse_ts(b["issued_at"]) < p1)  # inside the period
                    primary, counter = ("1100", "4000") if side == "sales" else ("2000", "5000")
                    rows_a, rows_b = _own_rows(ep, a["invoice_id"]), _own_rows(ep, b["invoice_id"])
                    self.assertEqual({r["account"] for r in rows_a}, {primary, counter})
                    self.assertEqual({r["account"] for r in rows_b}, {primary, counter})
                    p0, p1 = (parse_ts(ep.policy["reporting_period"][k]) for k in ("start", "end"))
                    for doc, rows in ((a, rows_a), (b, rows_b)):  # each copy is booked in its own period, at its own moment
                        self.assertEqual(len({parse_ts(r["timestamp"]) for r in rows}), 1)
                        for r in rows:
                            self.assertEqual(p0 <= parse_ts(r["timestamp"]) < p1, p0 <= parse_ts(doc["issued_at"]) < p1)
                    # the amount is the later copy's primary row; same-instant copies post equal amounts
                    amounts = [next(r for r in rows if r["account"] == primary) for rows in (rows_a, rows_b)]
                    got = [row["debit_minor"] or row["credit_minor"] for row in amounts]
                    self.assertEqual(got[1], issue["expected_amount_minor"])
                    if variant == "same_day_copy":
                        self.assertEqual(got[0], got[1])
                    self.assertEqual(ep.provenance["injections"][0]["variant"], variant)
                    self.assertEqual(ep.provenance["injections"][0]["change"], {})

    def test_a_foreign_rekeyed_copy_amount_is_the_later_posting(self):
        # a re-keyed copy of a foreign-currency invoice is converted at the rate of its own date, so the two postings usually
        # differ and the answer is the later one (not the original's)
        from auditgym.timeutil import parse_ts

        cfg = {"size": "small", "errors": {"duplicate_invoice": 1}, "variants": {"duplicate_invoice": ["rekeyed_copy"]}}
        checked = 0
        for seed in range(200):
            gen = generate_episode(seed, cfg)
            ep = gen.episode
            issue = ep.truth["issues"][0]
            a, b = (_by_id(ep)[i] for i in issue["affected_ids"])
            if a["currency"] == ep.manifest["base_currency"]:
                continue
            primary = "1100" if a["kind"] == "sales" else "2000"
            ra, rb = ([r for r in _own_rows(ep, x["invoice_id"]) if r["account"] == primary][0] for x in (a, b))
            amt = lambda r: r["debit_minor"] or r["credit_minor"]
            if amt(ra) == amt(rb):
                continue
            checked += 1
            self.assertEqual(issue["expected_amount_minor"], amt(rb))
            self.assertNotEqual(issue["expected_amount_minor"], amt(ra))
            self.assertTrue(gen.verification["ok"])
            for es in issue["evidence_sets"]:
                self.assertEqual(derive_from_evidence("duplicate_invoice", es, ep)[2], amt(rb))
            self.assertGreater(parse_ts(b["issued_at"]), parse_ts(a["issued_at"]))
            if checked >= 3:
                break
        self.assertGreaterEqual(checked, 3, "no foreign re-keyed duplicate with two different postings in 200 seeds")

    def test_every_evidence_set_re_derives_the_duplicate_on_both_sides(self):
        for (side, variant), eps in self.episodes(per_cell=1).items():
            for ep in eps:
                issue = ep.truth["issues"][0]
                docs = {d["invoice_id"]: d["doc_id"] for d in ep.invoices}
                rows = {r["row_id"]: r for r in ep.ledger}
                primary, counter = ("1100", "4000") if side == "sales" else ("2000", "5000")
                accounts = []
                for es in issue["evidence_sets"]:
                    self.assertTrue({docs[i] for i in issue["affected_ids"]} <= set(es))
                    accounts.append({rows[e]["account"] for e in es if e in rows})
                    self.assertEqual(derive_from_evidence("duplicate_invoice", es, ep),
                                     ("duplicate_invoice", frozenset(issue["affected_ids"]), issue["expected_amount_minor"]))
                self.assertEqual(sorted(map(sorted, accounts)), sorted([[counter], [primary]]))

    def test_a_legitimate_repeat_is_not_a_duplicate_on_either_side_or_shape(self):
        # clean episodes hold line-identical pairs of both sides and both shapes (the second invoice keyed again later, with
        # a fresh reference); the independent auditor reports none of them
        from auditgym.auditor import audit_episode
        from auditgym.tells import Ctx

        cells = set()
        for seed in range(16):
            ep = generate_episode(seed, {"size": "small"}).episode
            self.assertEqual(audit_episode(ep)["findings"], [])
            c = Ctx(ep)
            cells |= {(c.docs[ids[0]][1]["kind"], c.pair_shape[frozenset(ids)]) for ids in c.pairs}
        self.assertEqual(cells, {(s, sh) for s in ("sales", "purchase") for sh in ("same", "later")})

    def test_the_auditor_and_the_checker_see_a_rekeyed_copy_only_through_the_lines(self):
        from auditgym.auditor import audit_episode

        for (side, variant), eps in self.episodes(per_cell=1).items():
            for ep in eps:
                with self.subTest(side=side, variant=variant):
                    issue = ep.truth["issues"][0]
                    found = [f for f in audit_episode(ep)["findings"] if f["type"] == "duplicate_invoice"]
                    self.assertEqual(len(found), 1)
                    self.assertEqual(found[0]["amount"], issue["expected_amount_minor"])


class PairCountTests(unittest.TestCase):
    def resolved(self, cfg, seed):
        from auditgym.config import resolve
        from auditgym.generator import _base_text

        return resolve(cfg, Rng(_base_text(seed, cfg, None)).fork("config"))

    def test_the_pair_count_is_drawn_per_size_and_holds_the_duplicates(self):
        from auditgym.config import DEFAULT_REPEAT_PAIRS

        for size, (lo, hi) in DEFAULT_REPEAT_PAIRS.items():
            drawn = set()
            for dup in (0, 1, 2, 3):
                for seed in range(40):
                    r = self.resolved({"size": size, "errors": {"duplicate_invoice": dup}}, seed)
                    self.assertEqual(r["distractors"]["legit_repeat"], r["repeat_pairs"] - dup)
                    self.assertGreaterEqual(r["distractors"]["legit_repeat"], 0)
                    if dup <= lo:
                        self.assertTrue(lo <= r["repeat_pairs"] <= hi, (size, dup, r["repeat_pairs"]))
                    else:  # more duplicates than the range's lower bound: the decoys are drawn on top, never crowded out
                        self.assertTrue(lo <= r["distractors"]["legit_repeat"] <= hi, (size, dup, r))
                    drawn.add(r["repeat_pairs"])
            self.assertGreater(len(drawn), 2, "the count is drawn, not fixed")

    def test_a_duplicate_count_above_the_range_still_leaves_decoys(self):
        from auditgym.config import DEFAULT_REPEAT_PAIRS
        from auditgym.tells import Ctx

        for size, (lo, hi) in DEFAULT_REPEAT_PAIRS.items():
            dup = hi + 2
            for seed in range(3):
                ep = generate_episode(9000 + seed, {"size": size, "errors": {"duplicate_invoice": dup}}).episode
                r = ep.provenance["resolved_config"]
                self.assertGreaterEqual(r["distractors"]["legit_repeat"], lo)
                self.assertEqual(len(Ctx(ep).pairs), r["repeat_pairs"], (size, seed))
                self.assertGreater(len(Ctx(ep).pairs), len(ep.truth["issues"]), "every visible pair is not a duplicate")

    def test_an_explicit_legit_repeat_keeps_its_meaning(self):
        r = self.resolved({"size": "small", "errors": {"duplicate_invoice": 2}, "distractors": {"legit_repeat": 3}}, 1)
        self.assertEqual((r["distractors"]["legit_repeat"], r["repeat_pairs"]), (3, 5))
        r = self.resolved({"size": "small", "distractors": {"legit_repeat": 0}}, 1)
        self.assertEqual((r["distractors"]["legit_repeat"], r["repeat_pairs"]), (0, 0))

    def test_generated_episodes_show_exactly_the_drawn_pairs_with_or_without_duplicates(self):
        from auditgym.tells import Ctx

        for seed in range(10):
            for dup in (0, 1, 2):
                ep = generate_episode(seed, {"size": "medium", "errors": {"duplicate_invoice": dup}}).episode
                self.assertEqual(len(Ctx(ep).pairs), ep.provenance["resolved_config"]["repeat_pairs"], (seed, dup))
                self.assertEqual(len(ep.truth["issues"]), dup)


class SalesRefTests(unittest.TestCase):
    def test_sales_invoices_carry_one_unique_delivery_reference_each(self):
        import re

        from auditgym import catalog

        descriptions = {d for d, _p, _q in catalog.SALES_ITEMS}
        for seed in range(6):
            ep = generate_episode(seed, {"size": "medium", "errors": {"duplicate_invoice": 1}}).episode
            dup = set(ep.truth["issues"][0]["affected_ids"])
            seen = {}
            for inv in ep.invoices:
                if inv["kind"] != "sales":
                    continue
                parsed = [re.fullmatch(r"(SO-[0-9]{5})-([0-9]+)", li["ref"]) for li in inv["line_items"]]
                self.assertNotIn(None, parsed, inv["line_items"])
                self.assertEqual(len({m.group(1) for m in parsed}), 1)  # one delivery reference per invoice
                self.assertEqual([m.group(2) for m in parsed], [str(n) for n in range(1, len(parsed) + 1)])
                for li in inv["line_items"]:
                    self.assertIn(li["description"], descriptions)  # the reference stays out of the description
                seen.setdefault(parsed[0].group(1), []).append(inv["invoice_id"])
            for ref, ids in seen.items():
                self.assertTrue(len(ids) == 1 or set(ids) == dup, (ref, ids))  # unique except the two copies of a duplicate


class CommittedDuplicateCoverageTests(unittest.TestCase):
    def committed(self):
        out = {}
        for split in ("train", "dev"):
            for d in sorted((ROOT / "episodes" / split).iterdir()):
                truth = json.loads((d / "grader" / "truth.json").read_text(encoding="utf-8"))
                prov = json.loads((d / "grader" / "provenance.json").read_text(encoding="utf-8"))
                invs = {json.loads(ln)["invoice_id"]: json.loads(ln)
                        for ln in (d / "public" / "invoices.jsonl").read_text(encoding="utf-8").splitlines()}
                out[d.name] = (truth, prov, invs)
        return out

    def test_committed_set_covers_both_duplicate_sides_and_both_variants(self):
        sides, variants = {}, {}
        for name, (truth, prov, invs) in self.committed().items():
            for issue, inj in zip(truth["issues"], prov["injections"]):
                if issue["type"] == "duplicate_invoice":
                    sides.setdefault(invs[issue["affected_ids"][0]]["kind"], []).append(name)
                    variants.setdefault(inj["variant"], []).append(name)
        self.assertEqual(set(sides), {"sales", "purchase"}, sides)
        self.assertEqual(set(variants), {"same_day_copy", "rekeyed_copy"}, variants)

    def test_a_committed_foreign_rekeyed_duplicate_has_two_different_postings(self):
        # the amount a re-keyed copy is booked at is the later copy's posting, in the account's own currency: at least one
        # committed episode must differ from "the two rows are equal" so that it cannot be learned from the equal case
        found = []
        for name, (truth, prov, invs) in self.committed().items():
            path = ROOT / "episodes" / ("train" if name.startswith("t") else "dev") / name / "public" / "ledger.csv"
            with path.open(encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            for issue, inj in zip(truth["issues"], prov["injections"]):
                if issue["type"] != "duplicate_invoice" or inj["variant"] != "rekeyed_copy":
                    continue
                amounts = []
                for iid in issue["affected_ids"]:
                    prim = [r for r in rows if r["invoice_id"] == iid and not r["payment_id"] and r["account"] in ("1100", "2000")]
                    amounts.append({(r["account"], r["debit_minor"], r["credit_minor"]) for r in prim})
                if len(amounts) == 2 and amounts[0] != amounts[1]:
                    found.append(name)
        self.assertTrue(found, "no committed re-keyed duplicate with differing primary rows")

    def test_the_committed_twin_pair_still_has_opposite_answers_on_one_history(self):
        eps = self.committed()
        dup, twin = eps["t03_duplicate"], eps["t10_duplicate_twin_legit"]
        self.assertEqual(len(dup[0]["issues"]), 1)
        self.assertEqual(twin[0]["issues"], [])
        self.assertEqual(len([d for d in twin[1]["distractors"] if d["kind"] == "twin_legit_repeat"]), 1)
        self.assertEqual(dup[1]["resolved_config"]["repeat_pairs"], twin[1]["resolved_config"]["repeat_pairs"])
        self.assertEqual(len(dup[2]), len(twin[2]))  # the same documents
        from auditgym.episode import load_episode

        a = load_episode(ROOT / "episodes" / "train" / "t03_duplicate")
        b = load_episode(ROOT / "episodes" / "train" / "t10_duplicate_twin_legit")
        self.assertEqual(a.ledger, b.ledger)  # the same ledger rows in the same file order: only the line references differ
        self.assertEqual(a.payments, b.payments)
        self.assertEqual(a.fx, b.fx)
        self.assertEqual([_blank_refs(i) for i in a.invoices], [_blank_refs(i) for i in b.invoices])


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


class StandaloneUtcWallClockDstTests(unittest.TestCase):
    """New York, October 2026: 1 November is a Sunday, so the boundary night holds the DST change. A standalone
    utc_wall_clock error used to post inside that window in about half of the seeds, a time ordinary documents never
    use; it now keeps the boundary receipt's 75-minute clearance and the boundary's offset."""

    def test_the_posting_stays_clear_of_the_dst_change(self):
        from auditgym.timeutil import in_ambiguous_hour, offset_minutes, parse_ts

        cfg = {"size": "small", "timezone": "America/New_York", "period": "2026-10", "errors": {"wrong_period": 1},
               "variants": {"wrong_period": ["utc_wall_clock"]}}
        checked = 0
        for s in range(24):
            ep = generate_episode(10 ** 15 + s, cfg).episode
            ids = {a for t in ep.truth["issues"] if t["type"] == "wrong_period" for a in t["affected_ids"]}
            inv = next(d for d in ep.invoices if d["invoice_id"] in ids)
            off = offset_minutes("America/New_York", parse_ts(inv["issued_at"]))
            rows = [r for r in ep.ledger if r.get("invoice_id") in ids and not r.get("payment_id")]
            self.assertTrue(rows)
            for r in rows:
                posting = parse_ts(r["timestamp"])
                self.assertFalse(in_ambiguous_hour("America/New_York", posting), (s, r["timestamp"]))
                self.assertEqual(offset_minutes("America/New_York", posting), off, (s, r["timestamp"]))
            checked += 1
        self.assertEqual(checked, 24)


class BoundaryEveryMonthTests(unittest.TestCase):
    """boundary_fx_payment can be generated for a fixed period in every month, not only where both days around the
    period end are weekdays: where the utc_date error would have no amount the receipt carries another rate error."""

    def test_every_month_of_2025_to_2027_hosts_the_scenario(self):
        from auditgym.config import boundary_utc_date_ok
        from auditgym.timeutil import month_bounds, offset_minutes

        fallback_months = 0
        for y in (2025, 2026, 2027):
            for m in range(1, 13):
                period = f"{y}-{m:02d}"
                for tz in (None, "Asia/Almaty", "America/Sao_Paulo"):  # drawn, positive offset, negative offset
                    cfg = {"period": period, "interacting": ["boundary_fx_payment"]}
                    if tz:
                        cfg["timezone"] = tz
                    with self.subTest(period=period, tz=tz):
                        ep = generate_episode(3, cfg).episode
                        self.assertTrue(verify_generated(ep)["ok"], verify_generated(ep)["failures"][:2])
                        by_type = {i["type"]: i for i in ep.truth["issues"]}
                        self.assertEqual(sorted(by_type), ["wrong_fx_rate", "wrong_period"])
                        self.assertTrue(all(i["expected_amount_minor"] > 0 for i in by_type.values()))
                        self.assertEqual({i["scenario"] for i in by_type.values()}, {"boundary_fx_payment"})
                        self.assertEqual(by_type["wrong_fx_rate"]["affected_ids"], by_type["wrong_period"]["affected_ids"])
                        self.assertEqual(by_type["wrong_period"]["variant"], "utc_wall_clock")
                        zone = ep.provenance["resolved_config"]["timezone"]
                        off = offset_minutes(zone, month_bounds(zone, y, m)[1])
                        if boundary_utc_date_ok(period, off):
                            self.assertEqual(by_type["wrong_fx_rate"]["variant"], "utc_date")
                        else:
                            fallback_months += 1
                            self.assertIn(by_type["wrong_fx_rate"]["variant"], ("stale_rate", "transposed"))
                        _, g = run_one(ep, "oracle")
                        self.assertEqual(g["reward"], 1.0)
                        _, a = run_one(ep, "auditor", isolated=False)
                        self.assertTrue(a["closed"] and a["tp"] == 2 and a["fp"] == 0, a["missed_issues"])
        self.assertGreater(fallback_months, 15)

    def test_a_dst_change_after_the_boundary_leaves_no_row_in_its_hour(self):
        """America/New_York 2026-10: daylight time ends at 02:00 on Sunday 1 November, right after the boundary. The
        receipt's UTC-wall-clock posting must stay out of the hour ordinary documents avoid (else a public tell) and keep
        the receipt's UTC wall clock as its local wall clock."""
        from datetime import timedelta, timezone

        from auditgym.timeutil import in_ambiguous_hour, offset_minutes, parse_ts

        def utc_wall(inst):
            return inst.astimezone(timezone.utc).replace(tzinfo=None)

        tz = "America/New_York"
        for seed in range(1, 13):
            with self.subTest(seed=seed):
                ep = generate_episode(seed, {"period": "2026-10", "timezone": tz, "interacting": ["boundary_fx_payment"],
                                             "ts_repr": "local"}).episode
                self.assertTrue(verify_generated(ep)["ok"], verify_generated(ep)["failures"][:2])
                self.assertEqual([r["row_id"] for r in ep.ledger if in_ambiguous_hour(tz, parse_ts(r["timestamp"]))], [])
                pay = next(i for i in ep.truth["issues"] if i["type"] == "wrong_period")["affected_ids"][0]
                receipt = parse_ts(next(p for p in ep.payments if p["payment_id"] == pay)["timestamp"])
                rows = [r for r in ep.ledger if r["payment_id"] == pay]
                self.assertTrue(rows)
                for r in rows:  # booked by the receipt's UTC wall clock: the posting's local wall clock is that clock
                    post = parse_ts(r["timestamp"])
                    self.assertEqual(utc_wall(post) + timedelta(minutes=offset_minutes(tz, post)), utc_wall(receipt))

    def test_both_scenarios_in_a_fallback_month_and_a_zero_offset_refusal(self):
        for seed in (1, 2, 3):
            with self.subTest(seed=seed):
                ep = generate_episode(seed, {"period": "2025-10", "timezone": "Asia/Almaty",
                                             "interacting": ["boundary_fx_payment", "fx_invoice_partial_allocation"]}).episode
                self.assertTrue(verify_generated(ep)["ok"], verify_generated(ep)["failures"][:2])
                self.assertEqual({i["scenario"] for i in ep.truth["issues"]},
                                 {"boundary_fx_payment", "fx_invoice_partial_allocation"})
                _, a = run_one(ep, "auditor", isolated=False)
                self.assertTrue(a["closed"] and a["fp"] == 0 and a["tp"] == len(ep.truth["issues"]), a["missed_issues"])
        with self.assertRaises(ConfigError) as cm:  # Europe/London has a zero offset at the end of January
            generate_episode(1, {"period": "2026-01", "timezone": "Europe/London", "interacting": ["boundary_fx_payment"]})
        self.assertIn("non-zero UTC offset", str(cm.exception))

    def test_utc_date_amount_rule(self):
        from auditgym.config import boundary_utc_date_ok

        # 2025-10 ends on Friday, 2026-01 on Saturday, 2026-05 on Sunday, 2025-09 on Tuesday
        self.assertFalse(boundary_utc_date_ok("2025-10", 300) or boundary_utc_date_ok("2025-10", -300))
        self.assertFalse(boundary_utc_date_ok("2026-01", 300) or boundary_utc_date_ok("2026-01", -300))
        self.assertTrue(boundary_utc_date_ok("2026-05", 300))
        self.assertFalse(boundary_utc_date_ok("2026-05", -300))
        self.assertTrue(boundary_utc_date_ok("2025-09", 300) and boundary_utc_date_ok("2025-09", -300))
        self.assertFalse(boundary_utc_date_ok("2025-09", 0))

    def test_limited_to_utc_date_a_degenerate_month_is_refused(self):
        with self.assertRaises(ConfigError) as cm:
            generate_episode(1, {"interacting": ["boundary_fx_payment"], "period": "2025-10",
                                 "variants": {"wrong_fx_rate": ["utc_date"]}})
        self.assertIn("Nearest feasible periods: 2025-09, 2025-11", str(cm.exception))
        with self.assertRaises(ConfigError) as cm:
            generate_episode(1, {"interacting": ["boundary_fx_payment"], "period": "2025-10", "timezone": "America/Sao_Paulo",
                                 "variants": {"wrong_fx_rate": ["utc_date"]}})
        self.assertIn("Nearest feasible periods: 2025-09, 2025-12", str(cm.exception))
        ep = generate_episode(1, {"interacting": ["boundary_fx_payment"], "period": "2025-10",
                                  "variants": {"wrong_fx_rate": ["transposed"]}}).episode
        self.assertEqual([i["variant"] for i in ep.truth["issues"] if i["type"] == "wrong_fx_rate"], ["transposed"])


if __name__ == "__main__":
    unittest.main()
