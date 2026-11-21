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
import time
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from auditgym import auditor, evidence_check
from auditgym.episode import load_episode
from auditgym.generator import generate_episode
from auditgym.money import convert_minor, proportional_minor
from auditgym.schemas import MAX_EVIDENCE_IDS
from auditgym.splits import check_set, load_split_episodes
from auditgym.timeutil import parse_ts
from auditgym.transform import transform_episode
from auditgym.verify import check_provenance_structure, check_surface, verify_generated

ROOT = Path(__file__).resolve().parent.parent
D08 = ROOT / "episodes" / "dev" / "d08_both_interacting_kzt"


def _dir_with(variant: str) -> Path:
    """The first committed episode directory (train, then dev) whose provenance injects the variant."""
    for split in ("train", "dev"):
        for d in sorted((ROOT / "episodes" / split).iterdir()):
            if d.is_dir() and any(i["variant"] == variant for i in
                                  json.loads((d / "grader" / "provenance.json").read_text(encoding="utf-8"))["injections"]):
                return d
    raise AssertionError(f"no committed episode injects {variant}")


def run_verify(directory: Path):
    return subprocess.run([sys.executable, "-m", "auditgym", "verify", str(directory)], cwd=str(ROOT),
                          capture_output=True, text=True, encoding="utf-8", timeout=120)


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

    def test_an_fx_rate_with_a_huge_exponent_fails_at_once_without_a_traceback(self):
        # float() reads 1e99999999 as inf and 10 ** 99999999 would never finish: verify must report, not hang
        fx = self.dir / "public" / "fx.csv"
        lines = fx.read_text(encoding="utf-8").splitlines()
        rows = [lines[0]] + [",".join(x.split(",")[:-1] + ["1e99999999"]) for x in lines[1:]]
        fx.write_text("\n".join(rows) + "\n", encoding="utf-8")
        t0 = time.monotonic()
        r = run_verify(self.dir)
        self.assertLess(time.monotonic() - t0, 60)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("FAIL  records_schema", r.stdout)
        self.assertIn("FAIL  declared_discrepancies: [\"the independent auditor cannot run: ValueError: exponent out of range",
                      r.stdout)

    def test_crafted_rates_fail_at_once_without_a_traceback(self):
        # "1e9999_9999" passes float() (inf) and would reach Fraction("1e9999_9999"); a 4299-digit rate gives amounts
        # with more than 4300 digits, which an f-string refuses to print
        fx = self.dir / "public" / "fx.csv"
        original = fx.read_text(encoding="utf-8").splitlines()
        for value in ("1e9999_9999", "9" * 4299):
            rows = [original[0]] + [",".join(x.split(",")[:-1] + [value]) for x in original[1:]]
            fx.write_text("\n".join(rows) + "\n", encoding="utf-8")
            t0 = time.monotonic()
            r = run_verify(self.dir)
            self.assertLess(time.monotonic() - t0, 60, value[:12])
            self.assertEqual(r.returncode, 1, (value[:12], r.stdout[-500:]))
            self.assertNotIn("Traceback", r.stderr, value[:12])
            self.assertIn("FAIL  records_schema", r.stdout, value[:12])

    def _drop_field(self, name, field, value="__drop__"):
        p = self.dir / "public" / name
        rows = [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if value == "__drop__":
            rows[0].pop(field)
        else:
            rows[0][field] = value
        p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    def test_an_id_that_is_a_list_or_an_object_fails_without_a_traceback(self):
        for name, field in (("payments.jsonl", "payment_id"), ("invoices.jsonl", "invoice_id"),
                            ("payments.jsonl", "doc_id"), ("invoices.jsonl", "doc_id")):
            for value in ([], {}, 5):
                with self.subTest(name=name, field=field, value=value):
                    shutil.rmtree(self.dir)
                    shutil.copytree(D08, self.dir)
                    self._drop_field(name, field, value)
                    r = run_verify(self.dir)
                    self.assertEqual(r.returncode, 1, r.stdout + r.stderr[-500:])
                    self.assertNotIn("Traceback", r.stderr)
                    self.assertIn("FAIL  records_schema", r.stdout)

    def test_a_record_without_its_id_field_fails_without_a_traceback(self):
        # check_ids and check_key_consistency (and every later check) index the ID fields of a public record
        for label, name, field in (("payment without payment_id", "payments.jsonl", "payment_id"),
                                   ("invoice without invoice_id", "invoices.jsonl", "invoice_id"),
                                   ("payment without doc_id", "payments.jsonl", "doc_id"),
                                   ("invoice without doc_id", "invoices.jsonl", "doc_id")):
            with self.subTest(label):
                shutil.rmtree(self.dir)
                shutil.copytree(D08, self.dir)
                self._drop_field(name, field)
                r = run_verify(self.dir)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr[-500:])
                self.assertNotIn("Traceback", r.stderr)
                self.assertIn("FAIL  records_schema", r.stdout)
                self.assertIn("FAIL  ids_unique", r.stdout)  # check_ids names the record that lacks its ID
                self.assertIn(f"record without {field}", r.stdout)
                self.assertGreaterEqual(r.stdout.count("FAIL  "), 3, r.stdout)

    def test_the_id_checks_themselves_tolerate_a_missing_id(self):
        from auditgym.verify import check_ids, check_key_consistency

        ep = load_episode(self.dir)
        ep.payments[0].pop("payment_id")
        ep.invoices[0].pop("invoice_id")
        ep.ledger[0].pop("row_id")
        errs = check_ids(ep)  # no KeyError
        self.assertEqual(sorted(e for e in errs if "record without" in e),
                         ["invoice record without invoice_id", "ledger record without row_id",
                          "payment record without payment_id"])
        self.assertIsInstance(check_key_consistency(ep), list)
        self.assertTrue(verify_generated(ep)["failures"])

    def test_a_ledger_row_without_a_row_id_fails_without_a_traceback(self):
        p = self.dir / "public" / "ledger.csv"
        lines = p.read_text(encoding="utf-8").splitlines()
        header = lines[0].split(",")
        col = header.index("row_id")
        cells = lines[1].split(",")
        cells[col] = ""
        lines[1] = ",".join(cells)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        r = run_verify(self.dir)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr[-500:])
        self.assertIn("FAIL  ", r.stdout)
        keep = list(lines)
        keep[0] = ",".join(h for h in header if h != "row_id")  # the whole column gone: the loader refuses it, cleanly
        keep[1:] = [",".join(c for i, c in enumerate(ln.split(",")) if i != col) for ln in lines[1:]]
        p.write_text("\n".join(keep) + "\n", encoding="utf-8")
        r = run_verify(self.dir)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr[-500:])
        self.assertTrue(r.stderr.startswith("error:"), r.stderr)

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

    def _malformed_file_fails_cleanly(self, content):
        self.prov_path.write_text(json.dumps(content), encoding="utf-8")
        r = run_verify(self.dir)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(r.stdout.count("PASS  ") + r.stdout.count("FAIL  "), 9, r.stdout)
        self.assertIn("FAIL  provenance_roundtrip", r.stdout)

    def test_provenance_that_is_a_list_fails_without_a_traceback(self):
        self._malformed_file_fails_cleanly([])

    def test_ops_that_are_not_a_list_fail_without_a_traceback(self):
        self.prov["ops"] = "x"
        self._malformed_file_fails_cleanly(self.prov)

    def test_malformed_ops_fail_without_a_traceback(self):
        for bad in ("text", {"op": "add"}, {"table": "ledger", "op": "set", "field": "x"},
                    {"table": "ledger", "op": "remove"}, {"table": "nope", "op": "remove", "id": "x"},
                    {"table": "ledger", "op": "set", "id": "NO-ROW", "field": "x", "before": 1, "after": 2}):
            with self.subTest(op=bad):
                prov = copy.deepcopy(self.prov)
                prov["ops"].append(bad)
                self._malformed_file_fails_cleanly(prov)

    def _message_for(self, prov):
        self.prov_path.write_text(json.dumps(prov), encoding="utf-8")
        self._malformed_file_fails_cleanly(prov)
        return json.dumps(verify_dir(self.dir)["checks"])

    def test_op_rules_report_their_own_message_and_skip_the_replay(self):
        row_id = load_episode(D08).ledger[0]["row_id"]
        cases = [
            ({"table": "ledger", "op": "add", "id": "GL-X"}, "add needs a record"),
            ({"table": "ledger", "op": "set", "id": row_id}, "set needs a field"),
            ({"table": ["ledger"], "op": "remove", "id": "x"}, "needs a known table"),
            ({"table": {"a": 1}, "op": "remove", "id": "x"}, "needs a known table"),
        ]
        for bad, message in cases:
            with self.subTest(op=bad):
                prov = copy.deepcopy(self.prov)
                prov["ops"].append(bad)
                text = self._message_for(prov)
                self.assertIn(message, text)
                self.assertNotIn("cannot be replayed", text)
                self.assertNotIn("cannot be reconstructed: ", text.replace("cannot be reconstructed: provenance is malformed", ""))

    def test_ops_of_a_wrong_type_name_the_rule(self):
        for bad in (5, {"a": 1}):
            with self.subTest(ops=bad):
                prov = copy.deepcopy(self.prov)
                prov["ops"] = bad
                self.assertIn("provenance.ops must be a list", self._message_for(prov))

    def test_unhashable_issue_ids_fail_without_a_traceback(self):
        for bad in (["iss_01"], {"a": 1}):
            with self.subTest(issue_id=bad):
                prov = copy.deepcopy(self.prov)
                prov["injections"][0]["issue_id"] = bad
                self._malformed_file_fails_cleanly(prov)
        # on the answer-key side the load boundary rejects it first: bad input, one error line, exit 2
        truth_path = self.dir / "grader" / "truth.json"
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        truth["issues"][0]["issue_id"] = ["iss_01"]
        truth_path.write_text(json.dumps(truth), encoding="utf-8")
        self.prov_path.write_text(json.dumps(self.prov), encoding="utf-8")
        r = run_verify(self.dir)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual([ln for ln in r.stderr.splitlines() if ln.strip()][0][:6], "error:")
        self.assertIn("truth.json", r.stderr)

    def test_injection_missing_one_of_two_targets_fails(self):
        inj = next(i for i in self.prov["injections"] if len(i["targets"]) == 2)
        del inj["targets"]["invoice"]
        self.assertIn("differ from the affected_ids", self._message_for(self.prov))

    def test_retargeted_injection_fails(self):
        target = self.prov["injections"][0]["targets"]
        role = next(iter(target))
        other = next(d["invoice_id"] for d in load_episode(D08).invoices if d["invoice_id"] != target[role])
        target[role] = other
        self.save()
        r = run_verify(self.dir)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FAIL  provenance_roundtrip", r.stdout)
        self.assertIn("differ from the affected_ids", json.dumps(verify_dir(self.dir)["checks"]))


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


