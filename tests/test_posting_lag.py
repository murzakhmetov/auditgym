"""Posting lags: a posting is booked at its own moment inside the document's period (policy posting_rules.posting_timestamp).

Round 8: in the data before it, a document that is not an opening item had a posting row at another instant than its own
timestamp exactly when it was in the answer key (14 of 14 committed, 54 of 54 on 100 generated episodes), because the policy said
a posting's ledger timestamp equals its document's timestamp. The distractor kind posting_lag gives clean documents of both sides,
both currencies and both kinds a lag in four shapes, and documents of error issues take lags at the same rate. These tests pin the
policy text, the four shapes, the period and order limits, the independence of the count, and every reader of posting instants.
"""

import copy
import json
import unittest
from collections import Counter
from datetime import timedelta
from pathlib import Path

from auditgym import config as cfgmod
from auditgym import tells
from auditgym.auditor import OffsetSchedule, Rates, _convert_minor, audit_episode
from auditgym.config import ConfigError
from auditgym.episode import load_episode
from auditgym.generator import generate_episode
from auditgym.rng import Rng
from auditgym.timeutil import format_utc, parse_ts
from auditgym.transform import _shift_text, transform_episode
from auditgym.verify import derive_from_evidence

ROOT = Path(__file__).resolve().parent.parent
SHAPES = ("later", "earlier", "utc_wall_clock", "date_change")
_CACHE = {}


def committed() -> dict:
    if "committed" not in _CACHE:
        index = json.loads((ROOT / "episodes" / "index.json").read_text(encoding="utf-8"))["episodes"]
        _CACHE["committed"] = {e["name"]: load_episode(ROOT / "episodes" / e["split"] / e["name"]) for e in index}
    return _CACHE["committed"]


def gen(seed, cfg):
    key = (seed, json.dumps(cfg, sort_keys=True))
    if key not in _CACHE:
        _CACHE[key] = generate_episode(seed, cfg).episode
    return _CACHE[key]


def postings(ep) -> dict:
    """{invoice_id or payment_id: (document, document instant, posting instant, posting rows)} for every document with its
    own posting rows. Opening items (carried in at period start against 3900) have none."""
    inv_rows, pay_rows = {}, {}
    for r in ep.ledger:
        if r["payment_id"]:
            pay_rows.setdefault(r["payment_id"], []).append(r)
        elif r["invoice_id"]:
            inv_rows.setdefault(r["invoice_id"], []).append(r)
    out = {}
    for d in ep.invoices:
        rows = inv_rows.get(d["invoice_id"], [])
        if rows and not any(r["account"] == "3900" for r in rows):
            out[d["invoice_id"]] = (d, parse_ts(d["issued_at"]), parse_ts(rows[0]["timestamp"]), rows)
    for d in ep.payments:
        rows = pay_rows.get(d["payment_id"], [])
        if rows:
            out[d["payment_id"]] = (d, parse_ts(d["timestamp"]), parse_ts(rows[0]["timestamp"]), rows)
    return out


def periods(ep):
    return parse_ts(ep.policy["reporting_period"]["start"]), parse_ts(ep.policy["reporting_period"]["end"])


def lagged(ep) -> dict:
    return {i: v for i, v in postings(ep).items() if v[1] != v[2]}


def crossing_ids(ep) -> set:
    return {a for t in ep.truth["issues"] if t["type"] == "wrong_period" for a in t["affected_ids"]}


GEN_CASES = [
    (101, {"size": "small", "errors": {"duplicate_invoice": 1, "unallocated_payment": 1, "wrong_fx_rate": 1}}),
    (102, {"size": "medium", "errors": {"unallocated_payment": 2, "wrong_fx_rate": 2, "wrong_period": 1}}),
    (103, {"size": "small", "base_currency": "KZT", "timezone": "Asia/Almaty", "errors": {"wrong_period": 2, "duplicate_invoice": 1}}),
    (104, {"size": "small"}),
    (105, {"size": "large", "base_currency": "USD", "timezone": "America/New_York", "errors": {"wrong_fx_rate": 2, "duplicate_invoice": 2}}),
    (106, {"size": "medium", "interacting": ["boundary_fx_payment", "fx_invoice_partial_allocation"]}),
]


