"""Stdlib-only offline smoke tests; cannot validate an LLM's semantic correctness."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'src' / 'llm_rule_pilot.py'
spec = importlib.util.spec_from_file_location('llm_rule_pilot', SCRIPT)
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.bundle = {'domain': 'healthcare', 'passages': [
            {'id': 'P01', 'column': 'A', 'description': 'Official measurement A', 'source': 'official'},
            {'id': 'P02', 'column': 'B', 'description': 'Official measurement B', 'source': 'official'},
            {'id': 'P03', 'column': 'C', 'description': 'NO DOCUMENTED DEFINITION', 'source': 'none'},
        ]}

    def test_rejects_unsupported_reference(self):
        d = {'rules': [{'rule_type': 'arithmetic', 'columns': ['A', 'B'], 'expression': 'A=B', 'applicability': '', 'passage_ids': ['P03'], 'uncertainty': ''}]}
        self.assertEqual(pilot.validate_proposals(d, self.bundle)[0]['syntax_and_reference_check'], 'fail')

    def test_rejects_unknown_column(self):
        d = {'rules': [{'rule_type': 'arithmetic', 'columns': ['A', 'Z'], 'expression': 'A=Z', 'applicability': '', 'passage_ids': ['P01'], 'uncertainty': ''}]}
        self.assertEqual(pilot.validate_proposals(d, self.bundle)[0]['syntax_and_reference_check'], 'fail')

    def test_keeps_candidate_unverified(self):
        d = {'rules': [{'rule_type': 'arithmetic', 'columns': ['A', 'B'], 'expression': 'A=B', 'applicability': '', 'passage_ids': ['P01', 'P02'], 'uncertainty': ''}]}
        row = pilot.validate_proposals(d, self.bundle)[0]
        self.assertEqual(row['verification_status'], 'candidate_unverified')

    def test_hypothesis_mode_permits_uncited_suggestions_but_not_unknown_columns(self):
        rule = {'rule_type': 'arithmetic', 'columns': ['A', 'B'],
                'expression': 'A = k * B (k unknown)', 'applicability': 'check units',
                'passage_ids': [], 'uncertainty': 'no evidence for coefficient'}
        row = pilot.validate_proposals({'rules': [rule]}, self.bundle, mode='hypothesis')[0]
        self.assertEqual(row['syntax_and_reference_check'], 'pass')
        self.assertEqual(row['verification_status'], 'hypothesis_unverified')
        self.assertFalse(row['has_documented_definition_passage'])
        rule['columns'] = ['A', 'NONEXISTENT']
        bad = pilot.validate_proposals({'rules': [rule]}, self.bundle, mode='hypothesis')[0]
        self.assertEqual(bad['syntax_and_reference_check'], 'fail')

    def test_hypothesis_mode_rejects_fake_citation_and_keeps_strict_baseline(self):
        rule = {'rule_type': 'arithmetic', 'columns': ['A', 'B'],
                'expression': 'A=B', 'applicability': '',
                'passage_ids': ['P99'], 'uncertainty': ''}
        self.assertEqual(pilot.validate_proposals({'rules': [rule]}, self.bundle, mode='hypothesis')[0]['syntax_and_reference_check'], 'fail')
        rule['passage_ids'] = []
        self.assertEqual(pilot.validate_proposals({'rules': [rule]}, self.bundle, mode='strict')[0]['syntax_and_reference_check'], 'fail')

    def test_modes_have_separate_prompt_and_same_models(self):
        b = self.bundle
        strict = pilot._build_request('luna', b)
        hypothesis = pilot._build_request('luna', b, mode='hypothesis')
        self.assertNotEqual(strict['instructions'], hypothesis['instructions'])
        self.assertEqual(strict['model'], hypothesis['model'])
        self.assertEqual(strict['max_output_tokens'], hypothesis['max_output_tokens'])

    def test_all_no_call_default(self):
        bundle = {'domain': 'manufacturing', 'passages': []}
        self.assertEqual(pilot._build_request('luna', bundle)['model'], 'gpt-6-luna')
        self.assertEqual(pilot._build_request('sol', bundle)['reasoning']['effort'], 'low')
        self.assertFalse(pilot._build_request('sol', bundle)['store'])


if __name__ == '__main__':
    unittest.main()
