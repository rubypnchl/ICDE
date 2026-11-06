"""B4 tests: no model/API calls, no external data or secrets."""
import unittest

from src.rule_bridge import compile_proposal


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.base = {
            "proposal_version": "metaverify-proposal-v0.1", "id": "r1", "dataset_id": "toy",
            "origin": "test_fixture", "assertions": [{"left": {"column": "A"}, "op": "eq", "right": {"column": "B"}}],
            "context_keys": []}
        self.columns = ["A", "B", "C"]

    def test_valid_equality_compiles_unverified(self):
        r = compile_proposal(self.base, self.columns)
        self.assertEqual(r.status, "candidate_executable_unverified")
        self.assertFalse(r.as_dict()["semantic_verified"])
        self.assertEqual(r.rule["schema_version"], "metaverify-exec-v0.1")

    def test_legacy_english_expression_rejected(self):
        p = {"id": "legacy", "expression": "A = B"}
        self.assertEqual(compile_proposal(p, self.columns).status, "rejected_invalid")

    def test_unknown_column_rejected(self):
        self.base["assertions"][0]["right"] = {"column": "FAKE"}
        self.assertEqual(compile_proposal(self.base, self.columns).status, "rejected_invalid")

    def test_invented_numeric_literal_rejected(self):
        self.base["assertions"][0]["right"] = {"constant": "0.05551"}
        self.assertEqual(compile_proposal(self.base, self.columns).status, "rejected_invalid")

    def test_missing_parameter_blocks_without_executable_rule(self):
        self.base["assertions"][0]["right"] = {"parameter": "factor"}
        r = compile_proposal(self.base, self.columns)
        self.assertEqual(r.status, "blocked_unresolved")
        self.assertIsNone(r.rule)

    def test_documented_parameter_requires_source_url(self):
        self.base["assertions"][0]["right"] = {"multiply": [{"column": "B"}, {"parameter": "factor"}]}
        entry = {"toy:factor": {"kind": "number", "value": "0.05551", "origin": "documented_reference", "rationale": "test"}}
        self.assertEqual(compile_proposal(self.base, self.columns, entry).status, "blocked_unresolved")
        entry["toy:factor"]["source_url"] = "https://example.org/reference"
        self.assertEqual(compile_proposal(self.base, self.columns, entry).status, "candidate_executable_unverified")

    def test_nonfinite_parameter_rejected(self):
        self.base["assertions"][0]["right"] = {"parameter": "factor"}
        entry = {"toy:factor": {"kind": "number", "value": "NaN", "origin": "fixture_only", "rationale": "test"}}
        self.assertEqual(compile_proposal(self.base, self.columns, entry).status, "rejected_invalid")

    def test_registered_rounding_is_explicit(self):
        self.base["assertions"][0]["round_right"] = {"parameter": "rounding"}
        entry = {"toy:rounding": {"kind": "rounding", "value": {"mode": "significant_figures", "digits": 3}, "origin": "empirical_same_dataset", "rationale": "fitted in train"}}
        r = compile_proposal(self.base, self.columns, entry)
        self.assertEqual(r.rule["assertions"][0]["round_right"]["digits"], 3)
        self.assertEqual(r.parameter_provenance["rounding"]["origin"], "empirical_same_dataset")

    def test_bad_rounding_rejected(self):
        self.base["assertions"][0]["round_right"] = {"parameter": "rounding"}
        entry = {"toy:rounding": {"kind": "rounding", "value": {"mode": "significant_figures", "digits": 0}, "origin": "fixture_only", "rationale": "test"}}
        self.assertEqual(compile_proposal(self.base, self.columns, entry).status, "rejected_invalid")

    def test_unsupported_arithmetic_operator_rejected(self):
        self.base["assertions"][0]["right"] = {"divide": [{"column": "A"}, {"column": "B"}]}
        self.assertEqual(compile_proposal(self.base, self.columns).status, "rejected_invalid")

    def test_numeric_condition_must_use_registry(self):
        self.base["when"] = {"column": "C", "op": "gt", "value": "0"}
        self.assertEqual(compile_proposal(self.base, self.columns).status, "rejected_invalid")
        self.base["when"]["value"] = {"parameter": "zero"}
        entry = {"toy:zero": {"kind": "number", "value": "0", "origin": "fixture_only", "rationale": "test"}}
        self.assertEqual(compile_proposal(self.base, self.columns, entry).status, "candidate_executable_unverified")

    def test_categorical_condition_allowed(self):
        self.base["when"] = {"column": "C", "op": "eq", "value": "L"}
        r = compile_proposal(self.base, self.columns)
        self.assertEqual(r.status, "candidate_executable_unverified")
        self.assertEqual(r.rule["when"]["value"], "L")

    def test_unknown_proposal_key_rejected(self):
        self.base["exec"] = "print('bad')"
        self.assertEqual(compile_proposal(self.base, self.columns).status, "rejected_invalid")

    def test_four_domain_structured_fixtures(self):
        from pathlib import Path
        import json
        bundle = json.loads((Path(__file__).resolve().parents[1] / "data/rules/b4_example_proposals.json").read_text())
        allowed = {
            "nhanes-2017-2018-glu-j": ["LBXGLU", "LBDGLUSI"],
            "sec-companyfacts": ["Assets", "Liabilities", "StockholdersEquity"],
            "cic-ids2017": [" Total Fwd Packets", " Fwd Packet Length Min", " Fwd Packet Length Mean", " Fwd Packet Length Max"],
            "ai4i-2020": ["Type", "Torque [Nm]"],
        }
        for proposal in bundle["examples"]:
            with self.subTest(domain=proposal["dataset_id"]):
                result = compile_proposal(proposal, allowed[proposal["dataset_id"]], bundle["registrations"])
                self.assertEqual(result.status, "candidate_executable_unverified", result.reason)
                self.assertFalse(result.as_dict()["semantic_verified"])
                self.assertTrue(result.rule["assertions"])

    def test_negative_registered_tolerance_rejected(self):
        self.base["assertions"][0]["abs_tolerance"] = {"parameter": "tolerance"}
        registry = {"toy:tolerance": {"kind": "number", "value": "-1", "origin": "fixture_only", "rationale": "bad test"}}
        self.assertEqual(compile_proposal(self.base, self.columns, registry).status, "rejected_invalid")

    def test_tolerance_must_be_registered(self):
        self.base["assertions"][0]["abs_tolerance"] = "0.1"
        self.assertEqual(compile_proposal(self.base, self.columns).status, "rejected_invalid")


if __name__ == "__main__":
    unittest.main()