class PolicyTextTests(unittest.TestCase):
    def test_a_posting_is_booked_at_its_own_moment_in_its_documents_period(self):
        text = gen(*GEN_CASES[3]).policy["posting_rules"]["posting_timestamp"]
        for words in ("own moment", "earlier or later than its document's timestamp", "same reporting period",
                      "never changes an amount", "exchange rates follow the document", "never the posting moment"):
            self.assertIn(words, text)
        self.assertNotIn("equals its document's timestamp", text)

    def test_the_task_text_does_not_contradict_the_policy(self):
        from auditgym.task import FINDING_TYPE_RULES

        self.assertIn("another moment inside the document's own period is ordinary", FINDING_TYPE_RULES["wrong_period"]["meaning"])
        self.assertIn("not the moment it was posted", FINDING_TYPE_RULES["wrong_fx_rate"]["meaning"])
        self.assertNotIn("posted at that timestamp", gen(*GEN_CASES[3]).policy["duplicate_rule"])

    def test_every_committed_episode_publishes_the_new_rule(self):
        for name, ep in committed().items():
            with self.subTest(episode=name):
                self.assertIn("own moment", ep.policy["posting_rules"]["posting_timestamp"])


class ShapeTests(unittest.TestCase):
    """Every shape is present in the committed set and in generated episodes, and each one is what its name says."""

    def lag_distractors(self, ep):
        post = postings(ep)
        return [(d["shape"], post[d["ids"][0]]) for d in ep.provenance["distractors"] if d["kind"] == "posting_lag"]

    def check_shape(self, ep, shape, entry):
        doc, inst, post, rows = entry
        sched = OffsetSchedule(ep.policy["utc_offset_schedule"])
        lag = post - inst
        self.assertNotEqual(lag, timedelta(0))
        if shape == "later":
            self.assertGreater(lag, timedelta(0))
        elif shape == "earlier":
            self.assertLess(lag, timedelta(0))
        elif shape == "utc_wall_clock":
            self.assertEqual(lag, -timedelta(minutes=sched.offset_at(inst)))
            self.assertNotEqual(sched.offset_at(inst), 0)
        else:
            base = ep.manifest["base_currency"]
            self.assertNotEqual(doc["currency"], base)
            self.assertNotEqual(sched.local_date(post), sched.local_date(inst))
            rates = Rates(ep.fx, base)
            r_doc, _ = rates.for_date(doc["currency"], sched.local_date(inst))
            r_post, _ = rates.for_date(doc["currency"], sched.local_date(post))
            self.assertNotEqual(r_doc, r_post, "the posting date has the same rate: not a hard negative")
            exps = ep.policy["currency_exponents"]
            amount = doc["total_minor"] if "invoice_id" in doc else doc["amount_minor"]
            row = next(r for r in rows if r["account"] in (("1100", "2000") if "invoice_id" in doc else ("1000",)))
            booked = row["debit_minor"] or row["credit_minor"]
            mode = ep.policy["rounding"]["mode"]
            self.assertEqual(booked, _convert_minor(amount, r_doc, exps[doc["currency"]], exps[base], mode))
            self.assertNotEqual(booked, _convert_minor(amount, r_post, exps[doc["currency"]], exps[base], mode))

    def test_the_committed_set_holds_every_shape_and_each_is_what_it_says(self):
        seen = Counter()
        for name, ep in committed().items():
            for shape, entry in self.lag_distractors(ep):
                with self.subTest(episode=name, shape=shape):
                    self.check_shape(ep, shape, entry)
                seen[shape] += 1
        self.assertEqual(set(seen), set(SHAPES), seen)

    def test_both_sides_both_currencies_and_both_kinds_take_lags(self):
        kinds, currencies = set(), set()
        for ep in committed().values():
            for doc, _inst, _post, _rows in (v for v in lagged(ep).values()):
                kinds.add(("invoice", doc["kind"]) if "invoice_id" in doc else ("payment", doc["kind"]))
                currencies.add(doc["currency"] == ep.manifest["base_currency"])
        self.assertTrue({("invoice", "sales"), ("invoice", "purchase"), ("payment", "receipt"), ("payment", "disbursement")} <= kinds, kinds)
        self.assertEqual(currencies, {True, False})

    def test_every_committed_episode_has_lags_of_each_available_shape_in_its_provenance(self):
        for name, ep in committed().items():
            shapes = {s for s, _e in self.lag_distractors(ep)}
            with self.subTest(episode=name):
                self.assertGreaterEqual(len(shapes), 2, shapes)
                self.assertTrue(shapes <= set(SHAPES))

    def test_generated_episodes_carry_every_shape(self):
        seen = Counter()
        for case in GEN_CASES:
            ep = gen(*case)
            for shape, entry in self.lag_distractors(ep):
                self.check_shape(ep, shape, entry)
                seen[shape] += 1
        self.assertEqual(set(seen), set(SHAPES), seen)

    def test_lags_include_under_an_hour_and_several_days(self):
        lags = [abs(v[2] - v[1]) for case in GEN_CASES for v in lagged(gen(*case)).values()]
        self.assertTrue(any(x < timedelta(hours=1) for x in lags))
        self.assertTrue(any(x >= timedelta(days=2) for x in lags))


