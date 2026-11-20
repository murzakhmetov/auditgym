"""tools/mutation_smoke.py: the mutant list still fits the code, and the summary writer is deterministic.

A refactor that moves or rewords a listed snippet must fail here, loudly, instead of silently dropping a mutant
from the committed mutation run (runs/mutation/).
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "mutation_smoke.py"
RECORDED = ROOT / "runs" / "mutation"

CORE_FILES = {
    "auditgym/matcher.py", "auditgym/reward.py", "auditgym/grader.py", "auditgym/schemas.py", "auditgym/env.py",
    "auditgym/verify.py", "auditgym/evidence_check.py", "auditgym/protocol.py",
}


def load_tool():
    spec = importlib.util.spec_from_file_location("mutation_smoke", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = load_tool()


class MutantListTests(unittest.TestCase):
    def test_every_snippet_occurs_exactly_once_and_compiles(self):
        self.assertEqual(tool.list_problems(), [])

    def test_each_snippet_is_found_by_count_in_the_working_tree(self):
        for m in tool.MUTANTS:
            self.assertEqual(tool.occurrences(m), 1, f"{m.id}: {m.old!r} in {m.file}")

    def test_the_list_is_well_formed_and_covers_the_core(self):
        ids = [m.id for m in tool.MUTANTS]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 40)
        self.assertTrue(CORE_FILES <= {m.file for m in tool.MUTANTS}, CORE_FILES - {m.file for m in tool.MUTANTS})
        for m in tool.MUTANTS:
            self.assertTrue(m.breaks.strip(), m.id)
            self.assertNotEqual(m.old, m.new, m.id)
            self.assertTrue(m.modules and all(mod.startswith("tests.test_") for mod in m.modules), m.id)
            for mod in m.modules:
                self.assertTrue((ROOT / (mod.replace(".", "/") + ".py")).is_file(), f"{m.id}: {mod}")
            if m.equivalent:
                self.assertGreater(len(m.equivalent), 20, f"{m.id}: say why it is equivalent")


class WriterTests(unittest.TestCase):
    def results(self):
        fake = {"passed": False, "why": "FAILED (failures=1) at 12:34:56 in 1.5 s", "killed_by": "existing tests"}
        late = dict(fake, killed_by="survivor tests")
        ok = {"passed": True, "why": "", "killed_by": ""}
        a, b, c, d = tool.MUTANTS[0], tool.MUTANTS[1], tool.MUTANTS[2], tool.MUTANTS[3]
        d = d._replace(equivalent="the change cannot alter any behavior at all")
        return [(a, fake), (b, ok), (c, late), (d, ok)]

    def test_counts_and_classes(self):
        report = tool.build_report(self.results())
        self.assertEqual((report["listed"], report["counted"], report["killed"], report["survived"],
                          report["equivalent"]), (4, 3, 2, 1, 1))
        self.assertEqual([r["status"] for r in report["mutants"]], ["killed", "survived", "killed", "equivalent"])
        self.assertEqual((report["killed_by_existing"], report["killed_by_survivor_tests"]), (1, 1))
        self.assertIn("2 of 3 listed mutants killed", tool.render_markdown(report))
        self.assertIn("1 of 3 are killed by the existing tests, 1 more only by", tool.render_markdown(report))
        self.assertIn("## Survivors", tool.render_markdown(report))
        self.assertIn("## Equivalent mutants", tool.render_markdown(report))

    def test_the_summary_is_deterministic_and_has_no_run_noise(self):
        written = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as tmp:
                tool.write_report(tool.build_report(self.results()), Path(tmp))
                written.append({n: (Path(tmp) / n).read_bytes() for n in ("summary.md", "summary.json")})
        self.assertEqual(written[0], written[1])
        for data in written[0].values():
            self.assertNotIn(b"12:34:56", data)  # the tests' output never reaches the summary
            self.assertNotIn(b"\r", data)
            self.assertNotIn(str(ROOT).encode("utf-8"), data)
        report = json.loads(written[0]["summary.json"])
        self.assertEqual(set(report["mutants"][0]), {"id", "file", "breaks", "status", "killed_by", "tests", "sha256"})

    def test_a_killed_and_a_surviving_mutant_are_told_apart(self):
        kill = tool.Mutant("t-kill", "auditgym/matcher.py", "if nf.type != ni.type:", "if False:",
                           ("tests.test_matcher",), "type is not checked")
        live = tool.Mutant("t-live", "auditgym/matcher.py", "Shared, published matcher", "Shared, published Matcher",
                           ("tests.test_matcher",), "a docstring word")
        self.assertFalse(tool.run_mutant(kill, 120)["passed"])
        self.assertTrue(tool.run_mutant(live, 120)["passed"])
        self.assertEqual(tool.run_mutant(kill, 120)["killed_by"], "existing tests")
        self.assertEqual(tool.occurrences(kill), 1)  # the working tree itself was not touched


class RecordedRunTests(unittest.TestCase):
    def test_the_recorded_run_matches_the_current_list_and_text(self):
        path = RECORDED / "summary.json"
        if not path.is_file():
            self.skipTest("no recorded mutation run")
        stale = "runs/mutation is stale: python tools/mutation_smoke.py OUT_DIR --record"
        report = json.loads(path.read_text(encoding="utf-8"))
        rows = [(r["id"], r["file"], r["breaks"], r["tests"], r["sha256"]) for r in report["mutants"]]
        want = [(m.id, m.file, m.breaks, list(m.modules), tool.snippet_hash(m)) for m in tool.MUTANTS]
        self.assertEqual(rows, want, stale)
        self.assertEqual(report["survived"], 0)
        self.assertEqual(report["killed"], report["counted"])
        self.assertEqual(report["killed_by_existing"] + report["killed_by_survivor_tests"], report["killed"])
        # summary.md is a pure function of summary.json, byte for byte
        text = (RECORDED / "summary.md").read_bytes().decode("utf-8")
        self.assertEqual(text, tool.render_markdown(report), stale)


if __name__ == "__main__":
    unittest.main()
