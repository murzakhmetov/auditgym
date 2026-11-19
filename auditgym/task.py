"""Task description shown in the first observation. Constant across episodes
except for the episode ID, budget, and mode; it never reveals configuration
or error counts."""

from __future__ import annotations

from . import FINDING_TYPES
from .schemas import MAX_AFFECTED_IDS, MAX_EVIDENCE_IDS, MAX_EXPLANATION_CHARS, MAX_FINDINGS, MAX_PAGE

TOLERANCE_MINOR = 2

FINDING_TYPE_RULES = {
    "duplicate_invoice": {
        "meaning": "The same invoice is posted twice (see policy.duplicate_rule).",
        "affected_ids": "invoice_id of both copies",
        "amount": "base amount of one copy's posting",
        "evidence": "both invoice documents plus, for both copies, the posting row on the same side "
                    "(both payable/receivable rows, or both expense/revenue rows)",
    },
    "unallocated_payment": {
        "meaning": "A receipt references an invoice whose open balance covers it, yet part or all of it is "
                   "credited to 2900 instead of relieving the invoice.",
        "affected_ids": "payment_id and the referenced invoice_id",
        "amount": "base amount wrongly credited to 2900",
        "evidence": "the payment document, the invoice document, and the payment's 2900 row",
    },
    "wrong_fx_rate": {
        "meaning": "A foreign-currency document is converted with a rate other than the policy rate "
                   "(wrong date or wrong value).",
        "affected_ids": "invoice_id or payment_id of the document",
        "amount": "absolute difference between the posted base amount and the policy base amount, measured on the "
                  "receivable/payable row (invoices) or the bank row (payments)",
        "evidence": "the document, the posting row (invoices: either side; payments: bank row), and the fx record "
                    "of the correct date",
    },
    "wrong_period": {
        "meaning": "A document is posted outside the period its own timestamp belongs to, in company time; only "
                   "crossings into or out of the reporting period count.",
        "affected_ids": "invoice_id or payment_id of the document",
        "amount": "posted base amount of the receivable/payable row (invoices) or the bank row (payments)",
        "evidence": "the document and one of its posting rows (invoices: either side; payments: the bank row)",
    },
}


def build_task(episode, max_steps: int, mode: str) -> dict:
    return {
        "objective": (
            "Audit the reporting period's ledger against the source documents and the policy. Report every "
            "discrepancy of the four finding types with evidence, then call submit exactly once. Some ledgers are "
            "clean: an empty findings list is the correct answer when nothing is wrong."
        ),
        "episode_id": episode.episode_id,
        "finding_types": {t: FINDING_TYPE_RULES[t] for t in FINDING_TYPES},
        "conventions": {
            "amounts": "claimed_amount_minor is a non-negative integer in minor units of the base currency; "
                       "currency is the base currency code",
            "tolerance_minor": TOLERANCE_MINOR,
            "ids": "affected_ids and evidence_ids are compared as sets after trimming spaces (case-sensitive). A "
                   "document may be cited by doc_id or by its invoice_id/payment_id. FX records are cited as "
                   "'YYYY-MM-DD:SRC:TGT'. A finding needs at least one complete evidence set; extra IDs are ignored.",
            "matching": "one-to-one with the answer key; repeated or unmatched findings are false positives",
        },
        "reward": {
            "formula": "clip(2*F1 - 1 - 0.002*inspection_steps, -1, 1)",
            "inspection_steps": "every step except the final submit",
            "invalid_submission": -1,
            "returned_to_policy": "terminal reward at the end of the episode" if mode == "train"
            else "nothing during the run (evaluation mode)",
        },
        "limits": {
            "max_steps": max_steps,
            "page_size_max": MAX_PAGE,
            "max_findings": MAX_FINDINGS,
            "max_affected_ids": MAX_AFFECTED_IDS,
            "max_evidence_ids": MAX_EVIDENCE_IDS,
            "max_explanation_chars": MAX_EXPLANATION_CHARS,
            "time_limit_s": 60,
        },
        "actions": {
            "list_records": {"table": "ledger | invoices | payments | fx", "cursor": "null or next_cursor", "limit": "1..50"},
            "get_record": {"table": "ledger | invoices | payments | fx", "id": "row_id | invoice_id | payment_id | fx id"},
            "get_document": {"doc_id": "doc_id of an invoice or payment"},
            "calculator": {"expression": "arithmetic on decimal numbers: + - * / and parentheses; at most 256 characters "
                                                              "and at most 200 tokens (each number, operator and parenthesis is one token)"},
            "submit": {"findings": {"episode_id": "...", "findings": [{"type": "...", "affected_ids": ["..."],
                                                                      "claimed_amount_minor": 0, "currency": "XXX",
                                                                      "evidence_ids": ["..."], "explanation": "..."}]}},
        },
        "record_keys": {"ledger": "row_id", "invoices": "invoice_id", "payments": "payment_id", "fx": "date:source_currency:target_currency"},
    }
