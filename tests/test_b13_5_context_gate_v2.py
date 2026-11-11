"""B13.5 regression tests; only B13.4 TOY candidates, no real sources."""
from __future__ import annotations
import copy, json, unittest
from pathlib import Path
from unittest.mock import Mock
from src.b13_5_context_gate_v2 import ContextPolicyError, validate_versioned_policy, replay_toy_v2
from src.rule_bridge import compile_proposal
from src.generic_verifier import validate_rule
ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT/'data/evaluation/b13_5_context_policy_v2.json').read_text())
OLD = json.loads((ROOT/'data/evaluation/b13_3_gate_policy_v1.json').read_text())
CASES = json.loads((ROOT/'data/evaluation/b13_4_compiler_contract_toys_v1.json').read_text())['fixtures']

class ContextGateV2Tests(unittest.TestCase):
    def run_case(self, index=0, candidate=None, *, compile_fn=compile_proposal, policy=POLICY, old=OLD):
        return replay_toy_v2(CASES[index] if candidate is None else candidate,
                   policy=policy, previous_policy=old, compile_fn=compile_fn,
                   validate_rule_fn=validate_rule)

    def test_v2_policy_ancestry(self):
        validate_versioned_policy(POLICY,OLD)
    def test_required_context_admission(self):
        x=self.run_case(0)
        self.assertEqual(x['v2_arm_decisions'], {'A':'admit','B':'admit','C':'admit'})
    def test_missing_compiled_context_blocks_C(self):
        x=self.run_case(4)
        self.assertEqual(x['previous_arm_decisions']['C'],'admit')
        self.assertEqual(x['v2_arm_decisions'], {'A':'admit','B':'admit','C':'block'})
        self.assertEqual(x['missing_required_context_keys'], ['site'])
    def test_original_toy_compiler_unresolved_blocks(self):
        self.assertEqual(self.run_case(1)['v2_arm_decisions'], {'A':'block','B':'block','C':'block'})
    def test_original_toy_compiler_invalid_blocks(self):
        self.assertEqual(self.run_case(2)['v2_arm_decisions'], {'A':'block','B':'block','C':'block'})
    def test_unknown_metadata_abstains(self):
        self.assertEqual(self.run_case(3)['v2_arm_decisions'], {'A':'admit','B':'abstain','C':'abstain'})
    def test_extra_unreviewed_context_abstains_C(self):
        x=copy.deepcopy(CASES[0])
        x['proposal']['context_keys']=['site','region']
        r=self.run_case(candidate=x)
        self.assertEqual(r['v2_arm_decisions'], {'A':'admit','B':'admit','C':'abstain'})
        self.assertEqual(r['unreviewed_extra_context_keys'], ['region'])
    def test_missing_context_evidence_abstains_C(self):
        x=copy.deepcopy(CASES[0])
        x['policy_evidence']['context_evidence']={}
        self.assertEqual(self.run_case(candidate=x)['v2_arm_decisions']['C'],'abstain')
    def test_context_contradiction_blocks_C(self):
        x=copy.deepcopy(CASES[0]);x['policy_evidence']['context_evidence']['site']='contradicted'
        self.assertEqual(self.run_case(candidate=x)['v2_arm_decisions']['C'],'block')
    def test_doc_unknown_abstains_C(self):
        x=copy.deepcopy(CASES[0]);x['policy_evidence']['documentary']={'status':'unknown','verified':False,'evidence_url':'','evidence_locator':''}
        self.assertEqual(self.run_case(candidate=x)['v2_arm_decisions']['C'],'abstain')
    def test_doc_contradiction_blocks_C(self):
        x=copy.deepcopy(CASES[0]);x['policy_evidence']['documentary']={'status':'contradicted','verified':False,'evidence_url':'','evidence_locator':''}
        self.assertEqual(self.run_case(candidate=x)['v2_arm_decisions']['C'],'block')
    def test_b4_called_once(self):
        called=Mock(wraps=compile_proposal)
        self.run_case(0,compile_fn=called)
        self.assertEqual(called.call_count,1)
    def test_policy_missing_required_key_not_bypassed_by_candidate(self):
        x=copy.deepcopy(CASES[4]);x['policy_evidence']['required_contexts']=[]
        with self.assertRaisesRegex(ContextPolicyError,'frozen source policy'):
            self.run_case(candidate=x)
    def test_policy_scope_tamper_rejected(self):
        p=copy.deepcopy(POLICY);p['frozen_toy_required_contexts_by_dataset']={'b134-toy': []}
        with self.assertRaises(ContextPolicyError):self.run_case(0,policy=p)
    def test_status_tamper_rejected(self):
        p=copy.deepcopy(POLICY);p['arm_C_rule_context_policy']['missing_predeclared_required_compiled_context']='admit'
        with self.assertRaises(ContextPolicyError):self.run_case(0,policy=p)
    def test_ancestry_tamper_rejected(self):
        p=copy.deepcopy(POLICY);p['policy_ancestry']['b13_3_policy_canonical_sha256']='0'*64
        with self.assertRaises(ContextPolicyError):self.run_case(0,policy=p)
    def test_original_policy_change_detected(self):
        old=copy.deepcopy(OLD);old['phase']='different'
        with self.assertRaises(ContextPolicyError):self.run_case(0,old=old)
    def test_unregistered_dataset_rejected(self):
        x=copy.deepcopy(CASES[0]);x['proposal']['dataset_id']='some-new-unseen-dataset'
        with self.assertRaisesRegex(ContextPolicyError,'not in predeclared'):
            self.run_case(candidate=x)
    def test_real_candidate_guard(self):
        x=copy.deepcopy(CASES[0]);x['classification']='real_candidate'
        with self.assertRaisesRegex(ContextPolicyError,'Refusing real'):
            self.run_case(candidate=x)
    def test_unknown_evidence_key_rejected(self):
        x=copy.deepcopy(CASES[0]);x['policy_evidence']['gold']='supported'
        with self.assertRaisesRegex(ContextPolicyError,'Unexpected'):
            self.run_case(candidate=x)
    def test_bad_documentary_evidence_rejected(self):
        x=copy.deepcopy(CASES[0]);x['policy_evidence']['documentary']['evidence_url']='http://example.org'
        with self.assertRaises(ContextPolicyError):self.run_case(candidate=x)
    def test_b3_compiled_rule_identity_guard(self):
        from src.rule_bridge import compile_proposal as original
        def evil(*args,**kwargs):
            r=original(*args,**kwargs);r.rule['id']='wrong';return r
        with self.assertRaises(ContextPolicyError):self.run_case(0,compile_fn=evil)
    def test_same_input_fingerprint_stable(self):
        self.assertEqual(self.run_case(0)['input_sha256'],self.run_case(0)['input_sha256'])
    def test_no_real_result_claims(self):
        for i in range(5):
            x=self.run_case(i)
            self.assertEqual(x['real_candidate_gate_runs'],0)
            self.assertEqual(x['adjudicated_gold_rules'],0)
            self.assertFalse(x['semantic_accuracy_defined'])
            self.assertFalse(x['study_ready'])
    def test_preflight_expected(self):
        from scripts.run_b13_5_context_preflight import run_preflight
        run_preflight()

if __name__ == '__main__':unittest.main()
