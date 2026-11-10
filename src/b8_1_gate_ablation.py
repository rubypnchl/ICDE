"""B8.1 retrospective saved-decision audit: NOT a controlled accuracy experiment.

Never equate a model hypothesis, executable syntax, statistical support, and
verified semantic acceptance. Separate the saved LLM and data-mining cohorts.
Read original committed reports without mutating them or accessing raw records.
"""
from __future__ import annotations
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

class AuditError(ValueError):
    pass

PATHS = {
    'luna': 'data/evaluation/b7_1_pilot_comparison.json',
    'posthoc': 'data/evaluation/b5_1_evidence_review.json',
    'legacy': 'data/evaluation/b7_2_existing_dataonly_discovery.json',
    'context': 'data/evaluation/b7_3_context_audit.json',
    'catalogue': 'data/evaluation/b6_reference_catalogue.json',
}
PINNED_TARGET = 'sec-companyfacts-320193-assets-usd-5829762e6f'
GOOD_COMPILER = 'candidate_executable_unverified'

def read_obj(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(value, dict):
        raise AuditError('Expected a JSON object in '+str(path))
    return value

def hash_file(path: Path) -> str:
    h = sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(1 << 16), b''):
            h.update(chunk)
    return h.hexdigest()

def assert_same(path: Path, digest: str, label: str):
    if hash_file(path) != digest:
        raise AuditError('Frozen input SHA-256 mismatch ('+label+'); DO NOT modify historical files')

