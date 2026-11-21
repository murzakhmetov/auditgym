"""Payments as targets of the standalone wrong_fx_rate and wrong_period errors (version 0.4.0).

Before 0.4.0 both errors were always injected on a new invoice; a receipt carried one only as the boundary receipt of the
boundary_fx_payment scenario, and no disbursement was ever in an answer key, so a policy could skip the payments for these
two types. Now config.resolve draws the kind of every standalone target (invoice, receipt, disbursement) with
config.TARGET_KIND_SHARES, and a payment target comes with the invoice it settles. These tests pin, for every variant on a
receipt and on a disbursement: what the variant means on a payment, that the settlement is the clean one (same relief,
nothing in 2900, the invoice booked first in both sets of books), the answer key and its evidence, the scripted auditor,
the evidence checker, the share, the paid slots, the tells rules and the committed coverage.
"""

import json
import unittest
from collections import Counter
from datetime import timedelta
from pathlib import Path
from unittest import mock

from auditgym import config as cfgmod
from auditgym import tells
from auditgym.auditor import OffsetSchedule, audit_episode
from auditgym.episode import load_episode
from auditgym.evidence_check import convert_fraction, derive_from_evidence
from auditgym.generator import generate_episode
from auditgym.history import HistoryBuilder, LineItem
from auditgym.rng import Rng
from auditgym.timeutil import in_ambiguous_hour, offset_minutes, parse_ts
from auditgym.verify import compare_with_truth

ROOT = Path(__file__).resolve().parent.parent
ONLY = {"invoice": (1.0, 0.0, 0.0), "receipt": (0.0, 1.0, 0.0), "disbursement": (0.0, 0.0, 1.0)}
PAYMENT_KINDS = ("receipt", "disbursement")
FX_VARIANTS = ("utc_date", "posting_date", "stale_rate", "transposed")
PERIOD_VARIANTS = ("booked_early", "booked_late", "utc_wall_clock")
RELIEF_ACCOUNT = {"receipt": "1100", "disbursement": "2000"}
_CACHE = {}


def gen(seed, etype: str, variant: str, kind: str, **extra):
    """One standalone error of `etype` and `variant` on a target of `kind` (the share is patched to that kind alone)."""
    cfg = {"size": "small", "timezone": "Asia/Almaty", "errors": {etype: 1}, "variants": {etype: [variant]}, **extra}
    key = (seed, kind, json.dumps(cfg, sort_keys=True))
    if key not in _CACHE:
        with mock.patch.object(cfgmod, "TARGET_KIND_SHARES", ONLY[kind]):
            _CACHE[key] = generate_episode(seed, cfg)
    return _CACHE[key]


class Case:
    """The one issue of a generated episode with a payment target, and the records around it."""

    def __init__(self, g):
        self.g, self.ep, self.clean = g, g.episode, g.clean
        ep = self.ep
        self.inj = ep.provenance["injections"][0]
        self.issue = ep.truth["issues"][0]
        self.pid = self.inj["targets"]["payment"]
        self.pay = next(p for p in ep.payments if p["payment_id"] == self.pid)
        self.rows = [r for r in ep.ledger if r["payment_id"] == self.pid]
        self.clean_rows = [r for r in self.clean.ledger if r["payment_id"] == self.pid]
        self.bank = next(r for r in self.rows if r["account"] == "1000")
        self.clean_bank = next(r for r in self.clean_rows if r["account"] == "1000")
        pol = ep.policy
        self.base = pol["base_currency"]
        self.exps = pol["currency_exponents"]
        self.mode = pol["rounding"]["mode"]
        self.p0, self.p1 = parse_ts(pol["reporting_period"]["start"]), parse_ts(pol["reporting_period"]["end"])
        self.sched = OffsetSchedule(pol["utc_offset_schedule"])
        self.ts = parse_ts(self.pay["timestamp"])
        self.posting = parse_ts(self.bank["timestamp"])
        self.invoice = next(i for i in ep.invoices if i["invoice_id"] == self.pay["invoice_refs"][0])

    def in_period(self, inst) -> bool:
        return self.p0 <= inst < self.p1

    def convert(self, rate: str) -> int:
        ccy = self.pay["currency"]
        return convert_fraction(self.pay["amount_minor"], rate, self.exps[ccy], self.exps[self.base], self.mode)

    def policy_rate(self, day):
        """(rate, date text) of the latest rate published on or before `day`."""
        table = {r["date"]: r["rate"] for r in self.ep.fx
                 if r["source_currency"] == self.pay["currency"] and r["target_currency"] == self.base}
        for back in range(15):
            text = (day - timedelta(days=back)).isoformat()
            if text in table:
                return table[text], text
        raise AssertionError("no rate")

    @staticmethod
    def amounts(rows, account) -> list:
        return sorted((r["invoice_id"], r["debit_minor"], r["credit_minor"]) for r in rows if r["account"] == account)