class UnallocatedRecordsTests(unittest.TestCase):
    """verify reads the unallocated_payment records defensively, and the key's set is the only subset that derives."""

    def test_a_record_without_a_field_is_a_fail_line_not_a_traceback(self):
        for name, edit in (("dev/d08_both_interacting_kzt", "manifest"), ("train/t04_unallocated", "invoice")):
            with self.subTest(episode=name, edit=edit), tempfile.TemporaryDirectory() as tmp:
                d = Path(tmp) / "ep"
                shutil.copytree(ROOT / "episodes" / name, d)
                if edit == "manifest":
                    p = d / "public" / "manifest.json"
                    m = json.loads(p.read_text(encoding="utf-8"))
                    del m["base_currency"]
                    p.write_text(json.dumps(m), encoding="utf-8")
                else:
                    truth = json.loads((d / "grader" / "truth.json").read_text(encoding="utf-8"))
                    inv_id = next(t for t in truth["issues"] if t["type"] == "unallocated_payment")["affected_ids"]
                    p = d / "public" / "invoices.jsonl"
                    lines = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
                    for doc in lines:
                        if doc["invoice_id"] in inv_id:
                            del doc["currency"]
                    p.write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
                r = run_verify(d)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertNotIn("Traceback", r.stdout + r.stderr)
                self.assertIn("FAIL", r.stdout)

    def test_only_the_key_set_derives_among_the_records_of_the_issue(self):
        from itertools import combinations

        checked = 0
        for split, name in (("train", "t04_unallocated"), ("train", "t08_fx_partial_allocation"),
                            ("dev", "d04_unallocated_missing_eur"), ("dev", "d08_both_interacting_kzt"),
                            ("dev", "d09_large_mixed"), ("dev", "d10_large_dense_quarter_hour")):
            ep = load_episode(ROOT / "episodes" / split / name)
            for t in (t for t in ep.truth["issues"] if t["type"] == "unallocated_payment"):
                pay = next(i for i in t["affected_ids"] if any(p["payment_id"] == i for p in ep.payments))
                inv = next(i for i in t["affected_ids"] if i != pay)
                docs = [next(p["doc_id"] for p in ep.payments if p["payment_id"] == pay),
                        next(d["doc_id"] for d in ep.invoices if d["invoice_id"] == inv)]
                pool = sorted({r["row_id"] for r in ep.ledger if r["payment_id"] == pay or r["invoice_id"] == inv})
                self.assertLessEqual(len(pool), 14)
                want = (t["type"], frozenset(t["affected_ids"]), t["expected_amount_minor"])
                key = sorted(t["evidence_sets"][0])
                deriving = []
                for k in range(len(pool) + 1):
                    for rows in combinations(pool, k):
                        got = evidence_check.derive_from_evidence(t["type"], docs + list(rows), ep)
                        if got is not None:
                            deriving.append((sorted(docs + list(rows)), got))
                with self.subTest(episode=name, issue=t["issue_id"]):
                    self.assertEqual(deriving, [(key, want)])
                checked += 1
        self.assertGreaterEqual(checked, 9)


