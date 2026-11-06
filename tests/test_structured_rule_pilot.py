"""B5 smoke tests; no API calls and NO claims of LLM semantic accuracy."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src import structured_rule_pilot as b5


BUNDLE = {
    "dataset_id": "nhanes-2017-2018-glu-j",
    "domain": "healthcare",
    "passages": [
        {"id": "P01", "column": "LBXGLU", "description": "Glucose (mg/dL)"},
        {"id": "P02", "column": "LBDGLUSI", "description": "Glucose (mmol/L)"},
        {"id": "P03", "column": "OTHER", "description": "NO DOCUMENTED DEFINITION"},
    ],
}


def mk_rule(left=None, right=None, citations=None):
    return {
        "id": "r-1",
        "assertions": [{
            "left": left or {"column": "LBDGLUSI"},
            "op": "eq", "right": right or {"column": "LBXGLU"},
            "round_right": None, "abs_tolerance": None,
        }],
        "when": None, "context_keys": [],
        "passage_ids": ["P01", "P02"] if citations is None else citations,
        "uncertainty": "No documentary statement of equation",
    }


class StructuredPilotTests(unittest.TestCase):
    def test_schema_valid_jsonschema_draft(self):
        from jsonschema import Draft202012Validator
        Draft202012Validator.check_schema(b5.response_schema())

    def test_schema_example_uses_typed_expression_not_text(self):
        from jsonschema import Draft202012Validator
        Draft202012Validator(b5.response_schema()).validate({"rules": [mk_rule()]})

    def test_schema_rejects_free_text_equation(self):
        from jsonschema import Draft202012Validator, ValidationError
        rule = mk_rule()
        rule["assertions"][0]["right"] = "LBDGLUSI = k * LBXGLU"
        with self.assertRaises(ValidationError):
            Draft202012Validator(b5.response_schema()).validate({"rules": [rule]})

    def test_schema_rejects_raw_numeric_constant_node(self):
        from jsonschema import Draft202012Validator, ValidationError
        rule = mk_rule(right={"constant": "0.05551"})
        with self.assertRaises(ValidationError):
            Draft202012Validator(b5.response_schema()).validate({"rules": [rule]})

    def test_equal_columns_produces_compilable_unverified_candidate(self):
        out = b5.inspect_response({"rules": [mk_rule()]}, BUNDLE, "luna")
        self.assertEqual(out[0]["compilation"]["status"], "candidate_executable_unverified")
        self.assertFalse(out[0]["compilation"]["semantic_verified"])

    def test_unresolved_factor_blocks_without_executable_rule(self):
        rule = mk_rule(right={"multiply": [{"column": "LBXGLU"}, {"parameter": "k1"}]})
        out = b5.inspect_response({"rules": [rule]}, BUNDLE, "luna")
        self.assertEqual(out[0]["compilation"]["status"], "blocked_unresolved")
        self.assertIsNone(out[0]["compilation"]["rule"])

    def test_missing_rounding_parameter_blocks(self):
        rule = mk_rule()
        rule["assertions"][0]["round_right"] = {"parameter": "rounding1"}
        out = b5.inspect_response({"rules": [rule]}, BUNDLE, "luna")
        self.assertEqual(out[0]["compilation"]["status"], "blocked_unresolved")

    def test_unknown_column_rejected(self):
        out = b5.inspect_response({"rules": [mk_rule(left={"column": "MADEUP"})]}, BUNDLE, "sol")
        self.assertEqual(out[0]["compilation"]["status"], "rejected_invalid")

    def test_undocumented_passage_rejected(self):
        out = b5.inspect_response({"rules": [mk_rule(citations=["P03"])]}, BUNDLE, "luna")
        self.assertEqual(out[0]["status"], "rejected_invalid")

    def test_unknown_passage_rejected(self):
        out = b5.inspect_response({"rules": [mk_rule(citations=["P99"])]}, BUNDLE, "luna")
        self.assertEqual(out[0]["status"], "rejected_invalid")

    def test_uncited_hypothesis_permitted_but_unverified(self):
        out = b5.inspect_response({"rules": [mk_rule(citations=[])]}, BUNDLE, "luna")
        self.assertEqual(out[0]["compilation"]["status"], "candidate_executable_unverified")

    def test_empty_rules_allowed(self):
        self.assertEqual(b5.inspect_response({"rules": []}, BUNDLE, "luna"), [])

    def test_more_than_two_rules_rejected(self):
        with self.assertRaises(ValueError):
            b5.inspect_response({"rules": [mk_rule()] * 3}, BUNDLE, "luna")

    def test_request_hash_and_model_settings(self):
        luna = b5.build_request("luna", BUNDLE)
        sol = b5.build_request("sol", BUNDLE)
        self.assertEqual(luna["input"], sol["input"])
        self.assertEqual(luna["instructions"], sol["instructions"])
        self.assertEqual(luna["text"]["format"]["schema"], sol["text"]["format"]["schema"])
        self.assertFalse(luna["store"])
        self.assertNotEqual(b5.request_hash(luna), b5.request_hash(sol))

    def test_default_dry_run_no_api_no_prompt_for_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(b5, "make_bundle", return_value=BUNDLE), \
                 patch.object(b5, "_call_openai", side_effect=AssertionError("called API")), \
                 patch.object(b5.getpass, "getpass", side_effect=AssertionError("asked key")):
                self.assertEqual(b5.main(["--root", tmp]), 0)
                self.assertTrue((Path(tmp) / "data/llm_pilot/structured/inputs.json").exists())

    def test_stale_cache_blocks_without_api_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data/llm_pilot/structured/luna_healthcare.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"request_sha256": "wrong"}))
            with patch.object(b5, "make_bundle", return_value=BUNDLE), \
                 patch.object(b5, "_call_openai", side_effect=AssertionError("called API")):
                with self.assertRaises(SystemExit):
                    b5.main(["--root", tmp, "--domains", "healthcare", "--run"])


if __name__ == "__main__":
    unittest.main()
