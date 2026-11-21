"""Round 8 shortcuts of the credit side: what a row on account 2900 says about the answer key.

Credit shapes: overpaid, settled, prepaid and topped_up (a part payment, then a receipt above the rest and within the total).

The hunter found that a payment with a 2900 row on an invoice that has exactly one payment was an unallocated_payment error in
every episode (562 of 562: legitimate credits came only from refunded overpayments, and every error target was the only
payment of its invoice), that an episode with 8 or more rows on 2900 was an error episode (a clean ledger held exactly 4, 5 or
7 of them by size and every unallocated_payment added one), and that the number of invoices grew with the number of errors.
These tests pin the fixes: the credit_receipt distractor in three shapes, unallocated receipts whose invoice was already
part paid, the draw of the 2900 rows and of the invoices that never depends on the errors, and the evidence checker and the
verifier that accept the part-paid invoice.
"""

import copy
import json
import unittest
from datetime import timedelta
from pathlib import Path

from auditgym import config as cfgmod
from auditgym import tells
from auditgym.auditor import audit_episode
from auditgym.episode import load_episode
from auditgym.evidence_check import unallocated_open_balance
from auditgym.generator import generate_episode
from auditgym.rng import Rng
from auditgym.timeutil import format_utc, parse_ts
from auditgym.verify import check_evidence, derive_from_evidence

ROOT = Path(__file__).resolve().parent.parent
_CACHE = {}


def committed() -> dict:
    if "c" not in _CACHE:
        index = json.loads((ROOT / "episodes" / "index.json").read_text(encoding="utf-8"))["episodes"]
        _CACHE["c"] = {e["name"]: load_episode(ROOT / "episodes" / e["split"] / e["name"]) for e in index}
    return _CACHE["c"]


def gen(seed, cfg):
    key = (seed, json.dumps(cfg, sort_keys=True))
    if key not in _CACHE:
        _CACHE[key] = generate_episode(seed, cfg).episode
    return _CACHE[key]


def refs_by_invoice(ep) -> dict:
    out = {}
    for p in ep.payments:
        for r in p["invoice_refs"] or []:
            out.setdefault(r, []).append(p)
    return out


def rows_of(ep, payment_id) -> list:
    return [r for r in ep.ledger if r["payment_id"] == payment_id]


