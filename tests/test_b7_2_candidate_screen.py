"""B7.2 offline fixture tests. No real-source or scientific accuracy claims."""
from __future__ import annotations
import copy
import csv
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import b7_2_candidate_screen as S

class CandidateScreenTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = json.loads((ROOT/'data/evaluation/b7_2_plan_v1.json').read_text())
        self._write('data/evaluation/b7_2_plan_v1.json',self.plan)
        self._write('data/evaluation/b7_1_pilot_comparison.json', {
            'study_id':'b7_1_saved_pilot_opportunity_audit_v1',
            'independent_gold_rule_count':0,'published_method_reproduction':False})
        self.fields = [
            ('Glucose mg', 'Fasting Glucose (mg/dL)'),
            ('Glucose SI', 'Fasting Glucose (mmol/L)'),
            ('Flow Packet Min', ''),
            ('Flow Packet Max', ''),
            ('Other', 'Other different numeric field'),
            ('Failure', ''),
        ]
        for domain, path in S.PATHS.items():
            self._metadata(domain,path)
    def _write(self,rel,obj):
        path=self.root/rel
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(obj),encoding='utf-8')
    def _metadata(self,domain,rel,duplicate=False):
        cols=[{
            'name':name,'type':{'value':'number'},
            'description':{'value':desc,'status':'documented' if desc else 'unknown',
                           'source':'https://example.org/docs' if desc else None}
        } for name,desc in self.fields]
        if duplicate: cols.append(copy.deepcopy(cols[0]))
        self._write(rel, {'dataset':{'id':'fixture-'+domain},'columns':cols})
    def test_preflight_four_datasets(self):
        inputs=S.extract_metadata(self.root,self.plan)
        self.assertEqual(set(inputs['datasets']),set(S.DOMAINS))
    def test_known_paired_unit(self):
        x={'name':'Glucose mg','description':'Fasting Glucose (mg/dL)'}
        y={'name':'Glucose SI','description':'Fasting Glucose (mmol/L)'}
        value,kind=S.score_pair(x,y)
        self.assertGreaterEqual(value,4)
        self.assertEqual(kind,'same_measurement_different_unit_hypothesis')
    def test_not_unit_pair_with_same_unit(self):
        x={'name':'x','description':'Glucose (mg/dL)'}
        y={'name':'y','description':'Glucose (mg/dL)'}
        self.assertNotEqual(S.score_pair(x,y)[1],'same_measurement_different_unit_hypothesis')
    def test_name_masking(self):
        a={'name':'Glucose mg','description':'Fasting Glucose (mg/dL)'}
        b={'name':'Glucose SI','description':'Fasting Glucose (mmol/L)'}
        self.assertLess(S.score_pair(a,b,mask_descriptions=True)[0],S.score_pair(a,b)[0])
    def test_matched_budgets(self):
        rows,info=S.choose_candidates('healthcare',S.extract_metadata(self.root,self.plan)['datasets']['healthcare'],budget=12,seed=10)
        self.assertEqual(CounterOf(rows,'arm'), {'token_similarity_rank':12,'seeded_uniform_random_pairs':12})
        self.assertEqual(info['numeric_pair_universe'],15)
    def test_deterministic_ranking(self):
        first=S.generate(self.root)
        second=S.generate(self.root)
        self.assertEqual(first[1],second[1])
        self.assertEqual(first[2],second[2])
        self.assertEqual(first[0]['source_metadata_hashes'],second[0]['source_metadata_hashes'])
    def test_no_gold(self):
        result,rows,review=S.generate(self.root)
        self.assertEqual(result['independently_qualified_gold_constraints'],0)
        self.assertIsNone(result['semantic_precision'])
        self.assertTrue(all(r['is_executable_constraint']=='false' for r in rows))
        self.assertTrue(all(r['reviewer_id']==r['relationship_decision']=='' for r in review))
    def test_blinded_review_dedupes_pair_in_both_arms(self):
        result,rows,review=S.generate(self.root)
        self.assertEqual(len(review),len({(r['domain'],r['candidate_pair_id']) for r in rows}))
    def test_description_missing_retained_not_invented(self):
        _, rows, _=S.generate(self.root)
        vals=[r for r in rows if r['left_column']=='Failure']
        self.assertTrue(vals)
        self.assertTrue(all(r['left_description']=='' for r in vals))
    def test_duplicate_name_excluded_without_silent_overwrite(self):
        self._metadata('cybersecurity',S.PATHS['cybersecurity'],duplicate=True)
        data=S.extract_metadata(self.root,self.plan)['datasets']['cybersecurity']
        self.assertEqual(data['duplicate_column_names_excluded'],['Glucose mg'])
        self.assertEqual(len(data['numeric_columns']),5)
    def test_bad_plan_rejected(self):
        bad=copy.deepcopy(self.plan);bad['max_candidates_per_method_per_domain']=100
        with self.assertRaisesRegex(S.ScreenError,'plan differs'):
            S.extract_metadata(self.root,bad)
    def test_b7_1_gold_tampering_rejected(self):
        self._write('data/evaluation/b7_1_pilot_comparison.json',{
            'study_id':'b7_1_saved_pilot_opportunity_audit_v1',
            'independent_gold_rule_count':1,'published_method_reproduction':False})
        with self.assertRaisesRegex(S.ScreenError,'B7.1 historical'):
            S.generate(self.root)
    def test_missing_source_rejected(self):
        (self.root/S.PATHS['finance']).unlink()
        with self.assertRaises(FileNotFoundError):
            S.generate(self.root)
    def test_no_overwrite_results(self):
        S.save_results(self.root)
        with self.assertRaisesRegex(S.ScreenError,'refusing overwrite'):
            S.save_results(self.root)
    def test_output_csv_and_json(self):
        S.save_results(self.root)
        dest=self.root/'data/evaluation/b7_2_candidate_screen'
        self.assertEqual(set(p.name for p in dest.iterdir()),{'rankings.csv','blind_review_unfilled.csv','summary.json','README.md'})
        with (dest/'blind_review_unfilled.csv').open(newline='',encoding='utf-8') as file:
            rows=list(csv.DictReader(file))
        self.assertGreater(len(rows),0)
        self.assertTrue(all(not r['relationship_decision'] for r in rows))
    def test_all_candidates_in_numeric_pair_universe(self):
        result, rows, reviews = S.generate(self.root)
        for r in rows:
            self.assertNotEqual(r['left_column'],r['right_column'])
            self.assertLess(r['left_column'],r['right_column'])
            self.assertIn(r['domain'],S.DOMAINS)
    def test_pair_id_preserves_spaces(self):
        self.assertNotEqual(S.pair_id('cybersecurity',' A','B'),S.pair_id('cybersecurity','A','B'))
    def test_different_seed_changes_random_when_pool_big(self):
        data=S.extract_metadata(self.root,self.plan)['datasets']['finance']
        a,_=S.choose_candidates('finance',data,budget=5,seed=1)
        b,_=S.choose_candidates('finance',data,budget=5,seed=2)
        self.assertNotEqual([r['candidate_pair_id'] for r in a if r['arm']=='seeded_uniform_random_pairs'],
                            [r['candidate_pair_id'] for r in b if r['arm']=='seeded_uniform_random_pairs'])
    def test_source_hash_records_metadata_not_raw(self):
        result,_,_=S.generate(self.root)
        self.assertEqual(result['raw_data_rows_read'],0)
        self.assertEqual(len(result['source_metadata_hashes']['finance']),64)


def CounterOf(rows, key):
    from collections import Counter
    return dict(Counter(r[key] for r in rows))

if __name__=='__main__': unittest.main()