class Common(unittest.TestCase):
    def check_target_and_settlement(self, c: Case, etype: str, variant: str, kind: str):
        """What holds for every payment target: the key names the payment alone, and it settles its invoice as in the clean
        books: the same relief, nothing in 2900, the invoice booked before it in both sets of books."""
        ep = c.ep
        self.assertTrue(c.g.verification["ok"], c.g.verification["failures"])
        self.assertEqual((c.inj["type"], c.inj["variant"], c.inj["scenario"]), (etype, variant, "single"))
        self.assertEqual(c.inj["targets"], {"payment": c.pid})
        self.assertEqual(c.pay["kind"], kind)
        self.assertEqual(len(ep.truth["issues"]), 1)
        self.assertEqual((c.issue["type"], c.issue["affected_ids"]), (etype, [c.pid]))
        self.assertEqual(c.invoice["kind"], "sales" if kind == "receipt" else "purchase")
        self.assertEqual(c.invoice["currency"], c.pay["currency"])
        self.assertLessEqual(c.pay["amount_minor"], c.invoice["total_minor"])
        relief = RELIEF_ACCOUNT[kind]
        for rows in (c.rows, c.clean_rows):
            self.assertFalse([r for r in rows if r["account"] == "2900"])  # nothing unallocated, no customer credit
            self.assertEqual(sum(r["debit_minor"] for r in rows), sum(r["credit_minor"] for r in rows))
            self.assertEqual(len({parse_ts(r["timestamp"]) for r in rows}), 1)
        self.assertEqual(c.amounts(c.rows, relief), c.amounts(c.clean_rows, relief))
        self.assertEqual([x[0] for x in c.amounts(c.rows, relief)], [c.invoice["invoice_id"]])
        for ledger, rows in ((ep.ledger, c.rows), (c.clean.ledger, c.clean_rows)):
            booked = [parse_ts(r["timestamp"]) for r in ledger if r["invoice_id"] == c.invoice["invoice_id"] and not r["payment_id"]]
            self.assertTrue(booked)
            self.assertLess(max(booked), parse_ts(rows[0]["timestamp"]))
        # no other payment lists the invoice and the invoice is not in the key: the error creates and hides nothing else
        self.assertEqual([p["payment_id"] for p in ep.payments if c.invoice["invoice_id"] in (p["invoice_refs"] or [])], [c.pid])

    def check_auditor_and_checker(self, c: Case):
        found = audit_episode(c.ep)
        self.assertEqual(found["anomalies"], [])
        self.assertEqual(compare_with_truth(found, c.ep.truth), [])
        self.assertEqual([(f["type"], f["affected_ids"], f["amount"]) for f in found["findings"]],
                         [(c.issue["type"], [c.pid], c.issue["expected_amount_minor"])])
        self.assertEqual(found["findings"][0]["evidence_sets"], c.issue["evidence_sets"])
        clean = audit_episode(c.clean)
        self.assertEqual((clean["findings"], clean["anomalies"]), ([], []))
        want = (c.issue["type"], frozenset([c.pid]), c.issue["expected_amount_minor"])
        for es in c.issue["evidence_sets"]:
            self.assertEqual(derive_from_evidence(c.issue["type"], es, c.ep), want)
            self.assertIsNone(derive_from_evidence(c.issue["type"], es, c.clean))  # the clean books carry no such issue
            # the settlement row is not the payment's posting: only the bank row carries the whole payment
            other = next(r for r in c.rows if r["account"] == RELIEF_ACCOUNT[c.pay["kind"]])
            swapped = [other["row_id"] if e == c.bank["row_id"] else e for e in es]
            self.assertIsNone(derive_from_evidence(c.issue["type"], swapped, c.ep))
            self.assertIsNone(derive_from_evidence(c.issue["type"], [e for e in es if e != c.pay["doc_id"]], c.ep))


