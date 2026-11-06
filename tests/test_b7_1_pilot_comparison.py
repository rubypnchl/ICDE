"""B7.1 offline synthetic fixtures only, no new real-world or model run."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import tempfile
import unittest
from src.b7_1_pilot_comparison import (
    DATASETS, PilotAuditError, _description_unit, hash_file, lexical_candidates,
    object_hash, read_json, run, validate_inputs,
)

PLAN = Path('data/evaluation/b7_1_comparison_plan_v1.json')
HEALTH = 'nhanes-2017-2018-glu-j'
FINANCE = 'sec-companyfacts-320193'


def bundles():
    return {
        'healthcare': {
            'domain': 'healthcare', 'dataset_id': HEALTH,
            'passages': [
                {'id': 'P01', 'column': 'SEQN', 'description': 'Person id', 'unit':'unknown', 'type':'integer'},
                {'id': 'P02', 'column': 'LBXGLU', 'description':'Fasting Glucose (mg/dL)','unit':'unknown','type':'integer'},
                {'id': 'P03', 'column': 'LBDGLUSI', 'description':'Fasting Glucose (mmol/L)','unit':'unknown','type':'number'},
            ]
        },
        'finance': {
            'domain': 'finance','dataset_id': FINANCE,
            'passages': [
                {'id': 'P01', 'column':'Assets', 'description':'Sum of all assets', 'type':'number'},
                {'id': 'P02', 'column':'Liabilities', 'description':'Sum of all liabilities', 'type':'number'},
                {'id': 'P03', 'column':'StockholdersEquity', 'description':'Parent equity (noncontrolling excluded)', 'type':'number'},
            ]
        },
    }


def make_report(domain, bundle):
    pid = 'glucose_unit_conversion' if domain=='healthcare' else 'balance_sheet_equation'
    status = 'blocked_unresolved' if domain=='healthcare' else 'candidate_executable_unverified'
    return {'domain': domain,'dataset_id':bundle['dataset_id'], 'model_id_requested':'gpt-6-luna',
            'response_status':'completed','error':None,'request_sha256': f'request-{domain}',
            'input_bundle': bundle,
            'output':{'rules':[{'id':pid,'passage_ids':['P01','P02']}]},
            'compile_results':[{'id':pid,'compilation':{'status':status}}],
            'estimated_cost_usd':0.0001}


def gate_report(domain,bundle):
    pid = 'glucose_unit_conversion' if domain=='healthcare' else 'balance_sheet_equation'
    status = 'compiled_unverified_posthoc' if domain=='healthcare' else 'blocked_applicability_or_scope'
    return {'domain':domain,'dataset_id':bundle['dataset_id'], 'request_sha256':f'request-{domain}',
            'input_bundle_sha256':object_hash(bundle),
            'policy_development_stage':'posthoc_case_study_policy_developed_after_inspecting_luna_outputs',
            'decisions':[{'proposal_id':pid,'status':status,'semantically_verified':False,'independently_validated':False}]}


class LexicalTests(unittest.TestCase):
    def test_trailing_unit(self):
        self.assertEqual(_description_unit(' Fasting   Glucose (mg/dL) '), ('fasting glucose','mg/dl'))

    def test_ambiguous_description_not_parsed(self):
        self.assertIsNone(_description_unit('Includes (noncontrolling) equity and others'))
        self.assertIsNone(_description_unit(None))

    def test_health_pair(self):
        result = lexical_candidates(bundles()['healthcare'],2)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['columns'], ['LBDGLUSI', 'LBXGLU'])
        self.assertIsNone(result[0]['executable_rule'])
        self.assertFalse(result[0]['semantic_verified'])

    def test_finance_abstains(self):
        self.assertEqual(lexical_candidates(bundles()['finance'],2), [])

    def test_limit_respected_and_deterministic(self):
        b=bundles()['healthcare']
        b['passages'].append({'id':'P04','column':'NEW','description':'Fasting Glucose (nmol/L)','type':'number'})
        self.assertEqual(lexical_candidates(b,1),lexical_candidates(b,1))
        self.assertEqual(len(lexical_candidates(b,1)),1)
        self.assertEqual(len(lexical_candidates(b,2)),2)

    def test_duplicate_column_rejected(self):
        b=bundles()['healthcare']
        b['passages'][1]['column']='SEQN'
        with self.assertRaisesRegex(PilotAuditError,'duplicate'):
            lexical_candidates(b,2)

    def test_missing_passage_rejected(self):
        b=bundles()['healthcare']
        b['passages'][0].pop('id')
        with self.assertRaises(PilotAuditError): lexical_candidates(b,2)

    def test_invalid_budget_rejected(self):
        with self.assertRaises(PilotAuditError): lexical_candidates(bundles()['healthcare'],True)


class AuditIntegration(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.bundles=bundles()
        self.plan=json.loads((Path(__file__).resolve().parents[1]/PLAN).read_text())
        self.save(PLAN,self.plan)
        self.save('data/llm_pilot/structured/inputs.json',self.bundles)
        for domain in DATASETS:
            self.save(self.plan['input_paths']['llm_reports'][domain],make_report(domain,self.bundles[domain]))
        self.save('data/evaluation/b5_1_evidence_review.json',
                  {'model_reports':[gate_report(k,self.bundles[k]) for k in DATASETS]})

    def save(self,path,obj):
        f=self.root/path
        f.parent.mkdir(parents=True,exist_ok=True)
        f.write_text(json.dumps(obj),encoding='utf-8')

    def test_preflight(self):
        b,r,g=validate_inputs(self.root,self.plan)
        self.assertEqual(set(b),set(DATASETS)); self.assertEqual(set(r),set(g))

    def test_run_counts_and_no_gold(self):
        v=run(self.root)
        self.assertEqual(v['independent_gold_rule_count'],0)
        self.assertIsNone(v['independent_gold_precision'])
        self.assertFalse(v['published_method_reproduction'])
        self.assertEqual([x['lexical_heuristic']['candidate_count'] for x in v['results']],[1,0])
        self.assertEqual([x['saved_luna_pilot']['hypothesis_count'] for x in v['results']],[1,1])
        self.assertEqual(v['new_api_calls'],0)

    def test_finance_gate_is_blocked(self):
        out=run(self.root)
        self.assertEqual(out['results'][1]['saved_luna_pilot']['proposals'][0]['b5_1_posthoc_status'],'blocked_applicability_or_scope')

    def test_change_input_bundle_rejected(self):
        b=copy.deepcopy(self.bundles);b['healthcare']['passages'][1]['description']='Different (kg)'
        self.save(self.plan['input_paths']['input_bundles'],b)
        with self.assertRaisesRegex(PilotAuditError,'snapshot mismatch'):run(self.root)

    def test_change_gate_hash_rejected(self):
        p=self.plan['input_paths']['posthoc_gate'];g=read_json(self.root/p)
        g['model_reports'][0]['input_bundle_sha256']='bad'
        self.save(p,g)
        with self.assertRaisesRegex(PilotAuditError,'snapshot mismatch'):run(self.root)

    def test_change_rule_status_rejected(self):
        p=self.plan['input_paths']['posthoc_gate'];g=read_json(self.root/p)
        g['model_reports'][0]['decisions'][0]['semantically_verified']=True
        self.save(p,g)
        with self.assertRaisesRegex(PilotAuditError,'acceptance'):run(self.root)

    def test_delete_b4_result_rejected(self):
        p=self.plan['input_paths']['llm_reports']['finance'];r=read_json(self.root/p)
        r['compile_results']=[];self.save(p,r)
        with self.assertRaisesRegex(PilotAuditError,'ID mismatches'):run(self.root)

    def test_duplicate_model_id_rejected(self):
        p=self.plan['input_paths']['llm_reports']['healthcare'];r=read_json(self.root/p)
        r['output']['rules']*=2;self.save(p,r)
        with self.assertRaisesRegex(PilotAuditError,'ID mismatches'):run(self.root)

    def test_changed_plan_refused(self):
        self.plan['score_semantic_rule_precision']=True
        self.save(PLAN,self.plan)
        with self.assertRaisesRegex(PilotAuditError,'plan changed'):run(self.root)

    def test_no_files_written(self):
        prior={p:hash_file(p) for p in self.root.rglob('*') if p.is_file()}
        run(self.root)
        self.assertEqual(prior,{p:hash_file(p) for p in self.root.rglob('*') if p.is_file()})


if __name__=='__main__':unittest.main()
