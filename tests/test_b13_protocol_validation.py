import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.b13_protocol_validation import (
    B13Error, COLUMNS, candidate_hash_records, read_manifest, safe_write_lock,
    sha256_file, validate_candidates, validate_plan,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN = json.loads((ROOT / "data/evaluation/b13_plan_v1.json").read_text(encoding="utf-8"))


class B13ProtocolTests(unittest.TestCase):
    def test_design_valid(self):
        validate_plan(PLAN)

    def test_changed_arm_is_rejected(self):
        other = json.loads(json.dumps(PLAN))
        other["arms"][2]["name"] = "different_gate"
        with self.assertRaises(B13Error):
            validate_plan(other)

    def test_unsupported_claim_is_rejected(self):
        other = json.loads(json.dumps(PLAN))
        other["allowed_claims_now"].append("gold_precision")
        with self.assertRaises(B13Error):
            validate_plan(other)

    def test_blank_template_is_valid_for_preflight(self):
        path = ROOT / "data/evaluation/b13_candidate_manifest_template.csv"
        self.assertEqual(read_manifest(path), [])
        self.assertEqual(validate_candidates([], ROOT, PLAN, lock=False)["candidates_total"], 0)

    def test_empty_lock_rejected(self):
        with self.assertRaises(B13Error):
            validate_candidates([], ROOT, PLAN, lock=True)

    def make_row(self, directory):
        path = directory / "evidence.json"
        path.write_text('{"proof": "not independently validated"}', encoding="utf-8")
        digest = sha256_file(path)
        row = {c: "" for c in COLUMNS}
        row.update({"candidate_id": "B13-001", "domain": "manufacturing",
                    "source_group": "test-source", "source_path": str(path), "source_sha256": digest,
                    "opportunity_id": "o1", "proposal_method": "test", "proposal_path": str(path),
                    "proposal_sha256": digest, "context_path": str(path), "context_sha256": digest,
                    "registry_path": str(path), "registry_sha256": digest,
                    "source_evidence_url": "https://example.org/doc", "source_evidence_locator": "section-1"})
        return row

    def test_single_candidate_preflight_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = self.make_row(Path(tmp))
            stats = validate_candidates([row], Path(tmp), PLAN, lock=False)
            self.assertEqual(stats["by_domain"]["manufacturing"], 1)
            with self.assertRaises(B13Error):
                validate_candidates([row], Path(tmp), PLAN, lock=True)

    def test_hash_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = self.make_row(Path(tmp))
            row["source_sha256"] = "0" * 64
            with self.assertRaisesRegex(B13Error, "mismatch"):
                validate_candidates([row], Path(tmp), PLAN, lock=False)

    def test_duplicate_candidate_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = self.make_row(Path(tmp))
            with self.assertRaisesRegex(B13Error, "duplicated"):
                validate_candidates([row, dict(row)], Path(tmp), PLAN, lock=False)

    def test_http_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = self.make_row(Path(tmp))
            row["source_evidence_url"] = "http://example.com"
            with self.assertRaises(B13Error):
                validate_candidates([row], Path(tmp), PLAN, lock=False)

    def test_lock_records_do_not_contain_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = self.make_row(Path(tmp))
            record = candidate_hash_records([row])[0]
            self.assertNotIn("source_path", record)
            self.assertNotIn("evidence_url", record)
            self.assertEqual(record["candidate_id"], "B13-001")

    def test_exclusive_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "lock.json"
            safe_write_lock(out, {"a": 1})
            with self.assertRaises(FileExistsError):
                safe_write_lock(out, {"a": 2})
            self.assertEqual(json.loads(out.read_text()), {"a": 1})


if __name__ == "__main__":
    unittest.main()
