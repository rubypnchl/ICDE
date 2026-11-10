"""Unit and frozen-integration checks for the B10 retrospective experiment."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src import b10_matched_gate_pilot as b

class B10Tests(unittest.TestCase):
    def _report(self):
        return {
            'dataset_id':'nhanes-2017-2018-glu-j',
            'model_id_requested':'gpt-6-luna',
            'input_bundle':{'passages':[
                {'id':'P03','column':'LBXGLU','description':'Fasting Glucose (mg/dL)','source':'https://example.org/a'},
                {'id':'P04','column':'LBDGLUSI','description':'Fasting Glucose (mmol/L)','source':'https://example.org/a'},
            ]},
        }
    def _item(self):
        return {'id':'glucose_unit_conversion','assertions':[
            {'left':{'column':'LBDGLUSI'},'op':'eq','right':{'multiply':[{'column':'LBXGLU'},{'parameter':'k1'}]},'round_right':{'parameter':'t1'},'abs_tolerance':None}
        ],'when':None,'context_keys':[],'passage_ids':['P03','P04']}
    def _policy(self):
        item=self._item()
        p=self._report()['input_bundle']['passages']
        return {'binding_authorizations':[{'dataset_id':'nhanes-2017-2018-glu-j', 'rule_id':'glucose_unit_conversion',
            'expected_structure':{k:item.get(k) for k in ('assertions','when','context_keys','passage_ids')},
            'expected_evidence_passages':[dict(p[0],id='P03'),dict(p[1],id='P04')],
            'parameter_map':{'k1':'nhanes-2017-2018-glu-j:glucose_factor','t1':'nhanes-2017-2018-glu-j:glucose_rounding'}
        }]}
    def _registry(self):
        return {'nhanes-2017-2018-glu-j:glucose_factor':{'kind':'number','value':'0.05551'},
                'nhanes-2017-2018-glu-j:glucose_rounding':{'kind':'rounding','value':{'mode':'significant_figures','digits':3}}}
    def test_alias_exact_structure(self):
        out=b.fixed_curator_registrations(self._report(),self._item(),self._policy(),self._registry())
        self.assertEqual(out['nhanes-2017-2018-glu-j:k1']['value'],'0.05551')
        self.assertEqual(out['nhanes-2017-2018-glu-j:t1']['value']['digits'],3)
    def test_alias_mismatch_fails_closed(self):
        item=self._item();item['assertions'][0]['op']='gte'
        with self.assertRaisesRegex(b.B10Error,'structure mismatch'):
            b.fixed_curator_registrations(self._report(),item,self._policy(),self._registry())
    def test_evidence_passage_mismatch_fails_closed(self):
        r=self._report();r['input_bundle']['passages'][0]['description']='DIFFERENT'
        with self.assertRaisesRegex(b.B10Error,'documentary passage changed'):
            b.fixed_curator_registrations(r,self._item(),self._policy(),self._registry())
    def test_reject_cross_dataset_registration(self):
        pol=self._policy()
        pol['binding_authorizations'][0]['parameter_map']['k1']='different-dataset:glucose_factor'
        with self.assertRaisesRegex(b.B10Error,'Cross-dataset'):
            b.fixed_curator_registrations(self._report(),self._item(),pol,self._registry())
    def test_reject_ambiguous_grants(self):
        pol=self._policy();pol['binding_authorizations'].append(copy.deepcopy(pol['binding_authorizations'][0]))
        with self.assertRaisesRegex(b.B10Error,'Ambiguous'):
            b.fixed_curator_registrations(self._report(),self._item(),pol,self._registry())
    def test_registry_missing_fails_closed(self):
        with self.assertRaisesRegex(b.B10Error,'registration missing'):
            b.fixed_curator_registrations(self._report(),self._item(),self._policy(),{})
    def test_no_applicable_grant_produces_empty_registry(self):
        self.assertEqual(b.fixed_curator_registrations(self._report(),self._item(),{'binding_authorizations':[]},{}),{})
    def test_inputs_not_mutated_by_aliasing(self):
        raw=(self._report(),self._item(),self._policy(),self._registry())
        baseline=copy.deepcopy(raw)
        b.fixed_curator_registrations(*raw)
        self.assertEqual(raw,baseline)
    def test_summarize_separates_original_from_curated(self):
        d=[{'domain':'healthcare','original_compiler_status':'blocked_unresolved',
            'fixed_compiler_status':'candidate_executable_unverified',
            'evidence_review_status':'compiled_unverified_posthoc','gate_safe_to_deploy':False},
           {'domain':'finance','original_compiler_status':'candidate_executable_unverified',
            'fixed_compiler_status':'candidate_executable_unverified',
            'evidence_review_status':'blocked_applicability_or_scope','gate_safe_to_deploy':False}]
        s=b.summarize_decisions(d)
        self.assertEqual(s['candidate_proposals_present'],2)
        self.assertEqual(s['original_compiler_executable_without_curator_binding'],1)
        self.assertEqual(s['compiler_executable_with_fixed_curator_binding'],2)
        self.assertEqual(s['safe_for_deployment_according_to_existing_gate'],0)
        self.assertIsNone(s['rule_precision'])
    def test_summarize_refuses_incomplete_cohort(self):
        with self.assertRaises(b.B10Error):
            b.summarize_decisions([{'domain':'finance'}])
    def test_summarize_refuses_duplicate_domain(self):
        with self.assertRaises(b.B10Error):
            b.summarize_decisions([{'domain':'finance'},{'domain':'finance'}])
    def test_sha_file(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'x.txt';path.write_bytes(b'abc')
            self.assertEqual(b.sha_file(path),'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
    def test_json_object_validation(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'x.json';path.write_text('[1]')
            with self.assertRaises(b.B10Error):b.load_json(path)
    def test_canonicalization_does_not_change_original(self):
        # Imported into the installed ICDE repo, the real rule_bridge supplies PROPOSAL_VERSION.
        fake=types.ModuleType('src.rule_bridge');fake.PROPOSAL_VERSION='metaverify-proposal-v0.1'
        item=self._item();original=copy.deepcopy(item)
        with patch.dict(sys.modules,{'src.rule_bridge':fake}):
            x=b.proposal_to_b4(self._report(),item)
        self.assertEqual(item,original)
        self.assertNotIn('abs_tolerance',x['assertions'][0])
        self.assertNotIn('when',x)
        self.assertEqual(x['context_keys'],[])
    def test_actual_repository_preflight_when_available(self):
        if not (ROOT/b.BASELINE_PILOT).is_file():
            self.skipTest('Repository B7.1 inputs are only on the user machine')
        ready=b.preflight(ROOT)
        self.assertEqual(set(ready['reports']),{'finance','healthcare'})
    def test_actual_engine_run_when_available(self):
        if not (ROOT/b.BASELINE_PILOT).is_file():
            self.skipTest('Real B4/B5.1 engines are only on the user machine')
        summary,rows=b.run(ROOT)
        self.assertEqual(summary['results']['compiler_executable_with_fixed_curator_binding'],2)
        self.assertEqual(summary['results']['safe_for_deployment_according_to_existing_gate'],0)
        self.assertEqual(len(rows),2)

if __name__=='__main__': unittest.main()
