"""Offline tests of B13.12 numerical-only sensitivity; no original public data."""
from __future__ import annotations
import copy
import json
import tempfile
from pathlib import Path
import unittest
from decimal import Decimal
from src.b13_12_fixed_grid_sensitivity import (
    STUDY, OUTPUTS,SensitivityError, validate_plan, make_tolerance_compilation,
    execute_grid,render_tex,render_handover,exclusive_save)
from src.b13_11_retrospective_matched_replay import load_inputs
from src.generic_verifier import evaluate_rows

ROOT=Path(__file__).resolve().parents[1]
SPEC,B137,B138,B139,B1310=load_inputs(ROOT)
PLAN=json.loads((ROOT/'data/evaluation/b13_12_sensitivity_spec_v1.json').read_text())

class FakeFrame:
    def __init__(self,columns): self.data=columns;self.columns=list(columns)
    def __len__(self):return len(next(iter(self.data.values())))
    def __getitem__(self,key):return self.data[key]

class Tests(unittest.TestCase):
    def test_plan_good(self):validate_plan(PLAN,B139)
    def test_no_real_claim(self):
        self.assertFalse(PLAN['numerical_gate_effect_claimed'])
        self.assertFalse(PLAN['independent_precision_verified'])
        self.assertEqual(PLAN['independent_gold_rules'],0)
    def test_grid_pinned(self):
        p=copy.deepcopy(PLAN);p['tolerance_grid_mmol_l'].append('1')
        with self.assertRaises(SensitivityError):validate_plan(p,B139)
    def test_grid_tamper(self):
        p=copy.deepcopy(PLAN);p['tolerance_grid_mmol_l'][0]='0.001'
        with self.assertRaises(SensitivityError):validate_plan(p,B139)
    def test_gold_tamper(self):
        p=copy.deepcopy(PLAN);p['independent_gold_rules']=1
        with self.assertRaises(SensitivityError):validate_plan(p,B139)
    def test_truth_tamper(self):
        p=copy.deepcopy(PLAN);p['independent_precision_verified']=True
        with self.assertRaises(SensitivityError):validate_plan(p,B139)
    def test_phase_tamper(self):
        p=copy.deepcopy(PLAN);p['phase']='confirmatory'
        with self.assertRaises(SensitivityError):validate_plan(p,B139)
    def test_pair_list_tamper(self):
        p=copy.deepcopy(B139);p['pairs']=p['pairs'][:2]
        with self.assertRaises(SensitivityError):validate_plan(PLAN,p)
    def test_rule_compiled_same_columns(self):
        for p in B139['pairs']:
            rule,cols=make_tolerance_compilation(p,'nhanes_2015_2016_cycle',SPEC,'0.0005')
            self.assertEqual(rule['context_keys'],['survey_cycle'])
            self.assertEqual(rule['assertions'][0]['abs_tolerance'],'0.0005')
            self.assertEqual(len(cols),2)
    def test_unknown_threshold_rejected(self):
        with self.assertRaises(SensitivityError):
            make_tolerance_compilation(B139['pairs'][0],'nhanes_2015_2016_cycle',SPEC,'0.0006')
    def test_identity_compilation(self):
        rule,_=make_tolerance_compilation(B139['pairs'][0],'nhanes_2015_2016_cycle',SPEC,'0.005')
        self.assertIn('TRIGLY_TR_UNIT',rule['id'])
        self.assertTrue(rule['id'].endswith('sens_0p005'))
    def test_tolerance_changes_numeric_outcome_only(self):
        pair=B139['pairs'][0]
        # 100 mg/dL * 0.01129 = 1.129; observed 1.130 is 0.001 off.
        frame=FakeFrame({'LBXTR':[100,100,None], 'LBDTRSI':[1.129,1.130,1.129]})
        rows=execute_grid(frame,pair,SPEC,'nhanes_2015_2016_cycle')
        self.assertEqual(rows[0]['satisfied'],1)
        self.assertEqual(rows[0]['mismatched'],1)
        self.assertEqual(rows[0]['abstained'],1)
        self.assertEqual(rows[1]['satisfied'],2)
        self.assertEqual(rows[1]['mismatched'],0)
    def test_renderer_no_gold(self):
        report={'pairs':[{'pair_id':'TRIGLY_TR_UNIT', 'grid':[{'tolerance_mmol_l':'0.0005','satisfied':2,'mismatched':3,'abstained':1}]}]}
        tex=render_tex(report);md=render_handover(report)
        self.assertIn('TRIGLY\\_TR\\_UNIT',tex)
        self.assertIn('not independently justified',md)
        self.assertIn('B3 match',md)
    def test_external_cache_only(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'repo';root.mkdir()
            with self.assertRaises(Exception):exclusive_save(root/'cache',root,{'pairs':[]})
    def test_exclusive_save(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'repo';root.mkdir()
            cache=Path(t)/'cache';cache.mkdir()
            report={'pairs':[]}
            paths=exclusive_save(cache,root,report)
            self.assertEqual(len(paths),3)
            self.assertTrue(all(p.resolve().parent==cache.resolve() for p in paths))
            with self.assertRaises(SensitivityError):exclusive_save(cache,root,report)
    def test_no_raw_values_in_result_schema(self):
        report={'pairs':[{'pair_id':'TRIGLY_TR_UNIT','grid':[{'tolerance_mmol_l':'0.0005','satisfied':2,'mismatched':3,'abstained':1}]}]}
        output=render_handover(report)
        self.assertNotIn('SEQN',output)
        self.assertNotIn('LBXTR',output)

if __name__=='__main__': unittest.main()
