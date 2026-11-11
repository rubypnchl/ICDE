"""Deadline-day controlled policy interventions on one source-derived SEC candidate.

NOT an independent discovery, gold-label, empirical precision, or causal gate-effect study.
The 'simulated_verified' scenarios are mechanical contract tests that never assert
actual reviewer approval or independent documentary qualification.
"""
from __future__ import annotations

import copy
import csv
import io
import json
from collections import Counter
from pathlib import Path

from src.b13_13_matched_pilot import (
    PilotError, canonical_hash, exclusive_json, freeze, run_matched,
    read_json, validate_lock,
)
from src.b13_14_sec_intake import assert_external_cache
from src.b13_15_sec_filing_context_audit import RAW
from src.metaverify_deadline_sec_pilot import (
    EXPECTED_ORIGINAL_SHA256, audited_pair, make_packet,
    verify_b1315,
)

OUTDIR = 'CMG_Deadline_Control_Study'
HEADERS = ['scenario_id', 'classification', 'intervention', 'A', 'B', 'C', 'C_reason', 'b4_status']


def _simulate_review(c: dict) -> None:
    """For controlled contract checks ONLY. Not source evidence or a reviewer vote."""
    p = c['source_context_policy']
    for field in ('context_review', 'applicability_review', 'source_eligibility_review'):
        p[field] = 'supported'
    evidence = c['policy_evidence']
    evidence['documentary'] = {
        'status': 'supported', 'verified': True,
        'evidence_url': c['source_evidence_url'],
        'evidence_locator': 'SIMULATED VERIFICATION FLAG FOR CODE TEST; NOT AN ACTUAL REVIEW',
    }
    for field in p['required_context_keys']:
        evidence['context_evidence'][field] = 'supported'


def _variants(packet: dict):
    variants = [
      ('observed_baseline','real_unqualified','unchanged observed source and missing independent review',None),
      ('metadata_unknown','controlled_negative','metadata signal unknown',
       lambda c: c['policy_evidence'].__setitem__('metadata','unknown')),
      ('metadata_contradicted','controlled_negative','metadata signal contradicted',
       lambda c: c['policy_evidence'].__setitem__('metadata','contradicted')),
      ('document_contradicted','controlled_negative','document evidence contradicted',
       lambda c: c['policy_evidence']['documentary'].__setitem__('status','contradicted')),
      ('context_signal_contradicted','controlled_negative','required context evidence contradicted',
       lambda c: c['policy_evidence']['context_evidence'].__setitem__('report_date','contradicted')),
      ('source_review_contradicted','controlled_negative','source context review contradicted',
       lambda c: c['source_context_policy'].__setitem__('context_review','contradicted')),
      ('missing_compiled_context','controlled_negative','compiled proposal omits required context',
       lambda c: c['proposal']['context_keys'].remove('unit_ref')),
      ('unmet_required_predicate','controlled_negative','source policy requires an absent applicability predicate',
       lambda c: c['source_context_policy'].__setitem__('required_when',{'column':'Assets','op':'eq','value':'UNEXECUTED'})),
      ('extra_compiled_context','controlled_negative','proposal adds unreviewed context declaration',
       lambda c: c['proposal']['context_keys'].append('unreviewed_extra')),
      ('unqualified_field_date_conflict','controlled_negative','field date intentionally mismatched while source review unknown',
       lambda c: c['field_context_by_column']['Assets'].__setitem__('report_date','2024-12-31')),
    ]
    for id_,cl,description,fn in variants:
        q=copy.deepcopy(packet)
        # Original packet reuses a list object in policy and proposal; interventions must isolate them.
        q['candidates'][0]['proposal']['context_keys'] = list(q['candidates'][0]['proposal']['context_keys'])
        q['candidates'][0]['source_context_policy']['required_context_keys'] = list(q['candidates'][0]['source_context_policy']['required_context_keys'])
        if fn:fn(q['candidates'][0])
        yield id_,cl,description,q

    simulated = [
      ('simulated_verified_consistent','synthetic_credential_control','all review flags artificially set to supported; fields coherent',None),
      ('simulated_verified_date_conflict','synthetic_credential_control','after simulated approval, incompatible reporting dates',
       lambda c: c['field_context_by_column']['Assets'].__setitem__('report_date','2024-12-31')),
      ('simulated_verified_unit_conflict','synthetic_credential_control','after simulated approval, incompatible currency unit references',
       lambda c: c['field_context_by_column']['Assets'].__setitem__('unit_ref','INTENTIONALLY_DIFFERENT_UNIT')),
      ('simulated_verified_entity_conflict','synthetic_credential_control','after simulated approval, incompatible entity scope',
       lambda c: c['field_context_by_column']['Assets'].__setitem__('cik','0000320193')),
      ('simulated_verified_missing_field_context','synthetic_credential_control','after simulated approval, missing required field context',
       lambda c: c['field_context_by_column']['Assets'].pop('unit_ref')),
      ('simulated_verified_document_unverified','synthetic_credential_control','after simulated approval, document verification removed',
       lambda c: c['policy_evidence']['documentary'].__setitem__('verified',False)),
      ('simulated_verified_context_unknown','synthetic_credential_control','after simulated approval, one context signal unknown',
       lambda c: c['policy_evidence']['context_evidence'].__setitem__('unit_ref','unknown')),
    ]
    for id_,cl,description,fn in simulated:
        q=copy.deepcopy(packet)
        c=q['candidates'][0]
        _simulate_review(c)
        if fn:fn(c)
        yield id_,cl,description,q


