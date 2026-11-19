"""Diagnostics: soft return, micro P/R, unobserved-citation alarm, false-positive causes.

Pinned: only invariants (unobserved == 0 for recon/auditor, FP causes sum to FP, micro P/R formulas).
"""

import unittest
from pathlib import Path

from auditgym.diagnostics import citation_report, fp_causes, observed_closure, observed_with_refs
from auditgym.episode import load_episode
from auditgym.report import fp_table, markdown_table, miss_table, reward_table, summarize
from auditgym.policies.oracle import OraclePolicy
from auditgym.policies.recon import ReconPolicy
from auditgym.runner import run_many, run_one

DEV = Path(__file__).resolve().parents[1] / "episodes" / "dev"
GRADES = None
SUMMARY = None


def setUpModule():
    global GRADES, SUMMARY
    eps = [("dev", p.name, load_episode(p)) for p in sorted(DEV.iterdir()) if (p / "public").exists()]
    _traj, GRADES = run_many(eps, ["recon", "auditor", "oracle"], mode="eval", isolated=False)
    SUMMARY = summarize(GRADES)


class AliasRecon:
    """Recon that submits with the accepted alias form {"action": "submit", "args": {...}}."""

    def __init__(self):
        self.inner = ReconPolicy()

    def act(self, obs, reward=0.0, info=None):
        a = self.inner.act(obs, reward, info)
        if isinstance(a, dict) and a.get("action") == "submit":
            return {"action": "submit", "args": {k: v for k, v in a.items() if k != "action"}}
        return a


class LeakyLedgerScanner:
    """Simulated leak: lists the ledger only, then submits an answer handed to it out of band."""
    FINDINGS = None
    EPISODE_ID = None

    def __init__(self):
        self.started = False

    def act(self, obs, reward=0.0, info=None):
        res = obs.get("result") or {}
        if not self.started:
            self.started = True
            return {"action": "list_records", "table": "ledger"}
        nxt = res.get("next_cursor") if isinstance(res, dict) else None
        if nxt:
            return {"action": "list_records", "table": "ledger", "cursor": nxt}
        return {"action": "submit", "findings": {"episode_id": self.EPISODE_ID, "findings": self.FINDINGS}}


def finding(ids, evidence=()):
    return {"type": "duplicate_invoice", "affected_ids": list(ids), "evidence_ids": list(evidence),
            "claimed_amount_minor": 0, "currency": "GBP"}


class UnitTests(unittest.TestCase):
    def test_observed_ids_include_invoice_refs_fx_and_aliases(self):
        obs = {"result": {"table": "payments", "rows": [
            {"doc_id": "DOC-1", "payment_id": "RCPT-1", "invoice_refs": ["INV-9"]},
            {"date": "2026-05-04", "source_currency": "EUR", "target_currency": "GBP", "rate": "0.8"}]}}
        self.assertEqual(observed_with_refs(obs), {"DOC-1", "RCPT-1", "INV-9", "2026-05-04:EUR:GBP"})
        self.assertEqual(observed_with_refs({"result": None, "error": {"code": "x"}}), set())
        closure = observed_closure([obs, {"result": {"document": {"doc_id": "DOC-2"}}}], {"DOC-2": "INV-2"})
        self.assertIn("INV-2", closure)

    def test_citation_report_flags_unseen_ids_only(self):
        findings = [finding(["INV-1", "INV-2"], ["GL-1", "GL-9"])]
        obs = [{"result": {"rows": [{"row_id": "GL-1", "invoice_id": "INV-1"}, {"doc_id": "DOC-2"}]}}]
        rep = citation_report(findings, obs, {"DOC-2": "INV-2"})
        self.assertEqual(rep["cited_unobserved"], ["GL-9"])
        self.assertEqual(rep["n_cited"], 4)
        self.assertEqual(citation_report(findings, None, {})["n_cited_unobserved"], 4)
        self.assertEqual(citation_report([], obs, {}), {"n_cited": 0, "n_cited_unobserved": 0, "cited_unobserved": []})

    def test_fp_cause_priority(self):
        truth = {"id_aliases": {}, "issues": [{"affected_ids": ["A", "B"]}]}
        prov = {"distractors": [{"kind": "legit_repeat", "ids": ["B", "C"]}, {"kind": "recurring", "ids": ["D"]}]}
        findings = [finding(["C", "X"]), finding(["A", "Z"]), finding(["Q"]), finding(["B"])]
        un = [{"index": i} for i in range(4)]
        causes = [c["cause"] for c in fp_causes(findings, un, truth, prov)]
        self.assertEqual(causes, ["legit_repeat", "near_issue", "unrelated", "legit_repeat"])
        no_prov = [c["cause"] for c in fp_causes(findings, un, truth, {})]
        self.assertEqual(no_prov, ["unrelated", "near_issue", "unrelated", "near_issue"])