class LimitTests(unittest.TestCase):
    def test_a_lag_never_crosses_a_period(self):
        for case in GEN_CASES:
            ep = gen(*case)
            p0, p1 = periods(ep)
            skip = crossing_ids(ep)
            extract_end = parse_ts(ep.policy["ledger_extract"]["end"])
            n = 0
            for i, (doc, inst, post, rows) in postings(ep).items():
                if i in skip or post == inst:
                    continue
                n += 1
                with self.subTest(seed=case[0], document=i):
                    self.assertEqual(p0 <= inst < p1, p0 <= post < p1, (inst, post))
                    self.assertTrue(p0 <= post < extract_end)
                    self.assertEqual(len({parse_ts(r["timestamp"]) for r in rows}), 1)
            self.assertGreater(n, 5)

    def test_a_lag_never_changes_an_amount_or_the_posting_order(self):
        # every invoice is posted no later than the payments that settle it: the allocations are the ones of the document order
        for seed, cfg in GEN_CASES[:2] + GEN_CASES[3:5]:
            ep = gen(seed, cfg)
            post = postings(ep)
            for pay in ep.payments:
                for ref in pay["invoice_refs"] or []:
                    # a receipt that precedes its invoice (a prepayment) keeps that order as well
                    if ref in post and not crossing_ids(ep) and post[ref][1] <= post[pay["payment_id"]][1]:
                        with self.subTest(seed=seed, payment=pay["payment_id"], invoice=ref):
                            self.assertLessEqual(post[ref][2], post[pay["payment_id"]][2])

    def test_a_lag_moves_timestamps_only_never_an_amount_or_an_allocation(self):
        # the generator retries an attempt whose books fail verification, which would hide a lag that reorders an invoice and its
        # payments: so build the histories directly, post them with and without their lags and compare every row but its timestamp
        from auditgym.books import BooksError, post
        from auditgym.generator import _base_text
        from auditgym.history import HistoryBuilder, SampleRetry
        from auditgym.inject import plan_errors, plan_posting_lags

        cfg = {"size": "small", "errors": {"duplicate_invoice": 1, "unallocated_payment": 1, "wrong_fx_rate": 1}}
        checked = lagged_docs = 0
        for seed in range(150):
            rng0 = Rng(_base_text(seed, cfg, None))
            resolved = cfgmod.resolve(cfg, rng0.fork("config"))
            b = HistoryBuilder(rng0.fork("attempt:0").fork("history"), resolved)
            try:
                b.build_entities()
                b.build_regular()
                b.build_distractors()
                b.choose_holidays()
                plan = plan_errors(b, resolved)
                b.build_fx()
            except SampleRetry:
                continue
            plan_posting_lags(b, plan)
            docs = [*b.h.invoices.values(), *plan.extra_invoices, *b.h.payments.values()]
            lagged_docs += sum(d.posted is not None for d in docs)
            try:
                with_lags = post(b.h)
            except BooksError as exc:
                self.fail(f"seed {seed}: the books with lags cannot be posted: {exc}")
            saved = {id(d): d.posted for d in docs}
            for d in docs:
                d.posted = None
            without = post(b.h)
            for d in docs:
                d.posted = saved[id(d)]
            amounts = lambda books: {ln.ident: (ln.account, ln.debit, ln.credit, ln.invoice, ln.payment) for ln in books.lines}
            self.assertEqual(amounts(with_lags), amounts(without), seed)
            checked += 1
        self.assertGreater(checked, 100)
        self.assertGreater(lagged_docs, 1000)

    def test_lagged_documents_are_booked_at_the_rate_of_their_own_date(self):
        for case in GEN_CASES:
            ep = gen(*case)
            self.assertEqual(audit_episode(ep)["anomalies"], [])  # an amount at another rate would be a finding the key lacks
            keyed = {(t["type"], tuple(sorted(t["affected_ids"]))) for t in ep.truth["issues"]}
            found = {(f["type"], tuple(sorted(f["affected_ids"]))) for f in audit_episode(ep)["findings"]}
            self.assertEqual(found, keyed)

    def test_the_count_never_depends_on_the_error_count(self):
        lo, hi = cfgmod.DEFAULT_DISTRACTOR_RANGES["medium"]["posting_lag"]
        means = []
        for errors in ({}, {"duplicate_invoice": 1}, {"duplicate_invoice": 2, "wrong_period": 2, "unallocated_payment": 2}):
            drawn = [cfgmod.resolve({"size": "medium", "errors": errors}, Rng(f"n{n}"))["distractors"]["posting_lag"] for n in range(300)]
            self.assertTrue(lo <= min(drawn) and max(drawn) <= hi, errors)
            means.append(sum(drawn) / len(drawn))
        self.assertLess(max(means) - min(means), 1.5, means)  # the range is the same whatever the errors
        # and the postings at another instant of an episode are exactly that many, the errors' own postings included: the lags of
        # ordinary documents fill what the errors leave of the count (the visible total never reveals an error episode)
        cases = ({}, {"duplicate_invoice": 2, "wrong_period": 1}, {"wrong_period": 2, "wrong_fx_rate": 2, "unallocated_payment": 2})
        for seed in (1, 2, 3):
            for errors in cases:
                ep = generate_episode(seed, {"size": "medium", "errors": errors}).episode
                self.assertEqual(len(lagged(ep)), ep.provenance["resolved_config"]["distractors"]["posting_lag"], (seed, errors))

    def test_the_range_is_per_size_and_an_explicit_count_stays_exact(self):
        for size, (lo, hi) in {s: r["posting_lag"] for s, r in cfgmod.DEFAULT_DISTRACTOR_RANGES.items()}.items():
            drawn = {cfgmod.resolve({"size": size}, Rng(f"lag{n}"))["distractors"]["posting_lag"] for n in range(40)}
            self.assertTrue(drawn <= set(range(lo, hi + 1)) and len(drawn) > 3, (size, drawn))
        cfg = cfgmod.resolve({"size": "small", "distractors": {"posting_lag": 5}}, Rng("x"))
        self.assertEqual(cfg["distractors"]["posting_lag"], 5)
        ep = generate_episode(7, {"size": "small", "distractors": {"posting_lag": 0}}).episode
        self.assertEqual(lagged(ep), {})
        self.assertEqual(ep.provenance["posting_lags"], [])
        # an explicit count is exact or the attempt is resampled; it is never silently lowered (64 on a small ledger: 62 placed once)
        from auditgym.generator import GenerationError

        for seed in range(8):
            try:
                ep = generate_episode(seed, {"size": "small", "errors": {}, "distractors": {"posting_lag": cfgmod.MAX_POSTING_LAG}}).episode
            except GenerationError:
                continue
            self.assertEqual(len(lagged(ep)), cfgmod.MAX_POSTING_LAG, seed)
        quiet = {k: 0 for k in ("credit_receipt", "prepaid_receipt", "split_remainder", "overpayment_refund", "null_ref_receipt",
                                "boundary_doc", "midnight_fx", "weekend_fx", "recurring", "split_payment", "multi_invoice_payment",
                                "underpayment", "legit_repeat")}
        tiny = {"size": "small", "errors": {}, "distractors": {**quiet, "posting_lag": cfgmod.MAX_POSTING_LAG},
                "counts": {"sales_invoices": 1, "purchase_invoices": 1, "prior_invoices": 0}}
        with self.assertRaises(GenerationError):  # fewer eligible documents than lags: resampled until the attempts run out
            generate_episode(1, tiny)
        with self.assertRaises(ConfigError):
            cfgmod.validate({"distractors": {"posting_lag": cfgmod.MAX_POSTING_LAG + 1}})
        with self.assertRaises(ConfigError):
            cfgmod.validate({"distractors": {"boundary_doc": 9}})

    def test_the_lag_draw_moves_no_other_resolved_field(self):
        saved = {s: dict(r) for s, r in cfgmod.DEFAULT_DISTRACTOR_RANGES.items()}
        try:
            for seed in range(6):
                with_lag = cfgmod.resolve({"size": "medium", "errors": {"duplicate_invoice": 1}}, Rng(f"s{seed}"))
                for r in cfgmod.DEFAULT_DISTRACTOR_RANGES.values():
                    r.pop("posting_lag")
                without = cfgmod.resolve({"size": "medium", "errors": {"duplicate_invoice": 1}}, Rng(f"s{seed}"))
                for s, r in saved.items():
                    cfgmod.DEFAULT_DISTRACTOR_RANGES[s] = dict(r)
                with_lag["distractors"].pop("posting_lag")
                self.assertEqual(with_lag, without)
        finally:
            for s, r in saved.items():
                cfgmod.DEFAULT_DISTRACTOR_RANGES[s] = r

    def test_lag_draws_do_not_move_the_history(self):
        # the documents, the FX rates and the postings' amounts are those of an episode without lags
        saved = {s: dict(r) for s, r in cfgmod.DEFAULT_DISTRACTOR_RANGES.items()}
        try:
            for seed in (11, 12):
                # (a posting_date rate error books its own posting at another instant: not in this comparison)
                cfg = {"size": "small", "errors": {"duplicate_invoice": 1, "wrong_fx_rate": 1},
                       "variants": {"wrong_fx_rate": ["stale_rate", "transposed"]}}
                a = generate_episode(seed, cfg).episode
                for r in cfgmod.DEFAULT_DISTRACTOR_RANGES.values():
                    r.pop("posting_lag")  # the same config text, no lag distractor: the stream of everything else is unchanged
                b = generate_episode(seed, cfg).episode
                for s, r in saved.items():
                    cfgmod.DEFAULT_DISTRACTOR_RANGES[s] = dict(r)
                self.assertEqual(a.invoices, b.invoices)
                self.assertEqual(a.payments, b.payments)
                self.assertEqual(a.fx, b.fx)
                self.assertEqual(sorted((r["account"], r["debit_minor"], r["credit_minor"]) for r in a.ledger),
                                 sorted((r["account"], r["debit_minor"], r["credit_minor"]) for r in b.ledger))
                self.assertTrue(lagged(a))
                self.assertFalse(lagged(b))
        finally:
            for s, r in saved.items():
                cfgmod.DEFAULT_DISTRACTOR_RANGES[s] = r

    def test_two_generations_are_byte_identical(self):
        cfg = {"size": "medium", "errors": {"duplicate_invoice": 1, "unallocated_payment": 1}}
        a, b = generate_episode(21, cfg).episode, generate_episode(21, cfg).episode
        self.assertEqual(a.public_digest(), b.public_digest())
        self.assertEqual(a.grader_texts(), b.grader_texts())

    def test_the_twin_keeps_the_lags_of_its_source(self):
        a, b = committed()["t03_duplicate"], committed()["t10_duplicate_twin_legit"]
        self.assertEqual({i: v[2] - v[1] for i, v in lagged(a).items()}, {i: v[2] - v[1] for i, v in lagged(b).items()})
        self.assertEqual(a.ledger, b.ledger)


