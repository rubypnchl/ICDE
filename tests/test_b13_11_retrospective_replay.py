"""Offline research contract checks; real XPT results not available in this test suite."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.b13_11_retrospective_matched_replay import (
    ReplayError,load_inputs,validate_spec,make_candidate,diagnostic_admission,
    execute_pair,render_csv,render_tex,render_handover,exclusive_write_outputs)
from src.rule_bridge import compile_proposal

ROOT=Path(__file__).resolve().parents[1]
SPEC,R7,R8,R9,R10=load_inputs(ROOT)

class TestB1311(unittest.TestCase):
    def test_spec_valid(self):validate_spec(SPEC,R7,R8,R9,R10)
    def test_wrong_parent_hash_rejected(self):
        s=copy.deepcopy(SPEC);s['parent_b13_10_register_canonical_sha256']='0'*64
        with self.assertRaises(ReplayError):validate_spec(s,R7,R8,R9,R10)
    def test_fake_gold_rejected(self):
        s=copy.deepcopy(SPEC);s['independent_reference_judgments']=1
        with self.assertRaises(ReplayError):validate_spec(s,R7,R8,R9,R10)
    def test_fake_verified_evidence_rejected(self):
        s=copy.deepcopy(SPEC);s['documentary_independently_verified']=True
        with self.assertRaises(ReplayError):validate_spec(s,R7,R8,R9,R10)
    def test_fake_real_context_rejected(self):
        s=copy.deepcopy(SPEC);s['real_source_context_policy_independently_frozen']=True
        with self.assertRaises(ReplayError):validate_spec(s,R7,R8,R9,R10)
    def test_wrong_candidate_rejected(self):
        item=copy.deepcopy(R9['pairs'][0]);item['pair_id']='unsupported'
        with self.assertRaises(ReplayError):make_candidate(item,'nhanes_2015_2016_cycle',SPEC)
    def test_wrong_source_group_rejected(self):
        with self.assertRaises(ReplayError):make_candidate(R9['pairs'][0],'different_cycle',SPEC)
    def test_parameter_registry_linked(self):
        item=R9['pairs'][0];p,reg,cols=make_candidate(item,'nhanes_2015_2016_cycle',SPEC)
        self.assertEqual(reg[p['dataset_id']+':published_factor']['value'],item['factor'])
        self.assertEqual(cols,[item['left_column'],item['right_column']])
        self.assertEqual(p['context_keys'],['survey_cycle'])
    def test_actual_compiler_adapter_three_pairs(self):
        for item in R9['pairs']:
            with self.subTest(item=item['pair_id']):
                p,reg,cols=make_candidate(item,'nhanes_2015_2016_cycle',SPEC)
                compiled=compile_proposal(p,cols,reg)
                adapter,d=diagnostic_admission(p,compiled,cols,item,SPEC)
                self.assertEqual(adapter['compiler'],'compiled')
                self.assertEqual(d,{'A':'admit','B':'admit','C':'abstain'})
    def test_compiler_failure_does_not_create_results(self):
        item=R9['pairs'][0];p,reg,cols=make_candidate(item,'nhanes_2015_2016_cycle',SPEC)
        invalid=copy.deepcopy(p);invalid['context_keys']=[]
        compiled=compile_proposal(invalid,cols,reg)
        with self.assertRaises(ReplayError):diagnostic_admission(p,compiled,cols,item,SPEC)
    def test_readonly_example_execution(self):
        import pandas as pd
        item=R9['pairs'][0]
        # Test uses integers and deliberately inconsistent values; not clinical data.
        frame=pd.DataFrame({item['left_column']:[0,100,None],item['right_column']:[0,0,None]})
        result=execute_pair(frame,item,'nhanes_2015_2016_cycle',SPEC)
        self.assertEqual(result['record_count'],3)
        self.assertEqual(result['evaluated_records'],2)
        self.assertEqual(result['B4_compiler_calls'] if 'B4_compiler_calls' in result else result['b4_compiler_calls'],1)
        self.assertFalse(result['violations_mean_real_errors'])
    def test_render_outputs_no_gold_claim(self):
        stub={'pair_outcomes':[{'pair_id':'TOY_PAIR','source_id':'toy','source_group':'toy',
            'record_count':3,'evaluated_records':2,
            'b3_counts':{'satisfied':1,'violated':1,'abstained':1,'not_applicable':0},
            'A':'admit','B':'admit','C':'abstain'}],
            'data_source_receipts_sha256':{},'spec_sha256':'test','B4_compiler_invocations':1}
        self.assertIn('TOY_PAIR',render_csv(stub))
        self.assertIn('TOY',render_tex(stub))
        self.assertIn('no independent gold',render_handover(stub).lower())
    def test_exclusive_outputs_and_no_repo_writes(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'repo'; root.mkdir()
            cache=Path(t)/'cache';cache.mkdir()
            stub={'study_id':'toy','pair_outcomes':[],'data_source_receipts_sha256':{},
                  'spec_sha256':'test','B4_compiler_invocations':0}
            paths=exclusive_write_outputs(cache,root,stub)
            self.assertEqual(len(paths),4)
            # assert_external_cache() resolves the directory, which on Windows
            # may canonicalize a mapped H: network drive to its UNC path.
            # Compare canonical paths, not differently spelled aliases.
            self.assertTrue(all(x.is_file() and x.parent.resolve()==cache.resolve() for x in paths))
            self.assertFalse(any(root.iterdir()), 'Replay wrote inside the repository')
            with self.assertRaises(ReplayError):exclusive_write_outputs(cache,root,stub)
            self.assertFalse(any(root.iterdir()), 'A refused overwrite wrote inside the repository')

if __name__=='__main__':unittest.main()
