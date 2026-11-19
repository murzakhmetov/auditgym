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
catalogue-range check fail. With the current generator the best document rule reaches precision 0.28 with 5 hits (a paid twin invoice)
and the best recall among selective rules is 0.28 at precision 0.17 (an invoice with a twin), far from both
limits; the episode-level rules flag nothing (clean labels, catalogue outliers) or reach only 0.75 to 0.78
(error labels, whose base rate is 0.75). Run with -v/--verbose (or set AUDITGYM_TELLS_TABLE=1) to print the table.
"""

import json
import os
import random
import sys
import unittest
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from auditgym import catalog
from auditgym.auditor import OffsetSchedule
from auditgym.episode import load_episode
from auditgym.money import CURRENCY_EXPONENTS
from auditgym.splits import EPISODES_DIR
from auditgym.timeutil import parse_ts

SPEC_PRECISION, SPEC_RECALL = 0.5, 0.3
STRONG_PRECISION, STRONG_HITS = 0.8, 3

SALES = {d: (p, q) for d, p, q in catalog.SALES_ITEMS}
PURCHASES = [(t.split("{")[0].strip(), p) for t, p, _ in catalog.PURCHASE_ITEMS]


def usd(minor: int, ccy: str) -> float:
    return float(Decimal(minor) / (Decimal(10) ** CURRENCY_EXPONENTS[ccy]) * Decimal(catalog.USD_VALUE[ccy]))


def outside_catalogue(inv: dict) -> bool:
    for li in inv["line_items"]:
        if inv["kind"] == "sales":
            (plo, phi), (qlo, qhi) = SALES[li["description"]]
            if not qlo <= li["quantity"] <= qhi:
                return True
        else:
            plo, phi = next(p for prefix, p in PURCHASES if li["description"].startswith(prefix))
        price = usd(li["unit_price_minor"], inv["currency"])
        if not plo * 0.97 <= price <= phi * 1.03:
            return True
    return False


class Ctx:
    """Public view of one episode."""

    def __init__(self, ep):
        self.ep = ep
        self.sched = OffsetSchedule(ep.policy["utc_offset_schedule"])
        self.base = ep.manifest["base_currency"]
        self.p0 = parse_ts(ep.policy["reporting_period"]["start"])
        self.p1 = parse_ts(ep.policy["reporting_period"]["end"])
        self.docs = {}  # id -> (kind, record, instant)
        for inv in ep.invoices:
            self.docs[inv["invoice_id"]] = ("invoice", inv, parse_ts(inv["issued_at"]))
        for p in ep.payments:
            self.docs[p["payment_id"]] = ("payment", p, parse_ts(p["timestamp"]))
        self.paid = {r for p in ep.payments for r in (p["invoice_refs"] or [])}
        self.acct2900 = {r["payment_id"] for r in ep.ledger if r["account"] == "2900" and r["payment_id"]}
        self.local_cache = {}
        by_key = defaultdict(list)
        for inv in ep.invoices:
            by_key[(inv["kind"], inv["entity_id"], inv["currency"], inv["total_minor"], parse_ts(inv["issued_at"]))].append(inv["invoice_id"])
        self.twins = {i for ids in by_key.values() if len(ids) > 1 for i in ids}
        by_id = {i["invoice_id"]: i for i in ep.invoices}
        self.odd_terms_pair = {i for ids in by_key.values() if len(ids) > 1 and any(self.terms(by_id[x]) != 30 for x in ids) for i in ids}
        self.paid_or_odd_pair = {i for ids in by_key.values() if len(ids) > 1
                                 and (any(self.terms(by_id[x]) != 30 for x in ids) or any(x in self.paid for x in ids))
                                 for i in ids}
        self.holidays = set(ep.policy["fx"]["publication_calendar"]["holidays_without_rates"])
        foreign_p = sorted((i for i in ep.invoices if i["kind"] == "purchase" and i["currency"] != self.base),
                           key=lambda i: -usd(i["total_minor"], i["currency"]))
        foreign_s = sorted((i for i in ep.invoices if i["kind"] == "sales" and i["currency"] != self.base),
                           key=lambda i: -usd(i["total_minor"], i["currency"]))
        self.rank_p = {i["invoice_id"]: n for n, i in enumerate(foreign_p, 1)}
        self.rank_s = {i["invoice_id"]: n for n, i in enumerate(foreign_s, 1)}
        every = sorted(ep.invoices, key=lambda i: -usd(i["total_minor"], i["currency"]))
        self.rank_all = {i["invoice_id"]: n for n, i in enumerate(every, 1)}
        self.dominant_p = None  # the largest foreign purchase when it is at least 1.5x the runner-up
        if len(foreign_p) > 1 and usd(foreign_p[0]["total_minor"], foreign_p[0]["currency"]) >= 1.5 * usd(
                foreign_p[1]["total_minor"], foreign_p[1]["currency"]):
            self.dominant_p = foreign_p[0]["invoice_id"]

    def local(self, inst):
        return inst + timedelta(minutes=self.sched.offset_at(inst))

    def minutes_from_boundary(self, inst) -> float:
        return min(abs((inst - self.p0).total_seconds()), abs((inst - self.p1).total_seconds())) / 60.0

    def terms(self, inv) -> int:
        return (self.local(parse_ts(inv["due_at"])).date() - self.local(parse_ts(inv["issued_at"])).date()).days

    def affected(self):
        out = set()
        for issue in self.ep.truth["issues"]:
            out.update(issue["affected_ids"])
        return out


def _inv(c, i):
    return c.docs[i][0] == "invoice"


def _off_hours(c, i):
    h = c.local(c.docs[i][2]).hour
    return h < 8 or h > 18


def _near_midnight(c, i):
    inst = c.docs[i][2]
    return c.local(inst).date() != inst.date()


def _boundary_day(c, i):
    d = c.local(c.docs[i][2]).date()
    return d == c.local(c.p1).date() or d == c.local(c.p1 - timedelta(seconds=1)).date()


def in_error_window(inst, p1, sched) -> bool:
    """The exact minute window of the boundary errors (utc_wall_clock invoices, the boundary receipt): with a positive
    offset minutes 5 to offset-11 of the first day after the period, with a negative offset minutes 1440+offset+11
    to 1434 of the period's last day (local time)."""
    off = sched.offset_at(p1)
    if off == 0:
        return False
    local = inst + timedelta(minutes=sched.offset_at(inst))
    minute = local.hour * 60 + local.minute
    if off > 0:
        return local.date() == (p1 + timedelta(minutes=off)).date() and 5 <= minute <= off - 11
    last = p1 - timedelta(seconds=1)
    return local.date() == (last + timedelta(minutes=sched.offset_at(last))).date() and 1440 + off + 11 <= minute <= 1434


