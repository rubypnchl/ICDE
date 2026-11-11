"""B13.4 checks actual B4/B3 contract with synthetic-only inputs."""
from __future__ import annotations
import copy
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from src.b13_4_b4_adapter import AdapterError, normalize_b4_compilation, toy_three_arm_replay
from src.rule_bridge import compile_proposal
from src.generic_verifier import validate_rule

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = json.loads((ROOT / "data/evaluation/b13_4_compiler_contract_toys_v1.json").read_text())['fixtures']

class B134Tests(unittest.TestCase):
    def replay(self, n=0):
        return toy_three_arm_replay(FIXTURES[n], compile_fn=compile_proposal, validate_rule_fn=validate_rule)

    def test_exact_real_b4_compiled(self):
        r = self.replay(0)
        self.assertEqual(r['b4_status'], 'candidate_executable_unverified')
        self.assertEqual(r['arm_decisions'], {'A':'admit','B':'admit','C':'admit'})
        self.assertFalse(r['semantic_accuracy_defined'])

    def test_exact_real_b4_unresolved(self):
        self.assertEqual(self.replay(1)['arm_decisions'], {'A':'block','B':'block','C':'block'})
        self.assertEqual(self.replay(1)['b4_status'], 'blocked_unresolved')

    def test_exact_real_b4_invalid(self):
        self.assertEqual(self.replay(2)['b4_status'], 'rejected_invalid')

    def test_unknown_metadata_abstains_B_C(self):
        self.assertEqual(self.replay(3)['arm_decisions'], {'A':'admit','B':'abstain','C':'abstain'})

    def test_context_gap_critical_limitation_is_detected(self):
        r = self.replay(4)
        self.assertEqual(r['context_key_gap'], ['site'])
        self.assertEqual(r['arm_decisions']['C'], 'admit')  # exposes issue to resolve, not approval
        self.assertFalse(r['study_ready'])

    def test_real_candidate_guard(self):
        bad = copy.deepcopy(FIXTURES[0])
        bad['classification'] = 'prospective_real_data'
        with self.assertRaisesRegex(AdapterError, 'Refusing real input'):
            toy_three_arm_replay(bad, compile_fn=compile_proposal, validate_rule_fn=validate_rule)

    def test_b4_called_once_for_all_arms(self):
        called = Mock(wraps=compile_proposal)
        toy_three_arm_replay(FIXTURES[0], compile_fn=called, validate_rule_fn=validate_rule)
        self.assertEqual(called.call_count, 1)

    def test_unrecognized_b4_status_fails_closed(self):
        class Fake:
            status = 'new_mystery'
            proposal_id = 'B134-TOY-COMPILED'
            rule = None
            def as_dict(self):
                return {'status':self.status,'semantic_verified':False,'data_errors_adjudicated':False}
        with self.assertRaisesRegex(AdapterError, 'Unrecognized B4 status'):
            normalize_b4_compilation(Fake(), FIXTURES[0]['proposal'], ['x','y'], validate_rule_fn=validate_rule)

    def test_compiler_output_identity_fails_closed(self):
        r = compile_proposal(FIXTURES[0]['proposal'], ['x','y'], {})
        r.rule['id'] = 'OTHER'
        with self.assertRaisesRegex(AdapterError, "identity differs"):
            normalize_b4_compilation(r, FIXTURES[0]['proposal'], ['x','y'], validate_rule_fn=validate_rule)

    def test_invalid_B3_rule_fails_closed(self):
        r = compile_proposal(FIXTURES[0]['proposal'], ['x','y'], {})
        r.rule['schema_version'] = 'invalid'
        with self.assertRaisesRegex(AdapterError, 'B3 rejected'):
            normalize_b4_compilation(r, FIXTURES[0]['proposal'], ['x','y'], validate_rule_fn=validate_rule)

    def test_blocked_with_executable_rule_fails_closed(self):
        r = compile_proposal(FIXTURES[1]['proposal'], ['x','y'], {})
        r.rule = {'bogus':'not allowed'}
        with self.assertRaisesRegex(AdapterError, 'contains a compiled rule'):
            normalize_b4_compilation(r, FIXTURES[1]['proposal'], ['x','y'], validate_rule_fn=validate_rule)

    def test_ambiguity_in_allowed_columns_fails_closed(self):
        r = compile_proposal(FIXTURES[0]['proposal'], ['x','y'], {})
        with self.assertRaisesRegex(AdapterError, 'unambiguous'):
            normalize_b4_compilation(r, FIXTURES[0]['proposal'], ['x','x'], validate_rule_fn=validate_rule)

    def test_hash_stability(self):
        self.assertEqual(self.replay(0)['fixture_input_sha256'], self.replay(0)['fixture_input_sha256'])

    def test_extra_policy_field_fails_closed(self):
        bad=copy.deepcopy(FIXTURES[0]); bad['policy_evidence']['gold_answer']='valid'
        with self.assertRaisesRegex(AdapterError, 'Policy evidence fields'):
            toy_three_arm_replay(bad, compile_fn=compile_proposal, validate_rule_fn=validate_rule)

    def test_source_not_downloaded_or_written(self):
        self.assertFalse(self.replay(0)['study_ready'])

if __name__ == '__main__':
    unittest.main()