class CreditReceiptTests(unittest.TestCase):
    def credits(self, ep):
        byid = {d["invoice_id"]: d for d in ep.invoices}
        paymap = {d["payment_id"]: d for d in ep.payments}
        for d in ep.provenance["distractors"]:
            if d["kind"] == "credit_receipt":
                yield d["shape"], [byid[i] for i in d["ids"] if i in byid], [paymap[i] for i in d["ids"] if i in paymap]

    def check(self, ep, shape, invs, pays):
        inv, refs = invs[0], refs_by_invoice(ep)
        last = pays[-1]
        has_2900 = any(r["account"] == "2900" for r in rows_of(ep, last["payment_id"]))
        self.assertTrue(has_2900, shape)
        self.assertFalse(any(p["kind"] == "refund" for p in refs[inv["invoice_id"]]), "a credit receipt is never refunded")
        if shape == "overpaid":
            self.assertEqual(len(refs[inv["invoice_id"]]), 1)
            self.assertGreater(last["amount_minor"], inv["total_minor"])
        elif shape == "settled":
            self.assertEqual(len(refs[inv["invoice_id"]]), 2)
            self.assertEqual(pays[0]["amount_minor"], inv["total_minor"])
            self.assertLess(parse_ts(pays[0]["timestamp"]), parse_ts(last["timestamp"]))
            self.assertFalse(any(r["account"] == "1100" for r in rows_of(ep, last["payment_id"])), "nothing is open to relieve")
        elif shape == "topped_up":
            self.assertEqual(len(refs[inv["invoice_id"]]), 2)
            self.assertLess(pays[0]["amount_minor"], inv["total_minor"])
            self.assertGreater(last["amount_minor"], inv["total_minor"] - pays[0]["amount_minor"])
            self.assertLessEqual(last["amount_minor"], inv["total_minor"])
            self.assertTrue(any(r["account"] == "1100" for r in rows_of(ep, last["payment_id"])), "it relieves what was left")
        else:
            self.assertEqual(shape, "prepaid")
            self.assertEqual(len(refs[inv["invoice_id"]]), 1)
            self.assertLessEqual(last["amount_minor"], inv["total_minor"])
            self.assertLess(parse_ts(last["timestamp"]), parse_ts(inv["issued_at"]), "the receipt precedes its invoice")
            self.assertFalse(any(r["account"] == "1100" for r in rows_of(ep, last["payment_id"])))

    def test_the_committed_set_holds_each_shape_and_each_is_what_it_says(self):
        seen = set()
        for name, ep in committed().items():
            for shape, invs, pays in self.credits(ep):
                with self.subTest(episode=name, shape=shape):
                    self.check(ep, shape, invs, pays)
                seen.add(shape)
        self.assertEqual(seen, {"overpaid", "settled", "prepaid", "topped_up"})

    def test_generated_episodes_hold_them_and_the_auditor_flags_none(self):
        seen = set()
        for seed in range(12):
            ep = gen(500 + seed, {"size": "medium", "errors": {"unallocated_payment": 1, "wrong_fx_rate": 1}})
            for shape, invs, pays in self.credits(ep):
                self.check(ep, shape, invs, pays)
                seen.add(shape)
            keyed = {(t["type"], tuple(sorted(t["affected_ids"]))) for t in ep.truth["issues"]}
            found = {(f["type"], tuple(sorted(f["affected_ids"]))) for f in audit_episode(ep)["findings"]}
            self.assertEqual(found, keyed)
            self.assertEqual(audit_episode(ep)["anomalies"], [])
        self.assertEqual(seen, {"overpaid", "settled", "prepaid", "topped_up"})

    def test_the_over_received_credits_never_depend_on_the_errors(self):
        # the over-received shapes (overpaid, settled, topped_up) are drawn per size; the unallocated_payment errors take the
        # place of prepaid receipts, so the number of invoices whose receipts sum above their total says nothing about them
        for size in ("small", "medium", "large"):
            lo, hi = cfgmod.CREDIT_OVER_RANGES[size]
            phi = cfgmod.PREPAID_RANGES[size][1]
            for k in range(25):
                base = cfgmod.resolve({"size": size}, Rng(f"o{k}"))["distractors"]
                for errors in ({"unallocated_payment": 1}, {"unallocated_payment": 3, "wrong_fx_rate": 1}):
                    d = cfgmod.resolve({"size": size, "errors": errors}, Rng(f"o{k}"))["distractors"]
                    n = errors["unallocated_payment"]
                    self.assertEqual(d["credit_receipt"], base["credit_receipt"])
                    self.assertTrue(lo <= d["credit_receipt"] <= hi)
                    self.assertEqual(d["prepaid_receipt"], max(0, base["prepaid_receipt"] - n))
                    self.assertTrue(0 <= base["prepaid_receipt"] <= phi)

    def test_the_rows_on_2900_are_the_credit_receipts_the_prepaid_ones_and_the_errors(self):
        # one row on 2900 for every credit receipt, every prepaid receipt and every unallocated_payment error
        for seed in range(8):
            for errors in ({}, {"unallocated_payment": 1}, {"unallocated_payment": 3, "wrong_fx_rate": 1}):
                ep = gen(600 + seed, {"size": "small", "errors": errors})
                d = ep.provenance["resolved_config"]["distractors"]
                self.assertEqual(tells._unexplained_2900(tells.Ctx(ep)),
                                 d["credit_receipt"] + d["prepaid_receipt"] + errors.get("unallocated_payment", 0), (seed, errors))

    def test_half_of_the_episodes_draw_no_prepaid_receipt(self):
        for size in ("small", "large"):
            zero = sum(cfgmod.resolve({"size": size}, Rng(f"z{k}"))["distractors"]["prepaid_receipt"] == 0 for k in range(120))
            self.assertTrue(0.35 < zero / 120 < 0.65, (size, zero))

    def test_a_split_remainder_sits_on_an_opening_item_at_the_share_of_the_credits(self):
        opening = n = 0
        for seed in range(30):
            ep = gen(1500 + seed, {"size": "medium", "errors": {}})
            c = tells.Ctx(ep)
            for d in ep.provenance["distractors"]:
                if d["kind"] == "split_payment" and d.get("shape") == "remainder":
                    n += 1
                    opening += d["ids"][0] in c.opening
                    self.assertGreaterEqual(tells.usd(*[next(i for i in ep.invoices if i["invoice_id"] == d["ids"][0])[k]
                                                         for k in ("total_minor", "currency")]) + 1, 800)
        self.assertTrue(0.2 < opening / n < 0.5, (opening, n))

    def test_the_resolved_credit_counts(self):
        cfg = cfgmod.resolve({"size": "small", "distractors": {"credit_receipt": 3, "prepaid_receipt": 1}}, Rng("x"))
        self.assertEqual((cfg["distractors"]["credit_receipt"], cfg["distractors"]["prepaid_receipt"]), (3, 1))
        cfgmod.validate({"distractors": {"prepaid_receipt": 8, "split_remainder": 8}})
        with self.assertRaises(cfgmod.ConfigError):
            cfgmod.validate({"distractors": {"split_remainder": 9}})

    def test_the_credit_invoices_are_drawn_like_the_invoices_of_the_errors(self):
        # opening items, weekends and the size floor appear among the invoices of the credit receipts as among the unallocated ones
        opening = weekend = total = 0
        for seed in range(30):
            ep = gen(900 + seed, {"size": "medium", "errors": {}})
            c = tells.Ctx(ep)
            byid = {i["invoice_id"]: i for i in ep.invoices}
            for d in ep.provenance["distractors"]:
                if d["kind"] != "credit_receipt" or d["shape"] == "prepaid":
                    continue
                inv = byid[d["ids"][0]]
                total += 1
                opening += inv["invoice_id"] in c.opening
                weekend += c.local(parse_ts(inv["issued_at"])).date().weekday() >= 5
        self.assertTrue(0.2 < opening / total < 0.5, (opening, total))
        self.assertGreater(weekend, 0, (weekend, total))

    def test_a_fresh_unallocated_receipt_is_on_an_opening_item_at_the_share_of_the_credits(self):
        opening = n = 0
        for seed in range(40):
            ep = gen(950 + seed, {"size": "small", "errors": {"unallocated_payment": 2}})
            c = tells.Ctx(ep)
            pays = {p["payment_id"] for p in ep.payments}
            for t in ep.truth["issues"]:
                inv = next(i for i in t["affected_ids"] if i not in pays)
                n += 1
                opening += inv in c.opening
        self.assertTrue(0.2 < opening / n < 0.55, (opening, n))

    def test_the_unallocated_receipts_on_opening_items_are_the_ones_taken_out_of_the_prior_invoices(self):
        for seed in range(25):
            ep = gen(1400 + seed, {"size": "small", "errors": {"unallocated_payment": 4}})
            c = tells.Ctx(ep)
            pays = {p["payment_id"] for p in ep.payments}
            on_opening = sum(next(i for i in t["affected_ids"] if i not in pays) in c.opening for t in ep.truth["issues"])
            self.assertEqual(on_opening, ep.provenance["resolved_config"]["unallocated_prior"], seed)

    def test_the_credit_invoices_of_the_period_are_dated_over_the_whole_period_like_the_error_ones(self):
        late = n = 0
        for seed in range(30):
            ep = gen(900 + seed, {"size": "medium", "errors": {}})
            c = tells.Ctx(ep)
            byid = {i["invoice_id"]: i for i in ep.invoices}
            for d in ep.provenance["distractors"]:
                if d["kind"] == "credit_receipt" and d["shape"] != "prepaid" and d["ids"][0] not in c.opening:
                    n += 1
                    late += tells._day_of_period(c, d["ids"][0]) > 10
                    self.assertIn(d["ids"][0], byid)
        self.assertTrue(0.35 < late / n < 0.75, (late, n))  # the invoice dates run over days 0 to 22

    def test_the_share_of_credits_that_follow_an_earlier_receipt_is_drawn_per_episode(self):
        from auditgym.history import HistoryBuilder

        shares = set()
        for seed in range(10):
            cfg = cfgmod.resolve({"size": "small"}, Rng(f"w{seed}"))
            b = HistoryBuilder(Rng(f"w{seed}").fork("history"), cfg)
            b.build_entities()
            b.build_credit_receipts(2, 0)
            shares.add(round(b.credit_second_share, 6))
        self.assertEqual(len(shares), 10)
        self.assertTrue(min(shares) < 0.4 and max(shares) > 0.7, sorted(shares))

    def test_the_number_of_opening_items_never_depends_on_the_unallocated_errors(self):
        means = {}
        for label, errors in (("none", {}), ("many", {"unallocated_payment": 6})):
            vals = [len(tells.Ctx(gen(1000 + seed, {"size": "small", "errors": errors})).opening) for seed in range(20)]
            means[label] = sum(vals) / len(vals)
        self.assertLess(abs(means["none"] - means["many"]), 1.0, means)  # before: 6 * 0.35 = 2.1 more

    def test_the_payments_per_invoice_never_depend_on_the_wrong_rate_and_period_errors(self):
        means = {}
        for label, errors in (("none", {}), ("many", {"wrong_fx_rate": 3, "wrong_period": 3})):
            vals = []
            for seed in range(20):
                ep = gen(1100 + seed, {"size": "small", "errors": errors})
                vals.append(len(ep.payments) / len(ep.invoices))
            means[label] = sum(vals) / len(vals)
        self.assertLess(abs(means["none"] - means["many"]), 0.03, means)  # before: 6 unpaid invoices of about 64, 0.7 each

    def test_the_load_is_carried_in_the_resolved_config_and_an_explicit_count_stays_exact(self):
        cfg = cfgmod.resolve({"size": "small", "errors": {"wrong_fx_rate": 2, "wrong_period": 1}}, Rng("l"))
        self.assertEqual(cfg["error_invoice_load"]["sales"] + cfg["error_invoice_load"]["purchase"], 3)
        cfg = cfgmod.resolve({"size": "small", "errors": {"wrong_fx_rate": 2}, "counts": {"sales_invoices": 9, "purchase_invoices": 5,
                                                                                         "prior_invoices": 3}}, Rng("l"))
        self.assertEqual(cfg["error_invoice_load"], {"sales": 0, "purchase": 0, "sales_paid": 0})
        cfg = cfgmod.resolve({"size": "small", "errors": {"unallocated_payment": 4}, "counts": {"prior_invoices": 3}}, Rng("l"))
        self.assertEqual(cfg["counts"]["prior_invoices"], 3)

    def test_split_remainders_leave_a_rest_open_and_their_count_is_exact(self):
        for size in ("small", "medium"):
            lo, hi = cfgmod.DEFAULT_DISTRACTOR_RANGES[size]["split_remainder"]
            seen = set()
            for seed in range(10):
                ep = gen(1200 + seed, {"size": size, "errors": {"unallocated_payment": 1}})
                want = ep.provenance["resolved_config"]["distractors"]["split_remainder"]
                entries = [d for d in ep.provenance["distractors"] if d["kind"] == "split_payment" and d.get("shape") == "remainder"]
                self.assertEqual(len(entries), want)
                seen.add(want)
                byid = {i["invoice_id"]: i for i in ep.invoices}
                paymap = {p["payment_id"]: p for p in ep.payments}
                for d in entries:
                    inv = byid[d["ids"][0]]
                    pays = [paymap[i] for i in d["ids"][1:]]
                    self.assertLess(sum(p["amount_minor"] for p in pays), inv["total_minor"])
                    for p in pays:
                        self.assertFalse(any(r["account"] == "2900" for r in rows_of(ep, p["payment_id"])))
                        self.assertTrue(any(r["account"] == "1100" for r in rows_of(ep, p["payment_id"])))
            self.assertTrue(seen <= set(range(lo, hi + 1)) and len(seen) >= 2, (size, seen))

    def test_an_invoice_with_two_receipts_below_its_total_is_in_most_clean_episodes(self):
        hit = 0
        for seed in range(20):
            c = tells.Ctx(gen(1300 + seed, {"size": "small", "errors": {}}))
            hit += any(tells._part_paid_invoice(c, i) for i in c.docs)
        self.assertGreaterEqual(hit, 19)

    def test_a_shortfall_of_credit_receipts_resamples_the_attempt(self):
        from auditgym.generator import GenerationError

        tiny = {"size": "small", "errors": {}, "distractors": {"credit_receipt": 8, "prepaid_receipt": 8, "split_remainder": 8},
                "counts": {"sales_invoices": 1, "purchase_invoices": 1, "prior_invoices": 0}}
        for seed in range(4):
            try:
                ep = generate_episode(seed, tiny).episode
            except GenerationError:
                continue
            kinds = [d["kind"] for d in ep.provenance["distractors"]]
            self.assertEqual(kinds.count("credit_receipt"), 16)  # exact or resampled, never silently fewer

    def test_the_two_counts_that_were_fixed_are_drawn_per_episode(self):
        for size in ("small", "medium", "large"):
            for kind in ("overpayment_refund", "null_ref_receipt", "split_remainder"):
                lo, hi = cfgmod.DEFAULT_DISTRACTOR_RANGES[size][kind]
                drawn = {cfgmod.resolve({"size": size}, Rng(f"r{n}"))["distractors"][kind] for n in range(60)}
                self.assertTrue(drawn <= set(range(lo, hi + 1)) and len(drawn) >= 2, (size, kind, drawn))


