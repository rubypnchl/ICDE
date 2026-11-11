"""B13.10: artificial aggregate fixtures only; NEVER user-level source rows."""
from __future__ import annotations
import copy
import json
import tempfile
import unittest
from pathlib import Path
from src.b13_10_documentary_triage import (STUDY,TriageError,validate_register,
    summarize_existing_reports,assess_external_cache,exclusive_save)
from src.b13_8_source_schema_audit import canonical_sha,PINNED
from src.b13_7_source_acquisition import SourceError,sha256_file

ROOT=Path(__file__).resolve().parents[1]
def load(f): return json.loads((ROOT/'data/evaluation'/f).read_text(encoding='utf-8'))
REG=load('b13_10_evidence_applicability_register_v1.json')
SOURCES=load('b13_7_source_objects_v1.json')
P8=load('b13_8_schema_audit_plan_v1.json')
P9=load('b13_9_documented_pair_plan_v1.json')


def reports():
    r8={'study_id':'b13_8_read_only_source_schema_audit_v1',
        'classification':'exploratory_source_schema_characterization_only',
        'source_registry_canonical_sha256':canonical_sha(SOURCES),
        'b13_8_plan_canonical_sha256':canonical_sha(P8),
        'source_file_receipts':[{'source_id':sid,'source_group':a[3], 'sha256':a[1], 'size_bytes':a[2]} for sid,a in PINNED.items()],
        'healthcare':[{'source_id':'B13S-HLT-01','row_count':3191},
                      {'source_id':'B13S-HLT-02','row_count':8021}],
        'nhanes_cycle_join_inventory':{'raw_identifiers_emitted':False},
        'manufacturing':{'source_id':'B13S-MAN-01','row_count':1941,
                         'feature_column_count':27,'label_column_count':7,'total_column_count':34,
                         'label_positive_count_per_row':{str(x):(1941 if x==1 else 0) for x in range(8)}},
        'real_candidates_generated':0,'real_gate_executions':0,
        'independently_adjudicated_gold_rules':0,'source_semantic_eligibility_verified':False}
    pairs=[]
    for i,p in enumerate(P9['pairs']):
        n=[3191,3191,8021][i]
        paired=[2723,2699,7256][i]
        d={ 'rows_total':n,'paired_nonmissing':paired,'both_missing':n-paired,
            'only_left_missing':0,'only_right_missing':0,
            'absolute_residual_mmol_l':{'median':['0.000250','0.000240','0.002460'][i],
                    'p95':['0.0004700','0.0004800','0.00476000'][i],
                    'max':['0.000500','0.000500','0.005000'][i]},
            'precision_or_rounding_gold_established':False,
            'discrepancies_adjudicated_as_errors':0 }
        pairs.append({'pair_id':p['pair_id'],'source_id':p['source_id'],
                      'published_factor':p['factor'],'documentation_url':p['documentation_url'],
                      'units':p['units'],'interpretation':'recorded_value_consistency_only_not_gold',
                      'aggregates':d})
    r9={'study_id':P9['study_id'],
        'classification':'retrospective_documented_conversion_descriptive_audit_not_gold',
        'b13_9_plan_canonical_sha256':canonical_sha(P9),
        'b13_8_aggregate_sha256':'a'*64,
        'source_group':'nhanes_2015_2016_cycle','conversion_pairs':pairs,
        'source_eligibility_confirmed':False,'fitted_tolerance_or_rounding':False,
        'cross_file_clinical_join_performed':False,
        'real_candidate_admission_runs':0,'independently_adjudicated_gold_rules':0}
    return r8,r9


def run(r8=None,r9=None,reg=None,h='a'*64):
    if r8 is None or r9 is None:
        a,b=reports()
        if r8 is None:r8=a
        if r9 is None:r9=b
    return summarize_existing_reports(reg or REG,SOURCES,P8,P9,r8,r9,
                                      b138_sha256=h,b139_sha256='b'*64)

