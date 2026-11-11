"""Negative and positive tests of read-only B13.2 screening checks."""
import copy
import unittest
from pathlib import Path
from src.b13_2_source_screening import read, validate, ScreenError

REGISTRY = Path(__file__).resolve().parents[1] / "data/evaluation/b13_2_source_screening_v1.json"

class TestB13SourceScreen(unittest.TestCase):
    def setUp(self):
        self.data = read(REGISTRY)

    def fail_on(self, modify):
        value = copy.deepcopy(self.data)
        modify(value)
        with self.assertRaises(ScreenError):
            validate(value)

    def test_shortlist_valid(self):
        v = validate(self.data)
        self.assertEqual(v["source_entries"], 5)
        self.assertEqual(v["eligible_confirmatory_cohorts"], 0)

    def test_reject_completed_claim(self):
        self.fail_on(lambda d: d.__setitem__("evaluation_performed", True))

    def test_reject_pretend_gate_freeze(self):
        self.fail_on(lambda d: d.__setitem__("gate_policies_frozen", True))

    def test_reject_http_source(self):
        self.fail_on(lambda d: d["source_shortlist"][0].__setitem__("official_url", "http://www.sec.gov/example"))

    def test_reject_wrong_domain_host(self):
        self.fail_on(lambda d: d["source_shortlist"][0].__setitem__("official_url", "https://archive.ics.uci.edu/example"))

    def test_reject_duplicate(self):
        self.fail_on(lambda d: d["source_shortlist"][1].__setitem__("id", "B13S-FIN-01"))

    def test_reject_pretend_eligibility(self):
        self.fail_on(lambda d: d["source_shortlist"][0].__setitem__("eligibility_status", "confirmed"))

    def test_reject_deleted_claim_denial(self):
        self.fail_on(lambda d: d["disallowed_claims"].remove("new_natural_defects"))

    def test_reject_missing_domain(self):
        self.fail_on(lambda d: d.__setitem__("source_shortlist", d["source_shortlist"][:3]))

if __name__ == "__main__":
    unittest.main()