class RateExponentBoundTests(unittest.TestCase):
    """Both rate parsers refuse an exponent above 64 at once instead of computing 10 ** exponent."""

    def test_the_auditor_parser(self):
        self.assertEqual(auditor._ratio("0.00607246"), (607246, 100000000))
        self.assertEqual(auditor._ratio("1e64"), (10 ** 64, 1))
        self.assertEqual(auditor._ratio("1e-64"), (1, 10 ** 64))
        for bad in ("1e65", "1e-65", "1e99999999", "1e0001"):
            with self.assertRaisesRegex(ValueError, "exponent out of range"):
                auditor._ratio(bad)

    def test_the_evidence_checker_parser(self):
        from fractions import Fraction

        self.assertEqual(evidence_check._rate_fraction("0.00607246"), Fraction("0.00607246"))
        self.assertEqual(evidence_check._rate_fraction("1e64"), Fraction(10 ** 64))
        for bad in ("1e65", "1E-65", "1e99999999", "1e0001"):
            with self.assertRaisesRegex(ValueError, "exponent out of range"):
                evidence_check._rate_fraction(bad)
        # Fraction() itself reads "_" separators and non-ASCII digits: only a plain ASCII decimal may reach it
        for bad in ("1e9999_9999", "1e" + "٩" * 8, "1_000", "9" * 4299, "nan", "inf", "", "1/3", "0x10"):
            with self.assertRaises(ValueError, msg=bad[:20]):
                evidence_check._rate_fraction(bad)

    def test_the_auditor_parser_bounds_the_digits(self):
        self.assertEqual(auditor._ratio("1" * 30), (int("1" * 30), 1))
        for bad in ("1" * 31, "0." + "1" * 31, "9" * 4299):
            with self.assertRaisesRegex(ValueError, "too many digits"):
                auditor._ratio(bad)
        with self.assertRaises(ValueError):
            auditor._ratio("1e9999_9999")