class TriageTests(unittest.TestCase):
    def test_register_valid(self): validate_register(REG,SOURCES,P9)
    def test_four_items(self): self.assertEqual(len(REG['evidence_items']),4)
    def test_prior_exposure_required(self):
        v=copy.deepcopy(REG);v['previously_exposed_documents']=False
        with self.assertRaises(TriageError):validate_register(v,SOURCES,P9)
    def test_no_fake_reviewer(self):
        v=copy.deepcopy(REG);v['independent_review_performed']=True
        with self.assertRaises(TriageError):validate_register(v,SOURCES,P9)
    def test_cannot_claim_frozen_real_context(self):
        v=copy.deepcopy(REG);v['context_policy_frozen_for_real_source']=True
        with self.assertRaises(TriageError):validate_register(v,SOURCES,P9)
    def test_parent_plan_hash_tamper(self):
        v=copy.deepcopy(REG);v['parent_b13_9_plan_canonical_sha256']='0'*64
        with self.assertRaises(TriageError):validate_register(v,SOURCES,P9)
    def test_parent_registry_hash_tamper(self):
        v=copy.deepcopy(REG);v['parent_b13_7_registry_canonical_sha256']='0'*64
        with self.assertRaises(TriageError):validate_register(v,SOURCES,P9)
    def test_factor_tamper(self):
        v=copy.deepcopy(REG);v['evidence_items'][0]['documented_factor']='1.3'
        with self.assertRaises(TriageError):validate_register(v,SOURCES,P9)
    def test_documentation_url_tamper(self):
        v=copy.deepcopy(REG);v['evidence_items'][0]['documentation_url']='https://example.org'
        with self.assertRaises(TriageError):validate_register(v,SOURCES,P9)
    def test_onehot_as_axiom_tamper(self):
        v=copy.deepcopy(REG);v['evidence_items'][3]['documentary_status']='explicitly_required_onehot'
        with self.assertRaises(TriageError):validate_register(v,SOURCES,P9)
    def test_evidence_identity_tamper(self):
        v=copy.deepcopy(REG);v['evidence_items'][1]['item_id']='UNKNOWN'
        with self.assertRaises(TriageError):validate_register(v,SOURCES,P9)
    def test_valid_summary_no_gold(self):
        q=run();self.assertEqual(q['source_relationships_screened'],4)
        self.assertEqual(q['eligible_confirmatory_relationships'],0)
        self.assertEqual(q['evidence_items'][3]['observed_exactly_one_positive_label_rows'],1941)
        self.assertTrue(all(not x['confirmatory_accuracy_denominator_eligible'] for x in q['evidence_items']))
    def test_no_private_ids_in_summary(self):
        q=run();data=json.dumps(q)
        self.assertNotIn('participant_record',data)
        self.assertNotIn('respondent_sequence_number',data)
        self.assertNotIn('participant_values',data)
    def test_parent_report_changed(self):
        a,b=reports();b['b13_8_aggregate_sha256']='f'*64
        with self.assertRaises(TriageError):run(a,b)
    def test_gold_falsehood_rejected(self):
        a,b=reports();b['independently_adjudicated_gold_rules']=1
        with self.assertRaises(TriageError):run(a,b)
    def test_rounded_gold_falsehood_rejected(self):
        a,b=reports();b['conversion_pairs'][0]['aggregates']['precision_or_rounding_gold_established']=True
        with self.assertRaises(TriageError):run(a,b)
    def test_pair_missing_rejected(self):
        a,b=reports();b['conversion_pairs'].pop()
        with self.assertRaises(TriageError):run(a,b)
    def test_wrong_factor_in_report_rejected(self):
        a,b=reports();b['conversion_pairs'][2]['published_factor']='0.1'
        with self.assertRaises(TriageError):run(a,b)
    def test_mismatched_missingness_counts_rejected(self):
        a,b=reports();b['conversion_pairs'][0]['aggregates']['paired_nonmissing']=3000
        with self.assertRaises(TriageError):run(a,b)
    def test_negative_residual_rejected(self):
        a,b=reports();b['conversion_pairs'][0]['aggregates']['absolute_residual_mmol_l']['max']='-1'
        with self.assertRaises(TriageError):run(a,b)
    def test_bad_residual_order_rejected(self):
        a,b=reports();b['conversion_pairs'][1]['aggregates']['absolute_residual_mmol_l']['p95']='1'
        with self.assertRaises(TriageError):run(a,b)
    def test_manufacturing_histogram_mismatch_rejected(self):
        a,b=reports();a['manufacturing']['label_positive_count_per_row']['1']=1940
        with self.assertRaises(TriageError):run(a,b)
    def test_observed_onehot_not_semantic_gold(self):
        a,b=reports();a['manufacturing']['label_positive_count_per_row']['1']=1940
        a['manufacturing']['label_positive_count_per_row']['0']=1
        q=run(a,b)
        self.assertEqual(q['evidence_items'][3]['observed_exactly_one_positive_label_rows'],1940)
        self.assertFalse(q['evidence_items'][3]['confirmatory_accuracy_denominator_eligible'])
    def test_report_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            cache=base/'cache';cache.mkdir()
            x=exclusive_save(cache,base/'repo',{'study_id':STUDY})
            self.assertTrue(x.exists())
            with self.assertRaises(FileExistsError):exclusive_save(cache,base/'repo',{})
    def test_report_cache_cannot_be_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            with self.assertRaises(SourceError):exclusive_save(base/'repo'/'cache',base/'repo',{})
    def test_valid_external_aggregate_assessment(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            cache=base/'cache';cache.mkdir()
            a,b=reports()
            p8=cache/'B13_8_source_schema_audit_v1.json'
            p8.write_text(json.dumps(a),encoding='utf-8')
            b['b13_8_aggregate_sha256']=sha256_file(p8)
            p9=cache/'B13_9_documented_pair_consistency_v1.json'
            p9.write_text(json.dumps(b),encoding='utf-8')
            out=assess_external_cache(cache,base/'repo',REG,SOURCES,P8,P9)
            self.assertEqual(out['parent_B13_9_report_sha256'],sha256_file(p9))
            self.assertEqual(out['real_candidate_gate_runs'],0)

if __name__=='__main__':unittest.main()