class PartPaidTests(unittest.TestCase):
    """An unallocated receipt whose invoice an earlier receipt already part paid: a payment count says nothing."""

    def part_paid(self, ep):
        refs = refs_by_invoice(ep)
        pays = {p["payment_id"] for p in ep.payments}
        for t in ep.truth["issues"]:
            if t["type"] != "unallocated_payment":
                continue
            pid = next(i for i in t["affected_ids"] if i in pays)
            inv = next(i for i in t["affected_ids"] if i != pid)
            if len(refs[inv]) > 1:
                yield t, pid, inv, refs[inv]

    def cases(self):
        if "cases" not in _CACHE:
            out = []
            for seed in range(30):
                ep = gen(700 + seed, {"size": "small", "errors": {"unallocated_payment": 2}})
                out += [(ep, t, pid, inv, refs) for t, pid, inv, refs in self.part_paid(ep)]
            _CACHE["cases"] = out
        return _CACHE["cases"]

    def test_a_share_of_the_unallocated_receipts_have_an_earlier_payment_on_their_invoice(self):
        total = sum(1 for seed in range(30) for t in gen(700 + seed, {"size": "small", "errors": {"unallocated_payment": 2}}).truth["issues"]
                    if t["type"] == "unallocated_payment")
        part = len(self.cases())
        self.assertTrue(0.3 < part / total < 0.7, (part, total))

    def test_the_earlier_payment_is_posted_before_and_the_open_balance_covers_the_receipt(self):
        for ep, t, pid, inv, refs in self.cases():
            other = [p for p in refs if p["payment_id"] != pid]
            self.assertEqual(len(other), 1)
            self.assertLess(parse_ts(rows_of(ep, other[0]["payment_id"])[0]["timestamp"]), parse_ts(rows_of(ep, pid)[0]["timestamp"]))
            invoice = next(i for i in ep.invoices if i["invoice_id"] == inv)
            pay = next(p for p in ep.payments if p["payment_id"] == pid)
            self.assertLessEqual(pay["amount_minor"], invoice["total_minor"] - other[0]["amount_minor"])

    def test_the_evidence_derives_the_key_and_the_open_balance_is_what_the_earlier_payment_left(self):
        for ep, t, _pid, _inv, _refs in self.cases():
            self.assertEqual(check_evidence(ep), [])
            for es in t["evidence_sets"]:
                self.assertEqual(derive_from_evidence(t["type"], es, ep),
                                 (t["type"], frozenset(t["affected_ids"]), t["expected_amount_minor"]))
                before, after = unallocated_open_balance(es, ep)
                posted = sum(r["debit_minor"] for r in ep.ledger if r["row_id"] in es and r["account"] == "1100" and not r["payment_id"])
                self.assertLess(before, posted)  # the earlier payment relieved part of it
                self.assertGreater(after, 0)

    def test_the_auditor_finds_the_error_and_nothing_else(self):
        for ep, *_rest in self.cases()[:8]:
            found = {(f["type"], tuple(sorted(f["affected_ids"]))) for f in audit_episode(ep)["findings"]}
            self.assertEqual(found, {(t["type"], tuple(sorted(t["affected_ids"]))) for t in ep.truth["issues"]})

    def test_an_earlier_credit_booked_after_the_receipt_no_longer_supports_the_finding(self):
        ep, t, pid, inv, refs = self.cases()[0]
        moved = copy.deepcopy(ep)
        other = next(p for p in refs if p["payment_id"] != pid)
        last = max(parse_ts(r["timestamp"]) for r in rows_of(ep, pid))
        for r in moved.ledger:
            if r["payment_id"] == other["payment_id"]:
                r["timestamp"] = format_utc(last + timedelta(hours=1))
        self.assertIsNone(derive_from_evidence(t["type"], t["evidence_sets"][0], moved))
        self.assertTrue(check_evidence(moved))
        from auditgym.verify import _sole_receipt_errors

        self.assertEqual(_sole_receipt_errors(ep, t), [])  # the part payment is booked before the receipt
        self.assertTrue(_sole_receipt_errors(moved, t))  # booked after it, it is no longer an earlier part payment

    def test_a_payment_that_settled_the_invoice_elsewhere_is_still_refused(self):
        ep, t, pid, inv, refs = self.cases()[0]
        moved = copy.deepcopy(ep)
        other = next(p for p in refs if p["payment_id"] != pid)
        for r in moved.ledger:  # the earlier payment now leaves nothing on 1100: it did not relieve the invoice
            if r["payment_id"] == other["payment_id"] and r["account"] == "1100":
                r["account"] = "2900"
        self.assertTrue(check_evidence(moved))