def _boundary_window(c, i, kinds=None):
    kind, rec, inst = c.docs[i]
    label = rec["kind"]
    return (kinds is None or label in kinds) and in_error_window(inst, c.p1, c.sched)


def _round_amount(c, i):
    kind, rec, _ = c.docs[i]
    amount = rec["total_minor"] if kind == "invoice" else rec["amount_minor"]
    ccy = rec["currency"]
    return amount % (10 ** (CURRENCY_EXPONENTS[ccy] + 2)) == 0


RULES = {
    "qty/price outside catalogue": lambda c, i: _inv(c, i) and outside_catalogue(c.docs[i][1]),
    "sales qty above catalogue max": lambda c, i: _inv(c, i) and c.docs[i][1]["kind"] == "sales" and any(
        li["quantity"] > SALES[li["description"]][1][1] for li in c.docs[i][1]["line_items"]),
    "off-hours invoice": lambda c, i: _inv(c, i) and _off_hours(c, i),
    "off-hours payment": lambda c, i: not _inv(c, i) and _off_hours(c, i),
    "off-hours document": lambda c, i: _off_hours(c, i),
    "near-midnight (UTC date differs) invoice": lambda c, i: _inv(c, i) and _near_midnight(c, i),
    "near-midnight (UTC date differs) payment": lambda c, i: not _inv(c, i) and _near_midnight(c, i),
    "within 12 h of period boundary": lambda c, i: c.minutes_from_boundary(c.docs[i][2]) <= 12 * 60,
    "boundary day, off-hours invoice": lambda c, i: _inv(c, i) and _boundary_day(c, i) and _off_hours(c, i),
    "boundary day, off-hours payment": lambda c, i: not _inv(c, i) and _boundary_day(c, i) and _off_hours(c, i),
    "largest foreign purchase": lambda c, i: c.rank_p.get(i) == 1,
    "dominant foreign purchase (>= 1.5x runner-up)": lambda c, i: c.dominant_p == i,
    "top-3 foreign purchase": lambda c, i: c.rank_p.get(i, 99) <= 3,
    "largest foreign sale": lambda c, i: c.rank_s.get(i) == 1,
    "top-3 foreign sale": lambda c, i: c.rank_s.get(i, 99) <= 3,
    "largest invoice": lambda c, i: c.rank_all.get(i) == 1,
    "weekend date": lambda c, i: c.local(c.docs[i][2]).date().weekday() >= 5,
    "weekday date": lambda c, i: c.local(c.docs[i][2]).date().weekday() < 5,
    "terms not 30 days": lambda c, i: _inv(c, i) and c.terms(c.docs[i][1]) != 30,
    "terms 14 or 45 days": lambda c, i: _inv(c, i) and c.terms(c.docs[i][1]) in (14, 45),
    "unpaid twin invoice": lambda c, i: i in c.twins and i not in c.paid,
    "paid twin invoice": lambda c, i: i in c.twins and i in c.paid,
    "invoice with a twin": lambda c, i: i in c.twins,
    "same-instant pair with terms != 30": lambda c, i: i in c.odd_terms_pair,
    "same-instant pair, terms != 30 or one copy paid": lambda c, i: i in c.paid_or_odd_pair,
    "sales invoice in the error window": lambda c, i: _boundary_window(c, i, ("sales",)) and _inv(c, i),
    "purchase invoice in the error window": lambda c, i: _boundary_window(c, i, ("purchase",)) and _inv(c, i),
    "receipt in the error window": lambda c, i: _boundary_window(c, i, ("receipt",)) and not _inv(c, i),
    "disbursement in the error window": lambda c, i: _boundary_window(c, i, ("disbursement",)) and not _inv(c, i),
    "document on an FX holiday": lambda c, i: c.local(c.docs[i][2]).date().isoformat() in c.holidays,
    "payment with a 2900 row": lambda c, i: i in c.acct2900,
    "payment with a 2900 row and invoice refs": lambda c, i: i in c.acct2900 and bool(c.docs[i][1]["invoice_refs"]),
    "round amount": _round_amount,
}