class GuardTests(unittest.TestCase):
    """The guards of the lag placement, each pinned by what it protects."""

    CFGS = [
        {"size": "small", "errors": {"wrong_period": 2, "wrong_fx_rate": 2, "unallocated_payment": 1}, "variants": {"wrong_fx_rate": ["posting_date"]}},
        {"size": "medium", "interacting": ["boundary_fx_payment", "fx_invoice_partial_allocation"], "errors": {"wrong_period": 1}},
        {"size": "small", "errors": {"wrong_period": 3, "wrong_fx_rate": 1}, "variants": {"wrong_fx_rate": ["posting_date", "stale_rate"]}},
    ]

    def test_a_document_whose_posting_is_the_error_never_takes_a_lag(self):
        checked = 0
        for n, cfg in enumerate(self.CFGS):
            for seed in range(30):
                ep = gen(200 + seed, cfg)
                own = set()
                for inj in ep.provenance["injections"]:
                    # (the boundary receipt is covered by its wrong_period injection; a standalone rate error on a payment
                    # that is not posting_date takes lags like any clean document, as an invoice with a wrong rate does)
                    if inj["type"] == "wrong_period" or (inj["type"] == "wrong_fx_rate" and inj["variant"] == "posting_date"):
                        own.update(inj["targets"].values())
                lagged_ids = {d["ids"][0] for d in ep.provenance["distractors"] if d["kind"] == "posting_lag"}
                lagged_ids |= {e["id"] for e in ep.provenance["posting_lags"]}
                self.assertFalse(own & lagged_ids, (n, seed, own & lagged_ids))
                checked += len(own)
        self.assertGreater(checked, 50)

    def test_payments_of_one_invoice_and_the_invoice_keep_their_document_order(self):
        pairs = 0
        for seed in range(40):
            ep = gen(300 + seed, {"size": "medium", "errors": {"unallocated_payment": 1, "duplicate_invoice": 1}})
            post, skip = postings(ep), crossing_ids(ep)
            by_inv = {}
            for p in ep.payments:
                for ref in p["invoice_refs"] or []:
                    by_inv.setdefault(ref, []).append(p["payment_id"])
            for ref, pays in by_inv.items():
                group = [i for i in [ref, *pays] if i in post and i not in skip]
                for a in group:
                    for b in group:
                        if post[a][1] < post[b][1]:
                            self.assertLess(post[a][2], post[b][2], (seed, a, b))
                            pairs += 1
        self.assertGreater(pairs, 100)

    def test_no_lagged_posting_shares_its_instant_with_another_document(self):
        checked = 0
        for seed in range(150):
            ep = gen(400 + seed, {"size": "small", "errors": {"wrong_fx_rate": 1, "duplicate_invoice": 1}})
            post = postings(ep)
            for i, (_doc, inst, at, _rows) in post.items():
                if at == inst:
                    continue
                others = [(j, v) for j, v in post.items() if j != i]
                self.assertFalse(any(v[1] == at or v[2] == at for _j, v in others), (seed, i))
                checked += 1
        self.assertGreater(checked, 1000)


    def test_two_copies_of_one_instant_never_get_one_posting_instant(self):
        # the UTC wall-clock shape is deterministic (instant minus the offset), so two same-instant copies would collide on it
        cfg = {"size": "small", "errors": {}, "variants": {"duplicate_invoice": ["same_day_copy"]},
               "distractors": {"legit_repeat": 4, "posting_lag": 45}}
        checked = 0
        for seed in range(60):
            post = postings(gen(500 + seed, cfg))
            at = [v[2] for v in post.values() if v[1] != v[2]]
            self.assertEqual(len(at), len(set(at)), seed)
            checked += len(at)
        self.assertGreater(checked, 1500)