class InvoiceCountTests(unittest.TestCase):
    def test_the_number_of_invoices_never_depends_on_the_number_of_errors(self):
        means = {}
        for label, errors in (("none", {}), ("few", {"unallocated_payment": 1, "wrong_fx_rate": 1}),
                              ("many", {"unallocated_payment": 3, "wrong_fx_rate": 2, "wrong_period": 2}),
                              ("dup", {"duplicate_invoice": 2, "wrong_period": 1})):
            counts = [len(gen(800 + seed, {"size": "small", "errors": errors}).invoices) for seed in range(25)]
            means[label] = sum(counts) / len(counts)
        self.assertLess(max(means.values()) - min(means.values()), 3.5, means)  # before: about one invoice per error more (5 for "many")

    def test_an_explicit_count_stays_exact(self):
        cfg = cfgmod.resolve({"size": "small", "counts": {"sales_invoices": 5, "purchase_invoices": 3},
                              "errors": {"unallocated_payment": 2, "wrong_period": 2}}, Rng("e"))
        self.assertEqual((cfg["counts"]["sales_invoices"], cfg["counts"]["purchase_invoices"]), (5, 3))
        hi = cfgmod.SIZES["small"]["sales_invoices"][1]
        drawn = cfgmod.resolve({"size": "small", "errors": {"wrong_fx_rate": 4, "wrong_period": 2}}, Rng("e"))
        self.assertLessEqual(drawn["counts"]["sales_invoices"], hi - 3)

    def test_the_load_of_each_error_type(self):
        self.assertEqual(cfgmod.error_invoice_load({}), (0, 0))
        # an unallocated receipt takes the place of a credit receipt, whose count shrinks by one: no deduction here
        self.assertEqual(cfgmod.error_invoice_load({"errors": {"unallocated_payment": 2}}), (0, 0))
        self.assertEqual(cfgmod.error_invoice_load({"errors": {"duplicate_invoice": 3}}), (0, 0))  # a duplicate adds no invoice
        self.assertEqual(cfgmod.error_invoice_load({"interacting": ["boundary_fx_payment", "fx_invoice_partial_allocation"]}), (1, 0))
        self.assertEqual(sum(cfgmod.error_invoice_load({"errors": {"wrong_fx_rate": 3, "wrong_period": 2}})), 5)


if __name__ == "__main__":
    unittest.main()