_CACHE = {}


def episodes() -> list:
    if "eps" not in _CACHE:
        index = json.loads((EPISODES_DIR / "index.json").read_text(encoding="utf-8"))["episodes"]
        _CACHE["eps"] = [(e["name"], load_episode(EPISODES_DIR / e["split"] / e["name"])) for e in index]
    return _CACHE["eps"]


def measure() -> dict:
    ctxs = [Ctx(ep) for _name, ep in episodes()]
    truth = [(n, i) for n, c in enumerate(ctxs) for i in c.affected()]
    result = {}
    for name, rule in RULES.items():
        predicted = {(n, i) for n, c in enumerate(ctxs) for i in c.docs if rule(c, i)}
        hits = len(predicted & set(truth))
        result[name] = {
            "predicted": len(predicted), "hits": hits,
            "precision": hits / len(predicted) if predicted else 0.0,
            "recall": hits / len(truth) if truth else 0.0,
        }
    return {"rules": result, "episode_rules": measure_episodes(ctxs), "affected": len(truth), "episodes": len(ctxs),
            "documents": sum(len(c.docs) for c in ctxs)}


def _count(c, pred):
    return sum(1 for p in c.ep.payments if pred(p))


# episode-level rules: (label predicted, predicate). "error" rules need exactly-perfect precision with 3 episodes,
# "clean" rules precision >= 0.9 with 2 episodes (only 5 of the 20 episodes are clean)
EPISODE_RULES = {
    "any quantity/price outside catalogue -> error": ("error", lambda c: any(outside_catalogue(i) for i in c.ep.invoices)),
    "any off-hours payment on a boundary day -> error": ("error", lambda c: any(
        k == "payment" and _boundary_day(c, i) and _off_hours(c, i) for i, (k, _r, _t) in c.docs.items())),
    "any same-instant pair with terms != 30 -> error": ("error", lambda c: bool(c.odd_terms_pair)),
    "small ledger (< 500 rows) with >= 2 refunds -> clean": ("clean", lambda c: len(c.ep.ledger) < 500 and _count(
        c, lambda p: p["kind"] == "refund") >= 2),
    "small ledger (< 500 rows) with >= 3 null-ref receipts -> clean": ("clean", lambda c: len(c.ep.ledger) < 500 and _count(
        c, lambda p: p["kind"] == "receipt" and not p["invoice_refs"]) >= 3),
}


def measure_episodes(ctxs: list) -> dict:
    out = {}
    for name, (label, rule) in EPISODE_RULES.items():
        flagged = [c for c in ctxs if rule(c)]
        hits = sum(1 for c in flagged if bool(c.ep.truth["issues"]) == (label == "error"))
        out[name] = {"label": label, "predicted": len(flagged), "hits": hits,
                     "precision": hits / len(flagged) if flagged else 0.0}
    return out


def table(m: dict) -> str:
    lines = [f"{m['episodes']} episodes, {m['documents']} documents, {m['affected']} affected documents",
             f"{'rule':44s} {'pred':>5s} {'hits':>5s} {'prec':>6s} {'recall':>6s}"]
    for name, r in sorted(m["rules"].items(), key=lambda kv: -kv[1]["precision"] * (kv[1]["hits"] > 0)):
        lines.append(f"{name:44s} {r['predicted']:5d} {r['hits']:5d} {r['precision']:6.2f} {r['recall']:6.2f}")
    lines.append("episode-level rules (episodes flagged, correct, precision)")
    for name, r in m["episode_rules"].items():
        lines.append(f"{name:62s} {r['predicted']:3d} {r['hits']:3d} {r['precision']:5.2f}")
    return "\n".join(lines)


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


if __name__ == "__main__":
    unittest.main()
