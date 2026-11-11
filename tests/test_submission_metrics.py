"""Fixture-backed validation of descriptive metrics and no-gold safeguards."""
import copy
import unittest
from scripts.summarize_submission_metrics import calculate, MetricsError

PAIRS = {
    'TRIGLY_TR_UNIT': (3191, 2723, 16, 2707, 468, 2723, 2723, 1386),
    'TRIGLY_LDL_UNIT': (3191, 2699, 50, 2649, 492, 2699, 2699, 1369),
    'TCHOL_TC_UNIT': (8021, 7256, 0, 7256, 765, 779, 7256, 3657),
}


def fixture():
    b11 = {'study_id':'b13_11_real_xpt_matched_compiler_diagnostic_v1', 'gold_rules':0,
           'independent_documentary_reviews':0, 'source_clusters':1,
           'pair_candidates_hand_curated':3, 'exact_equality_mismatch_counts_are_data_errors':False,
           'pair_outcomes':[]}
    b12 = {'study_id':'b13_12_fixed_grid_precision_sensitivity_v1','gold_rules':0,
           'thresholds_independently_justified':False,'pairs':[]}
    p = {'study_id':'metaverify_submission_day_controlled_precision_perturbation_v1',
         'source_clusters':1,'independent_semantic_gold':0,
         'candidate_admission_accuracy_measured':False,'cells':[]}
    baseline = {'study_id':'metaverify_matched_numeric_coefficient_baselines_v1',
        'source_group_count':1,'independent_semantic_gold':0,
        'real_sota_guardrail_run':False,'real_sota_autotest_run':False,'pairs':[],'cells':[]}
    for pid,(total,n,sat,vio,abst,small,large,test) in PAIRS.items():
        c = {'satisfied':sat,'violated':vio,'abstained':abst,'not_applicable':0}
        b11['pair_outcomes'].append({'pair_id':pid,'record_count':total,'evaluated_records':n,'b3_counts':c})
        grid=[]
        for tol in ('0.0005','0.005','0.01','0.05','0.1'):
            good=small if tol=='0.0005' else large
            grid.append({'tolerance_mmol_l':tol,'satisfied':good,'mismatched':n-good,'abstained':abst})
        b12['pairs'].append({'pair_id':pid,'paired_nonmissing':n,'previous_exact_counts':c,'grid':grid})
        for tol in ('0.0005','0.005'):
            good=small if tol=='0.0005' else large
            for shift in ('0.001','0.005','0.01'):
                flagged = good if shift=='0.01' else 0
                original={'satisfied':good,'violated':n-good,'abstained':abst}
                shifted={'satisfied':good-flagged,'violated':n-good+flagged,'abstained':abst}
                p['cells'].append({'pair_id':pid,'tolerance_mmol_l':tol,
                                  'added_to_recorded_right_mmol_l':shift,
                                  'paired_nonmissing':n,'unchanged':original,'shifted':shifted,
                                  'satisfied_to_violated':flagged,'violated_to_satisfied':0})
        baseline['pairs'].append({'pair_id':pid,'test_rows':test+6,'test_nonmissing':test})
        for method in ('documented_cdc_factor','train_median_ratio','train_least_squares'):
            for tol in ('0.0005','0.005'):
                for shift in ('-0.01','-0.005','-0.001','0.001','0.005','0.01'):
                    old=8 if (pid=='TCHOL_TC_UNIT' and method=='train_median_ratio' and tol=='0.005') else 0
                    newly=test-old if shift=='0.01' else 0
                    baseline['cells'].append({'pair_id':pid,'method':method,'tolerance_mmol_l':tol,
                        'synthetic_shift_mmol_l':shift,'test_nonmissing':test,'test_abstained':6,
                        'unmodified_satisfied':test-old,'unmodified_violated':old,
                        'modified_violated':old+newly,'newly_flagged':newly,'violated_to_satisfied':0})
    scenarios = [
        ('observed_baseline','real_unqualified','admit','admit','abstain'),
        ('metadata_unknown','controlled_negative','admit','abstain','abstain'),
        ('metadata_contradicted','controlled_negative','admit','block','block'),
        ('document_contradicted','controlled_negative','admit','admit','block'),
        ('context_signal_contradicted','controlled_negative','admit','admit','block'),
        ('source_review_contradicted','controlled_negative','admit','admit','block'),
        ('missing_compiled_context','controlled_negative','admit','admit','block'),
        ('unmet_required_predicate','controlled_negative','admit','admit','block'),
        ('extra_compiled_context','controlled_negative','admit','admit','abstain'),
        ('unqualified_field_date_conflict','controlled_negative','admit','admit','abstain'),
        ('simulated_verified_consistent','synthetic_credential_control','admit','admit','admit'),
        ('simulated_verified_date_conflict','synthetic_credential_control','admit','admit','block'),
        ('simulated_verified_unit_conflict','synthetic_credential_control','admit','admit','block'),
        ('simulated_verified_entity_conflict','synthetic_credential_control','admit','admit','block'),
        ('simulated_verified_missing_field_context','synthetic_credential_control','admit','admit','abstain'),
        ('simulated_verified_document_unverified','synthetic_credential_control','admit','admit','abstain'),
        ('simulated_verified_context_unknown','synthetic_credential_control','admit','admit','abstain'),
    ]
    cases=[{'scenario_id':name,'classification':cl,'A':a,'B':b,'C':c,'C_reason':'synthetic_fixture_reason'}
        for name,cl,a,b,c in scenarios]
    sec = {'study':'metaverify_deadline_single_source_controlled_policy_stress_test_v1',
        'controlled_scenarios_total':17,'candidate_count_independent':1,
        'scenarios_simulated_evidence_not_real':7,'scenarios_unqualified_real_evidence':10,
        'human_reviewer_decisions':0,'gold_rules':0,'measured_accuracy_or_gate_effect':False,
        'arm_counts_over_repeated_scenarios_not_independent_samples':{
            k:{v:sum(row[k]==v for row in cases) for v in ('admit','abstain','block')} for k in 'ABC'},
        'cases':cases}
    return [b11,b12,p,baseline,sec]