class RateOnPaymentTests(Common):
    def test_every_variant_keeps_its_meaning_on_a_receipt_and_on_a_disbursement(self):
        for kind in PAYMENT_KINDS:
            for variant in FX_VARIANTS:
                for seed in (9100, 9101):
                    with self.subTest(kind=kind, variant=variant, seed=seed):
                        c = Case(gen(seed, "wrong_fx_rate", variant, kind))
                        self.check_target_and_settlement(c, "wrong_fx_rate", variant, kind)
                        ch = c.inj["change"]
                        ccy = c.pay["currency"]
                        self.assertNotEqual(ccy, c.base)
                        self.assertTrue(c.in_period(c.ts))
                        local_d = c.sched.local_date(c.ts)
                        self.assertEqual((ch["correct_rate"], ch["correct_rate_date"]), c.policy_rate(local_d))
                        # the bank row carries the whole payment at the wrong rate; the clean one at the policy rate
                        self.assertEqual(c.bank["debit_minor"] or c.bank["credit_minor"], c.convert(ch["wrong_rate"]))
                        self.assertEqual(c.clean_bank["debit_minor"] or c.clean_bank["credit_minor"], c.convert(ch["correct_rate"]))
                        delta = abs(c.convert(ch["wrong_rate"]) - c.convert(ch["correct_rate"]))
                        self.assertGreaterEqual(delta, 100)
                        self.assertEqual(c.issue["expected_amount_minor"], delta)
                        self.assertEqual(c.issue["evidence_sets"],
                                         [[c.pay["doc_id"], c.bank["row_id"], f"{ch['correct_rate_date']}:{ccy}:{c.base}"]])
                        # the settlement takes the difference: the FX row (7900) moves by exactly what the bank row moved
                        net = lambda rows: sum(r["credit_minor"] - r["debit_minor"] for r in rows if r["account"] == "7900")
                        bank_move = (c.bank["debit_minor"] - c.bank["credit_minor"]) - (c.clean_bank["debit_minor"] - c.clean_bank["credit_minor"])
                        self.assertEqual(net(c.rows) - net(c.clean_rows), bank_move)
                        if variant == "utc_date":
                            self.assertNotEqual(c.ts.date(), local_d)
                            self.assertEqual((ch["wrong_rate"], ch["wrong_rate_date"]), c.policy_rate(c.ts.date()))
                        elif variant == "posting_date":
                            self.assertEqual(c.posting, parse_ts(ch["posting_ts"]))
                            self.assertTrue(c.in_period(c.posting))  # a rate error, not a period error
                            self.assertGreater(c.sched.local_date(c.posting), local_d)
                            self.assertEqual((ch["wrong_rate"], ch["wrong_rate_date"]), c.policy_rate(c.sched.local_date(c.posting)))
                            self.assertEqual(parse_ts(c.clean_bank["timestamp"]), c.ts)
                        elif variant == "stale_rate":
                            before = c.sched.local_date(c.p0) - timedelta(days=1)
                            self.assertEqual((ch["wrong_rate"], ch["wrong_rate_date"]), c.policy_rate(before))
                        else:
                            self.assertIsNone(ch["wrong_rate_date"])
                            self.assertEqual(sorted(ch["wrong_rate"]), sorted(ch["correct_rate"]))
                            self.assertNotEqual(ch["wrong_rate"], ch["correct_rate"])
                        if variant != "posting_date":
                            self.assertNotIn("posting_ts", ch)
                        self.check_auditor_and_checker(c)

    def test_the_checker_refuses_the_wrong_rate_row_and_a_clean_payment(self):
        c = Case(gen(9100, "wrong_fx_rate", "stale_rate", "disbursement"))
        ch = c.inj["change"]
        ccy = c.pay["currency"]
        es = c.issue["evidence_sets"][0]
        wrong_fx = f"{ch['wrong_rate_date']}:{ccy}:{c.base}"
        self.assertIsNone(derive_from_evidence("wrong_fx_rate", [es[0], es[1], wrong_fx], c.ep))  # not the rate of the payment's date
        # another foreign-currency payment, booked at its own policy rate, derives nothing
        for p in c.ep.payments:
            if p["payment_id"] == c.pid or p["currency"] == c.base:
                continue
            rows = [r for r in c.ep.ledger if r["payment_id"] == p["payment_id"] and r["account"] == "1000"]
            if not rows:
                continue
            day = c.sched.local_date(parse_ts(p["timestamp"]))
            table = {r["date"] for r in c.ep.fx if r["source_currency"] == p["currency"] and r["target_currency"] == c.base}
            fx_day = next((day - timedelta(days=k)).isoformat() for k in range(15) if (day - timedelta(days=k)).isoformat() in table)
            self.assertIsNone(derive_from_evidence("wrong_fx_rate", [p["doc_id"], rows[0]["row_id"], f"{fx_day}:{p['currency']}:{c.base}"], c.ep))
            break
        else:
            self.fail("no other foreign-currency payment")