EXPECTED = {
    'observed_baseline':('admit','admit','abstain'),
    'metadata_unknown':('admit','abstain','abstain'),
    'metadata_contradicted':('admit','block','block'),
    'document_contradicted':('admit','admit','block'),
    'context_signal_contradicted':('admit','admit','block'),
    'source_review_contradicted':('admit','admit','block'),
    'missing_compiled_context':('admit','admit','block'),
    'unmet_required_predicate':('admit','admit','block'),
    'extra_compiled_context':('admit','admit','abstain'),
    'unqualified_field_date_conflict':('admit','admit','abstain'),
    'simulated_verified_consistent':('admit','admit','admit'),
    'simulated_verified_date_conflict':('admit','admit','block'),
    'simulated_verified_unit_conflict':('admit','admit','block'),
    'simulated_verified_entity_conflict':('admit','admit','block'),
    'simulated_verified_missing_field_context':('admit','admit','abstain'),
    'simulated_verified_document_unverified':('admit','admit','abstain'),
    'simulated_verified_context_unknown':('admit','admit','abstain'),
}


def run_controls(packet: dict, repo_root: Path) -> dict:
    """17 paired development control scenarios; no source-data row execution or gold."""
    if len(packet.get('candidates',[]))!=1 or packet['candidates'][0].get('prior_exposure')!='previously_inspected':
        raise PilotError('Controls require the single previously inspected CMG pilot; not a novel cohort')
    rows=[]
    for scenario_id, classification, description, candidate_packet in _variants(packet):
        frozen,_ = freeze(candidate_packet,repo_root)
        result=run_matched(candidate_packet,frozen,repo_root)
        outcome=result['outcomes'][0]
        actual=(outcome['A'],outcome['B'],outcome['C'])
        if actual!=EXPECTED[scenario_id] or result['compiler_invocations'] != 1:
            raise PilotError(f'Unexpected controlled response for {scenario_id}: {actual}; STOP before reporting')
        rows.append({'scenario_id':scenario_id,'classification':classification,
                     'intervention':description,'A':actual[0],'B':actual[1],'C':actual[2],
                     'C_reason':outcome['reasons']['C'],'b4_status':outcome['b4_status']})
    if len(rows)!=len(EXPECTED):
        raise PilotError('Control-design version mismatch')
    counts={arm:{decision:sum(r[arm]==decision for r in rows) for decision in ('admit','abstain','block')} for arm in 'ABC'}
    return {'study':'metaverify_deadline_single_source_controlled_policy_stress_test_v1',
            'classification':'single_source_repeated_development_controls_not_gold_not_prospective',
            'source': 'Chipotle 2025 10-K previously inspected source-derived candidate',
            'source_sha256':packet['candidates'][0]['source_sha256'],
            'candidate_count_independent':1,
            'controlled_scenarios_total':len(rows),
            'scenarios_simulated_evidence_not_real':sum(r['classification']=='synthetic_credential_control' for r in rows),
            'scenarios_unqualified_real_evidence':sum(r['classification']!='synthetic_credential_control' for r in rows),
            'b4_compiler_invocations':len(rows),'arm_counts_over_repeated_scenarios_not_independent_samples':counts,
            'cases':rows,'human_reviewer_decisions':0,'gold_rules':0,
            'measured_accuracy_or_gate_effect':False,
            'limitations':[
                'Controlled perturbations of a single previously observed typed candidate are not independent constraint examples.',
                'Synthetic verified flags test branch logic; they are NOT genuine independently validated documentary evidence.',
                'Some source-unqualified context mismatches abstain before a deep per-field consistency comparison.',
                'Structural source audit does not transform or test SEC monetary fact values.',
                'No published discovery baseline, natural-error labels, statistical inference, or superiority result.',
            ]}


