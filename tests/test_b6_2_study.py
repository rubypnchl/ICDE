"""B6.2 offline synthetic-fixture tests. They do NOT validate real defect labels."""
from __future__ import annotations

import copy
import csv
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from src import b6_2_study as b
from scripts import run_b6_1_real_baselines as b61
from scripts import run_b6_2_study as study


class PureStudyTests(unittest.TestCase):
    def setUp(self):
        self.man={"UDI":"1","TWF":"1","HDF":"0","PWF":"0","OSF":"0","RNF":"0","Machine failure":"1"}
        self.cyb={" Total Fwd Packets":"3"," Fwd Packet Length Min":"2"," Fwd Packet Length Mean":"2.5"," Fwd Packet Length Max":"4"}

    def test_man_satisfied(self):
        self.assertEqual(b.simple_rule_checker('manufacturing',self.man),'satisfied')

    def test_man_original_violation(self):
        row=self.man|{'Machine failure':'0'}
        self.assertEqual(b.simple_rule_checker('manufacturing',row),'violated')

    def test_man_nonapp(self):
        row=self.man|{'TWF':'0'}
        self.assertEqual(b.simple_rule_checker('manufacturing',row),'not_applicable')

    def test_man_missing_flag_abstain_even_other_true(self):
        row=self.man|{'HDF':''}
        self.assertEqual(b.simple_rule_checker('manufacturing',row),'abstained')

    def test_man_nonbinary_abstain(self):
        self.assertEqual(b.simple_rule_checker('manufacturing',self.man|{'RNF':'5'}),'abstained')

    def test_cyber_satisfied(self):
        self.assertEqual(b.simple_rule_checker('cybersecurity',self.cyb),'satisfied')

    def test_cyber_violated(self):
        self.assertEqual(b.simple_rule_checker('cybersecurity',self.cyb|{' Fwd Packet Length Mean':'8'}),'violated')

    def test_cyber_zero_count_not_applicable(self):
        self.assertEqual(b.simple_rule_checker('cybersecurity',self.cyb|{' Total Fwd Packets':'0',' Fwd Packet Length Mean':''}),'not_applicable')

    def test_cyber_noninteger_count_abstains(self):
        self.assertEqual(b.simple_rule_checker('cybersecurity',self.cyb|{' Total Fwd Packets':'1.4'}),'abstained')

    def test_cyber_nan_abstains(self):
        self.assertEqual(b.simple_rule_checker('cybersecurity',self.cyb|{' Fwd Packet Length Mean':'NaN'}),'abstained')

    def test_mutated_original_not_touched(self):
        before=self.man.copy()
        changed=b.injected_positive('manufacturing',self.man)
        self.assertEqual(self.man,before)
        self.assertEqual(changed['Machine failure'],'0')

    def test_cyber_mutated_mean_exceeds_max(self):
        changed=b.injected_positive('cybersecurity',self.cyb)
        self.assertEqual(changed[' Fwd Packet Length Mean'],'5')
        self.assertEqual(b.simple_rule_checker('cybersecurity',changed),'violated')

    def test_mutation_requires_clean_satisfying(self):
        with self.assertRaisesRegex(b.StudyError,'satisfying'):
            b.injected_positive('manufacturing',self.man|{'Machine failure':'0'})

    def test_score_sanity_not_independent_precision(self):
        report=b.score_binary([self.man]*3,'manufacturing',b.simple_rule_checker)
        self.assertEqual(report['confusion_by_rule_only'],{'TP':3,'FP':0,'TN':3,'FN':0,'unresolved':0})
        self.assertIn('Not independent',report['note'])

    def test_missing_and_nonapp_controls(self):
        self.assertEqual(b.simple_rule_checker('manufacturing',b.missing_control('manufacturing',self.man)),'abstained')
        self.assertEqual(b.simple_rule_checker('cybersecurity',b.out_of_scope_control('cybersecurity',self.cyb)),'not_applicable')

    def test_duplicate_udi_fails(self):
        with self.assertRaisesRegex(b.StudyError,'duplicate UDI'):
            b.analyze_rows('manufacturing',[self.man,self.man],quota=1,seed=2)

    def test_worksheet_votes_always_blank(self):
        r=b.worksheet_rows([{'UDI':'7','case':'forward_frozen_rule_violation','active_modes':'RNF'}],'f'*64)
        self.assertEqual(r[0]['reviewer_1_decision'],'')
        self.assertEqual(r[0]['reviewer_2_decision'],'')
        self.assertEqual(r[0]['adjudicated_decision'],'')

    def test_positional_csv_duplicate_unrelated_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.csv'
            p.write_text('A,B,Z,Z\n1,2,x,y\n',encoding='utf-8')
            rows=list(b.rows_by_position(p,['A','B']))
            self.assertEqual(rows,[{'A':'1','B':'2'}])

    def test_positional_csv_duplicate_required_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.csv'
            p.write_text('A,A,Z\n1,2,3\n',encoding='utf-8')
            with self.assertRaisesRegex(b.StudyError,'Duplicate required'):
                list(b.rows_by_position(p,['A']))

    def test_positional_csv_malformed_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.csv'
            p.write_text('A,B\n1\n',encoding='utf-8')
            with self.assertRaisesRegex(b.StudyError,'Malformed row'):
                list(b.rows_by_position(p,['A']))


class IntegrationStudyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        source_root=Path(__file__).resolve().parents[1]
        for filename in ('data/evaluation/b6_reference_catalogue.json','data/evaluation/b6_protocol_v1.json','data/evaluation/b6_2_design_v1.json'):
            p=self.root/filename
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes((source_root/filename).read_bytes())
        self.man_rows=[]
        for uid in range(1,76):
            self.man_rows.append([uid,1,0,0,0,0,1])
        for uid in range(76,94):
            self.man_rows.append([uid,0,0,0,0,1,0])
        for uid in range(94,103):
            self.man_rows.append([uid,0,0,0,0,0,1])
        for uid in range(103,113):
            self.man_rows.append([uid,0,0,0,0,0,0])
        self.cyb_rows=[[3,1,2,3]]*80+[[0,0,0,0]]*20
        self._csv('data/originals/ai4i/ai4i2020.csv', ['UDI',*b.REQUIRED['manufacturing']],self.man_rows)
        self._csv('data/samples/cic_ids2017/flows-50000.csv',b.REQUIRED['cybersecurity'],self.cyb_rows)
        source_files={"datasets":{
            "ai4i-2020":{"files":["data/originals/ai4i/ai4i2020.csv"]},
            "cic-ids2017":{"samples":["data/samples/cic_ids2017/flows-50000.csv"],"sampling":{"seed":2017,"records_sampled":100}}
        }}
        self._json('data/sources.json',source_files)
        spec=copy.deepcopy(b61.SPECS)
        spec['manufacturing']['expected_rows']=len(self.man_rows)
        spec['cybersecurity']['expected_rows']=len(self.cyb_rows)
        p=patch.dict(b61.SPECS,spec,clear=True)
        p.start();self.addCleanup(p.stop)
        baseline=b61.run(self.root,['manufacturing','cybersecurity'])
        self._json('data/evaluation/b6_1_real_baselines.json',baseline)

    def _json(self,rel,obj):
        f=self.root/rel;f.parent.mkdir(parents=True,exist_ok=True)
        f.write_text(json.dumps(obj,indent=2)+'\n',encoding='utf-8')

    def _csv(self,rel,columns,rows):
        f=self.root/rel;f.parent.mkdir(parents=True,exist_ok=True)
        with f.open('w',newline='',encoding='utf-8') as h:
            w=csv.writer(h);w.writerow(columns);w.writerows(rows)

    def test_preflight_matches_fixture(self):
        ready=b61.prepare(self.root,['manufacturing','cybersecurity'])
        study.check_design(self.root,study.load_json(self.root/study.DESIGN_PATH),study.load_json(self.root/study.B61_PATH),ready)

    def test_entire_pipeline_constructed_controls_and_27_blank_reviews(self):
        report,worksheet=study.run(self.root)
        self.assertEqual(len(worksheet),27)
        self.assertEqual(report['manufacturing_discrepancy_review']['case_counts'],{
            'forward_frozen_rule_violation':18,'reverse_exploratory_only_not_frozen_rule':9})
        self.assertEqual(report['manufacturing_discrepancy_review']['rnf_only_forward'],18)
        self.assertTrue(all(w['reviewer_1_decision']=='' for w in worksheet))
        for item in report['domains']:
            self.assertEqual(item['probe_counts_by_expected_status'],{'no_op':64,'injected_violation':64,'out_of_scope':64,'missing_field':64})
            self.assertEqual(item['simple_checker_constructed_case_metrics']['confusion_by_rule_only'],{
                'TP':64,'FP':0,'TN':64,'FN':0,'unresolved':0})
        self.assertFalse(report['domains'][0]['independent_source_review_complete'])

    def test_changed_source_hash_refused(self):
        with (self.root/'data/samples/cic_ids2017/flows-50000.csv').open('a',encoding='utf-8') as f:
            f.write('\n')
        with self.assertRaisesRegex(b.StudyError,'checksum'):
            study.run(self.root)

    def test_changed_reference_catalogue_refused(self):
        cat=study.load_json(self.root/'data/evaluation/b6_reference_catalogue.json')
        cat['catalogue_scope']='altered post hoc'
        self._json('data/evaluation/b6_reference_catalogue.json',cat)
        with self.assertRaisesRegex(b.StudyError,'catalogue differs'):
            study.run(self.root)

    def test_corrupt_b61_counts_detected(self):
        old=study.load_json(self.root/study.B61_PATH)
        old['results'][0]['counts']['satisfied']+=1
        self._json(study.B61_PATH,old)
        with self.assertRaisesRegex(b.StudyError,'DISAGREES'):
            study.run(self.root)

    def test_missing_review_material_wont_be_assumed_gold(self):
        result,_=study.run(self.root)
        self.assertEqual(result['reviewer_count_completed'],0)
        self.assertEqual(result['real_natural_defect_gold_labels'],0)
        self.assertEqual(result['final_gold_reference_rules'],0)

    def test_no_test_changes_original_files(self):
        orig=b61._sha256(self.root/'data/originals/ai4i/ai4i2020.csv')
        study.run(self.root)
        self.assertEqual(orig,b61._sha256(self.root/'data/originals/ai4i/ai4i2020.csv'))


if __name__=='__main__':
    unittest.main()