class PeriodOnPaymentTests(Common):
    def test_every_variant_keeps_its_meaning_on_a_receipt_and_on_a_disbursement(self):
        for kind in PAYMENT_KINDS:
            for variant in PERIOD_VARIANTS:
                for seed in (9200, 9201):
                    with self.subTest(kind=kind, variant=variant, seed=seed):
                        c = Case(gen(seed, "wrong_period", variant, kind))
                        self.check_target_and_settlement(c, "wrong_period", variant, kind)
                        ch = c.inj["change"]
                        self.assertEqual(set(ch), {"posting_ts"})
                        self.assertEqual(c.posting, parse_ts(ch["posting_ts"]))
                        self.assertNotEqual(c.in_period(c.ts), c.in_period(c.posting))  # posted in another period
                        self.assertEqual(parse_ts(c.clean_bank["timestamp"]), c.ts)  # the clean books post it at its own moment
                        # only the moment moves: every row keeps its account and amount
                        key = lambda rows: sorted((r["account"], r["invoice_id"], r["debit_minor"], r["credit_minor"]) for r in rows)
                        self.assertEqual(key(c.rows), key(c.clean_rows))
                        self.assertEqual(c.issue["expected_amount_minor"], c.bank["debit_minor"] or c.bank["credit_minor"])
                        self.assertEqual(c.issue["evidence_sets"], [[c.pay["doc_id"], c.bank["row_id"]]])
                        last_day = c.sched.local_date(c.p1 - timedelta(seconds=1))
                        if variant == "booked_early":
                            self.assertGreaterEqual(c.ts, c.p1)
                            self.assertIn((c.sched.local_date(c.ts) - last_day).days, (1, 2, 3))
                            self.assertIn((last_day - c.sched.local_date(c.posting)).days, (0, 1, 2, 3))
                            self.assertLess(c.posting, c.p1)
                        elif variant == "booked_late":
                            self.assertIn((last_day - c.sched.local_date(c.ts)).days, (0, 1, 2))
                            self.assertGreaterEqual(c.posting, c.p1)
                        else:
                            off = c.sched.offset_at(c.ts)
                            self.assertNotEqual(off, 0)
                            self.assertEqual(c.posting, c.ts - timedelta(minutes=off))  # the UTC wall clock of the local time
                            self.assertTrue(tells.in_error_window(c.ts, c.p1, c.sched))
                        self.check_auditor_and_checker(c)

    def test_the_utc_wall_clock_posting_of_a_payment_stays_clear_of_the_dst_change(self):
        # New York, October 2026: the boundary night holds the DST change (see StandaloneUtcWallClockDstTests in test_generator)
        zone = "America/New_York"
        for kind in PAYMENT_KINDS:
            for seed in range(12):
                c = Case(gen(10 ** 14 + seed, "wrong_period", "utc_wall_clock", kind, timezone=zone, period="2026-10"))
                off = offset_minutes(zone, c.ts)
                for r in c.rows:
                    posting = parse_ts(r["timestamp"])
                    self.assertFalse(in_ambiguous_hour(zone, posting), (kind, seed, r["timestamp"]))
                    self.assertEqual(offset_minutes(zone, posting), off, (kind, seed, r["timestamp"]))

    def test_a_base_currency_company_hosts_a_period_error_on_a_payment(self):
        c = Case(gen(9300, "wrong_period", "booked_late", "disbursement", foreign_currencies=[]))
        self.assertEqual(c.pay["currency"], c.base)
        self.check_target_and_settlement(c, "wrong_period", "booked_late", "disbursement")
        self.check_auditor_and_checker(c)