class SubmissionMetricsTests(unittest.TestCase):
    def test_expected_descriptive_metrics_and_no_gold(self):
        r=calculate(*fixture())
        self.assertEqual(r['nhanes']['evaluated_checks'],12678)
        self.assertEqual(r['nhanes']['pair_record_checks_total'],14403)
        self.assertEqual(r['nhanes']['abstained_checks'],1725)
        self.assertEqual(r['nhanes']['exploratory_tolerance']['0.0005']['within_tolerance'],6201)
        self.assertEqual(r['controlled_perturbation']['flagged_after_shift'],12678)
        self.assertEqual(r['matched_numeric_coefficient_baselines']['methods']['train_median_ratio']['newly_flagged'],6404)
        self.assertEqual(r['matched_numeric_coefficient_baselines']['methods']['documented_cdc_factor']['newly_flagged'],6412)
        self.assertIsNone(r['effectiveness_not_estimable']['admission_precision'])
        self.assertEqual(r['sec_controlled_policy']['arm_decision_rates']['C']['block']['count'],9)

    def test_rejects_parent_count_drift(self):
        data=fixture()
        data[1]['pairs'][0]['grid'][1]['satisfied']-=1
        with self.assertRaises(MetricsError):calculate(*data)

    def test_rejects_fake_independent_gold_and_sota(self):
        for index,key,value in [(0,'gold_rules',1),(3,'real_sota_autotest_run',True),(4,'gold_rules',1)]:
            data=fixture()
            data[index][key]=value
            with self.subTest(index=index,key=key),self.assertRaises((MetricsError, ValueError)):
                calculate(*data)

    def test_rejects_duplicate_baseline_cell(self):
        data=fixture()
        data[3]['cells'][0]=copy.deepcopy(data[3]['cells'][1])
        with self.assertRaises(MetricsError):calculate(*data)

if __name__=='__main__':unittest.main()