class EvidenceCheckerTests(unittest.TestCase):
    def test_evidence_check_imports_nothing_from_auditor_or_money(self):
        tree = ast.parse(Path(evidence_check.__file__).read_text(encoding="utf-8"))
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported += [(0, a.name) for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                imported.append((node.level, node.module or ""))
        stdlib = {"datetime", "fractions", "re", "__future__"}
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
        """Dropping any one record from any committed acceptable set (every issue type, every train/dev episode) breaks
        the derivation; there is no exception."""
        n = 0
        for _split, _name, ep in load_split_episodes():
            for issue in ep.truth["issues"]:
                for es in issue["evidence_sets"]:
                    self.assertEqual(evidence_check.derive_from_evidence(issue["type"], es, ep),
                                     (issue["type"], frozenset(issue["affected_ids"]), issue["expected_amount_minor"]))
                    for i in range(len(es)):
                        reduced = es[:i] + es[i + 1:]
                        self.assertIsNone(evidence_check.derive_from_evidence(issue["type"], reduced, ep),
                                          (ep.manifest.get("episode_id"), issue["issue_id"], es[i]))
                        n += 1
        self.assertGreater(n, 100)

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

    def test_check_set_error_entries_use_every_timestamp_representation(self):
        # an episode written entirely in the local offset must not be clean by construction
        errors = [e for e in check_set() if not e["name"].endswith("_clean")]
        self.assertEqual({e["config"]["ts_repr"] for e in errors}, {"utc", "mixed", "local"})
        for rep in ("utc", "mixed", "local"):
            self.assertGreaterEqual(sum(e["config"]["ts_repr"] == rep for e in errors), 4)

    def test_literal_timestamp_strings_would_split_journals(self):
        unbalanced = []
        for split in ("train", "dev"):
            for d in sorted((ROOT / "episodes" / split).iterdir()):
                literal = {}
                for r in load_episode(d).ledger:
                    if not (r["payment_id"] or r["invoice_id"]):
                        literal.setdefault(r["timestamp"], []).append(r)
                unbalanced += [(d.name, k) for k, rows in literal.items()
                               if sum(r["debit_minor"] for r in rows) != sum(r["credit_minor"] for r in rows)]
        self.assertTrue(unbalanced, "the committed data should need instant comparison")


class AnswerKeyCrossChecks(unittest.TestCase):
    """verify DIR checks truth id_aliases and issue variants against the public records and the config."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name) / "ep"
        shutil.copytree(D08, self.dir)
        self.truth_path = self.dir / "grader" / "truth.json"
        self.truth = json.loads(self.truth_path.read_text(encoding="utf-8"))

    def tearDown(self):
        self._tmp.cleanup()

    def save(self):
        self.truth_path.write_text(json.dumps(self.truth, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def assert_fails_declared(self, needle):
        self.save()
        r = run_verify(self.dir)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("FAIL  declared_discrepancies", r.stdout)
        self.assertIn(needle, r.stdout)
        self.assertEqual(r.stdout.count("PASS  "), 8)

    def test_untouched_copy_exits_zero(self):
        r = run_verify(self.dir)
        self.assertEqual((r.returncode, r.stdout.count("PASS  ")), (0, 9), r.stdout)

    def test_wrong_alias_fails(self):
        a = self.truth["id_aliases"]
        k1, k2 = sorted(a)[:2]
        a[k1], a[k2] = a[k2], a[k1]
        self.assert_fails_declared("id_aliases maps")

    def test_missing_alias_fails(self):
        del self.truth["id_aliases"][sorted(self.truth["id_aliases"])[0]]
        self.assert_fails_declared("id_aliases missing")

    def test_extra_alias_fails(self):
        self.truth["id_aliases"]["D/2026/000000"] = "SI/2026/000000"
        self.assert_fails_declared("id_aliases has extra")

    def test_unknown_variant_fails(self):
        self.truth["issues"][0]["variant"] = "no_such_variant"
        self.assert_fails_declared("not a known variant")

    def test_variant_of_another_type_fails(self):
        issue = self.truth["issues"][0]
        issue["variant"] = "same_day_copy" if issue["type"] != "duplicate_invoice" else "utc_date"
        self.assert_fails_declared("not a known variant")

    def test_overflowing_amount_in_an_op_is_a_fail_line_not_a_traceback(self):
        prov_path = self.dir / "grader" / "provenance.json"
        prov = json.loads(prov_path.read_text(encoding="utf-8"))
        doc = json.loads((self.dir / "public" / "invoices.jsonl").read_text(encoding="utf-8").splitlines()[0])
        prov["ops"].insert(0, {"table": "invoices", "op": "set", "id": doc["doc_id"], "field": "total_minor",
                               "before": float("inf"), "after": doc["total_minor"]})
        prov_path.write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
        r = run_verify(self.dir)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("FAIL  provenance_roundtrip", r.stdout)
        self.assertEqual(sum(ln.startswith(("PASS  ", "FAIL  ")) for ln in r.stdout.splitlines()), 9, r.stdout)

    def test_committed_and_hidden_like_episodes_and_transforms_keep_passing(self):
        for split in ("train", "dev"):
            for d in sorted((ROOT / "episodes" / split).iterdir()):
                ep = load_episode(d)
                for tf in ({}, {"permute_seed": 3}, {"remap_seed": 4}, {"ts_repr": "utc"}, {"rename_seed": 5}):
                    with self.subTest(episode=d.name, transform=tf):
                        self.assertTrue(verify_generated(transform_episode(ep, **tf) if tf else ep)["ok"])


T08 = ROOT / "episodes" / "train" / "t08_fx_partial_allocation"
D05 = ROOT / "episodes" / "dev" / "d05_fx_utc_stale_mixed_ts"
T05 = ROOT / "episodes" / "train" / "t05_fx_rate"
T04 = ROOT / "episodes" / "train" / "t04_unallocated"


def _alloc_is_pinned(src: Path, inj: dict) -> bool:
    """change.alloc is pinned by the ledger only for a base-currency payment: in a foreign currency one more document unit
    can convert to the same base amount (verify.py docstring)."""
    pol = json.loads((src / "public" / "policy.json").read_text(encoding="utf-8"))
    pays = {json.loads(ln)["payment_id"]: json.loads(ln) for ln in (src / "public" / "payments.jsonl").read_text(encoding="utf-8").splitlines()}
    return pays[inj["targets"]["payment"]]["currency"] == pol["base_currency"]


def _dir_with_pinned_partial() -> Path:
    """The first committed episode (train, then dev) with a partial unallocated_payment whose payment is in the base currency."""
    for split in ("train", "dev"):
        for d in sorted((ROOT / "episodes" / split).iterdir()):
            if d.is_dir():
                for inj in json.loads((d / "grader" / "provenance.json").read_text(encoding="utf-8"))["injections"]:
                    if inj["type"] == "unallocated_payment" and inj["variant"] == "partial" and _alloc_is_pinned(d, inj):
                        return d
    raise AssertionError("no committed partial unallocated_payment in the base currency")


def _shifted(key, value):
    """A plausible but wrong value for one change key."""
    if value is None:
        return "2026-01-02"
    if isinstance(value, int):
        return value + 1
    if key == "posting_ts":
        return (parse_ts(value) + timedelta(minutes=1)).isoformat()
    if key.endswith("_date"):
        return (date.fromisoformat(value) + timedelta(days=1)).isoformat()
    return value + "1"  # a rate with one more digit


class ChangeRecordTests(unittest.TestCase):
    """provenance.injections[].change is checked against fx.csv, the ledger and the ops (check provenance_roundtrip)."""

    def copy(self, src: Path) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dst = Path(tmp.name) / "ep"
        shutil.copytree(src, dst)
        return dst

    def edit_provenance(self, directory: Path, edit):
        path = directory / "grader" / "provenance.json"
        prov = json.loads(path.read_text(encoding="utf-8"))
        edit(prov)
        path.write_text(json.dumps(prov, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def assert_rejected(self, directory: Path, check: str, needle: str = ""):
        r = run_verify(directory)
        self.assertNotIn("Traceback", r.stderr, r.stderr)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(f"FAIL  {check}", r.stdout)
        self.assertIn(needle, r.stdout)
        self.assertEqual(sum(ln.startswith(("PASS  ", "FAIL  ")) for ln in r.stdout.splitlines()), 9, r.stdout)

    def test_untouched_copies_exit_zero(self):
        for src in (D08, T08):
            r = run_verify(self.copy(src))
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertEqual(r.stdout.count("PASS  "), 9)

    def test_every_tampered_change_key_fails(self):
        seen = set()
        for src in dict.fromkeys((D08, T08, D05, T05, T04, _dir_with_pinned_partial(), *(_dir_with(v) for v in ("transposed", "stale_rate", "posting_date", "utc_date")))):
            injections = json.loads((src / "grader" / "provenance.json").read_text(encoding="utf-8"))["injections"]
            for n, inj in enumerate(injections):
                for key in inj["change"]:
                    if key == "alloc" and not _alloc_is_pinned(src, inj):
                        continue
                    seen.add((inj["type"], inj["variant"], key))
                    with self.subTest(episode=src.name, issue=inj["issue_id"], key=key):
                        d = self.copy(src)
                        self.edit_provenance(d, lambda p, n=n, key=key: p["injections"][n]["change"].__setitem__(
                            key, _shifted(key, p["injections"][n]["change"][key])))
                        self.assert_rejected(d, "provenance_roundtrip", "injection iss_")
        self.assertTrue({("wrong_fx_rate", "utc_date", "wrong_rate_date"), ("wrong_fx_rate", "transposed", "correct_rate"),
                         ("wrong_fx_rate", "posting_date", "posting_ts"), ("wrong_period", "utc_wall_clock", "posting_ts"),
                         ("unallocated_payment", "partial", "alloc"), ("wrong_fx_rate", "stale_rate", "wrong_rate_date")} <= seen)

    def test_missing_unknown_and_malformed_change_fail(self):
        injections = json.loads((D08 / "grader" / "provenance.json").read_text(encoding="utf-8"))["injections"]
        fx = next(n for n, i in enumerate(injections) if i["type"] == "wrong_fx_rate" and "invoice" in i["targets"])
        cases = {
            "lacks": lambda p: p["injections"][fx]["change"].pop("wrong_rate"),
            "unknown key": lambda p: p["injections"][fx]["change"].__setitem__("note", 1),
            "not an object": lambda p: p["injections"][fx].__setitem__("change", [1, 2]),
            "emptied": lambda p: p["injections"][fx].__setitem__("change", {}),
            "null rate": lambda p: p["injections"][fx]["change"].__setitem__("wrong_rate", None),
            "bool alloc": lambda p: next(i for i in p["injections"] if i["type"] == "unallocated_payment")["change"].__setitem__("alloc", True),
        }
        for label, edit in cases.items():
            with self.subTest(label):
                d = self.copy(D08)
                self.edit_provenance(d, edit)
                self.assert_rejected(d, "provenance_roundtrip", "injection iss_")

    def test_rule_by_rule_tampers_fail(self):
        d04 = ROOT / "episodes" / "dev" / "d04_unallocated_missing_eur"
        t04 = _dir_with_pinned_partial()
        d10 = _dir_with("transposed")  # a committed episode with a transposed rate (it has a second valid transposition)
        by_id = lambda p, i: next(x for x in p["injections"] if x["issue_id"] == i)

        def transposed(p):
            return next(x for x in p["injections"] if x["variant"] == "transposed")["change"]

        def another_transposition(rate, recorded):
            """A rate that is also a valid transposition of `rate` (two adjacent digits swapped, at least 0.2 % apart)
            but not the recorded one: the rule accepts its shape, only the ledger amount tells it from the recorded one."""
            digits = [i for i, ch in enumerate(rate) if ch.isdigit()]
            for a, c in zip(digits, digits[1:]):
                if c != a + 1 or rate[a] == rate[c]:
                    continue
                cand = list(rate)
                cand[a], cand[c] = cand[c], cand[a]
                cand = "".join(cand)
                if cand != recorded and not (cand.startswith("0") and not cand.startswith("0.")) and abs(Decimal(cand) - Decimal(rate)) >= Decimal(rate) * Decimal("0.002"):
                    return cand
            raise AssertionError(f"no other transposition of {rate}")

        def set_rate(rate_of):
            def edit(p):
                ch = transposed(p)
                ch["wrong_rate"] = rate_of(ch)
            return edit

        def lower_alloc(p):
            ch = next(x for x in p["injections"] if x["type"] == "unallocated_payment" and x["variant"] == "partial")["change"]
            ch["alloc"] -= 1

        cases = [
            (d10, "another transposition of the rate", set_rate(lambda ch: another_transposition(ch["correct_rate"], ch["wrong_rate"]))),
            (d10, "a transposition with a trailing zero", set_rate(lambda ch: ch["wrong_rate"] + "0")),
            (d10, "exponent rate", set_rate(lambda ch: "1e99999999")),
            (d10, "signed rate", set_rate(lambda ch: "+" + ch["wrong_rate"])),
            (d04, "alloc is a bool", lambda p: by_id(p, "iss_01")["change"].__setitem__("alloc", False)),
            (d04, "variant swapped to partial", lambda p: by_id(p, "iss_01").__setitem__("variant", "partial")),
            (t04, "alloc one unit lower (2900 rule)", lower_alloc),  # a base-currency receipt: one unit is visible in the ledger
        ]
        for src, label, edit in cases:
            with self.subTest(label):
                d = self.copy(src)
                self.edit_provenance(d, edit)
                self.assert_rejected(d, "provenance_roundtrip", "2900 holds" if "2900" in label else "injection iss_")

    def test_a_change_on_a_known_type_with_an_extra_key_fails_for_duplicates_too(self):
        d = self.copy(next(p for p in (ROOT / "episodes" / "train").iterdir() if p.name.startswith("t03")))
        self.edit_provenance(d, lambda p: p["injections"][0]["change"].__setitem__("alloc", 0))
        self.assert_rejected(d, "provenance_roundtrip", "unknown key")


class SoleReceiptTests(unittest.TestCase):
    """unallocated_payment: no second receipt and no second relieving row for the invoice (check evidence_sufficient)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name) / "ep"
        shutil.copytree(D08, self.dir)
        self.ep = load_episode(self.dir)
        issue = next(t for t in self.ep.truth["issues"] if t["type"] == "unallocated_payment")
        self.pay = next(d for d in self.ep.payments if d["payment_id"] in issue["affected_ids"])
        self.inv = next(d for d in self.ep.invoices if d["invoice_id"] in issue["affected_ids"])

    def save_and_reject(self, needle: str):
        self.ep.manifest["record_counts"] = {t: len(self.ep.table(t)) for t in ("ledger", "invoices", "payments", "fx")}
        self.ep.write(self.dir)
        r = run_verify(self.dir)
        self.assertNotIn("Traceback", r.stderr, r.stderr)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FAIL  evidence_sufficient", r.stdout)
        self.assertIn(needle, r.stdout)
        self.assertEqual(sum(ln.startswith(("PASS  ", "FAIL  ")) for ln in r.stdout.splitlines()), 9, r.stdout)

    def test_untouched_copy_exits_zero(self):
        r = run_verify(self.dir)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(r.stdout.count("PASS  "), 9)

    def test_second_receipt_referencing_the_invoice_fails(self):
        other = copy.deepcopy(self.pay)
        other.update({"doc_id": "D-ZZ-1", "payment_id": "RCPT-ZZ-1"})
        self.ep.payments.append(other)
        self.save_and_reject("also lists invoice")

    def test_second_receipt_document_with_the_same_payment_id_fails(self):
        other = copy.deepcopy(self.pay)
        other.update({"doc_id": "D-ZZ-1"})
        self.ep.payments.append(other)
        self.save_and_reject("2 payment and 1 invoice documents carry the affected IDs")

    def test_second_receipt_in_a_list_of_invoices_fails(self):
        other = copy.deepcopy(self.pay)
        other.update({"doc_id": "D-ZZ-1", "payment_id": "RCPT-ZZ-1", "invoice_refs": ["INV-OTHER", self.inv["invoice_id"]]})
        self.ep.payments.append(other)
        self.save_and_reject("also lists invoice")

    def test_second_relieving_row_without_a_payment_fails(self):
        row = copy.deepcopy(next(r for r in self.ep.ledger if r["account"] == "1000"))
        row.update({"row_id": "ROW-ZZ-1", "account": "1100", "debit_minor": 0, "credit_minor": 5,
                    "invoice_id": self.inv["invoice_id"], "payment_id": None})
        self.ep.ledger.append(row)
        self.save_and_reject("relieves invoice")

    def test_second_relieving_row_of_another_payment_fails(self):
        other = next(d for d in self.ep.payments if d["payment_id"] != self.pay["payment_id"])
        row = copy.deepcopy(next(r for r in self.ep.ledger if r["account"] == "1000"))
        row.update({"row_id": "ROW-ZZ-1", "account": "1100", "debit_minor": 0, "credit_minor": 5,
                    "invoice_id": self.inv["invoice_id"], "payment_id": other["payment_id"]})
        self.ep.ledger.append(row)
        self.save_and_reject("relieves invoice")

    def test_the_issue_payments_own_relief_and_the_invoice_booking_are_allowed(self):
        rows = [r for r in self.ep.ledger if r["invoice_id"] == self.inv["invoice_id"]]
        self.assertTrue(any(r["payment_id"] == self.pay["payment_id"] and r["credit_minor"] > 0 for r in rows))
        self.assertTrue(any(r["payment_id"] is None and r["debit_minor"] > 0 for r in rows))
        self.assertEqual(verify_generated(self.ep)["checks"]["evidence_sufficient"], "pass")