class PostingOrderTests(unittest.TestCase):
    """A posting lag of the invoice never lands between the moment the clean books post the payment and the moment the
    error moved it to: the invoice is booked before the payment in both sets of books, so no attempt is thrown away for a
    payment that is allocated differently in the clean books."""

    # (type, variant, kind, seed, extra config): with a lag bounded by the moved posting only, an attempt of each
    # loses the invoice's place: the clean books then book the receipt to 2900 (first case) or refuse the disbursement
    # ("exceeds open payables", second case), and the attempt is thrown away. Found by a scan of 640 such episodes.
    KNOWN = (("wrong_period", "booked_late", "receipt", 9400, {}),
             ("wrong_fx_rate", "posting_date", "disbursement", 9435, {"distractors": {"posting_lag": 40}}))

    def check(self, g, where):
        reasons = [r["reason"] for r in g.rejected]
        self.assertFalse([r for r in reasons if "payment target" in r or "exceeds open payables" in r], (where, reasons))

    def test_invoice_lag_stays_before_the_clean_payment_moment(self):
        cfg = cfgmod.resolve({"size": "small", "timezone": "Asia/Almaty", "period": "2026-06",
                             "base_currency": "USD", "foreign_currencies": [],
                             "distractors": {"posting_lag": 2}}, Rng(4))
        builder = HistoryBuilder(Rng(5), cfg)
        builder.build_entities()
        customer = next(e.key for e in builder.h.entities.values() if e.role == "customer")
        issued = builder.h.p0 + timedelta(days=2, hours=9)
        item = LineItem("Consulting", 1, 10000, 10000, "consulting")
        invoice = builder.add_invoice("sales", customer, issued, [item])
        payment = builder.add_payment("receipt", customer, "USD", issued + timedelta(hours=1),
                                      invoice.total, [invoice.key])
        moved_posting = issued + timedelta(hours=3)
        valid_lag = issued + timedelta(minutes=30)
        # The first candidate is before the erroneous posting but after the clean receipt.
        candidates = iter((issued + timedelta(hours=2), valid_lag))

        def lag_candidate(shape, _timestamp):
            return next(candidates, None) if shape == "later" else None

        directions = mock.Mock()
        directions.random.return_value = 0.0  # two later slots, one already used by the moved receipt
        with mock.patch.object(builder.lag_rng, "fork", return_value=directions), \
                mock.patch.object(builder, "_lag_candidate", side_effect=lag_candidate):
            builder.apply_posting_lags([], {payment.key: moved_posting}, {payment.key}, {payment.key})

        self.assertEqual(invoice.posted, valid_lag)

    def test_the_known_cases_lose_no_attempt_to_the_invoice_order(self):
        for etype, variant, kind, seed, extra in self.KNOWN:
            with self.subTest(variant=variant, kind=kind, seed=seed):
                self.check(gen(seed, etype, variant, kind, **extra), (variant, kind, seed))

    def test_no_attempt_is_rejected_for_a_different_clean_allocation(self):
        seen = 0
        for etype, variant in (("wrong_fx_rate", "posting_date"), ("wrong_period", "booked_late")):
            for kind in PAYMENT_KINDS:
                for seed in range(9400, 9408):
                    self.check(gen(seed, etype, variant, kind, distractors={"posting_lag": 40}), (variant, kind, seed))
                    seen += 1
        self.assertEqual(seen, 32)


