"""Fixture-only safeguards for the existing SEC A/B/C summary (no SEC source needed)."""
import copy
import unittest

from scripts.summarize_sec_ablation import STUDY, STATES, summarize


class SummaryTests(unittest.TestCase):
    def fixture(self):
        # Mirrors the 17 predeclared code-path controls; NOT independently labelled data.
        rows = [
            ("baseline", "real_unqualified", "admit", "abstain"),
            ("meta_unknown", "controlled_negative", "abstain", "abstain"),
            ("meta_block", "controlled_negative", "block", "block"),
            *[(f"negative_block_{i}", "controlled_negative", "admit", "block") for i in range(5)],
            *[(f"negative_abstain_{i}", "controlled_negative", "admit", "abstain") for i in range(2)],
            ("sim_approved", "synthetic_credential_control", "admit", "admit"),
            *[(f"sim_block_{i}", "synthetic_credential_control", "admit", "block") for i in range(3)],
            *[(f"sim_abstain_{i}", "synthetic_credential_control", "admit", "abstain") for i in range(3)],
        ]
        self.assertEqual(len(rows), 17)
        cases = [{"scenario_id": sid, "classification": category, "A": "admit", "B": b,
                  "C": c, "C_reason": "fixture_only"} for sid, category, b, c in rows]
        return {"study": STUDY, "cases": cases, "controlled_scenarios_total": 17,
                "candidate_count_independent": 1, "scenarios_simulated_evidence_not_real": 7,
                "scenarios_unqualified_real_evidence": 10, "human_reviewer_decisions": 0,
                "gold_rules": 0, "measured_accuracy_or_gate_effect": False,
                "arm_counts_over_repeated_scenarios_not_independent_samples": {
                    arm: {state: sum(x[arm] == state for x in cases) for state in STATES}
                    for arm in "ABC"}}

    def test_transitions_and_category_counts(self):
        s = summarize(self.fixture())
        self.assertEqual(s["arm_counts"]["B"], {"admit": 15, "abstain": 1, "block": 1})
        self.assertEqual(s["arm_counts"]["C"], {"admit": 1, "abstain": 7, "block": 9})
        self.assertEqual(s["B_to_C"], {"abstain -> abstain": 1, "admit -> abstain": 6,
                                       "admit -> admit": 1, "admit -> block": 8,
                                       "block -> block": 1})
        self.assertEqual(s["C_by_classification"]["synthetic_credential_control"],
                         {"admit": 1, "abstain": 3, "block": 3})

    def test_cannot_claim_gold_or_accuracy(self):
        for key, bad in (("gold_rules", 1), ("measured_accuracy_or_gate_effect", True),
                         ("scenarios_simulated_evidence_not_real", 0)):
            report = self.fixture()
            report[key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                summarize(report)

    def test_rejects_mismatched_stored_counts_and_duplicates(self):
        report = self.fixture()
        report["arm_counts_over_repeated_scenarios_not_independent_samples"]["C"]["block"] = 0
        with self.assertRaises(ValueError):
            summarize(report)
        report = self.fixture()
        report["cases"][1]["scenario_id"] = report["cases"][0]["scenario_id"]
        with self.assertRaises(ValueError):
            summarize(report)


if __name__ == "__main__":
    unittest.main()