def _issue_parts(ep, issue):
    pay = next(d for d in ep.payments if d["payment_id"] in issue["affected_ids"])
    inv = next(d for d in ep.invoices if d["invoice_id"] in issue["affected_ids"])
    return pay, inv


def _plain_partial_base():
    """(episode, issue) of a committed unallocated_payment in the base currency with a relief row whose invoice has no other
    payment: the plain story the balance tests below edit row by row (a part-paid invoice has a second relief on it)."""
    for _s, _n, ep in load_split_episodes():
        refs = {}
        for p in ep.payments:
            for r in p["invoice_refs"] or []:
                refs.setdefault(r, []).append(p["payment_id"])
        for t in ep.truth["issues"]:
            if t["type"] != "unallocated_payment":
                continue
            pay, inv = _issue_parts(ep, t)
            relieved = any(r["payment_id"] == pay["payment_id"] and r["account"] == "1100" for r in ep.ledger)
            if inv["currency"] == ep.policy["base_currency"] and relieved and len(refs[inv["invoice_id"]]) == 1:
                return ep, t
    raise AssertionError("no plain base-currency unallocated_payment with a relief among the committed episodes")


class UnallocatedEvidenceSetTests(unittest.TestCase):
    """The one acceptable set of an unallocated_payment issue: both documents, the payment's 2900 row and every
    receivable row that carries the invoice ID, so the cited records alone show that the invoice was open."""

    @classmethod
    def setUpClass(cls):
        cls.episodes = [ep for _s, _n, ep in load_split_episodes() if any(
            t["type"] == "unallocated_payment" for t in ep.truth["issues"])]

    def issues(self):
        for ep in self.episodes:
            for t in ep.truth["issues"]:
                if t["type"] == "unallocated_payment":
                    yield ep, t

    def test_the_key_holds_one_set_of_documents_2900_row_and_every_receivable_row(self):
        n = 0
        for ep, t in self.issues():
            pay, inv = _issue_parts(ep, t)
            rows = [r["row_id"] for r in ep.ledger if r["account"] == "2900" and r["payment_id"] == pay["payment_id"]]
            rows += [r["row_id"] for r in ep.ledger if r["account"] == "1100" and r["invoice_id"] == inv["invoice_id"]]
            if inv["currency"] != ep.policy["base_currency"]:  # the whole receipt at the payment-date rate
                rows += [r["row_id"] for r in ep.ledger if r["account"] == "1000" and r["payment_id"] == pay["payment_id"]]
            self.assertEqual(len(t["evidence_sets"]), 1)
            self.assertEqual(sorted(t["evidence_sets"][0]), sorted([pay["doc_id"], inv["doc_id"]] + rows))
            self.assertGreaterEqual(len(rows), 2)
            n += 1
        self.assertGreaterEqual(n, 6)

    def test_the_largest_generated_set_fits_the_evidence_cap(self):
        biggest = 0
        configs = [{"size": "large", "errors": {"unallocated_payment": 3}},
                   {"size": "medium", "errors": {"unallocated_payment": 2}, "interacting": ["fx_invoice_partial_allocation"]},
                   {"size": "small", "errors": {"unallocated_payment": 1}, "variants": {"unallocated_payment": ["partial"]}}]
        for k, cfg in enumerate(configs):
            ep = generate_episode(700 + k, cfg).episode
            for t in ep.truth["issues"]:
                if t["type"] == "unallocated_payment":
                    biggest = max(biggest, len(t["evidence_sets"][0]))
        for _ep, t in self.issues():
            biggest = max(biggest, len(t["evidence_sets"][0]))
        # 2 documents + the 2900 row + the invoice's posting (or opening) row + this receipt's relief row + the relief row of an
        # earlier part payment + the receipt's bank row for a foreign-currency invoice
        self.assertEqual(biggest, 7)
        self.assertLessEqual(biggest, MAX_EVIDENCE_IDS)

    def test_the_open_balance_comes_from_the_rows_not_from_the_invoice_total(self):
        ep, t = _plain_partial_base()
        es = t["evidence_sets"][0]
        pay, inv = _issue_parts(ep, t)
        before, after = evidence_check.unallocated_open_balance(es, ep)
        posting = next(r for r in ep.ledger if r["row_id"] in es and r["account"] == "1100" and r["debit_minor"] > 0)
        relief = next(r for r in ep.ledger if r["row_id"] in es and r["account"] == "1100" and r["credit_minor"] > 0)
        self.assertEqual((before, after), (posting["debit_minor"], posting["debit_minor"] - relief["credit_minor"]))
        inv["total_minor"] += 1000  # the document total does not enter the balance
        self.assertEqual(evidence_check.unallocated_open_balance(es, ep), (before, after))

    def test_a_receipt_story_with_a_foreign_relief_or_a_bad_balance_derives_nothing(self):
        ep, t = _plain_partial_base()
        es = t["evidence_sets"][0]
        pay, inv = _issue_parts(ep, t)

        def derive(evidence):
            return evidence_check.derive_from_evidence("unallocated_payment", evidence, ep)

        self.assertIsNotNone(derive(es))
        other_pay = next(d for d in ep.payments if d["payment_id"] != pay["payment_id"])
        posting = next(r for r in ep.ledger if r["row_id"] in es and r["account"] == "1100" and r["debit_minor"] > 0)
        relief = next(r for r in ep.ledger if r["row_id"] in es and r["account"] == "1100" and r["credit_minor"] > 0)
        own = relief["credit_minor"]
        relief["payment_id"] = other_pay["payment_id"]
        self.assertIsNone(derive(es))  # relieved by another receipt: the invoice may have been settled there
        relief["payment_id"] = pay["payment_id"]
        relief["credit_minor"] = posting["debit_minor"]
        self.assertIsNone(derive(es))  # nothing left open
        relief["credit_minor"] = own - 1
        self.assertIsNone(derive(es))  # base currency: the receipt is its relief plus the 2900 amount
        relief["credit_minor"] = own
        self.assertIsNotNone(derive(es))
        self.assertIsNone(derive(es + [es[0]]))  # a repeated ID

    def test_a_base_currency_balance_on_the_rows_must_cover_the_receipt(self):
        ep, t = _plain_partial_base()
        es = t["evidence_sets"][0]
        pay, inv = _issue_parts(ep, t)
        self.assertEqual(inv["currency"], ep.policy["base_currency"])
        derive = lambda: evidence_check.derive_from_evidence("unallocated_payment", es, ep)  # noqa: E731
        self.assertIsNotNone(derive())
        posting = next(r for r in ep.ledger if r["row_id"] in es and r["account"] == "1100" and r["debit_minor"] > 0)
        own = posting["debit_minor"]
        # the invoice document still says it covers the receipt, the cited posting no longer does
        posting["debit_minor"] = pay["amount_minor"] - 1
        self.assertGreater(inv["total_minor"], posting["debit_minor"])
        self.assertIsNone(derive())
        posting["debit_minor"] = pay["amount_minor"]
        self.assertIsNotNone(derive())
        posting["debit_minor"] = own

    def test_a_foreign_currency_story_needs_the_bank_row_to_split_the_receipt(self):
        ep = load_episode(D08)
        t = next(t for t in ep.truth["issues"] if t["type"] == "unallocated_payment")
        es = t["evidence_sets"][0]
        pay, inv = _issue_parts(ep, t)
        derive = lambda e: evidence_check.derive_from_evidence("unallocated_payment", e, ep)  # noqa: E731
        bank = next(r for r in ep.ledger if r["row_id"] in es and r["account"] == "1000")
        self.assertIsNotNone(derive(es))
        self.assertIsNone(derive([e for e in es if e != bank["row_id"]]))
        own = bank["debit_minor"]
        unalloc = next(r for r in ep.ledger if r["row_id"] in es and r["account"] == "2900")
        bank["debit_minor"] = unalloc["credit_minor"]  # a relief was booked, so 2900 must be less than the bank amount
        self.assertIsNone(derive(es))
        bank["debit_minor"] = own
        self.assertIsNotNone(derive(es))
        other = next(r for r in ep.ledger if r["account"] == "1000" and r["payment_id"] != pay["payment_id"])
        self.assertIsNone(derive([e for e in es if e != bank["row_id"]] + [other["row_id"]]))  # another payment's bank row

    def test_a_foreign_currency_story_needs_an_open_balance_and_a_relief_the_receipt_paid_for(self):
        ep = load_episode(D08)
        t = next(t for t in ep.truth["issues"] if t["type"] == "unallocated_payment")
        es = t["evidence_sets"][0]
        pay, inv = _issue_parts(ep, t)
        self.assertNotEqual(inv["currency"], ep.policy["base_currency"])
        derive = lambda: evidence_check.derive_from_evidence("unallocated_payment", es, ep)  # noqa: E731
        self.assertIsNotNone(derive())
        posting = next(r for r in ep.ledger if r["row_id"] in es and r["account"] == "1100" and r["debit_minor"] > 0)
        relief = next(r for r in ep.ledger if r["row_id"] in es and r["account"] == "1100" and r["credit_minor"] > 0)
        own = relief["credit_minor"]
        own_amount = pay["amount_minor"]
        pay["amount_minor"] = inv["total_minor"]  # the receipt pays for the whole invoice: the relief bound cannot be what rejects
        self.assertIsNotNone(derive())
        relief["credit_minor"] = posting["debit_minor"]
        self.assertIsNone(derive())  # the relief takes the whole balance: nothing is left for the 2900 amount
        relief["credit_minor"] = own
        pay["amount_minor"] = own_amount
        self.assertIsNotNone(derive())
        pay["amount_minor"] = 1
        self.assertIsNone(derive())  # the relief is more than the receipt can have paid for

    def test_a_set_without_every_receivable_row_fails_verify(self):
        ep, t = next(self.issues())
        ep = copy.deepcopy(ep)
        t = next(t for t in ep.truth["issues"] if t["type"] == "unallocated_payment")
        pay, inv = _issue_parts(ep, t)
        dropped = next(r["row_id"] for r in ep.ledger if r["invoice_id"] == inv["invoice_id"] and r["account"] == "1100"
                       and r["row_id"] in t["evidence_sets"][0])
        t["evidence_sets"][0].remove(dropped)
        rep = verify_generated(ep)
        self.assertTrue(any("lacks the 1100 rows" in f for f in rep["failures"]), rep["failures"])
        self.assertNotEqual(rep["checks"]["declared_discrepancies"], "pass")

    def test_a_foreign_currency_set_without_the_bank_row_fails_verify(self):
        ep = copy.deepcopy(load_episode(D08))
        t = next(t for t in ep.truth["issues"] if t["type"] == "unallocated_payment")
        es = t["evidence_sets"][0]
        bank = next(r["row_id"] for r in ep.ledger if r["row_id"] in es and r["account"] == "1000")
        es.remove(bank)
        rep = verify_generated(ep)
        self.assertTrue(any("lacks the payment's bank (1000) row" in f for f in rep["failures"]), rep["failures"])


if __name__ == "__main__":
    unittest.main()