def analyze(luna: dict, posthoc: dict, legacy: dict, context: dict, catalogue: dict) -> dict:
    if luna.get('study_id') != 'b7_1_saved_pilot_opportunity_audit_v1' or luna.get('opportunities_total') != 2:
        raise AuditError('B7.1 historical pilot not pinned to the two known opportunities')
    if posthoc.get('stage') != 'B5.1' or len(posthoc.get('model_reports',[])) != 2:
        raise AuditError('B5.1 report malformed')
    gates = {x['domain']: x for x in posthoc['model_reports']}
    if set(gates) != {'healthcare','finance'}:
        raise AuditError('Unexpected posthoc domains')
    if len(luna.get('results',[])) != 2:
        raise AuditError('Unexpected pilot result count')
    all_llm = []
    for item in sorted(luna['results'], key=lambda r:r['domain']):
        domain = item['domain']
        saved = item['saved_luna_pilot']
        decisions = gates[domain]['decisions']
        if len(decisions) != saved['hypothesis_count'] or len(decisions)!=1:
            raise AuditError('Expected exactly one saved proposal per LLM domain')
        p = saved['proposals'][0]
        d = decisions[0]
        if (p['id'] != d['proposal_id'] or
            p['b4_status'] != d['b5_original_compilation_status'] or
            p['b5_1_posthoc_status'] != d['status'] or
            d.get('safe_to_deploy_as_integrity_constraint') is not False or
            d.get('semantically_verified') is not False or
            d.get('independently_validated') is not False):
            raise AuditError('Saved LLM compiler/posthoc status mismatch')
        if domain == 'finance':
            if not (p['id']=='balance_sheet_equation' and p['b4_status']==GOOD_COMPILER and d['status']=='blocked_applicability_or_scope'):
                raise AuditError('Unexpected finance status, audit blocked')
            reason='finance_reporting_scope_unproven'
        elif domain == 'healthcare':
            if not (p['id']=='glucose_unit_conversion' and p['b4_status']=='blocked_unresolved' and d['status']=='compiled_unverified_posthoc'):
                raise AuditError('Unexpected healthcare status, audit blocked')
            provenance=d.get('parameter_provenance', {})
            if not any(x.get('origin')=='empirical_same_dataset' for x in provenance.values()):
                raise AuditError('Healthcare posthoc precision provenance lost')
            reason='healthcare_precision_posthoc_and_unverified'
        else:
            raise AuditError('Unexpected LLM domain')
        all_llm.append({
            'cohort':'saved_llm_two_manually_selected', 'domain':domain,
            'proposal_id':p['id'],
            'proposal_present':True,
            'original_compiler_status':p['b4_status'],
            'original_compiler_executable_unverified':p['b4_status']==GOOD_COMPILER,
            'posthoc_evidence_status':d['status'],
            'posthoc_compiled_rule_present':d.get('compiled_rule') is not None,
            'posthoc_curator_intervention':domain=='healthcare',
            'posthoc_safe_to_deploy':False,
            'gate_nonacceptance_reason':reason,
            'independent_gold':False,
        })
    if sorted(x['domain'] for x in all_llm) != ['finance','healthcare']:
        raise AuditError('Missing LLM domains')
    if context.get('baseline_commit')!='40a7ddb' or context.get('legacy_supported_rule',{}).get('rule_id') != PINNED_TARGET:
        raise AuditError('B7.3 retrospective target mismatch')
    saved = context['legacy_supported_rule']
    if saved.get('recorded_decision')!='documented_support' or saved.get('recorded_heldout_rows')!=41 or saved.get('recorded_violations')!=0:
        raise AuditError('41/41 historical record changed')
    conservative = context.get('conservative_saved_candidate_decisions', {})
    if conservative.get('without_new_context_proof')!='abstain_context_unsubstantiated' or conservative.get('with_frozen_B6_universal_exclusion')!='blocked_unqualified_universal_identity':
        raise AuditError('B7.3 strict decisions unexpectedly changed')
    excluded = [x for x in catalogue.get('entries',[]) if x.get('id')=='B6-FIN-002']
    if len(excluded)!=1 or excluded[0].get('status')!='excluded' or excluded[0].get('scoring_eligible') is not False:
        raise AuditError('Frozen negative finance reference changed')
    datasets = legacy.get('datasets')
    if not isinstance(datasets,dict) or set(datasets) != {'ai4i-2020','sec-companyfacts-320193'}:
        raise AuditError('Unexpected legacy discovery datasets')
    all_mined=[]
    for ds in sorted(datasets):
        v=datasets[ds]
        candidates=v.get('candidates',[])
        if len(candidates)!=v.get('candidate_count'):
            raise AuditError('Saved legacy count mismatch')
        actual=Counter(x['heldout']['decision'] for x in candidates)
        if any(actual[k]!=v.get('decision_counts',{}).get(k,0) for k in ('abstain','documented_support','documented_conflict')):
            raise AuditError('Legacy decision counts altered')
        for c in candidates:
            rule=c['rule'];rid=rule['id'];hd=c['heldout'];ev=c['documented_evidence']
            dec=hd['decision']
            if dec not in {'abstain','documented_support'}:
                raise AuditError('Unexpected legacy decision; audit assumptions invalid')
            if dec=='documented_support':
                if rid != PINNED_TARGET or ev.get('status')!='documented' or hd.get('applicable_rows')!=41 or hd.get('violations')!=0:
                    raise AuditError('Unsupported legacy positive candidate')
                if c['rule']['assertion'].get('term_columns')!=['Liabilities [USD]','StockholdersEquity [USD]']:
                    raise AuditError('Saved supported finance formula changed')
                strict_context='abstain_context_unsubstantiated'
                strict_catalogue='blocked_unqualified_universal_identity'
                reason='hardcoded_accounting_scope_and_existing_catalogue_exclusion'
            else:
                if ev.get('status') not in ('not_found',):
                    raise AuditError('Abstaining source-evidence status not recognized')
                strict_context='abstain_no_documentary_rule_support'
                strict_catalogue='abstain_no_documentary_rule_support'
                reason='no_documented_constraint_source'
            all_mined.append({
                'cohort':'legacy_data_only_discovery_two_domains','dataset_id':ds,
                'candidate_id':rid,'rule_type':rule.get('rule_type'),
                'legacy_decision':dec,
                'heldout_applicable_rows':hd.get('applicable_rows'),
                'heldout_violations':hd.get('violations'),
                'strict_context_decision':strict_context,
                'strict_context_and_catalogue_decision':strict_catalogue,
                'nonacceptance_reason':reason,
                'independent_gold':False,
            })
    if len(all_mined)!=28 or sum(x['legacy_decision']=='documented_support' for x in all_mined)!=1:
        raise AuditError('Expected 28 mined hypotheses and exactly one historical positive')
    seen=[x['candidate_id'] for x in all_mined]
    if len(seen)!=len(set(seen)):
        raise AuditError('Duplicate discovered rule id')
    counts_legacy=Counter(x['legacy_decision'] for x in all_mined)
    counts_context=Counter(x['strict_context_decision'] for x in all_mined)
    counts_catalogue=Counter(x['strict_context_and_catalogue_decision'] for x in all_mined)
    n= len(all_llm)
    return {
        'study_id':'b8_1_retrospective_paired_saved_decision_audit_v1',
        'study_class':'retrospective_exploratory_saved_decision_reconstruction_not_independent_ablation',
        'cohorts_not_pooled':True,
        'llm_pilot':{
            'candidates':n,'original_compiler_executable_unverified':sum(x['original_compiler_executable_unverified'] for x in all_llm),
            'original_compiler_blocked':sum(not x['original_compiler_executable_unverified'] for x in all_llm),
            'posthoc_curator_assisted_compiled_unverified':sum(x['posthoc_compiled_rule_present'] for x in all_llm),
            'posthoc_safe_to_deploy':0,
            'different_inputs_or_interventions_between_stages':True,
            'proposal_details':all_llm,
            'note':'B4 and B5.1 have different curator intervention. Proposals exist before compilation; no matched on/off randomized gating or rule precision.'},
        'legacy_data_only':{
            'candidates':len(all_mined),'legacy_evidence_counts':dict(counts_legacy),
            'strict_context_reconstruction_counts':dict(counts_context),
            'strict_context_plus_frozen_catalogue_counts':dict(counts_catalogue),
            'apparent_positive_decisions_legacy':counts_legacy['documented_support'],
            'independently_verified_positive_decisions_strict':0,
            'changed_candidates':sum(x['legacy_decision']=='documented_support' and x['strict_context_decision']!='documented_support' for x in all_mined),
            'legacy_single_accepted_heldout_records':41,
            'legacy_single_accepted_heldout_violations':0,
            'candidate_details':all_mined,
            'note':'All strict decisions are reconstructed conservatively from saved source evidence; no new source proof, novel baseline, or independently evaluated rule labels.'},
        'independently_adjudicated_gold_constraints':0,
        'rule_precision':None,'rule_recall':None,'uncertainty_interval':None,
        'published_baseline_reproduced':False,
        'source_models_newly_queried':0,
        'limitations':[
            'Saved pilot has only two manually selected LLM proposals across two domains.',
            'The B5.1 curator authorized additional parameters after observing outputs; not a controlled isolated gate-only ablation.',
            'The B7.2 data-only miner and B7.1 LLM pilot have different candidate/input regimes and MUST NOT be directly compared.',
            'The B7.3 strict SEC policy was designed/assessed retrospectively and uses an already known catalogue exclusion.',
            'No independently adjudicated gold labels or prospective holdout: precision/recall/benefit of gating cannot be estimated.',
            'No Auto-Test, Guardrail, Metanome or other published discovery baseline was executed.',
            'Two human reviewer assessments are separate private artifacts and are not automatically converted into gold truth.',
        ],
    }

