"""B6.1 offline tests with synthetic CSV fixtures ONLY; no real-data claim."""
from __future__ import annotations

import copy
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts/run_b6_1_real_baselines.py"
spec = importlib.util.spec_from_file_location("run_b6_1_real_baselines", FILE)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class B61Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        cat = json.loads((ROOT / "data/evaluation/b6_reference_catalogue.json").read_text())
        pro = json.loads((ROOT / "data/evaluation/b6_protocol_v1.json").read_text())
        manifest = {"datasets": {
            "ai4i-2020": {"files": [runner.SPECS["manufacturing"]["source"]]},
            "cic-ids2017": {"samples": [runner.SPECS["cybersecurity"]["source"]],
                            "sampling": {"seed": 2017, "records_sampled": 5}},
        }}
        self._write_json("data/evaluation/b6_reference_catalogue.json", cat)
        self._write_json("data/evaluation/b6_protocol_v1.json", pro)
        self._write_json("data/sources.json", manifest)
        self.man_cols = ["TWF", "HDF", "PWF", "OSF", "RNF", "Machine failure"]
        self.cyber_cols = [" Total Fwd Packets", " Fwd Packet Length Min", " Fwd Packet Length Mean", " Fwd Packet Length Max"]
        self.man = [
            [1, 0, 0, 0, 0, 1],  # satisfied
            [0, 1, 0, 0, 0, 0],  # violated
            [0, 0, 0, 0, 0, 0],  # not applicable
            ["", 0, 0, 0, 0, 1], # missing mode -> abstained
            [0, 0, 0, 0, 0, 2],  # nonbinary target -> abstained
        ]
        self.cyb = [
            [3, 1, 2, 3],       # satisfied
            [4, 1, 8, 3],       # violated
            [0, "", "", ""],# not applicable
            [-1, 1, 2, 3],      # invalid packet count -> abstained
            [2, 1, "NaN", 3],  # missing/nonfinite feature -> abstained
        ]
        self._csv(runner.SPECS["manufacturing"]["source"], self.man_cols, self.man)
        self._csv(runner.SPECS["cybersecurity"]["source"], self.cyber_cols, self.cyb)
        cfg = copy.deepcopy(runner.SPECS)
        cfg["manufacturing"]["expected_rows"] = 5
        cfg["cybersecurity"]["expected_rows"] = 5
        p = patch.dict(runner.SPECS, cfg, clear=True)
        p.start()
        self.addCleanup(p.stop)

    def _write_json(self, rel, obj):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj), encoding="utf-8")

    def _csv(self, rel, fields, rows):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(fields)
            writer.writerows(rows)

    def test_both_preflight(self):
        self.assertEqual(set(runner.prepare(self.root, ["manufacturing", "cybersecurity"])), {"manufacturing", "cybersecurity"})

    def test_manufacturing_denominators(self):
        row = runner.run(self.root, ["manufacturing"])["results"][0]
        self.assertEqual(row["counts"], {"satisfied": 1, "violated": 1, "abstained": 2, "not_applicable": 1})
        self.assertEqual((row["record_count"], row["eligible_records"], row["evaluated_records"]), (5, 4, 2))
        self.assertAlmostEqual(row["coverage_on_eligible"], 0.5)

    def test_cyber_denominators(self):
        row = runner.run(self.root, ["cybersecurity"])["results"][0]
        self.assertEqual(row["counts"], {"satisfied": 1, "violated": 1, "abstained": 2, "not_applicable": 1})
        self.assertEqual((row["record_count"], row["eligible_records"], row["evaluated_records"]), (5, 4, 2))

    def test_report_is_never_gold(self):
        report = runner.run(self.root, ["manufacturing", "cybersecurity"])
        self.assertEqual(report["independently_adjudicated_gold_rules"], 0)
        self.assertIn("development", report["mode"])
        self.assertTrue(all(not r["independently_adjudicated_row_defects"] for r in report["results"]))

    def test_hash_and_source_provenance(self):
        report = runner.run(self.root, ["cybersecurity"])
        self.assertEqual(len(report["results"][0]["source_sha256"]), 64)
        self.assertIn("not_entire", report["results"][0]["source_type"])
        self.assertEqual(report["protocol_id"], runner.PROTOCOL_ID)

    def test_exact_header_required(self):
        self._csv(runner.SPECS["cybersecurity"]["source"],
                  [x.strip() for x in self.cyber_cols], self.cyb)
        with self.assertRaisesRegex(runner.EvaluationError, "Missing exact CSV columns"):
            runner.run(self.root, ["cybersecurity"])

    def test_duplicate_required_header_rejected(self):
        self._csv(runner.SPECS["manufacturing"]["source"],
                  self.man_cols + ["TWF"], [r + [1] for r in self.man])
        with self.assertRaisesRegex(runner.EvaluationError, "Duplicate required CSV columns"):
            runner.run(self.root, ["manufacturing"])

    def test_duplicate_unrelated_column_is_logged_without_data_loss(self):
        cols = self.cyber_cols + [" Extra Field", " Extra Field"]
        rows = [row + ["unrelated-a", "unrelated-b"] for row in self.cyb]
        self._csv(runner.SPECS["cybersecurity"]["source"], cols, rows)
        report = runner.run(self.root, ["cybersecurity"])["results"][0]
        self.assertEqual(report["counts"], {
            "satisfied": 1, "violated": 1, "abstained": 2, "not_applicable": 1
        })
        self.assertEqual(report["csv_header_diagnostics"]["nonrequired_duplicate_names"], [" Extra Field"])
        self.assertEqual(report["csv_header_diagnostics"]["reader"], "positional_csv_reader_no_header_overwrite")

    def test_blank_unrelated_headers_logged(self):
        cols = self.cyber_cols + ["", ""]
        rows = [row + ["x", "y"] for row in self.cyb]
        self._csv(runner.SPECS["cybersecurity"]["source"], cols, rows)
        report = runner.run(self.root, ["cybersecurity"])["results"][0]
        self.assertEqual(report["csv_header_diagnostics"]["blank_header_positions_1based"], [5, 6])
        self.assertEqual(report["record_count"], 5)

    def test_malformed_row_is_still_rejected(self):
        cols = self.cyber_cols + [" Duplicate Name", " Duplicate Name"]
        rows = [row + ["x", "y"] for row in self.cyb]
        rows[-1].pop()  # partial last row must not be misread as data.
        self._csv(runner.SPECS["cybersecurity"]["source"], cols, rows)
        with self.assertRaisesRegex(runner.EvaluationError, "Malformed CSV row"):
            runner.run(self.root, ["cybersecurity"])

    def test_required_file_missing(self):
        (self.root / runner.SPECS["cybersecurity"]["source"]).unlink()
        with self.assertRaisesRegex(runner.EvaluationError, "Required LOCAL CSV not found"):
            runner.run(self.root, ["manufacturing", "cybersecurity"])

    def test_manifest_wrong_sampling_seed_rejected(self):
        path = self.root / "data/sources.json"
        obj = json.loads(path.read_text())
        obj["datasets"]["cic-ids2017"]["sampling"]["seed"] = 123
        path.write_text(json.dumps(obj))
        with self.assertRaisesRegex(runner.EvaluationError, "sampling provenance"):
            runner.prepare(self.root, ["cybersecurity"])

    def test_rule_status_changed_refused(self):
        path = self.root / "data/evaluation/b6_reference_catalogue.json"
        obj = json.loads(path.read_text())
        next(x for x in obj["entries"] if x["id"] == "B6-MAN-001")["status"] = "excluded"
        path.write_text(json.dumps(obj))
        with self.assertRaisesRegex(runner.EvaluationError, "Reference status"):
            runner.prepare(self.root, ["manufacturing"])

    def test_protocol_mismatch_refused(self):
        path = self.root / "data/evaluation/b6_protocol_v1.json"
        obj = json.loads(path.read_text())
        obj["protocol_id"] = "different"
        path.write_text(json.dumps(obj))
        with self.assertRaisesRegex(runner.EvaluationError, "mismatched"):
            runner.prepare(self.root, ["manufacturing"])

    def test_pinned_record_count_enforced(self):
        self._csv(runner.SPECS["manufacturing"]["source"], self.man_cols, self.man[:4])
        with self.assertRaisesRegex(runner.EvaluationError, "Unexpected source count"):
            runner.run(self.root, ["manufacturing"])

    def test_nonbinary_flag_abstains_even_if_another_flag_is_true(self):
        self.man[0][1] = 5
        self._csv(runner.SPECS["manufacturing"]["source"], self.man_cols, self.man)
        result = runner.run(self.root, ["manufacturing"])["results"][0]
        self.assertEqual(result["counts"]["satisfied"], 0)
        self.assertEqual(result["counts"]["abstained"], 3)


if __name__ == "__main__":
    unittest.main()
