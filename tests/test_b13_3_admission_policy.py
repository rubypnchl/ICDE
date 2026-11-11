"""B13.3 fail-closed synthetic admission decision tests; no real dataset use."""
import copy
import unittest
from pathlib import Path
from src.b13_3_admission_policy import (load_json, validate_spec, validate_case,
                                        evaluate_three_arms, check_policy_invariants, PolicyError)
ROOT = Path(__file__).resolve().parents[1]
SPEC = load_json(ROOT / "data/evaluation/b13_3_gate_policy_v1.json")
CASES = load_json(ROOT / "data/evaluation/b13_3_synthetic_cases_v1.json")["cases"]


class B13AdmissionTests(unittest.TestCase):
    def test_spec(self):
        validate_spec(SPEC)

    def test_synthetic_invariants(self):
        s = check_policy_invariants(CASES)
        self.assertEqual(s["toy_case_count"], 9)
        self.assertFalse(s["semantic_accuracy_defined"])

    def test_compiled_all_evidence_admits(self):
        self.assertEqual(evaluate_three_arms(CASES[0]), {"A": "admit", "B": "admit", "C": "admit"})

    def test_metadata_unknown_abstains_B_C(self):
        self.assertEqual(evaluate_three_arms(CASES[1]), {"A": "admit", "B": "abstain", "C": "abstain"})

    def test_documentary_unverified_abstains_C(self):
        self.assertEqual(evaluate_three_arms(CASES[2]), {"A": "admit", "B": "admit", "C": "abstain"})

    def test_context_contradiction_precedence(self):
        self.assertEqual(evaluate_three_arms(CASES[3]), {"A": "admit", "B": "admit", "C": "block"})

    def test_compiler_blocked_all_block(self):
        self.assertEqual(evaluate_three_arms(CASES[4]), {"A": "block", "B": "block", "C": "block"})

    def test_compiler_unknown_all_abstain(self):
        self.assertEqual(evaluate_three_arms(CASES[5]), {"A": "abstain", "B": "abstain", "C": "abstain"})

    def test_metadata_contradiction(self):
        self.assertEqual(evaluate_three_arms(CASES[6]), {"A": "admit", "B": "block", "C": "block"})

    def test_documentary_contradiction(self):
        self.assertEqual(evaluate_three_arms(CASES[7]), {"A": "admit", "B": "admit", "C": "block"})

    def test_missing_context_abstains(self):
        self.assertEqual(evaluate_three_arms(CASES[8]), {"A": "admit", "B": "admit", "C": "abstain"})

    def test_missing_required_contexts_rejected(self):
        c = copy.deepcopy(CASES[0]); c["required_contexts"] = []
        with self.assertRaises(PolicyError): evaluate_three_arms(c)

    def test_extra_context_rejected(self):
        c = copy.deepcopy(CASES[0]); c["context_evidence"]["new"] = "supported"
        with self.assertRaises(PolicyError): evaluate_three_arms(c)

    def test_http_documentary_evidence_rejected(self):
        c = copy.deepcopy(CASES[0]); c["documentary"]["evidence_url"] = "http://example.org/x"
        with self.assertRaises(PolicyError): evaluate_three_arms(c)

    def test_unverified_doc_status_cannot_claim_verified(self):
        c = copy.deepcopy(CASES[0]); c["documentary"]["status"] = "unknown"
        with self.assertRaises(PolicyError): evaluate_three_arms(c)

    def test_spec_claim_tampering_rejected(self):
        d = copy.deepcopy(SPEC); d["disallowed_claims"].remove("prospective_accuracy_result")
        with self.assertRaises(PolicyError): validate_spec(d)

    def test_spec_arm_tampering_rejected(self):
        d = copy.deepcopy(SPEC); d["arm_order"] = ["A", "C", "B"]
        with self.assertRaises(PolicyError): validate_spec(d)

    def test_spec_not_integrated_check(self):
        d = copy.deepcopy(SPEC); d["status"] = "integrated"
        with self.assertRaises(PolicyError): validate_spec(d)

    def test_duplicate_synthetic_ids_rejected(self):
        d = copy.deepcopy(CASES); d[1]["candidate_id"] = d[0]["candidate_id"]
        with self.assertRaises(PolicyError): check_policy_invariants(d)


if __name__ == "__main__":
    unittest.main()
