"""The `large` preset stays within the case's suggested 200 documents and 2,000 ledger rows.

The suggestion is not enforced for every config (more errors and distractors add documents, and explicit `counts` are the
caller's choice); the preset ranges are what keeps a default large episode inside it.
"""

import unittest

from auditgym import config
from auditgym.generator import generate_episode


def sizes(gen):
    pub = gen.episode.public_texts()
    docs = len(pub["invoices.jsonl"].splitlines()) + len(pub["payments.jsonl"].splitlines())
    return docs, len(pub["ledger.csv"].splitlines()) - 1


class LargePresetSizeTests(unittest.TestCase):
    def test_the_large_preset_ranges_are_lowered(self):
        self.assertLessEqual(config.SIZES["large"]["sales_invoices"][1], 30)
        self.assertLessEqual(config.SIZES["large"]["purchase_invoices"][1], 15)

    def test_default_large_episodes_stay_within_the_suggested_sizes(self):
        for seed in range(1, 21):
            with self.subTest(seed=seed):
                docs, rows = sizes(generate_episode(seed * 7919, {"size": "large"}, verify=False))
                self.assertLessEqual(docs, 200)
                self.assertLessEqual(rows, 2000)
                self.assertGreaterEqual(rows, 1500)

    def test_explicit_counts_still_make_a_bigger_episode(self):
        docs, _rows = sizes(generate_episode(5, {"size": "large", "counts": {"sales_invoices": 120, "purchase_invoices": 40}},
                                             verify=False))
        self.assertGreater(docs, 200)


if __name__ == "__main__":
    unittest.main()