def run(root:Path, *, preflight:bool=False)->dict:
    files={key:root/rel for key,rel in PATHS.items()}
    for key,f in files.items():
        if not f.is_file():
            raise AuditError('Required frozen input missing: '+str(f))
    objs={key:read_obj(f) for key,f in files.items()}
    # Cross-check source hashes already recorded by the earlier frozen audits.
    assert_same(files['posthoc'],objs['luna']['input_sha256']['b5_1_review'],'B5.1 gate')
    assert_same(files['legacy'],objs['context']['input_sha256'][PATHS['legacy']],'B7.2 data miner')
    assert_same(files['catalogue'],objs['context']['input_sha256'][PATHS['catalogue']],'B6 catalogue')
    plan_file=root/'data/evaluation/b8_1_plan_v1.json'
    plan=read_obj(plan_file)
    if (plan.get('study_id')!='b8_1_retrospective_paired_saved_decision_audit_v1'
            or plan.get('protocol_developed_prior_to_results') is not False
            or plan.get('independent_gold_available') is not False
            or plan.get('external_published_baseline_executed') is not False
            or [(x.get('name'),x.get('candidate_count')) for x in plan.get('separate_cohorts',[])] !=
               [('saved_llm_pilot',2),('legacy_data_only_miner',28)]):
        raise AuditError('Study plan changed: review protocol version instead of silently repurposing')
    result=analyze(**objs)
    result['analysis_plan_sha256']=hash_file(plan_file)
    result['input_sha256']={key:hash_file(f) for key,f in files.items()}
    result['inputs_checked_by_prior_report_hash_chain']=True
    return result
