"""verify DIR checks what it names; the evidence checker is independent of auditor.py and money.py, and the
auditor is independent of money.py and the generator modules."""

import ast
import copy
import json
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from auditgym import auditor, evidence_check
from auditgym.episode import load_episode
from auditgym.generator import generate_episode
from auditgym.money import convert_minor, proportional_minor
from auditgym.splits import check_set
from auditgym.timeutil import parse_ts
from auditgym.transform import transform_episode
from auditgym.verify import check_provenance_structure, check_surface, verify_generated

ROOT = Path(__file__).resolve().parent.parent
D08 = ROOT / "episodes" / "dev" / "d08_both_interacting_kzt"


def run_verify(directory: Path):
    return subprocess.run([sys.executable, "-m", "auditgym", "verify", str(directory)], cwd=str(ROOT),
                          capture_output=True, text=True, encoding="utf-8")


def verify_dir(directory: Path) -> dict:
    return verify_generated(load_episode(directory))


class DirectoryModeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name) / "ep"
        shutil.copytree(D08, self.dir)
        self.prov_path = self.dir / "grader" / "provenance.json"
        self.prov = json.loads(self.prov_path.read_text(encoding="utf-8"))

    def tearDown(self):
        self._tmp.cleanup()

    def save(self):
        self.prov_path.write_text(json.dumps(self.prov, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def test_untouched_copy_passes(self):
        r = run_verify(self.dir)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(r.stdout.count("PASS  "), 9)

    def test_deleted_op_fails_roundtrip(self):
        del self.prov["ops"][0]
        self.save()
        r = run_verify(self.dir)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FAIL  provenance_roundtrip", r.stdout)

    def test_all_ops_deleted_and_digest_zeroed_fails(self):
        # the jury's tamper test: delete every op and zero the stored digests
        self.prov["ops"] = []
        self.prov["clean_digest"] = "0" * 64
        self.prov["clean_records_digest"] = "0" * 64
        self.save()
        rep = verify_dir(self.dir)
        self.assertFalse(rep["ok"])
        self.assertNotEqual(rep["checks"]["provenance_roundtrip"], "pass")
        self.assertNotEqual(rep["checks"]["no_surface_tells"], "pass")

    def test_zeroed_clean_digest_fails(self):
        self.prov["clean_records_digest"] = "0" * 64
        self.save()
        rep = verify_dir(self.dir)
        self.assertFalse(rep["ok"])
        self.assertNotEqual(rep["checks"]["provenance_roundtrip"], "pass")

    def test_zeroed_clean_digest_fails_when_no_ops(self):
        d = Path(self._tmp.name) / "t01"
        shutil.copytree(sorted((ROOT / "episodes" / "train").glob("t01*"))[0], d)
        pp = d / "grader" / "provenance.json"
        prov = json.loads(pp.read_text(encoding="utf-8"))
        self.assertEqual(prov["ops"], [])
        self.assertTrue(verify_dir(d)["ok"])
        prov["clean_digest"] = "0" * 64
        pp.write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
        self.assertNotEqual(verify_dir(d)["checks"]["provenance_roundtrip"], "pass")

    def test_missing_clean_digest_fails(self):
        del self.prov["clean_records_digest"]
        self.save()
        rep = verify_dir(self.dir)
        self.assertFalse(rep["ok"])
        self.assertNotEqual(rep["checks"]["provenance_roundtrip"], "pass")

    def test_edited_public_amount_fails(self):
        path = self.dir / "public" / "invoices.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()
        rec = json.loads(lines[0])
        rec["total_minor"] += 1
        lines[0] = json.dumps(rec, ensure_ascii=False, separators=(",", ":"))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        rep = verify_dir(self.dir)
        self.assertFalse(rep["ok"])
        self.assertNotEqual(rep["checks"]["provenance_roundtrip"], "pass")

    def test_issue_without_ops_fails_surface(self):
        ep = load_episode(D08)
        self.assertEqual(check_surface(ep, strict=True), [])
        ep.provenance["ops"] = []
        self.assertTrue(check_surface(ep, strict=True))
        self.assertEqual(check_surface(ep, strict=False), [])  # generation mode keeps its old behaviour
        rep = verify_generated(ep)
        self.assertFalse(rep["ok"])
        self.assertNotEqual(rep["checks"]["no_surface_tells"], "pass")

    def test_issue_whose_ops_miss_its_records_fails(self):
        ep = load_episode(D08)
        ep.truth["issues"][0]["affected_ids"] = ["NOT-A-RECORD"]
        rep = verify_generated(ep)
        self.assertTrue(any("no provenance op touches" in m for m in rep["checks"]["provenance_roundtrip"]))

    def _tampered_exits_1(self, edit, message):
        edit(self.prov)
        self.save()
        r = run_verify(self.dir)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FAIL  provenance_roundtrip", r.stdout)
        self.assertIn(message, r.stdout)

    def test_unknown_injection_variant_fails(self):
        self._tampered_exits_1(lambda p: p["injections"][0].update(variant="nonsense"), "unknown variant")

    def test_unknown_injection_type_fails(self):
        self._tampered_exits_1(lambda p: p["injections"][0].update(type="nonsense"), "unknown type")

    def test_injection_target_that_does_not_exist_fails(self):
        def edit(p):
            role = next(iter(p["injections"][0]["targets"]))
            p["injections"][0]["targets"][role] = "NO-SUCH-RECORD"
        self._tampered_exits_1(edit, "is not a public")

    def test_distractor_id_that_does_not_exist_fails(self):
        self._tampered_exits_1(lambda p: p["distractors"][0]["ids"].append("NO-SUCH-RECORD"), "is not a public record")

    def test_unknown_distractor_kind_fails(self):
        self._tampered_exits_1(lambda p: p["distractors"][0].update(kind="nonsense"), "not a known kind")

    def test_truth_issue_without_matching_injection_fails(self):
        def edit(p):
            dropped = p["injections"][0]["type"]
            p["injections"] = [i for i in p["injections"] if i["type"] != dropped]
        self._tampered_exits_1(edit, "do not match truth issues")


    def test_entity_id_is_not_a_public_document(self):
        ent = load_episode(D08).invoices[0]["entity_id"]
        self._tampered_exits_1(lambda p: p["distractors"][0].update(ids=[ent]), "is not a public record")

    def test_entity_id_as_injection_target_fails(self):
        ent = load_episode(D08).invoices[0]["entity_id"]

        def edit(p):
            role = next(iter(p["injections"][0]["targets"]))
            p["injections"][0]["targets"][role] = ent
        self._tampered_exits_1(edit, "is not a public")

    def test_payment_role_needs_a_payment_id(self):
        ep = load_episode(D08)

        def edit(p):
            inj = next(i for i in p["injections"] if "payment" in i["targets"])
            inj["targets"]["payment"] = ep.invoices[0]["invoice_id"]
        self._tampered_exits_1(edit, "is not a public payment")

    def test_dropped_injection_of_the_same_type_fails(self):
        def edit(p):
            p["injections"].append(dict(p["injections"][0], issue_id="iss_99"))
        self._tampered_exits_1(edit, "do not match truth issues")

    def test_empty_targets_fail(self):
        self._tampered_exits_1(lambda p: p["injections"][0].update(targets={}), "non-empty object")

    def test_distractor_without_ids_fails(self):
        self._tampered_exits_1(lambda p: p["distractors"][0].pop("ids"), "ids must be a list")

    def test_malformed_provenance_fails_without_a_traceback(self):
        for edit in (lambda p: p.update(injections=None),
                     lambda p: p["injections"][0].update(type=["x"]),
                     lambda p: p["injections"][0].update(targets={"x": {"a": 1}}),
                     lambda p: p["distractors"].__setitem__(0, "text")):
            prov = copy.deepcopy(self.prov)
            edit(prov)
            ep = load_episode(D08)
            ep.provenance = prov
            self.assertTrue(check_provenance_structure(ep))


class TransformedEpisodeTests(unittest.TestCase):
    def test_transformed_episodes_verify_in_directory_mode(self):
        ep = load_episode(D08)
        for tf in ({"permute_seed": 3, "remap_seed": 4}, {"ts_repr": "mixed", "remap_seed": 8}, {"ts_repr": "utc"}):
            with self.subTest(tf=tf):
                t = transform_episode(ep, **tf)
                self.assertTrue(verify_generated(t)["ok"], verify_generated(t)["failures"][:2])

    def _tampered_transform_fails(self, rel, edit):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "ep"
            shutil.copytree(D08, d)
            edit(d / rel)
            self.assertNotEqual(verify_dir(d)["checks"]["provenance_roundtrip"], "pass")  # sanity: source is bad
            t = transform_episode(load_episode(d), remap_seed=4)
            self.assertFalse(verify_generated(t)["ok"])
            self.assertNotEqual(verify_generated(t)["checks"]["provenance_roundtrip"], "pass")

    def test_transform_of_tampered_payments_fails(self):
        def edit(p):
            lines = p.read_text(encoding="utf-8").splitlines()
            rec = json.loads(lines[0])
            rec["bank_ref"] = str(rec.get("bank_ref", "")) + "X"
            lines[0] = json.dumps(rec, ensure_ascii=False, separators=(",", ":"))
            p.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        self._tampered_transform_fails(Path("public") / "payments.jsonl", edit)

    def test_transform_of_tampered_fx_fails(self):
        def edit(p):
            p.write_text(p.read_text(encoding="utf-8").replace("1", "2", 1), encoding="utf-8", newline="\n")
        self._tampered_transform_fails(Path("public") / "fx.csv", edit)

    def test_transform_of_deleted_op_fails(self):
        def edit(p):
            prov = json.loads(p.read_text(encoding="utf-8"))
            del prov["ops"][0]
            p.write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
        self._tampered_transform_fails(Path("grader") / "provenance.json", edit)


class EvidenceCheckerTests(unittest.TestCase):
    def test_evidence_check_imports_nothing_from_auditor_or_money(self):
        tree = ast.parse(Path(evidence_check.__file__).read_text(encoding="utf-8"))
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported += [(0, a.name) for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                imported.append((node.level, node.module or ""))
        stdlib = {"datetime", "fractions", "__future__"}
        for level, mod in imported:
            if level == 0:
                self.assertIn(mod.split(".")[0], stdlib, f"non-stdlib import {mod}")
            else:
                self.assertIn(mod, {"timeutil", "episode"}, f"forbidden relative import .{mod}")
        names = " ".join(m for _l, m in imported)
        self.assertNotIn("auditor", names)
        self.assertNotIn("money", names)

    def test_fraction_conversion_matches_money(self):
        rng = random.Random(20251119)
        for _ in range(10000):
            amount = rng.randint(0, 10 ** rng.randint(1, 12))
            rate = format(Decimal(rng.randint(1, 10 ** 9)) / Decimal(10 ** rng.randint(0, 9)), "f")
            src, dst = rng.choice((0, 2, 3)), rng.choice((0, 2, 3))
            mode = rng.choice(("half_even", "half_up"))
            self.assertEqual(evidence_check.convert_fraction(amount, rate, src, dst, mode),
                             convert_minor(amount, rate, src, dst, mode), (amount, rate, src, dst, mode))

    def test_fraction_conversion_exact_halves(self):
        # amount 5 minor units at rate 0.5, same exponent: 2.5 exactly
        self.assertEqual(evidence_check.convert_fraction(5, "0.5", 2, 2, "half_even"), 2)
        self.assertEqual(evidence_check.convert_fraction(5, "0.5", 2, 2, "half_up"), 3)
        self.assertEqual(evidence_check.convert_fraction(7, "0.5", 2, 2, "half_even"), 4)

    def test_reduced_evidence_derives_nothing(self):
        ep = load_episode(D08)
        for issue in ep.truth["issues"]:
            es = issue["evidence_sets"][0]
            self.assertEqual(evidence_check.derive_from_evidence(issue["type"], es, ep),
                             (issue["type"], frozenset(issue["affected_ids"]), issue["expected_amount_minor"]))
            for i in range(len(es)):
                self.assertIsNone(evidence_check.derive_from_evidence(issue["type"], es[:i] + es[i + 1:], ep))

    def test_duplicate_rule_must_name_the_fields(self):
        ep = load_episode(ROOT / "episodes" / "train" / "t03_duplicate")
        issue = ep.truth["issues"][0]
        es = issue["evidence_sets"][0]
        self.assertIsNotNone(evidence_check.derive_from_evidence(issue["type"], es, ep))
        broken = copy.deepcopy(ep)
        broken.policy["duplicate_rule"] = "Invoices are duplicates when they look alike."
        self.assertIsNone(evidence_check.derive_from_evidence(issue["type"], es, broken))


class AuditorIndependenceTests(unittest.TestCase):
    def test_auditor_imports_only_the_standard_library_and_timeutil(self):
        tree = ast.parse(Path(auditor.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    self.assertIn(a.name.split(".")[0], {"re", "datetime"}, f"import {a.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    self.assertIn((node.module or "").split(".")[0], {"datetime", "__future__"}, node.module)
                else:
                    self.assertEqual(node.module, "timeutil", f"forbidden relative import .{node.module}")

    def test_integer_conversion_matches_money(self):
        rng = random.Random(20251120)
        for _ in range(10000):
            amount = rng.randint(-10 ** 6, 10 ** rng.randint(1, 12))
            rate = format(Decimal(rng.randint(1, 10 ** 9)) / Decimal(10 ** rng.randint(0, 9)), "f")
            src, dst = rng.choice((0, 2, 3)), rng.choice((0, 2, 3))
            mode = rng.choice(("half_even", "half_up"))
            self.assertEqual(auditor._convert_minor(amount, rate, src, dst, mode),
                             convert_minor(amount, rate, src, dst, mode), (amount, rate, src, dst, mode))

    def test_integer_proportion_matches_money(self):
        rng = random.Random(7)
        for _ in range(10000):
            whole = rng.randint(1, 10 ** 9)
            part, total = rng.randint(0, whole), rng.randint(-10 ** 6, 10 ** 9)
            mode = rng.choice(("half_even", "half_up"))
            self.assertEqual(auditor._proportional_minor(total, part, whole, mode),
                             proportional_minor(total, part, whole, mode), (total, part, whole, mode))

    def test_exact_halves_and_bad_input(self):
        self.assertEqual(auditor._convert_minor(5, "0.5", 2, 2, "half_even"), 2)
        self.assertEqual(auditor._convert_minor(5, "0.5", 2, 2, "half_up"), 3)
        self.assertEqual(auditor._convert_minor(-5, "0.5", 2, 2, "half_up"), -3)
        self.assertEqual(auditor._convert_minor(7, "0.5", 2, 2, "half_even"), 4)
        self.assertEqual(auditor._convert_minor(3, "2E-1", 0, 2, "half_even"), 60)
        for bad in ("", ".", "1.2.3", "abc", "1,5"):
            with self.assertRaises(ValueError):
                auditor._ratio(bad)
        with self.assertRaises(ValueError):
            auditor._convert_minor(1, "1", 2, 2, "floor")


def journals(ep) -> dict:
    """Ledger rows grouped by the published journal_grouping rule: payment_id, else invoice_id, else the instant."""
    groups = {}
    for r in ep.ledger:
        if r["payment_id"]:
            key = ("payment", r["payment_id"])
        elif r["invoice_id"]:
            key = ("invoice", r["invoice_id"])
        else:
            key = ("instant", parse_ts(r["timestamp"]))
        groups.setdefault(key, []).append(r)
    return groups


class JournalGroupingTests(unittest.TestCase):
    def assert_journals_balance(self, ep, name):
        for key, rows in journals(ep).items():
            debit, credit = sum(r["debit_minor"] for r in rows), sum(r["credit_minor"] for r in rows)
            self.assertEqual(debit, credit, f"{name}: journal {key} is out of balance")

    def test_policy_says_timestamps_are_compared_as_instants(self):
        rule = load_episode(D08).policy["journal_grouping"]
        self.assertIn("same instant", rule)
        self.assertIn("compare as instants", rule)
        self.assertIn("whatever offset", rule)

    def test_committed_episodes_balance_by_the_published_rule(self):
        dirs = sorted(p for split in ("train", "dev") for p in (ROOT / "episodes" / split).iterdir())
        self.assertEqual(len(dirs), 20)
        for d in dirs:
            self.assert_journals_balance(load_episode(d), d.name)

    def test_hidden_like_episodes_balance_by_the_published_rule(self):
        entries = check_set()
        self.assertEqual(len(entries), 20)
        for e in entries:
            ep = generate_episode(e["seed"], e["config"], verify=False).episode
            self.assertIn("same instant", ep.policy["journal_grouping"])
            self.assert_journals_balance(ep, e["name"])

    def test_literal_timestamp_strings_would_split_journals(self):
        ep = load_episode(ROOT / "episodes" / "train" / "t01_clean_small")
        literal = {}
        for r in ep.ledger:
            if not (r["payment_id"] or r["invoice_id"]):
                literal.setdefault(r["timestamp"], []).append(r)
        unbalanced = [k for k, rows in literal.items()
                      if sum(r["debit_minor"] for r in rows) != sum(r["credit_minor"] for r in rows)]
        self.assertTrue(unbalanced, "the committed data should need instant comparison")


if __name__ == "__main__":
    unittest.main()
