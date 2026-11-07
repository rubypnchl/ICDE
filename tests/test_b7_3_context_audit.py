"""B7.3 strict policy and lineage tests; no raw records or API."""
import ast
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.b7_3_context_audit import (
    ContextAuditError, RULE_COLUMNS, TARGET_RULE_ID, REQUIRED, TRI,
    assert_legacy_hardcoding, assert_target, context_only_decision,
    controls, frozen_catalogue_decision, validate_plan,
)


def fake_data():
    a = {"op": "sum_eq", "result_column": RULE_COLUMNS[0], "term_columns": list(RULE_COLUMNS[1:]), "tolerance": 0}
    supported = {
        "rule": {"id": TARGET_RULE_ID, "dataset_id": "sec-companyfacts-320193", "assertion": a},
        "heldout": {"applicable_rows": 41, "violations": 0, "decision": "documented_support"},
        "documented_evidence": {"status": "documented", "requirements": list(REQUIRED),
                                "context_compatibility": {k: True for k in REQUIRED}},
    }
    other = {"rule": {"id": "other"}, "heldout": {"decision": "abstain"}}
    old = {"datasets": {
        "ai4i-2020": {"candidate_count": 1, "candidates": [other], "decision_counts": {"abstain": 1, "documented_support": 0}},
        "sec-companyfacts-320193": {"candidate_count": 1, "candidates": [supported], "decision_counts": {"abstain": 0, "documented_support": 1}},
    }}
    catalogue = {"entries": [{"id": "B6-FIN-002", "status": "excluded", "scoring_eligible": False,
                               "columns": ["Assets", "Liabilities", "StockholdersEquity"],
                               "exclusion_reason": "Not a universal identity"}]}
    registry = {"entries": [{"id": "SEC-BALANCE-001", "requirements": list(REQUIRED), "assertion": a}]}
    return old, catalogue, registry


class SavedAuditTests(unittest.TestCase):
    def test_accept_exact_pinned_structure(self):
        legacy, cat, reg = fake_data()
        item, summary, ex = assert_target(legacy, cat, reg)
        self.assertEqual(item["rule"]["id"], TARGET_RULE_ID)
        self.assertEqual(summary["sec-companyfacts-320193"]["candidates"], 1)
        self.assertEqual(ex["status"], "excluded")

    def test_reject_wrong_assertion(self):
        a, b, c = fake_data()
        a["datasets"]["sec-companyfacts-320193"]["candidates"][0]["rule"]["assertion"]["term_columns"] = ["Other"]
        with self.assertRaises(ContextAuditError): assert_target(a, b, c)

    def test_reject_missing_exclusion(self):
        a, b, c = fake_data()
        b["entries"] = []
        with self.assertRaises(ContextAuditError): assert_target(a, b, c)

    def test_reject_changed_heldout(self):
        a, b, c = fake_data()
        a["datasets"]["sec-companyfacts-320193"]["candidates"][0]["heldout"]["violations"] = 1
        with self.assertRaises(ContextAuditError): assert_target(a, b, c)

    def test_reject_extra_supported(self):
        a, b, c = fake_data()
        d = copy.deepcopy(a["datasets"]["sec-companyfacts-320193"]["candidates"][0]); d["rule"]["id"] = "extra"
        a["datasets"]["sec-companyfacts-320193"]["candidates"].append(d)
        a["datasets"]["sec-companyfacts-320193"]["candidate_count"] = 2
        a["datasets"]["sec-companyfacts-320193"]["decision_counts"]["documented_support"] = 2
        with self.assertRaises(ContextAuditError): assert_target(a, b, c)

    def test_reject_decision_count_mismatch(self):
        a, b, c = fake_data()
        a["datasets"]["ai4i-2020"]["decision_counts"]["abstain"] = 0
        with self.assertRaises(ContextAuditError): assert_target(a, b, c)

    def test_scope_hardcoding_ast(self):
        code = '''def run_discovery():\n    context = {"same-entity": bool(1), "same-reporting-date": True, "same-accounting-scope": True, "same-currency": 3 == 3}\n'''
        got = assert_legacy_hardcoding(code)
        self.assertEqual(got["same-accounting-scope"], "hardcoded_true")
        self.assertEqual(got["same-entity"], "computed_expression")

    def test_reject_updated_scope_code(self):
        code = '''def run_discovery():\n    context = {"same-entity": bool(1), "same-reporting-date": True, "same-accounting-scope": scope, "same-currency": True}\n'''
        with self.assertRaises(ContextAuditError): assert_legacy_hardcoding(code)

    def test_reject_missing_source_function(self):
        with self.assertRaises(ContextAuditError): assert_legacy_hardcoding("def other(): pass")

    def test_unknown_abstains(self):
        c = {k: "supported" for k in REQUIRED}; c["same accounting scope"] = "unknown"
        self.assertEqual(context_only_decision(c), "abstain_context_unsubstantiated")

    def test_contradiction_blocks(self):
        c = {k: "supported" for k in REQUIRED}; c["same currency"] = "contradicted"
        self.assertEqual(context_only_decision(c), "blocked_context_incompatible")

    def test_all_supported_still_only_candidate(self):
        self.assertEqual(context_only_decision({k: "supported" for k in REQUIRED}), "candidate_only_unverified")

    def test_contradiction_overrides_unknown(self):
        c = {k: "unknown" for k in REQUIRED}; c["same entity"] = "contradicted"
        self.assertEqual(context_only_decision(c), "blocked_context_incompatible")

    def test_no_partial_context(self):
        with self.assertRaises(ContextAuditError): context_only_decision({"same entity": "supported"})

    def test_reject_bool_context(self):
        with self.assertRaises(ContextAuditError): context_only_decision({k: True for k in REQUIRED})

    def test_frozen_exclusion_takes_precedence(self):
        self.assertEqual(frozen_catalogue_decision("candidate_only_unverified", excluded=True), "blocked_unqualified_universal_identity")

    def test_controls_fixed_count_and_unique(self):
        cs = controls()
        self.assertEqual(len(cs), 10)
        self.assertEqual(len({c["id"] for c in cs}), len(cs))
        self.assertTrue(all(c["nature"] != "natural_data_case" for c in cs))
        self.assertEqual(sum(context_only_decision(c["context"]) == "blocked_context_incompatible" for c in cs), 4)
        self.assertEqual(sum(context_only_decision(c["context"]) == "abstain_context_unsubstantiated" for c in cs), 5)

    def test_wrong_plan_fails_closed(self):
        good = json.loads((ROOT / "data/evaluation/b7_3_plan_v1.json").read_text())
        validate_plan(good)
        good["independent_gold_available"] = True
        with self.assertRaises(ContextAuditError): validate_plan(good)


if __name__ == "__main__": unittest.main()