class ShareTests(unittest.TestCase):
    def test_the_shares_are_a_distribution_and_the_draw_follows_them(self):
        self.assertEqual(cfgmod.TARGET_KINDS, ("invoice", "receipt", "disbursement"))
        self.assertAlmostEqual(sum(cfgmod.TARGET_KIND_SHARES), 1.0)
        self.assertTrue(all(0.2 <= s <= 0.5 for s in cfgmod.TARGET_KIND_SHARES), cfgmod.TARGET_KIND_SHARES)
        drawn = cfgmod.draw_target_kinds(Rng("share"), {"wrong_fx_rate": 3000, "wrong_period": 3000})
        self.assertEqual({k: len(v) for k, v in drawn.items()}, {"wrong_fx_rate": 3000, "wrong_period": 3000})
        for etype, kinds in drawn.items():
            counts = Counter(kinds)
            for kind, share in zip(cfgmod.TARGET_KINDS, cfgmod.TARGET_KIND_SHARES):
                with self.subTest(etype=etype, kind=kind):
                    self.assertAlmostEqual(counts[kind] / 3000, share, delta=0.03)

    def test_the_resolved_config_carries_one_kind_per_standalone_error(self):
        cfg = cfgmod.resolve({"size": "small", "errors": {"wrong_fx_rate": 3, "wrong_period": 2, "duplicate_invoice": 1},
                              "interacting": ["boundary_fx_payment", "fx_invoice_partial_allocation"]}, Rng("k"))
        self.assertEqual({k: len(v) for k, v in cfg["target_kinds"].items()}, {"wrong_fx_rate": 3, "wrong_period": 2})
        self.assertTrue(all(k in cfgmod.TARGET_KINDS for v in cfg["target_kinds"].values() for k in v))
        clean = cfgmod.resolve({"size": "small"}, Rng("k"))
        self.assertEqual(clean["target_kinds"], {"wrong_fx_rate": [], "wrong_period": []})
        # the kinds are drawn on a stream of their own: no other resolved field moves with the shares
        with mock.patch.object(cfgmod, "TARGET_KIND_SHARES", ONLY["invoice"]):
            other = cfgmod.resolve({"size": "small", "errors": {"wrong_fx_rate": 3, "wrong_period": 2, "duplicate_invoice": 1},
                                    "interacting": ["boundary_fx_payment", "fx_invoice_partial_allocation"]}, Rng("k"))
        self.assertEqual(other["target_kinds"], {"wrong_fx_rate": ["invoice"] * 3, "wrong_period": ["invoice"] * 2})
        moved = {k for k in cfg if cfg[k] != other[k]}
        self.assertLessEqual(moved, {"target_kinds", "counts", "error_invoice_load"})

    def test_a_payment_target_takes_a_paid_slot_of_its_side(self):
        req = {"size": "small", "errors": {"wrong_fx_rate": 2, "wrong_period": 2}}
        for kind, side in (("receipt", "sales"), ("disbursement", "purchase")):
            with mock.patch.object(cfgmod, "TARGET_KIND_SHARES", ONLY[kind]):
                cfg = cfgmod.resolve(req, Rng("p"))
                self.assertEqual(cfgmod.error_invoice_load(req, cfg["target_kinds"]), (4, 0) if side == "sales" else (0, 4))
            load = cfg["error_invoice_load"]
            other = "purchase" if side == "sales" else "sales"
            self.assertEqual((load[side], load[f"{side}_paid"], load[other], load[f"{other}_paid"]), (4, 4, 0, 0))
        with mock.patch.object(cfgmod, "TARGET_KIND_SHARES", ONLY["invoice"]):
            load = cfgmod.resolve(req, Rng("p"))["error_invoice_load"]
        self.assertEqual(load, {"sales": 2, "purchase": 2, "sales_paid": 0, "purchase_paid": 0})  # an invoice target is never paid

    def test_the_payments_per_invoice_do_not_move_with_payment_targets(self):
        means = {}
        with mock.patch.object(cfgmod, "TARGET_KIND_SHARES", (0.0, 0.5, 0.5)):
            for label, errors in (("none", {}), ("many", {"wrong_fx_rate": 3, "wrong_period": 3})):
                vals = []
                for seed in range(20):
                    ep = generate_episode(9500 + seed, {"size": "small", "errors": errors}).episode
                    vals.append(len(ep.payments) / len(ep.invoices))
                means[label] = sum(vals) / len(vals)
        self.assertLess(abs(means["none"] - means["many"]), 0.04, means)

    def test_generated_episodes_follow_the_resolved_kinds(self):
        seen = Counter()
        for seed in range(9600, 9612):
            ep = generate_episode(seed, {"size": "small", "errors": {"wrong_fx_rate": 2, "wrong_period": 2}}).episode
            kind_of = {p["payment_id"]: p["kind"] for p in ep.payments}
            got = {"wrong_fx_rate": [], "wrong_period": []}
            for inj in ep.provenance["injections"]:
                got[inj["type"]].append(kind_of[inj["targets"]["payment"]] if "payment" in inj["targets"] else "invoice")
            want = ep.provenance["resolved_config"]["target_kinds"]
            self.assertEqual({k: sorted(v) for k, v in got.items()}, {k: sorted(v) for k, v in want.items()}, seed)
            seen.update(k for v in got.values() for k in v)
        self.assertEqual(set(seen), set(cfgmod.TARGET_KINDS), seen)  # 48 targets: every kind occurs


