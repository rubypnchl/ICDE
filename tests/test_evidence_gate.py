"""B5.1 tests: offline only; do NOT establish constraint correctness."""
from copy import deepcopy
from pathlib import Path
import json
import unittest

from src.evidence_gate import load_policy, review_report

ROOT = Path(__file__).resolve().parents[1]


def b5_report(domain: str, rule: dict, *, dataset: str, passages: list[dict], baseline: str):
    return {
        "dataset_id": dataset,
        "domain": domain,
        "model_id_requested": "gpt-6-luna",
        "request_sha256": "synthetic-test",
        "response_status": "completed",
        "error": None,
        "input_bundle": {"dataset_id": dataset, "domain": domain, "passages": deepcopy(passages)},
        "output": {"rules": [rule]},
        "compile_results": [{"id": rule["id"], "compilation": {"status": baseline}}],
    }


class EvidenceGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy, cls.registry = load_policy(ROOT)
        cls.health_ds = "nhanes-2017-2018-glu-j"
        cls.finance_ds = "sec-companyfacts-320193"
        cls.passes_health = [
            {"id": "P01", "column": "SEQN", "description": "Respondent sequence number"},
            {"id": "P02", "column": "WTSAF2YR", "description": "Fasting Subsample 2 Year MEC Weight"},
            {"id": "P03", "column": "LBXGLU", "description": "Fasting Glucose (mg/dL)",
             "source": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/GLU_J.htm"},
            {"id": "P04", "column": "LBDGLUSI", "description": "Fasting Glucose (mmol/L)",
             "source": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/GLU_J.htm"},
        ]
        cls.passes_finance = [
            {"id": "P01", "column": "Assets", "description": "Assets"},
            {"id": "P02", "column": "Liabilities", "description": "Liabilities"},
            {"id": "P03", "column": "StockholdersEquity", "description": "parent equity"},
        ]
        cls.health_rule = {
            "id": "glucose_unit_conversion",
            **deepcopy(cls.policy["binding_authorizations"][0]["expected_structure"]),
            "uncertainty": "factor and reporting precision unknown",
        }
        cls.finance_rule = {
            "id": "balance_sheet_equation",
            "assertions": [{"left": {"column": "Assets"}, "op": "eq",
                            "right": {"add": [{"column": "Liabilities"}, {"column": "StockholdersEquity"}]},
                            "round_right": None, "abs_tolerance": None}],
            "when": None, "context_keys": [], "passage_ids": ["P01", "P02", "P03"],
            "uncertainty": "parent vs total equity unresolved"
        }

    def health(self, rule=None):
        return b5_report("healthcare", rule or deepcopy(self.health_rule),
                         dataset=self.health_ds, passages=self.passes_health,
                         baseline="blocked_unresolved")

    def finance(self, rule=None):
        return b5_report("finance", rule or deepcopy(self.finance_rule),
                         dataset=self.finance_ds, passages=self.passes_finance,
                         baseline="candidate_executable_unverified")

    def decision(self, report):
        return review_report(report, self.policy, self.registry)["decisions"][0]

    def test_exact_healthcare_snapshot_curator_bindings_compile(self):
        d = self.decision(self.health())
        self.assertEqual(d["status"], "compiled_unverified_posthoc")
        self.assertEqual(d["b5_original_compilation_status"], "blocked_unresolved")
        self.assertEqual(d["compiled_rule"]["assertions"][0]["round_right"],
                         {"mode": "significant_figures", "digits": 3})
        self.assertEqual(d["compiled_rule"]["assertions"][0]["right"]["multiply"][1],
                         {"constant": "0.05551"})
        self.assertEqual(d["parameter_provenance"]["k1"]["origin"], "documented_reference")
        self.assertEqual(d["parameter_provenance"]["t1"]["origin"], "empirical_same_dataset")
        self.assertFalse(d["independently_validated"])
        self.assertFalse(d["safe_to_deploy_as_integrity_constraint"])

    def test_changed_coefficient_role_does_not_inherit_binding(self):
        rule = deepcopy(self.health_rule)
        rule["assertions"][0]["right"]["multiply"].reverse()
        d = self.decision(self.health(rule))
        self.assertEqual(d["status"], "blocked_unresolved")
        self.assertIsNone(d["compiled_rule"])
        self.assertIn("structure differs", d["reasons"][0])

    def test_rule_name_matching_alone_never_resolves_parameter(self):
        rule = deepcopy(self.health_rule)
        rule["assertions"][0]["right"]["multiply"][1] = {"parameter": "k99"}
        d = self.decision(self.health(rule))
        self.assertEqual(d["status"], "blocked_unresolved")

    def test_changed_metadata_snapshot_cannot_inherit_binding(self):
        r = self.health()
        r["input_bundle"]["passages"][2]["description"] = "Different clinical concept"
        d = self.decision(r)
        self.assertEqual(d["status"], "blocked_unresolved")
        self.assertIn("evidence passage snapshot changed", d["reasons"][0])

    def test_missing_registry_entry_blocks(self):
        reg = deepcopy(self.registry)
        reg.pop("nhanes-2017-2018-glu-j:glucose_factor")
        d = review_report(self.health(), self.policy, reg)["decisions"][0]
        self.assertEqual(d["status"], "blocked_unresolved")
        self.assertIsNone(d["compiled_rule"])

    def test_finance_omitted_context_and_equity_scope_blocked(self):
        d = self.decision(self.finance())
        self.assertEqual(d["status"], "blocked_applicability_or_scope")
        self.assertIsNone(d["compiled_rule"])
        self.assertTrue(any("entity" in reason for reason in d["reasons"]))
        self.assertTrue(any("noncontrolling" in reason for reason in d["reasons"]))

    def test_finance_adding_context_does_not_override_equity_scope(self):
        rule = deepcopy(self.finance_rule)
        rule["context_keys"] = list(self.policy["domain_policies"][self.finance_ds]["required_context_keys"])
        d = self.decision(self.finance(rule))
        self.assertEqual(d["status"], "blocked_applicability_or_scope")
        self.assertEqual(len(d["reasons"]), 1)
        self.assertIn("semantic scope", d["reasons"][0])

    def test_unknown_dataset_policy_fails_closed(self):
        r = self.health()
        r["dataset_id"] = r["input_bundle"]["dataset_id"] = "other-dataset"
        d = self.decision(r)
        self.assertEqual(d["status"], "blocked_no_curator_policy")

    def test_citation_outside_documented_bundle_rejected(self):
        r = self.health()
        r["output"]["rules"][0]["passage_ids"] = ["P03", "P99"]
        d = self.decision(r)
        self.assertEqual(d["status"], "rejected_invalid")

    def test_noncompleted_response_refused(self):
        r = self.health()
        r["response_status"] = "incomplete"
        with self.assertRaises(ValueError):
            review_report(r, self.policy, self.registry)

    def test_input_domain_dataset_mismatch_refused(self):
        r = self.health()
        r["input_bundle"]["domain"] = "finance"
        with self.assertRaises(ValueError):
            review_report(r, self.policy, self.registry)

    def test_too_many_rules_refused(self):
        r = self.health()
        r["output"]["rules"] *= 3
        with self.assertRaises(ValueError):
            review_report(r, self.policy, self.registry)

    def test_policy_discloses_posthoc(self):
        out = review_report(self.health(), self.policy, self.registry)
        self.assertEqual(out["policy_development_stage"],
                         "posthoc_case_study_policy_developed_after_inspecting_luna_outputs")
        self.assertIn("not blinded", out["scope"])

    def test_original_report_not_modified(self):
        original = self.health()
        snapshot = deepcopy(original)
        review_report(original, self.policy, self.registry)
        self.assertEqual(original, snapshot)

    def test_empty_rule_list_has_no_fabricated_results(self):
        r = self.health()
        r["output"] = {"rules": []}
        self.assertEqual(review_report(r, self.policy, self.registry)["decisions"], [])


if __name__ == "__main__":
    unittest.main()