class ErrorDocumentTests(unittest.TestCase):
    """A lag does not mark a document clean either: documents of error issues take lags, and the issue and its evidence stay valid."""

    def error_cases(self):
        for etype in ("duplicate_invoice", "unallocated_payment", "wrong_fx_rate"):
            for seed in range(40):
                ep = gen(seed, {"size": "medium", "errors": {etype: 2}})
                post = lagged(ep)
                hit = [t for t in ep.truth["issues"] if any(a in post for a in t["affected_ids"])]
                if hit:
                    yield etype, ep, hit
                    break
            else:
                self.fail(f"no episode with a lagged {etype} document in 40 seeds")

    def test_the_evidence_of_an_issue_with_a_lagged_document_derives_the_key(self):
        for etype, ep, hit in self.error_cases():
            for t in hit:
                for es in t["evidence_sets"]:
                    with self.subTest(type=etype, issue=t["issue_id"]):
                        got = derive_from_evidence(t["type"], es, ep)
                        self.assertEqual(got, (t["type"], frozenset(t["affected_ids"]), t["expected_amount_minor"]))

    def test_a_duplicate_copy_posted_at_another_moment_still_supports_the_finding(self):
        for seed in range(60):
            ep = copy.deepcopy(gen(seed, {"size": "small", "errors": {"duplicate_invoice": 1}, "distractors": {"posting_lag": 0}}))
            t = ep.truth["issues"][0]
            es = t["evidence_sets"][0]
            copy_id = next(r["invoice_id"] for r in ep.invoices if r["doc_id"] in es and r["invoice_id"] == t["affected_ids"][1])
            p0, p1 = periods(ep)
            rows = [r for r in ep.ledger if r["row_id"] in es and r["invoice_id"] == copy_id]
            inst = parse_ts(rows[0]["timestamp"])
            if p0 < inst - timedelta(hours=26) and inst + timedelta(hours=26) < p1:
                for shift in (timedelta(hours=26), -timedelta(hours=26)):
                    moved = copy.deepcopy(ep)
                    for r in moved.ledger:
                        if r["row_id"] in {x["row_id"] for x in rows}:
                            r["timestamp"] = format_utc(parse_ts(r["timestamp"]) + shift)
                    self.assertEqual(derive_from_evidence(t["type"], es, moved),
                                     (t["type"], frozenset(t["affected_ids"]), t["expected_amount_minor"]))
                    for r in moved.ledger:  # out of the period: no longer the invoice's posting in its period
                        if r["row_id"] in {x["row_id"] for x in rows}:
                            r["timestamp"] = format_utc(p1 + timedelta(days=1))
                    self.assertIsNone(derive_from_evidence(t["type"], es, moved))
                return
        self.fail("no duplicate with room for a lag")

    def test_lags_also_occur_on_answer_key_documents_not_only_on_clean_ones(self):
        keyed = lagged_keyed = 0
        for etype in ("duplicate_invoice", "unallocated_payment", "wrong_fx_rate"):
            for seed in range(25):
                ep = gen(seed, {"size": "small", "errors": {etype: 1}})
                post = lagged(ep)
                for t in ep.truth["issues"]:
                    for a in t["affected_ids"]:
                        keyed += a in postings(ep)
                        lagged_keyed += a in post
        self.assertGreater(lagged_keyed, 0)
        self.assertLess(lagged_keyed, keyed)  # but not all of them: the rate is the clean one, about a quarter

    def test_the_period_errors_still_cross_the_boundary(self):
        for case in GEN_CASES[1:3]:
            ep = gen(*case)
            p0, p1 = periods(ep)
            ids = crossing_ids(ep)
            self.assertTrue(ids)
            post = postings(ep)
            for i in ids:
                _doc, inst, at, _rows = post[i]
                self.assertNotEqual(p0 <= inst < p1, p0 <= at < p1)


