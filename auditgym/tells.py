"""Shortcut-tell measurement: how well single public features pick out the answer key.

The rules, the context they read and the pooled measurement live here so that the regression test
(tests/test_tells.py, 20 open episodes) and the large reproducible run use one implementation:

    python -m auditgym.tells --n 200 --out runs/tells

generates N episodes from a public master string with the check-set config mix (auditgym.splits.check_set, one
batch of 20 per derived master), measures every document rule, the residual tells (largest foreign purchase,
off-hours payment) and the episode-level rules, and writes summary.md and summary.json. The files hold no
timings and are byte-identical across runs; the elapsed time goes to stdout only.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from . import catalog
from .auditor import OffsetSchedule
from .money import CURRENCY_EXPONENTS
from .timeutil import parse_ts

DEFAULT_MASTER = "auditgym-tells-v1"
BATCH = 20

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


# Payments outside business hours (no longer only the boundary receipt), stated as explicit rules so that one
# command reproduces them. The other residual tell, the FX target being the largest foreign purchase, is scored
# against wrong_fx_rate targets only (Tally.add_fx), not against the whole answer key.
RESIDUAL_RULES = {
    "residual: off-hours payment": lambda c, i: not _inv(c, i) and _off_hours(c, i),
    "residual: off-hours payment outside the error window": lambda c, i: (
        not _inv(c, i) and _off_hours(c, i) and not in_error_window(c.docs[i][2], c.p1, c.sched)),
    "residual: off-hours payment inside the error window": lambda c, i: (
        not _inv(c, i) and _off_hours(c, i) and in_error_window(c.docs[i][2], c.p1, c.sched)),
}


class Tally:
    """Pooled counts for the document rules and the episode rules, fed one episode at a time."""

    def __init__(self, rules: dict):
        self.rules = rules
        self.fired = dict.fromkeys(rules, 0)
        self.hit = dict.fromkeys(rules, 0)
        self.episodes_firing = dict.fromkeys(rules, 0)
        self.ep_flagged = dict.fromkeys(EPISODE_RULES, 0)
        self.ep_hits = dict.fromkeys(EPISODE_RULES, 0)
        self.episodes = self.documents = self.affected = self.error_episodes = 0
        self.fx_eligible = self.fx_hits = 0
        self.fx_chance = 0.0

    def add(self, ep) -> None:
        c = Ctx(ep)
        truth = c.affected()
        self.episodes += 1
        self.documents += len(c.docs)
        self.affected += len(truth)
        self.error_episodes += bool(ep.truth["issues"])
        self.add_fx(c)
        for name, rule in self.rules.items():
            fired = {i for i in c.docs if rule(c, i)}
            self.fired[name] += len(fired)
            self.hit[name] += len(fired & truth)
            self.episodes_firing[name] += bool(fired)
        for name, (label, rule) in EPISODE_RULES.items():
            if rule(c):
                self.ep_flagged[name] += 1
                self.ep_hits[name] += bool(ep.truth["issues"]) == (label == "error")

    def add_fx(self, c) -> None:
        """Count one episode for the FX-target tell: eligible when a wrong_fx_rate target is a foreign purchase;
        a hit when the largest foreign purchase is one; chance is the share of foreign purchases that are targets."""
        fx = {i for iss in c.ep.truth["issues"] if iss["type"] == "wrong_fx_rate" for i in iss["affected_ids"]}
        targets = fx & set(c.rank_p)
        if not targets:
            return
        self.fx_eligible += 1
        self.fx_hits += any(c.rank_p[i] == 1 for i in targets)
        self.fx_chance += len(targets) / len(c.rank_p)

    def result(self) -> dict:
        rules = {n: {"predicted": self.fired[n], "hits": self.hit[n],
                     "precision": self.hit[n] / self.fired[n] if self.fired[n] else 0.0,
                     "recall": self.hit[n] / self.affected if self.affected else 0.0,
                     "episodes_firing": self.episodes_firing[n]} for n in self.rules}
        episode_rules = {n: {"label": label, "predicted": self.ep_flagged[n], "hits": self.ep_hits[n],
                             "precision": self.ep_hits[n] / self.ep_flagged[n] if self.ep_flagged[n] else 0.0}
                         for n, (label, _r) in EPISODE_RULES.items()}
        fx = {"eligible_episodes": self.fx_eligible, "largest_is_target": self.fx_hits,
              "rate": self.fx_hits / self.fx_eligible if self.fx_eligible else 0.0,
              "chance": self.fx_chance / self.fx_eligible if self.fx_eligible else 0.0}
        return {"rules": rules, "episode_rules": episode_rules, "fx_target": fx, "affected": self.affected,
                "episodes": self.episodes, "documents": self.documents, "error_episodes": self.error_episodes}


def measure_episode_objects(episodes) -> dict:
    """Pooled measurement of RULES and EPISODE_RULES over Episode objects."""
    tally = Tally(RULES)
    for ep in episodes:
        tally.add(ep)
    return tally.result()


def sample_entries(n: int, master: str = DEFAULT_MASTER) -> list:
    """n (name, seed, config) entries with the check-set mix: batches of 20 from check_set("<master>/<batch>");
    a short batch takes evenly spread entries, so n=2 still sees one clean and one error episode."""
    from .splits import check_set

    out = []
    for batch in range((n + BATCH - 1) // BATCH):
        take = min(BATCH, n - batch * BATCH)
        entries = check_set(f"{master}/{batch:02d}")
        for j in range(take):
            e = entries[j * BATCH // take]
            out.append((f"b{batch:02d}_{e['name']}", e["seed"], e["config"]))
    return out


def generate_sample(n: int, master: str = DEFAULT_MASTER):
    """Yield the generated episodes of sample_entries(n, master)."""
    from .generator import generate_episode

    for _name, seed, config in sample_entries(n, master):
        yield generate_episode(seed, config).episode


def run(n: int, master: str = DEFAULT_MASTER) -> dict:
    """Generate n episodes and measure RULES, RESIDUAL_RULES and the episode rules over them."""
    tally = Tally({**RULES, **RESIDUAL_RULES})
    for ep in generate_sample(n, master):
        tally.add(ep)
    out = tally.result()
    out["master"] = master
    out["residual"] = sorted(RESIDUAL_RULES)
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


def rounded(m: dict) -> dict:
    """A copy of the measurement with ratios rounded to 4 places, for the committed files."""
    out = json.loads(json.dumps(m))
    for key in ("rate", "chance"):
        out["fx_target"][key] = round(out["fx_target"][key], 4)
    for group in ("rules", "episode_rules"):
        for r in out[group].values():
            for key in ("precision", "recall"):
                if key in r:
                    r[key] = round(r[key], 4)
    return out


def to_json(m: dict) -> str:
    return json.dumps(rounded(m), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def to_markdown(m: dict) -> str:
    m = rounded(m)
    lines = ["# Shortcut-tell measurement", "",
             f"Master string `{m['master']}`, {m['episodes']} generated episodes ({m['error_episodes']} with errors), "
             f"{m['documents']} public documents, {m['affected']} affected documents (the answer key).",
             f"Reproduce: `python -m auditgym.tells --n {m['episodes']} --master {m['master']} --out runs/tells`.", "",
             "A rule fires on the documents it selects. True hits are fired documents that are in the answer key; "
             "precision = hits / fires on; recall = hits / affected documents; support = episodes in which the rule "
             "fires at least once.", "",
             "| rule | fires on | true hits | precision | recall | support |", "|---|---:|---:|---:|---:|---:|"]
    for name, r in sorted(m["rules"].items(), key=lambda kv: (-kv[1]["precision"] * (kv[1]["hits"] > 0), kv[0])):
        lines.append(f"| {name} | {r['predicted']} | {r['hits']} | {r['precision']:.4f} | {r['recall']:.4f} | {r['episodes_firing']} |")
    n, n_err = m["episodes"], m["error_episodes"]
    base = {"error": n_err / n if n else 0.0, "clean": (n - n_err) / n if n else 0.0}
    lines += ["", "## Episode-level rules", "",
              f"Base rate: {n_err} of {n} episodes have errors ({base['error']:.4f}) and {n - n_err} are clean "
              f"({base['clean']:.4f}). A rule is a tell only if its precision is well above the base rate of its label.", "",
              "| rule | label | episodes flagged | correct | precision | base rate of the label |",
              "|---|---|---:|---:|---:|---:|"]
    for name, r in m["episode_rules"].items():
        lines.append(f"| {name} | {r['label']} | {r['predicted']} | {r['hits']} | {r['precision']:.4f} | "
                     f"{base.get(r['label'], 0.0):.4f} |")
    fx = m["fx_target"]
    lines += ["", "## FX target and the largest foreign purchase", "",
              f"Among the {fx['eligible_episodes']} episodes whose answer key has a wrong_fx_rate target that is a foreign "
              f"purchase invoice, the largest foreign purchase is such a target in {fx['largest_is_target']} "
              f"(rate {fx['rate']:.4f}). Chance level, the mean share of foreign purchases that are targets: {fx['chance']:.4f}.",
              "", "## Measured only in the regression test", "",
              "The episode rules on the count of documents in the error window (more or fewer than the typical count, by "
              "size and kind) and the window-by-kind rules scored against utc_wall_clock targets only are measured in "
              "tests/test_tells.py on 100 generated episodes. The window rows above are scored against all affected documents."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m auditgym.tells", description="Measure shortcut tells on generated episodes.")
    ap.add_argument("--n", type=int, default=200, help="number of generated episodes")
    ap.add_argument("--master", default=DEFAULT_MASTER, help="public master string the seeds derive from")
    ap.add_argument("--out", default="runs/tells", help="directory for summary.md and summary.json")
    args = ap.parse_args(argv)
    if args.n < 1:
        ap.error("--n must be at least 1")
    t0 = time.time()
    m = run(args.n, args.master)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(to_json(m), encoding="utf-8", newline="\n")
    (out / "summary.md").write_text(to_markdown(m), encoding="utf-8", newline="\n")
    print(f"{m['episodes']} episodes, {m['documents']} documents, {m['affected']} affected; wrote {out}/summary.md and summary.json")
    print(f"elapsed {time.time() - t0:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
