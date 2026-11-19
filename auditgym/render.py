"""Rendering: internal books -> public records with opaque IDs, plus truth and
provenance.

One Renderer (one ID map, one timestamp-representation map) renders both the
clean books and the erroneous books, so provenance can be computed as an
exact record-level diff that reverts cleanly.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from . import SCHEMA_VERSION, __version__
from .books import Books
from .history import History
from .ids import IdFactory
from .policy import build_policy
from .rng import Rng, seed_from_text
from .timeutil import format_local, format_ts, format_utc, offset_schedule
from .task import TOLERANCE_MINOR

ALT_OFFSETS = (-300, 0, 180, 330, 540, 600)


def _ident_key(ident: tuple) -> tuple:
    journal, role, extra = ident
    return (journal[0], journal[1] if len(journal) > 1 else "", role, extra or "")


class Renderer:
    def __init__(self, h: History, cfg: dict, rng: Rng, invoices: dict, idents: list):
        self.h = h
        self.cfg = cfg
        self.ids = IdFactory(rng.fork("ids"), cfg["id_style"], h.year)
        self.repr_salt = rng.fork("repr").next_u64()
        self.order_rng = rng.fork("order")
        self.ent_id = {}
        for k in sorted(h.entities):
            self.ent_id[k] = self.ids.new("customer" if h.entities[k].role == "customer" else "supplier")
        self.inv_id, self.inv_doc = {}, {}
        for k in sorted(invoices):
            self.inv_id[k] = self.ids.new("sales_invoice" if invoices[k].kind == "sales" else "purchase_invoice")
            self.inv_doc[k] = self.ids.new("doc")
        self.pay_id, self.pay_doc = {}, {}
        for k in sorted(h.payments):
            self.pay_id[k] = self.ids.new(h.payments[k].kind)
            self.pay_doc[k] = self.ids.new("doc")
        self.row_id = {}
        for ident in sorted(set(idents), key=_ident_key):
            self.row_id[ident] = self.ids.new("row")

    # ------------------------------------------------------------ formatting
    def ts(self, inst: datetime, key: str) -> str:
        mode = self.cfg["ts_repr"]
        if mode == "local":
            return format_local(inst, self.h.tz)
        if mode == "utc":
            return format_utc(inst)
        hsh = seed_from_text(f"{self.repr_salt}|{key}")
        pick = hsh % 3
        if pick == 0:
            return format_local(inst, self.h.tz)
        if pick == 1:
            return format_utc(inst)
        return format_ts(inst, ALT_OFFSETS[(hsh // 3) % len(ALT_OFFSETS)])

    def _tiebreak(self, key: str) -> int:
        return seed_from_text(f"{self.repr_salt}|order|{key}")

    def fx_id(self, key: tuple) -> str:
        d, src, tgt = key
        return f"{d.isoformat()}:{src}:{tgt}"

    # ------------------------------------------------------------ records
    def ledger(self, books: Books) -> list:
        rows = []
        for ln in books.lines:
            rid = self.row_id[ln.ident]
            rows.append((ln.ts, ln.seq, ln.order, rid, {
                "row_id": rid,
                "timestamp": self.ts(ln.ts, rid),
                "account": ln.account,
                "debit_minor": ln.debit,
                "credit_minor": ln.credit,
                "currency": self.h.base,
                "entity_id": self.ent_id.get(ln.entity) if ln.entity else None,
                "invoice_id": self.inv_id.get(ln.invoice) if ln.invoice else None,
                "payment_id": self.pay_id.get(ln.payment) if ln.payment else None,
            }))
        return self._order(rows, lambda r: (r[0], r[1], r[2]))

    def invoices(self, invoices: dict) -> list:
        out = []
        for k, inv in invoices.items():
            did = self.inv_doc[k]
            rec = {
                "doc_id": did,
                "invoice_id": self.inv_id[k],
                "kind": inv.kind,
                "entity_id": self.ent_id[inv.entity],
                "issued_at": self.ts(inv.issued, did),
                "due_at": self.ts(inv.due, did),
                "currency": inv.currency,
                "total_minor": inv.total,
                "line_items": [
                    {"line_no": i + 1, "description": li.description, "quantity": li.quantity,
                     "unit_price_minor": li.unit_price_minor, "amount_minor": li.amount_minor, "ref": li.ref}
                    for i, li in enumerate(inv.lines)
                ],
            }
            out.append((inv.issued, self._tiebreak(did), 0, did, rec))
        return self._order(out, lambda r: (r[0], r[1]))

    def payments(self) -> list:
        out = []
        for k, p in self.h.payments.items():
            did = self.pay_doc[k]
            rec = {
                "doc_id": did,
                "payment_id": self.pay_id[k],
                "kind": p.kind,
                "entity_id": self.ent_id[p.entity] if p.entity else None,
                "timestamp": self.ts(p.ts, did),
                "currency": p.currency,
                "amount_minor": p.amount,
                "invoice_refs": [self.inv_id[r] for r in p.refs] if p.refs is not None else None,
                "bank_ref": p.bank_ref,
            }
            out.append((p.ts, self._tiebreak(did), 0, did, rec))
        return self._order(out, lambda r: (r[0], r[1]))

    def fx(self) -> list:
        out = []
        for key, rate in list(self.h.fx.items()) + list(self.h.fx_noise.items()):
            d, src, tgt = key
            rec = {"date": d.isoformat(), "source_currency": src, "target_currency": tgt, "rate": rate}
            out.append((d, src, tgt, 0, rec))
        return self._order(out, lambda r: (r[0], r[1], r[2]))

    def _order(self, items: list, key) -> list:
        if self.cfg["row_order"] == "shuffled":
            items = sorted(items, key=key)
            self.order_rng.fork(str(len(items))).shuffle(items)
            return [it[-1] for it in items]
        return [it[-1] for it in sorted(items, key=key)]

    # ------------------------------------------------------------ meta
    def policy(self) -> dict:
        h = self.h
        fx_dates = sorted(d for d, _s, _t in h.fx)
        sched = offset_schedule(h.tz, datetime.combine(fx_dates[0], datetime.min.time()).replace(tzinfo=h.p0.tzinfo) - timedelta(days=1),
                                h.cutoff_end + timedelta(days=2)) if fx_dates else offset_schedule(h.tz, h.lookback_start, h.cutoff_end)
        return build_policy(
            tz=h.tz,
            schedule=sched,
            period_start=format_local(h.p0, h.tz),
            period_end=format_local(h.p1, h.tz),
            extract_end=format_local(h.cutoff_end, h.tz),
            rounding=h.rounding,
            exponents=h.exponents,
            base=h.base,
            holidays=[d.isoformat() for d in h.holidays],
            fx_first=fx_dates[0].isoformat() if fx_dates else None,
            fx_last=fx_dates[-1].isoformat() if fx_dates else None,
        )

    def manifest(self, episode_id: str, ledger: list, invoices: list, payments: list, fx: list) -> dict:
        h = self.h
        return {
            "schema_version": SCHEMA_VERSION,
            "generator_version": __version__,
            "episode_id": episode_id,
            "company": {"name": h.company, "synthetic": True},
            "base_currency": h.base,
            "currency_exponents": dict(h.exponents),
            "period_start": format_local(h.p0, h.tz),
            "period_end": format_local(h.p1, h.tz),
            "ledger_extract_end": format_local(h.cutoff_end, h.tz),
            "timezone": h.tz,
            "record_counts": {"ledger": len(ledger), "invoices": len(invoices), "payments": len(payments), "fx": len(fx)},
            "document_counts": {"invoices": len(invoices), "payments": len(payments), "total": len(invoices) + len(payments)},
            "rounding": {"mode": h.rounding, "fx_conversion": "round(amount_minor * rate * 10^(exp_base - exp_document))"},
            "files": ["manifest.json", "ledger.csv", "invoices.jsonl", "payments.jsonl", "fx.csv", "policy.json"],
        }

    # ------------------------------------------------------------ answer key
    def public_ref(self, ref) -> str:
        kind, val = ref
        if kind == "doc":
            return self.inv_doc[val] if val in self.inv_doc else self.pay_doc[val]
        if kind == "row":
            return self.row_id[val]
        if kind == "fx":
            return self.fx_id(val)
        raise ValueError(kind)

    def affected_id(self, ref) -> str:
        kind, key = ref
        return self.inv_id[key] if kind == "invoice" else self.pay_id[key]

    def truth(self, episode_id: str, issues: list, invoices: dict) -> dict:
        out = []
        for n, iss in enumerate(issues, start=1):
            it = iss["item"]
            out.append({
                "issue_id": f"iss_{n:02d}",
                "type": it.type,
                "variant": it.variant,
                "scenario": it.scenario,
                "affected_ids": [self.affected_id(r) for r in iss["affected"]],
                "expected_amount_minor": int(iss["amount"]),
                "currency": self.h.base,
                "tolerance_minor": TOLERANCE_MINOR,
                "evidence_sets": [[self.public_ref(r) for r in es] for es in iss["evidence"]],
                "explanation": iss["explanation"],
            })
        aliases = {}
        for k in sorted(invoices):
            aliases[self.inv_doc[k]] = self.inv_id[k]
        for k in sorted(self.h.payments):
            aliases[self.pay_doc[k]] = self.pay_id[k]
        return {"schema_version": SCHEMA_VERSION, "episode_id": episode_id, "issues": out, "id_aliases": aliases}


def diff_records(clean: dict, injected: dict) -> list:
    """Record-level ops turning clean public tables into injected ones."""
    ops = []
    for table, key in (("ledger", "row_id"), ("invoices", "doc_id"), ("payments", "doc_id")):
        a = {r[key]: r for r in clean[table]}
        b = {r[key]: r for r in injected[table]}
        for rid in sorted(set(a) | set(b)):
            if rid not in b:
                ops.append({"op": "remove", "table": table, "id": rid, "record": a[rid]})
            elif rid not in a:
                ops.append({"op": "add", "table": table, "id": rid, "record": b[rid]})
            else:
                for field in a[rid]:
                    if a[rid][field] != b[rid].get(field):
                        ops.append({"op": "set", "table": table, "id": rid, "field": field,
                                    "before": a[rid][field], "after": b[rid][field]})
    return ops


def apply_ops(tables: dict, ops: list, reverse: bool = False) -> dict:
    """Apply (or revert) provenance ops to {table: [records]}; returns new tables keyed by id."""
    keys = {"ledger": "row_id", "invoices": "doc_id", "payments": "doc_id"}
    out = {t: {r[keys[t]]: dict(r) for r in tables[t]} for t in keys}
    seq = list(reversed(ops)) if reverse else list(ops)
    for op in seq:
        t, rid = op["table"], op["id"]
        kind = op["op"]
        if reverse:
            kind = {"add": "remove", "remove": "add", "set": "set"}[kind]
        if kind == "add":
            out[t][rid] = dict(op["record"])
        elif kind == "remove":
            out[t].pop(rid, None)
        else:
            out[t][rid][op["field"]] = op["before"] if reverse else op["after"]
    return out