class ReaderTests(unittest.TestCase):
    """The readers of posting instants accept a lag: the independent auditor, the evidence checker, the transforms."""

    def clean_with_lags(self):
        ep = gen(104, {"size": "small"})
        self.assertTrue(lagged(ep))
        return ep

    def test_the_auditor_ignores_a_lag(self):
        ep = self.clean_with_lags()
        self.assertEqual(audit_episode(ep), {"findings": [], "anomalies": []})
        p0, p1 = periods(ep)
        post = postings(ep)
        # move an unpaid in-period invoice's posting by hours either way: still nothing to find
        paid = {r for p in ep.payments for r in (p["invoice_refs"] or [])}
        pick = [i for i, (d, inst, at, rows) in post.items() if "invoice_id" in d and i not in paid
                and p0 + timedelta(days=3) < inst < p1 - timedelta(days=3)]
        self.assertTrue(pick)
        for shift in (timedelta(hours=5), -timedelta(hours=40), timedelta(days=3)):
            moved = copy.deepcopy(ep)
            ids = {r["row_id"] for r in post[pick[0]][3]}
            for r in moved.ledger:
                if r["row_id"] in ids:
                    r["timestamp"] = format_utc(parse_ts(r["timestamp"]) + shift)
            self.assertEqual(audit_episode(moved), {"findings": [], "anomalies": []}, shift)

    def test_the_scripted_auditor_equals_the_key_on_episodes_with_lags(self):
        from auditgym.runner import run_one

        for name in ("t08_fx_partial_allocation", "d03_duplicates_gbp", "d10_large_dense_quarter_hour"):
            ep = committed()[name]
            self.assertTrue(lagged(ep))
            _traj, grade = run_one(ep, "auditor", isolated=False)
            self.assertEqual((grade["fp"], grade["fn"]), (0, 0), name)

    def test_the_recon_baseline_survives_lags(self):
        from auditgym.runner import run_one

        for name in ("t01_clean_small", "d05_fx_utc_stale_mixed_ts"):
            _traj, grade = run_one(committed()[name], "recon", isolated=False)
            self.assertIsNone(grade.get("agent_error"), name)

    def test_transform_preserves_every_lag(self):
        ep = committed()["t08_fx_partial_allocation"]
        want = {i: v[2] - v[1] for i, v in lagged(ep).items()}
        self.assertTrue(want)
        for kwargs in ({"ts_repr": "utc"}, {"ts_repr": "mixed"}, {"permute_seed": 3}, {"rename_seed": 4}, {"shift_years": 28}):
            with self.subTest(kwargs=kwargs):
                new = transform_episode(ep, **kwargs)
                # a year shift also moves the year inside a dated ID (id_style "dated": SI/2027/... becomes SI/2055/...)
                moved = {_shift_text(i, 28): v for i, v in want.items()} if "shift_years" in kwargs else want
                self.assertEqual({i: v[2] - v[1] for i, v in lagged(new).items()}, moved)
        remapped = transform_episode(ep, remap_seed=9)
        self.assertEqual(sorted(v[2] - v[1] for v in lagged(remapped).values()), sorted(want.values()))
        public = {d["invoice_id"] for d in remapped.invoices} | {d["payment_id"] for d in remapped.payments}
        self.assertTrue(ep.provenance["posting_lags"])
        for e in remapped.provenance["posting_lags"]:  # the provenance follows the remapped IDs
            self.assertIn(e["id"], public)
        for d in remapped.provenance["distractors"]:
            self.assertTrue(set(d["ids"]) <= public)

    def test_the_tells_see_the_lags_of_the_public_records(self):
        ep = committed()["d05_fx_utc_stale_mixed_ts"]
        c = tells.Ctx(ep)
        post = postings(ep)
        sched = OffsetSchedule(ep.policy["utc_offset_schedule"])
        want_off = {i for i, (_d, inst, at, _r) in post.items() if at - inst == -timedelta(minutes=sched.offset_at(inst)) and at != inst}
        want_short = {i for i, (_d, inst, at, _r) in post.items() if timedelta(0) < abs(at - inst) < timedelta(hours=1)}
        want_later = {i for i, (_d, inst, at, _r) in post.items() if at > inst}
        self.assertEqual({i for i in c.docs if tells.RULES["lag equals the zone offset"](c, i)}, want_off)
        self.assertEqual({i for i in c.docs if tells.RULES["lag of less than one hour"](c, i)}, want_short)
        self.assertEqual({i for i in c.docs if tells.RULES["posted later than its document"](c, i)}, want_later)
        self.assertEqual({i for i in c.docs if tells.RULES["posting row at a different instant than its document"](c, i)}, set(lagged(ep)))
        early = {i for i, v in lagged(ep).items() if v[2] < v[1]}
        self.assertEqual({i for i in c.docs if tells.RULES["posted earlier than its document"](c, i)}, early)
        self.assertTrue(want_off and early and want_later)
        base = ep.manifest["base_currency"]
        date_change = {i for i, (d, inst, at, _r) in post.items()
                       if at != inst and d["currency"] != base and sched.local_date(at) != sched.local_date(inst)}
        self.assertEqual({i for i in c.docs if tells.RULES["lag across a date change on a foreign-currency document"](c, i)}, date_change)
        self.assertTrue(tells.EPISODE_RULES["any posting at a different instant than its document -> error"][1](c))


if __name__ == "__main__":
    unittest.main()