def _csv(report:dict)->str:
    stream=io.StringIO(newline='')
    writer=csv.DictWriter(stream,fieldnames=HEADERS,lineterminator='\n')
    writer.writeheader();writer.writerows(report['cases'])
    return stream.getvalue()


def _handover(report:dict)->str:
    counts=report['arm_counts_over_repeated_scenarios_not_independent_samples']
    return f'''# Deadline-day SEC policy stress test — manuscript handoff

One previously inspected SEC filing gave one hand-curated typed balance-sheet relationship. We exercised **{report['controlled_scenarios_total']} controlled metadata/evidence-context configurations** with one B4 compilation per configuration and matched A/B/C admission decisions. Of these, **{report['scenarios_simulated_evidence_not_real']}** required explicitly *simulated* evidence approval flags; none represents a genuine independent documentary review. Aggregate policy decisions over repeated scenarios: A {counts['A']}; B {counts['B']}; C {counts['C']}. These are descriptive **code-path** interventions on one candidate, not independent test samples, not accuracy, and not inferential statistics. The unchanged real unqualified candidate produced A admit, B admit and C abstain. Under simulated approved evidence, deliberately incompatible entity/date/unit contexts block C, while missing field-context values lead C to abstain.

**Allowable claim:** The implementation responds deterministically to controlled evidence/context perturbations, preserving conservative missing-evidence behaviour. **Disallowed claim:** More accurate discovery, correct natural data-quality defects, reduced false positives, independent gold, or published-baseline superiority. No p-values, F1 or confidence intervals should be computed from these scenarios.

This is an optional supplementary software robustness check for the ICDE manuscript; the previously executed NHANES and manufacturing/cybersecurity evaluations remain the substantive real-data demonstrations.
'''


def run_real(cache_dir:Path, repo_root:Path)->tuple[dict,list[Path]]:
    cache=assert_external_cache(cache_dir,repo_root)
    # Re-verify the actual source bytes, original intake lineage and fixed audit.
    plan=read_json(repo_root/'data/evaluation/b13_14_sec_intake_plan_v1.json')
    development=read_json(repo_root/'data/sources.json')
    aggregate=verify_b1315(cache,repo_root,plan,development)
    from src.b13_15_sec_filing_context_audit import sha as sha_source
    raw=(cache/RAW).read_bytes()
    if sha_source(raw)!=EXPECTED_ORIGINAL_SHA256:
        raise PilotError('Original filing changed')
    context_id,unit_id=audited_pair(raw,aggregate)
    expected=make_packet(cache,repo_root,aggregate=aggregate,context_id=context_id,unit_id=unit_id)
    pilot=cache/'CMG_Deadline_Pilot'
    existing=read_json(pilot/'candidate_packet.json')
    existing_lock=read_json(pilot/'frozen_input_lock.json')
    if canonical_hash(expected)!=canonical_hash(existing):
        raise PilotError('Saved pilot differs from source-derived candidate')
    validate_lock(existing,existing_lock,repo_root)
    report=run_controls(existing,repo_root)
    destination=cache/OUTDIR
    names=[destination/'controls.json',destination/'controls.csv',destination/'MANUSCRIPT_CONTROL_LIMITATIONS.md']
    if any(p.exists() for p in names):
        raise PilotError('Controls already exist; refusing overwrite')
    destination.mkdir(parents=True,exist_ok=True)
    saved=[]
    try:
        for path,data in zip(names,(report,_csv(report),_handover(report))):
            if isinstance(data,dict): exclusive_json(path,data)
            else:
                with path.open('x',encoding='utf-8',newline='') as f:f.write(data)
            saved.append(path)
    except BaseException:
        for p in saved:p.unlink(missing_ok=True)
        raise
    return report,names