class TellsRuleTests(unittest.TestCase):
    def test_the_payment_rules_fire_on_what_they_name(self):
        c = Case(gen(9200, "wrong_period", "booked_late", "disbursement"))
        ctx = tells.Ctx(c.ep)
        fired = {name: {i for i in ctx.docs if tells.RULES[name](ctx, i)} for name in (
            "a receipt", "a disbursement", "an invoice", "a payment in a foreign currency",
            "a payment posted in another period (its rows are outside the reporting period)",
            "a payment dated in another period (its timestamp is outside the reporting period)")}
        by_kind = lambda kind: {p["payment_id"] for p in c.ep.payments if p["kind"] == kind}
        self.assertEqual(fired["a receipt"], by_kind("receipt"))
        self.assertEqual(fired["a disbursement"], by_kind("disbursement"))
        self.assertEqual(fired["an invoice"], {i["invoice_id"] for i in c.ep.invoices})
        self.assertEqual(fired["a payment in a foreign currency"], {p["payment_id"] for p in c.ep.payments if p["currency"] != c.base})
        outside = fired["a payment posted in another period (its rows are outside the reporting period)"]
        self.assertIn(c.pid, outside)  # booked late: its rows are after the period
        self.assertGreater(len(outside), 1)  # and so are the rows of the ordinary payments of the cut-off days
        self.assertNotIn(c.pid, fired["a payment dated in another period (its timestamp is outside the reporting period)"])
        early = Case(gen(9200, "wrong_period", "booked_early", "receipt"))
        ctx = tells.Ctx(early.ep)
        self.assertFalse(tells.RULES["a payment posted in another period (its rows are outside the reporting period)"](ctx, early.pid))
        self.assertTrue(tells.RULES["a payment dated in another period (its timestamp is outside the reporting period)"](ctx, early.pid))

    def test_the_payment_error_statistic_reads_the_answer_key(self):
        tally = tells.Tally(tells.RULES)
        tally.add(gen(9200, "wrong_period", "booked_late", "disbursement").episode)
        tally.add(gen(9100, "wrong_fx_rate", "stale_rate", "receipt").episode)
        with mock.patch.object(cfgmod, "TARGET_KIND_SHARES", ONLY["invoice"]):
            tally.add(generate_episode(9100, {"size": "small", "errors": {"wrong_fx_rate": 1}}).episode)
            tally.add(generate_episode(9101, {"size": "small", "errors": {"unallocated_payment": 1}}).episode)
            tally.add(generate_episode(9102, {"size": "small"}).episode)
        pe = tally.result()["payment_errors"]
        self.assertEqual(pe, {"error_episodes": 4, "with_payment_error": 3, "share": 0.75,
                              "with_rate_or_period_error_on_payment": 2, "share_rate_or_period": 0.5,
                              "issues_on_payment": {"unallocated_payment": 1, "wrong_fx_rate": 1, "wrong_period": 1}})
        self.assertIn("## An error episode has a payment error", tells.to_markdown(tells.run(2)))