class DevMeasurements(unittest.TestCase):
    """Measured on episodes/dev (10 episodes, 2 clean) and pinned."""

    def s(self, policy):
        return SUMMARY[f"dev/{policy}"]

    def test_oracle_alarm_positive_control(self):
        o = self.s("oracle")
        self.assertEqual(o["unobserved_citation_share"], 1.0)
        self.assertEqual(o["n_cited_unobserved"], o["n_cited"])
        self.assertGreater(o["n_cited"], 0)

    def test_agent_policies_cite_only_observed_ids(self):
        for pol in ("recon", "auditor"):
            self.assertEqual(self.s(pol)["n_cited_unobserved"], 0, pol)
            self.assertEqual(self.s(pol)["unobserved_citation_share"], 0.0, pol)
            self.assertGreater(self.s(pol)["n_cited"], 0, pol)

    def test_recon_fp_causes_sum_to_fp(self):
        r = self.s("recon")
        self.assertEqual(sum(r["fp_causes"].values()), r["fp"])
        for g in GRADES:
            self.assertEqual(len(g["fp_details"]), g["fp"], g["episode_name"])
        self.assertEqual(self.s("auditor")["fp_causes"], {})
        self.assertEqual(self.s("oracle")["fp_causes"], {})

    def test_micro_precision_recall(self):
        a, r, o = self.s("auditor"), self.s("recon"), self.s("oracle")
        self.assertEqual((o["micro_precision"], o["micro_recall"]), (1.0, 1.0))
        self.assertEqual((a["micro_precision"], a["micro_recall"]), (1.0, 1.0))
        self.assertEqual(r["micro_precision"], round(r["tp"] / (r["tp"] + r["fp"]), 4))
        self.assertEqual(r["micro_recall"], round(r["tp"] / (r["tp"] + r["fn"]), 4))

    def test_evidence_timing(self):
        r, a, o = self.s("recon"), self.s("auditor"), self.s("oracle")
        self.assertIsNone(o["mean_first_full_evidence_step"])
        for v in (r, a):
            self.assertIsNotNone(v["mean_first_full_evidence_step"])
            self.assertLessEqual(v["issues_seen_not_flagged"], v["issues_total"])

    def test_soft_columns_and_tables(self):
        for v in SUMMARY.values():
            for k in ("return", "return_experimental", "soft_f1", "micro_precision", "micro_recall", "precision", "recall",
                      "f1", "miss_reasons", "recall_by_type", "closed_share"):
                self.assertIn(k, v)  # old keys stay, new ones are added
        md = markdown_table(SUMMARY)
        for h in ("soft return", "micro P", "micro R", "unobserved citations"):
            self.assertIn(h, md)
        self.assertIn("P = R = 0", md)
        self.assertIn("experimental (soft) return", reward_table(SUMMARY))
        self.assertIn("FP causes", fp_table(SUMMARY))
        self.assertIn("P and R are macro means", md)
        no_clean = {k: dict(v, return_clean=None) for k, v in SUMMARY.items()}
        self.assertNotIn("P and R are macro means", markdown_table(no_clean))
        full = miss_table(SUMMARY)
        self.assertIn("Common vs experimental reward", full)
        self.assertIn("legit_repeat=", full)

    def test_diagnostics_stay_out_of_observations(self):
        ep = load_episode(DEV / "d03_duplicates_gbp")
        traj, rec = run_one(ep, "recon", split="dev", isolated=False)
        blob = repr(traj)
        for k in ("cited_unobserved", "fp_details", "n_cited"):
            self.assertNotIn(k, blob)
            self.assertIn(k, rec)

    def test_alias_submit_form_is_diagnosed(self):
        ep = load_episode(DEV / "d03_duplicates_gbp")
        _t, plain = run_one(ep, "recon", split="dev", isolated=False)
        _t, alias = run_one(ep, f"{__name__}:AliasRecon", split="dev", isolated=False)
        self.assertEqual((alias["tp"], alias["fp"]), (plain["tp"], plain["fp"]))
        self.assertGreater(alias["n_cited"], 0)
        self.assertEqual(alias["n_cited"], plain["n_cited"])
        self.assertEqual(alias["n_cited_unobserved"], 0)
        self.assertEqual(len(alias["fp_details"]), alias["fp"])

    def test_leaky_policy_raises_alarm(self):
        """Positive control with real observations: sees only the ledger, cites the answer key."""
        ep = load_episode(DEV / "d03_duplicates_gbp")
        LeakyLedgerScanner.FINDINGS = OraclePolicy(ep.truth).findings()
        LeakyLedgerScanner.EPISODE_ID = ep.episode_id
        _t, g = run_one(ep, f"{__name__}:LeakyLedgerScanner", split="dev", isolated=False)
        self.assertGreater(g["n_cited"], 0)
        self.assertGreater(g["n_cited_unobserved"], 0)


if __name__ == "__main__":
    unittest.main()
