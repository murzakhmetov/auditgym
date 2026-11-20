"""Independent full-information auditor.

Recomputes every expected posting from the public records and policy.json
alone and reports discrepancies of the four finding types plus "anomalies"
(inconsistencies that are not a finding type). It imports only the standard
library and the timestamp parser (timeutil), never the generator modules
(history, books, inject, render) and not money.py, whose conversion the
generator uses: FX conversion and proportional relief are its own integer
arithmetic (_convert_minor, _proportional_minor). So it is a second,
independent implementation of the published rules. verify.py requires it to
reproduce the answer key exactly on erroneous books and to find nothing on the
clean twin.

The strong scripted `auditor` policy runs the same code on records it fetched
through the tool interface.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from .timeutil import parse_ts

_DECIMAL = re.compile(r"([+-]?)([0-9]*)(?:\.([0-9]*))?(?:[eE]([+-]?[0-9]+))?")
MAX_DECIMAL_EXPONENT = 64  # far beyond any published amount or rate; 10 ** 99999999 would not finish


def _ratio(text) -> tuple:
    """A decimal string as an exact pair of integers (numerator, denominator > 0): "1.25" -> (125, 100)."""
    m = _DECIMAL.fullmatch(str(text).strip())
    if m is None or not (m.group(2) or m.group(3)):
        raise ValueError(f"not a decimal number: {text!r}")
    sign, whole, frac = m.group(1), m.group(2) or "0", m.group(3) or ""
    if m.group(4) and len(m.group(4).lstrip("+-")) > 3 or abs(int(m.group(4) or 0)) > MAX_DECIMAL_EXPONENT:
        raise ValueError(f"exponent out of range in {str(text)[:40]!r}")
    exp = int(m.group(4) or 0)
    num, den = int(whole + frac), 10 ** len(frac)
    if exp >= 0:
        num *= 10 ** exp
    else:
        den *= 10 ** -exp
    return (-num if sign == "-" else num), den


def _round_ratio(num: int, den: int, rounding: str) -> int:
    """num / den rounded to an integer: half_even (ties to even) or half_up (ties away from zero)."""
    if rounding not in ("half_even", "half_up"):
        raise ValueError(f"unknown rounding mode {rounding!r}")
    if den == 0:
        raise ZeroDivisionError("denominator must be non-zero")
    if den < 0:
        num, den = -num, -den
    q, r = divmod(abs(num), den)
    if 2 * r > den or (2 * r == den and (rounding == "half_up" or q % 2 == 1)):
        q += 1
    return -q if num < 0 else q


def _convert_minor(amount_minor: int, rate, src_exp: int, dst_exp: int, rounding: str) -> int:
    """amount_minor * rate * 10^(dst_exp - src_exp), rounded per the policy."""
    num, den = _ratio(rate)
    num *= int(amount_minor)
    shift = int(dst_exp) - int(src_exp)
    if shift >= 0:
        num *= 10 ** shift
    else:
        den *= 10 ** -shift
    return _round_ratio(num, den, rounding)


def _proportional_minor(total_minor: int, part: int, whole: int, rounding: str) -> int:
    """total_minor * part / whole, rounded per the policy."""
    return _round_ratio(int(total_minor) * int(part), int(whole), rounding)


def parse_offset(text: str) -> int:
    sign = -1 if text.startswith("-") else 1
    hh, mm = text[1:].split(":")
    return sign * (int(hh) * 60 + int(mm))


class OffsetSchedule:
    def __init__(self, schedule: list):
        self.entries = sorted((parse_ts(e["from_utc"]), parse_offset(e["offset"])) for e in schedule)
        if not self.entries:
            raise ValueError("empty utc_offset_schedule")

    def offset_at(self, inst: datetime) -> int:
        off = self.entries[0][1]
        for start, o in self.entries:
            if start <= inst:
                off = o
            else:
                break
        return off

    def local_date(self, inst: datetime) -> date:
        return (inst + timedelta(minutes=self.offset_at(inst))).date()


class Rates:
    def __init__(self, fx_rows: list, base: str):
        self.base = base
        self.table = {(r["date"], r["source_currency"], r["target_currency"]): r["rate"] for r in fx_rows}

    def for_date(self, ccy: str, d: date):
        """(rate, fx record id) per policy: exact date, else latest earlier published date."""
        if ccy == self.base:
            return "1", None
        for back in range(15):
            day = (d - timedelta(days=back)).isoformat()
            r = self.table.get((day, ccy, self.base))
            if r is not None:
                return r, f"{day}:{ccy}:{self.base}"
        return None, None


def _amt(row: dict) -> int:
    return row["debit_minor"] or row["credit_minor"]


def doc_signature(doc: dict) -> tuple:
    return (
        doc["kind"], doc["entity_id"], doc["currency"], doc["total_minor"], parse_ts(doc["issued_at"]),
        tuple((li["description"], li["quantity"], li["unit_price_minor"], li["amount_minor"], li["ref"]) for li in doc["line_items"]),
    )


def audit(manifest: dict, policy: dict, ledger: list, invoices: list, payments: list, fx: list) -> dict:
    base = policy["base_currency"]
    exps = policy["currency_exponents"]
    rounding = policy["rounding"]["mode"]
    p0 = parse_ts(policy["reporting_period"]["start"])
    p1 = parse_ts(policy["reporting_period"]["end"])
    extract_end = parse_ts(policy["ledger_extract"]["end"])
    sched = OffsetSchedule(policy["utc_offset_schedule"])
    rates = Rates(fx, base)
    accounts = set(policy["accounts"])
    findings: list[dict] = []
    anomalies: list[str] = []

    def in_period(inst):
        return p0 <= inst < p1

    inv_by_id = {d["invoice_id"]: d for d in invoices}
    pay_by_id = {d["payment_id"]: d for d in payments}

    # ------------------------------------------------------------ rows and journals
    journals: dict = {}
    for r in ledger:
        r_ts = parse_ts(r["timestamp"])
        if r["currency"] != base:
            anomalies.append(f"row {r['row_id']} not in base currency")
        if (r["debit_minor"] > 0) == (r["credit_minor"] > 0) or r["debit_minor"] < 0 or r["credit_minor"] < 0:
            anomalies.append(f"row {r['row_id']} must have exactly one positive side")
        if r["account"] not in accounts:
            anomalies.append(f"row {r['row_id']} unknown account {r['account']}")
        if r["invoice_id"] is not None and r["invoice_id"] not in inv_by_id:
            anomalies.append(f"row {r['row_id']} references unknown invoice")
        if r["payment_id"] is not None and r["payment_id"] not in pay_by_id:
            anomalies.append(f"row {r['row_id']} references unknown payment")
        if not (p0 <= r_ts < extract_end):
            anomalies.append(f"row {r['row_id']} outside the ledger extract")
        if r["payment_id"]:
            key = ("P", r["payment_id"])
        elif r["invoice_id"]:
            key = ("I", r["invoice_id"])
        else:
            key = ("T", r_ts)
        journals.setdefault(key, []).append((r_ts, r))
    for key, rows in journals.items():
        if sum(r["debit_minor"] for _, r in rows) != sum(r["credit_minor"] for _, r in rows):
            anomalies.append(f"journal {key[0]}:{key[1]} does not balance")
        if len({t for t, _ in rows}) != 1 and key[0] != "I":
            anomalies.append(f"journal {key[0]}:{key[1]} has several timestamps")
    if sum(r["debit_minor"] for r in ledger) != sum(r["credit_minor"] for r in ledger):
        anomalies.append("trial balance does not balance")

    # ------------------------------------------------------------ invoices
    booked: dict = {}  # invoice_id -> {"ts", "base", "open_doc", "carry"}
    for doc in sorted(invoices, key=lambda d: (parse_ts(d["issued_at"]), d["invoice_id"])):
        iid, ccy = doc["invoice_id"], doc["currency"]
        issued = parse_ts(doc["issued_at"])
        if doc["total_minor"] != sum(li["amount_minor"] for li in doc["line_items"]):
            anomalies.append(f"invoice {iid} total differs from its lines")
        for li in doc["line_items"]:
            if li["amount_minor"] != li["quantity"] * li["unit_price_minor"]:
                anomalies.append(f"invoice {iid} line {li['line_no']} amount differs from quantity x price")
        rate, fx_id = rates.for_date(ccy, sched.local_date(issued))
        if rate is None:
            anomalies.append(f"invoice {iid} has no FX rate")
            continue
        expected = _convert_minor(doc["total_minor"], rate, exps[ccy], exps[base], rounding)
        rows = [r for _, r in journals.get(("I", iid), [])]
        primary_acct, counter_acct = ("1100", "4000") if doc["kind"] == "sales" else ("2000", "5000")
        if issued < p0:
            opening = [r for r in rows if r["account"] in (primary_acct, "3900")]
            prim = [r for r in opening if r["account"] == primary_acct]
            if len(prim) != 1:
                anomalies.append(f"prior-period invoice {iid} has no single opening item")
                continue
            if _amt(prim[0]) != expected:
                anomalies.append(f"opening item of {iid} differs from its booked amount")
            booked[iid] = {"ts": p0, "base": _amt(prim[0]), "open_doc": doc["total_minor"], "carry": _amt(prim[0])}
            continue
        prim = [r for r in rows if r["account"] == primary_acct]
        ctr = [r for r in rows if r["account"] == counter_acct]
        if issued >= extract_end:
            if rows:
                anomalies.append(f"invoice {iid} dated after the extract is posted")
            continue
        if len(prim) != 1 or len(ctr) != 1:
            anomalies.append(f"invoice {iid} lacks a single posting")
            continue
        prim, ctr = prim[0], ctr[0]
        post_ts = parse_ts(prim["timestamp"])
        posted = _amt(prim)
        booked[iid] = {"ts": post_ts, "base": posted, "open_doc": doc["total_minor"], "carry": posted}
        doc_in, post_in = in_period(issued), in_period(post_ts)
        fx_finding = False
        if posted != expected:
            if ccy == base:
                anomalies.append(f"base-currency invoice {iid} posted with a different amount")
            elif doc_in or post_in:
                fx_finding = True
                findings.append({
                    "type": "wrong_fx_rate", "affected_ids": [iid], "amount": abs(posted - expected), "currency": base,
                    "evidence_sets": [[doc["doc_id"], prim["row_id"], fx_id], [doc["doc_id"], ctr["row_id"], fx_id]],
                })
        if doc_in != post_in:
            findings.append({
                "type": "wrong_period", "affected_ids": [iid], "amount": posted, "currency": base,
                "evidence_sets": [[doc["doc_id"], prim["row_id"]], [doc["doc_id"], ctr["row_id"]]],
            })
        elif post_ts != issued and not fx_finding:
            anomalies.append(f"invoice {iid} posted at a different time within the same period")

    # ------------------------------------------------------------ duplicates
    groups: dict = {}
    for doc in invoices:
        if doc["invoice_id"] in booked and booked[doc["invoice_id"]]["ts"] >= p0 and parse_ts(doc["issued_at"]) >= p0:
            groups.setdefault(doc_signature(doc), []).append(doc)
    for sig, docs in groups.items():
        if len(docs) < 2:
            continue
        if len(docs) > 2:
            anomalies.append("more than two identical invoices")
            continue
        a, b = docs
        pa, pb = ("1100", "4000") if a["kind"] == "sales" else ("2000", "5000")
        ra = {r["account"]: r for _, r in journals[("I", a["invoice_id"])]}
        rb = {r["account"]: r for _, r in journals[("I", b["invoice_id"])]}
        findings.append({
            "type": "duplicate_invoice", "affected_ids": [a["invoice_id"], b["invoice_id"]], "amount": _amt(rb[pa]),
            "currency": base,
            "evidence_sets": [[a["doc_id"], b["doc_id"], ra[pa]["row_id"], rb[pa]["row_id"]],
                              [a["doc_id"], b["doc_id"], ra[pb]["row_id"], rb[pb]["row_id"]]],
        })

    # ------------------------------------------------------------ payments
    credit: dict = {}  # (entity, currency) -> [doc, base] customer credits in 2900
    pay_rows = []
    for doc in payments:
        rows = [r for _, r in journals.get(("P", doc["payment_id"]), [])]
        if not rows:
            if parse_ts(doc["timestamp"]) < extract_end:
                anomalies.append(f"payment {doc['payment_id']} not posted")
            continue
        pay_rows.append((parse_ts(rows[0]["timestamp"]), doc["payment_id"], doc, rows))
    for post_ts, pid, doc, rows in sorted(pay_rows, key=lambda x: (x[0], x[1])):
        ccy, kind = doc["currency"], doc["kind"]
        ts_doc = parse_ts(doc["timestamp"])
        rate, fx_id = rates.for_date(ccy, sched.local_date(ts_doc))
        if rate is None:
            anomalies.append(f"payment {pid} has no FX rate")
            continue
        expected_bank = _convert_minor(doc["amount_minor"], rate, exps[ccy], exps[base], rounding)
        bank_rows = [r for r in rows if r["account"] == "1000"]
        if len(bank_rows) != 1:
            anomalies.append(f"payment {pid} lacks a single bank row")
            continue
        bank = bank_rows[0]
        posted_bank = _amt(bank)
        doc_in, post_in = in_period(ts_doc), in_period(post_ts)
        has_finding = False
        if posted_bank != expected_bank:
            if ccy == base:
                anomalies.append(f"base-currency payment {pid} posted with a different amount")
            elif doc_in or post_in:
                has_finding = True
                findings.append({"type": "wrong_fx_rate", "affected_ids": [pid], "amount": abs(posted_bank - expected_bank),
                                 "currency": base, "evidence_sets": [[doc["doc_id"], bank["row_id"], fx_id]]})
        relief_acct = "1100" if kind == "receipt" else "2000"
        reliefs = {}
        for r in rows:
            if r["account"] == relief_acct and r["invoice_id"]:
                reliefs[r["invoice_id"]] = r
        if doc_in != post_in:
            has_finding = True
            findings.append({"type": "wrong_period", "affected_ids": [pid], "amount": posted_bank, "currency": base,
                             "evidence_sets": [[doc["doc_id"], bank["row_id"]]]})
        elif post_ts != ts_doc:
            anomalies.append(f"payment {pid} posted at a different time within the same period")
        rate_used = rate
        if kind in ("receipt", "disbursement"):
            remaining = doc["amount_minor"]
            expected_allocs = []
            for ref in doc["invoice_refs"] or []:
                item = booked.get(ref)
                ref_doc = inv_by_id.get(ref)
                if item is None or ref_doc is None or item["ts"] > post_ts or item["open_doc"] <= 0:
                    continue
                if ref_doc["currency"] != ccy:
                    anomalies.append(f"payment {pid} currency differs from invoice {ref}")
                    continue
                a = min(remaining, item["open_doc"])
                expected_allocs.append((ref, a))
                remaining -= a
            expected_unalloc_doc = remaining
            posted_unalloc = sum(r["credit_minor"] for r in rows if r["account"] == "2900")
            expected_unalloc = _convert_minor(expected_unalloc_doc, rate_used, exps[ccy], exps[base], rounding) if expected_unalloc_doc else 0
            shortfall = False
            if kind == "receipt" and posted_unalloc > expected_unalloc and expected_allocs:
                shortfall = True
                has_finding = True
                refs_short = [ref for ref, _a in expected_allocs]
                unalloc_rows = [r for r in rows if r["account"] == "2900"]
                if len(refs_short) == 1 and len(unalloc_rows) == 1:
                    ref = refs_short[0]
                    findings.append({
                        "type": "unallocated_payment", "affected_ids": [pid, ref],
                        "amount": posted_unalloc - expected_unalloc, "currency": base,
                        "evidence_sets": [[doc["doc_id"], inv_by_id[ref]["doc_id"], unalloc_rows[0]["row_id"]]],
                    })
                else:
                    anomalies.append(f"payment {pid} under-allocated across several invoices")
            elif posted_unalloc != expected_unalloc and not has_finding:
                anomalies.append(f"payment {pid} unallocated amount differs from policy")
            # relief and FX-difference consistency (skipped where a finding explains the journal)
            total_relief = 0
            for ref, a in expected_allocs:
                item = booked[ref]
                exp_relief = item["carry"] if a == item["open_doc"] else _proportional_minor(item["carry"], a, item["open_doc"], rounding)
                row = reliefs.get(ref)
                posted_relief = _amt(row) if row else 0
                if not shortfall and posted_relief != exp_relief:
                    anomalies.append(f"payment {pid} relief of {ref} differs from the carrying amount rule")
                item["open_doc"] -= a
                item["carry"] -= posted_relief if shortfall else exp_relief
                total_relief += posted_relief
            fx_net = sum(r["credit_minor"] - r["debit_minor"] for r in rows if r["account"] == "7900")
            if kind == "receipt":
                expected_fx = posted_bank - total_relief - posted_unalloc
                if posted_unalloc and not shortfall and doc["invoice_refs"]:
                    c = credit.setdefault(doc["invoice_refs"][0], [0, 0])
                    c[0] += expected_unalloc_doc
                    c[1] += posted_unalloc
            else:
                expected_fx = total_relief - posted_bank
            if fx_net != expected_fx:
                anomalies.append(f"payment {pid} FX difference does not balance")
        elif kind == "refund":
            c = credit.get(doc["invoice_refs"][0]) if doc["invoice_refs"] else None
            relief_rows = [r for r in rows if r["account"] == "2900" and r["debit_minor"] > 0]
            if c is None or c[0] < doc["amount_minor"] or len(relief_rows) != 1:
                anomalies.append(f"refund {pid} exceeds the customer's credit")
                continue
            exp_relief = c[1] if doc["amount_minor"] == c[0] else _proportional_minor(c[1], doc["amount_minor"], c[0], rounding)
            if _amt(relief_rows[0]) != exp_relief:
                anomalies.append(f"refund {pid} relieves a different credit amount")
            c[0] -= doc["amount_minor"]
            c[1] -= exp_relief
        else:
            anomalies.append(f"payment {pid} has unknown kind")
    findings.sort(key=lambda f: (f["type"], sorted(f["affected_ids"])))
    return {"findings": findings, "anomalies": anomalies}


def audit_episode(ep) -> dict:
    return audit(ep.manifest, ep.policy, ep.ledger, ep.invoices, ep.payments, ep.fx)