class GeneratedShareTests(unittest.TestCase):
    """The share on generated episodes of the check-set mix: a receipt, a disbursement and an invoice are in the answer key
    at about the same rate, and both payment kinds carry both error types."""

    def test_a_payment_and_a_disbursement_sit_near_the_base_rate(self):
        m = tells.run(80)
        base = m["affected"] / m["documents"]
        for name in ("a receipt", "a disbursement", "an invoice"):
            r = m["rules"][name]
            with self.subTest(rule=name):
                self.assertGreaterEqual(r["hits"], 10)
                self.assertLess(r["precision"], 2 * base, (r, base))
                self.assertGreater(r["precision"], base / 2, (r, base))
        for name in ("a payment in a foreign currency", "a payment posted in another period (its rows are outside the reporting period)",
                     "a payment dated in another period (its timestamp is outside the reporting period)"):
            r = m["rules"][name]
            with self.subTest(rule=name):
                self.assertGreater(r["hits"], 0)
                self.assertLess(r["precision"], 0.15, r)
        pe = m["payment_errors"]
        self.assertGreater(pe["issues_on_payment"]["wrong_fx_rate"], 10)
        self.assertGreater(pe["issues_on_payment"]["wrong_period"], 10)


class CommittedPaymentCoverageTests(unittest.TestCase):
    def test_the_committed_set_holds_a_standalone_rate_and_period_error_on_a_payment(self):
        found = {}
        index = json.loads((ROOT / "episodes" / "index.json").read_text(encoding="utf-8"))["episodes"]
        for e in index:
            ep = load_episode(ROOT / "episodes" / e["split"] / e["name"])
            kind_of = {p["payment_id"]: p["kind"] for p in ep.payments}
            for inj in ep.provenance["injections"]:
                if inj["scenario"] == "single" and inj["type"] in cfgmod.TARGETED_TYPES and "payment" in inj["targets"]:
                    found.setdefault((inj["type"], kind_of[inj["targets"]["payment"]]), []).append(e["name"])
        for etype in cfgmod.TARGETED_TYPES:
            for kind in PAYMENT_KINDS:
                with self.subTest(type=etype, kind=kind):
                    self.assertTrue(found.get((etype, kind)), found)
        # and the invoice targets stay: skipping either kind of document loses answers
        invoice_side = [inj["type"] for e in index for inj in load_episode(ROOT / "episodes" / e["split"] / e["name"]).provenance["injections"]
                        if inj["scenario"] == "single" and inj["type"] in cfgmod.TARGETED_TYPES and "invoice" in inj["targets"]]
        self.assertEqual(set(invoice_side), set(cfgmod.TARGETED_TYPES))


if __name__ == "__main__":
    unittest.main()
