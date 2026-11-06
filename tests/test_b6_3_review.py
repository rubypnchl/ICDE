"""B6.3 synthetic fixtures. These are workflow tests, NOT independent human review."""
from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
SCRIPT = BASE / "scripts/run_b6_3_review.py"
spec = importlib.util.spec_from_file_location("b63", SCRIPT)
b63 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b63)

FWD = [1222, 1303, 1749, 2073, 2560, 3066, 3453, 5472, 5490, 5496, 5510,
       5554, 5640, 6092, 6914, 6961, 7489, 7869]
REV = [1438, 2750, 4045, 4685, 5537, 5942, 6479, 8507, 9016]


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "data/evaluation").mkdir(parents=True)
        shutil.copy(BASE / b63.POLICY, self.root / b63.POLICY)
        cat = {
            "protocol_id": "b6-frozen-protocol-v1",
            "entries": [
                {"id": "B6-MAN-001", "domain": "manufacturing", "status": "provisional_source_supported",
                 "scoring_eligible": False, "evidence": [{"url": "https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset"}]},
                {"id": "B6-CYB-001", "domain": "cybersecurity", "status": "provisional_source_supported",
                 "scoring_eligible": False, "evidence": [{"url": "https://github.com/ahlashkari/CICFlowMeter/blob/master/ReadMe.txt"},
                                                        {"url": "https://github.com/ahlashkari/CICFlowMeter/blob/master/src/main/java/cic/cs/unb/ca/jnetpcap/BasicFlow.java"}]}
            ]
        }
        pro = {"protocol_id": "b6-frozen-protocol-v1"}
        self.writejson(b63.CAT, cat)
        self.writejson(b63.PRO, pro)
        r61 = {"catalogue_sha256": b63.filehash(self.root / b63.CAT),
               "protocol_sha256": b63.filehash(self.root / b63.PRO),
               "results": [
                   {"domain": "manufacturing", "source_sha256": b63.EXPECTED_MAN_SHA},
                   {"domain": "cybersecurity", "source_sha256": b63.EXPECTED_CYB_SHA}]
               }
        self.writejson(b63.B61, r61)
        r62 = {"B6_1_report_sha256": b63.filehash(self.root / b63.B61),
               "reviewer_count_completed": 0, "final_gold_reference_rules": 0,
               "real_natural_defect_gold_labels": 0,
               "manufacturing_discrepancy_review": {"worksheets_generated": 27},
               "domains": [
                   {"domain": "manufacturing", "source_sha256": b63.EXPECTED_MAN_SHA},
                   {"domain": "cybersecurity", "source_sha256": b63.EXPECTED_CYB_SHA}]}
        self.writejson(b63.B62, r62)
        rows = []
        for uid in sorted(FWD + REV):
            forward = uid in FWD
            record = {"reference_id": "B6-MAN-001", "source_sha256": b63.EXPECTED_MAN_SHA,
                      "UDI": str(uid),
                      "case": "forward_frozen_rule_violation" if forward else "reverse_exploratory_only_not_frozen_rule",
                      "active_modes": "RNF" if forward else "",
                      **{m: "0" for m in ("TWF", "HDF", "PWF", "OSF")},
                      "RNF": "1" if forward else "0", "Machine failure": "0" if forward else "1",
                      **{k: "" for k in ["reviewer_1_id", "reviewer_1_decision", "reviewer_1_evidence",
                                         "reviewer_2_id", "reviewer_2_decision", "reviewer_2_evidence",
                                         "adjudicator", "adjudicated_decision", "notes"]}}
            rows.append(record)
        path = self.root / b63.BASE_CASES
        b63.write_csv(path, list(rows[0]), rows)

    def writejson(self, rel, data):
        dest = self.root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def rows(self, r, p):
        return b63.read_csv(self.root / b63.OUT / f"reviewer_{r}_{p}.csv")

    def replace_rows(self, r, p, rows):
        dst = self.root / b63.OUT / f"reviewer_{r}_{p}.csv"
        b63.write_csv(dst, list(rows[0]), rows)

    @staticmethod
    def vote(rows, who, choice):
        rows[0].update({"reviewer_id": who, "decision": choice,
                        "evidence_url": "https://example.org/official-paper",
                        "evidence_locator": "Section 3, paragraph 2",
                        "rationale": "Source and record context reviewed; unresolved until adjudicated."})

    def test_preflight_honours_frozen_counts(self):
        p, cases, rules, hashes = b63.load(self.root)
        self.assertEqual((len(cases), len(rules), len(hashes)), (27, 2, 6))
        self.assertEqual(sum(x["case"].startswith("forward") for x in cases), 18)

    def test_prepare_two_independent_blank_packs(self):
        result = b63.prepare(self.root)
        self.assertEqual(result["case_rows"], 27)
        for r in (1, 2):
            self.assertEqual(len(self.rows(r, "cases")), 27)
            self.assertEqual(len(self.rows(r, "rules")), 2)
            self.assertTrue(all(row["decision"] == "" for row in self.rows(r, "cases")))
        manifest = b63.obj(self.root / b63.OUT / "review_manifest.json")
        self.assertFalse(manifest["two_independent_reviews_completed"])
        self.assertEqual(manifest["independent_gold_rule_count"], 0)

    def test_audit_blank_cannot_infer_gold(self):
        b63.prepare(self.root)
        report = b63.audit(self.root)
        self.assertEqual(report["cases"]["both_completed"], 0)
        self.assertEqual(report["source_rules"]["both_completed"], 0)
        self.assertEqual(report["independently_adjudicated_gold_rules"], 0)
        self.assertFalse(report["eligible_for_final_gold_scoring"])

    def test_prepare_refuses_overwrite(self):
        b63.prepare(self.root)
        with self.assertRaisesRegex(b63.ReviewError, "overwrite"):
            b63.prepare(self.root)

    def test_original_has_nonblank_vote_rejected(self):
        rows = b63.read_csv(self.root / b63.BASE_CASES)
        rows[0]["reviewer_1_decision"] = "supported_discrepancy"
        b63.write_csv(self.root / b63.BASE_CASES, list(rows[0]), rows)
        with self.assertRaisesRegex(b63.ReviewError, "human reviews filled"):
            b63.load(self.root)

    def test_original_udi_duplicate_rejected(self):
        rows = b63.read_csv(self.root / b63.BASE_CASES)
        rows[1]["UDI"] = rows[0]["UDI"]
        b63.write_csv(self.root / b63.BASE_CASES, list(rows[0]), rows)
        with self.assertRaisesRegex(b63.ReviewError, "duplicate UDI|reordered"):
            b63.load(self.root)

    def test_original_tampered_case_rejected(self):
        rows = b63.read_csv(self.root / b63.BASE_CASES)
        rows[0]["RNF"] = "0"
        b63.write_csv(self.root / b63.BASE_CASES, list(rows[0]), rows)
        with self.assertRaisesRegex(b63.ReviewError, "pattern mismatch"):
            b63.load(self.root)

    def test_missing_second_review_file_refused(self):
        b63.prepare(self.root)
        (self.root / b63.OUT / "reviewer_2_rules.csv").unlink()
        with self.assertRaisesRegex(b63.ReviewError, "Missing CSV"):
            b63.audit(self.root)

    def test_partial_vote_refused(self):
        b63.prepare(self.root)
        rows = self.rows(1, "cases")
        rows[0]["decision"] = "ambiguous"
        self.replace_rows(1, "cases", rows)
        with self.assertRaisesRegex(b63.ReviewError, "Partially filled"):
            b63.audit(self.root)

    def test_invalid_decision_refused(self):
        b63.prepare(self.root)
        rows = self.rows(1, "cases")
        self.vote(rows, "Reviewer-01", "confirmed_gold_defect")
        self.replace_rows(1, "cases", rows)
        with self.assertRaisesRegex(b63.ReviewError, "Unsupported human decision"):
            b63.audit(self.root)

    def test_same_reviewer_id_refused(self):
        b63.prepare(self.root)
        for index in (1, 2):
            rows = self.rows(index, "cases")
            self.vote(rows, "SAME_PERSON", "ambiguous")
            self.replace_rows(index, "cases", rows)
        with self.assertRaisesRegex(b63.ReviewError, "different IDs"):
            b63.audit(self.root)

    def test_disagreements_reported_not_gold(self):
        b63.prepare(self.root)
        for idx, choice in ((1, "supported_discrepancy"), (2, "ambiguous")):
            rows = self.rows(idx, "cases")
            self.vote(rows, f"Reviewer-{idx}", choice)
            self.replace_rows(idx, "cases", rows)
        result = b63.audit(self.root)
        self.assertEqual(result["cases"]["both_completed"], 1)
        self.assertEqual(result["cases"]["disagreed"], 1)
        self.assertEqual(result["confirmed_natural_defects"], 0)

    def test_agreements_not_automatically_gold(self):
        b63.prepare(self.root)
        for idx in (1, 2):
            cases = self.rows(idx, "cases")
            rules = self.rows(idx, "rules")
            self.vote(cases, f"Reviewer-{idx}", "supported_discrepancy")
            self.vote(rules, f"Reviewer-{idx}", "supports_as_written")
            self.replace_rows(idx, "cases", cases)
            self.replace_rows(idx, "rules", rules)
        result = b63.audit(self.root)
        self.assertEqual(result["cases"]["agreed"], 1)
        self.assertEqual(result["source_rules"]["agreed"], 1)
        self.assertEqual(result["independently_adjudicated_gold_rules"], 0)

    def test_changed_rule_header_rejected(self):
        b63.prepare(self.root)
        dest = self.root / b63.OUT / "reviewer_1_rules.csv"
        rows = self.rows(1, "rules")
        cols = list(rows[0]); cols[0] = "wrong_field"
        with dest.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            for row in rows:
                w.writerow(list(row.values()))
        with self.assertRaisesRegex(b63.ReviewError, "header/order"):
            b63.audit(self.root)

    def test_changed_source_worksheet_after_prepare_refused(self):
        b63.prepare(self.root)
        path = self.root / b63.BASE_CASES
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(b63.ReviewError, "changed since review preparation|Malformed CSV record"):
            b63.audit(self.root)

    def test_mismatched_B62_report_hash_refused(self):
        report = b63.obj(self.root / b63.B62)
        report["B6_1_report_sha256"] = "0" * 64
        self.writejson(b63.B62, report)
        with self.assertRaisesRegex(b63.ReviewError, "hashes changed"):
            b63.load(self.root)

    def test_source_urls_change_is_refused(self):
        data = b63.obj(self.root / b63.CAT)
        data["entries"][0]["evidence"][0]["url"] = "https://example.org/other"
        self.writejson(b63.CAT, data)
        report = b63.obj(self.root / b63.B61)
        report["catalogue_sha256"] = b63.filehash(self.root / b63.CAT)
        self.writejson(b63.B61, report)
        b62 = b63.obj(self.root / b63.B62)
        b62["B6_1_report_sha256"] = b63.filehash(self.root / b63.B61)
        self.writejson(b63.B62, b62)
        with self.assertRaisesRegex(b63.ReviewError, "source URLs"):
            b63.load(self.root)

    def test_source_files_stay_untouched(self):
        initial = b63.filehash(self.root / b63.BASE_CASES)
        b63.prepare(self.root)
        b63.audit(self.root)
        self.assertEqual(initial, b63.filehash(self.root / b63.BASE_CASES))


if __name__ == "__main__":
    unittest.main()
