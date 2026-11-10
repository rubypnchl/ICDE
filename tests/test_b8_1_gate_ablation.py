import copy
import unittest
from src.b8_1_gate_ablation import analyze,AuditError,PINNED_TARGET


def examples():
    luna={
        'study_id':'b7_1_saved_pilot_opportunity_audit_v1','opportunities_total':2,
        'results':[
            {'domain':'finance','saved_luna_pilot':{'hypothesis_count':1,'proposals':[{'id':'balance_sheet_equation','b4_status':'candidate_executable_unverified','b5_1_posthoc_status':'blocked_applicability_or_scope'}]}},
            {'domain':'healthcare','saved_luna_pilot':{'hypothesis_count':1,'proposals':[{'id':'glucose_unit_conversion','b4_status':'blocked_unresolved','b5_1_posthoc_status':'compiled_unverified_posthoc'}]}},
        ]}
    posthoc={'stage':'B5.1','model_reports':[]}
    for d,pid,original,status,prov in [
        ('finance','balance_sheet_equation','candidate_executable_unverified','blocked_applicability_or_scope',{}),
        ('healthcare','glucose_unit_conversion','blocked_unresolved','compiled_unverified_posthoc',{'t1':{'origin':'empirical_same_dataset'}}),
    ]:
        posthoc['model_reports'].append({'domain':d,'decisions':[{'proposal_id':pid,'status':status,
         'b5_original_compilation_status':original,'safe_to_deploy_as_integrity_constraint':False,
         'semantically_verified':False,'independently_validated':False,
         'compiled_rule':{'assertions':[1]} if d=='healthcare' else None,
         'parameter_provenance':prov}]})
    ai=[]
    for i in range(17):
        ai.append({'rule':{'id':f'ai4i-{i}','rule_type':'conditional_range'},
                   'heldout':{'decision':'abstain','applicable_rows':99,'violations':0},
                   'documented_evidence':{'status':'not_found'}})
    sec=[]
    for i in range(10):
        sec.append({'rule':{'id':f'sec-{i}','rule_type':'cross_field'},
                   'heldout':{'decision':'abstain','applicable_rows':99,'violations':0},
                   'documented_evidence':{'status':'not_found'}})
    sec.append({'rule':{'id':PINNED_TARGET,'rule_type':'cross_field',
               'assertion':{'term_columns':['Liabilities [USD]','StockholdersEquity [USD]']}},
                'heldout':{'decision':'documented_support','applicable_rows':41,'violations':0},
                'documented_evidence':{'status':'documented'}})
    legacy={'datasets':{'ai4i-2020':{'candidates':ai,'candidate_count':17,'decision_counts':{'abstain':17,'documented_support':0,'documented_conflict':0}},
                        'sec-companyfacts-320193':{'candidates':sec,'candidate_count':11,'decision_counts':{'abstain':10,'documented_support':1,'documented_conflict':0}}}}
    context={'baseline_commit':'40a7ddb',
             'legacy_supported_rule':{'rule_id':PINNED_TARGET,'recorded_decision':'documented_support','recorded_heldout_rows':41,'recorded_violations':0},
             'conservative_saved_candidate_decisions':{'without_new_context_proof':'abstain_context_unsubstantiated','with_frozen_B6_universal_exclusion':'blocked_unqualified_universal_identity'}}
    catalogue={'entries':[{'id':'B6-FIN-002','status':'excluded','scoring_eligible':False}]}
    return (luna,posthoc,legacy,context,catalogue)

class TestAblation(unittest.TestCase):
    def test_legacy_28_and_saved_two_cohorts_separate(self):
        d=analyze(*examples())
        self.assertEqual(d['llm_pilot']['candidates'],2)
        self.assertEqual(d['llm_pilot']['original_compiler_executable_unverified'],1)
        self.assertEqual(d['llm_pilot']['posthoc_curator_assisted_compiled_unverified'],1)
        self.assertEqual(d['legacy_data_only']['candidates'],28)
        self.assertEqual(d['legacy_data_only']['apparent_positive_decisions_legacy'],1)
        self.assertEqual(d['legacy_data_only']['changed_candidates'],1)
        self.assertEqual(d['legacy_data_only']['strict_context_plus_frozen_catalogue_counts']['blocked_unqualified_universal_identity'],1)
        self.assertEqual(d['legacy_data_only']['strict_context_plus_frozen_catalogue_counts']['abstain_no_documentary_rule_support'],27)
        self.assertIsNone(d['rule_precision'])
        self.assertFalse(d['published_baseline_reproduced'])
    def test_missing_candidate_rejected(self):
        xs=list(examples());xs[2]['datasets']['ai4i-2020']['candidates'].pop()
        with self.assertRaises(AuditError):analyze(*xs)
    def test_duplicate_candidate_rejected(self):
        xs=list(examples());xs[2]['datasets']['ai4i-2020']['candidates'][0]['rule']['id']='ai4i-1'
        with self.assertRaises(AuditError):analyze(*xs)
    def test_unjustified_positive_rejected(self):
        xs=list(examples());xs[2]['datasets']['ai4i-2020']['candidates'][0]['heldout']['decision']='documented_support'
        xs[2]['datasets']['ai4i-2020']['decision_counts']['documented_support']=1
        xs[2]['datasets']['ai4i-2020']['decision_counts']['abstain']=16
        with self.assertRaises(AuditError):analyze(*xs)
    def test_changed_finance_target_rejected(self):
        xs=list(examples());xs[3]['legacy_supported_rule']['recorded_heldout_rows']=42
        with self.assertRaises(AuditError):analyze(*xs)
    def test_compiler_stage_change_rejected(self):
        xs=list(examples());xs[0]['results'][0]['saved_luna_pilot']['proposals'][0]['b4_status']='blocked_unresolved'
        with self.assertRaises(AuditError):analyze(*xs)
    def test_unsafe_claim_rejected(self):
        xs=list(examples());xs[1]['model_reports'][0]['decisions'][0]['safe_to_deploy_as_integrity_constraint']=True
        with self.assertRaises(AuditError):analyze(*xs)
    def test_posthoc_precision_lineage_required(self):
        xs=list(examples());xs[1]['model_reports'][1]['decisions'][0]['parameter_provenance']={}
        with self.assertRaises(AuditError):analyze(*xs)
    def test_frozen_catalogue_exclusion_required(self):
        xs=list(examples());xs[4]['entries'][0]['status']='provisional_source_supported'
        with self.assertRaises(AuditError):analyze(*xs)
    def test_unknown_context_decision_rejected(self):
        xs=list(examples());xs[3]['conservative_saved_candidate_decisions']['without_new_context_proof']='documented_support'
        with self.assertRaises(AuditError):analyze(*xs)

if __name__=='__main__':unittest.main()
