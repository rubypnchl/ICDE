"""B13.12: real-source B4/B3 numerical tolerance sweep; NOT gold or gate effect.

Only the predeclared B13.9 residual thresholds are explored, never fitted here.
Original B13.11 exact-equality execution and policy admissions remain unchanged.
"""
from __future__ import annotations
from decimal import Decimal
import csv
import io
import json
from pathlib import Path

from src.b13_11_retrospective_matched_replay import (
    load_inputs, validate_spec as validate_b1311_spec, make_candidate,
    PAIRS, REPORTS, ReplayError, _check_reports)
from src.b13_9_documented_pair_consistency import BINS
from src.b13_8_source_schema_audit import PINNED, canonical_sha
from src.b13_7_source_acquisition import assert_external_cache, verify_existing, sha256_file
from src.rule_bridge import compile_proposal
from src.generic_verifier import evaluate_rows, validate_rule

STUDY='b13_12_fixed_grid_precision_sensitivity_v1'
OUTPUTS=('B13_12_fixed_grid_sensitivity_v1.json','B13_12_sensitivity_table_v1.tex','B13_12_handover_v1.md')

class SensitivityError(ValueError): pass


def validate_plan(plan:dict,b139:dict)->None:
    expected={'study_id':STUDY, 'phase':'retrospective_numeric_sensitivity_not_independent_gold',
      'parent_b13_11_study_id':'b13_11_real_xpt_matched_compiler_diagnostic_v1',
      'source_group':'nhanes_2015_2016_cycle','pair_ids':list(PAIRS),
      'tolerance_grid_mmol_l':list(BINS),
      'tolerance_origin':'empirical_same_dataset_exploratory_bins_predeclared_B13_9_not_independent_precision_truth',
      'numerical_gate_effect_claimed':False,'independent_precision_verified':False,
      'prospective_candidates':0,'independent_gold_rules':0,
      'output_policy':'external_cache_exclusive_aggregate_only',
      'allowed_claims':['B3_fixed_grid_numeric_sensitivity_reconciled_with_B13_9'],
      'disallowed_claims':['true_data_errors','gold_rounding_spec','independent_constraint_discovery','three_arm_gate_improvement','production_approval']}
    if not isinstance(plan,dict) or plan != expected:
        raise SensitivityError('B13.12 frozen exploratory plan differs')
    if [p['pair_id'] for p in b139.get('pairs',[])] != list(PAIRS) or b139.get('absolute_residual_thresholds_mmol_l')!=list(BINS):
        raise SensitivityError('B13.9 previously declared bins or pairs changed')


def make_tolerance_compilation(pair:dict,source_group:str,b1311_spec:dict,tolerance:str):
    if tolerance not in BINS:
        raise SensitivityError('Tolerance not in previously declared B13.9 grid')
    proposal,registry,columns=make_candidate(pair,source_group,b1311_spec)
    proposal=dict(proposal)
    proposal['id'] += '_sens_' + tolerance.replace('.','p')
    proposal['assertions']=[dict(proposal['assertions'][0],abs_tolerance={'parameter':'exploratory_tolerance'})]
    ds=proposal['dataset_id']
    registry[f'{ds}:exploratory_tolerance']={
        'kind':'number','value':tolerance,'origin':'empirical_same_dataset',
        'rationale':'B13.9 predeclared numerical residual grid, re-used post-observation for exploratory sensitivity; no independent precision justification.'}
    result=compile_proposal(proposal,columns,registry)
    if result.status!='candidate_executable_unverified' or not isinstance(result.rule,dict):
        raise SensitivityError('B4 did not compile a numeric sensitivity candidate')
    refs=validate_rule(result.rule)
    if refs != set(columns) or result.rule.get('context_keys')!=['survey_cycle']:
        raise SensitivityError('Compiled field references or context differ')
    if Decimal(result.rule['assertions'][0].get('abs_tolerance','-1'))!=Decimal(tolerance):
        raise SensitivityError('Numeric threshold did not flow through B4')
    if result.parameter_provenance.get('exploratory_tolerance',{}).get('origin')!='empirical_same_dataset':
        raise SensitivityError('Tolerance provenance is incorrectly represented as independent')
    return result.rule,columns


def execute_grid(frame, pair:dict, b1311_spec:dict, group:str, thresholds=tuple(BINS))->list[dict]:
    out=[]
    for tol in thresholds:
        rule,columns=make_tolerance_compilation(pair,group,b1311_spec,tol)
        context={'_field_context':{col:{'survey_cycle':group} for col in columns}}
        rows=({**context,columns[0]:v1,columns[1]:v2}
              for v1,v2 in zip(frame[columns[0]],frame[columns[1]]))
        counts=evaluate_rows(rule,rows)['counts']
        if sum(counts.values())!=len(frame) or counts['not_applicable']!=0:
            raise SensitivityError('B3 row status aggregation inconsistent')
        out.append({'tolerance_mmol_l':tol,'satisfied':counts['satisfied'],
                    'mismatched':counts['violated'],'abstained':counts['abstained']})
    return out


def run(cache:Path, root:Path, plan:dict, *,reader=None)->dict:
    b1311_spec,b137,b138,b139,b1310=load_inputs(root)
    validate_b1311_spec(b1311_spec,b137,b138,b139,b1310)
    validate_plan(plan,b139)
    cache=assert_external_cache(cache,root)
    if not all((cache/n).is_file() for n in REPORTS):
        raise SensitivityError('B13.8-10 parent reports missing')
    r8,r9,r10,parent_hashes=_check_reports(cache,root,b137,b138,b139,b1310)
    prior_path=cache/'B13_11_retrospective_matched_replay_v1.json'
    prior_hash=sha256_file(prior_path)
    prior=json.loads(prior_path.read_text(encoding='utf-8'))
    if (prior.get('study_id')!='b13_11_real_xpt_matched_compiler_diagnostic_v1'
        or prior.get('classification')!='retrospective_real_data_engineering_replay_not_prospective_no_gold'
        or prior.get('pair_candidates_hand_curated')!=3 or prior.get('source_clusters')!=1
        or prior.get('gold_rules')!=0 or prior.get('confirmatory_candidates')!=0
        or prior.get('spec_sha256')!=canonical_sha(b1311_spec)
        or prior.get('parent_aggregate_sha256')!=parent_hashes):
        raise SensitivityError('B13.11 ancestry or scientific scope unexpectedly changed')
    prior_pairs={item['pair_id']:item for item in prior.get('pair_outcomes',[])}
    if set(prior_pairs)!=set(PAIRS):
        raise SensitivityError('B13.11 pair outcomes changed')
    r9_pairs={item['pair_id']:item for item in r9.get('conversion_pairs',[])}
    if set(r9_pairs)!=set(PAIRS):raise SensitivityError('B13.9 paired residual summary changed')
    sources={item['source_id']:item for item in b137['source_ids']}
    pmap={item['pair_id']:item for item in b139['pairs']}
    if reader is None:
        import pyreadstat
        reader=pyreadstat.read_xport
    frames={}
    for sid in ('B13S-HLT-01','B13S-HLT-02'):
        receipt=verify_existing(sources[sid],cache)
        if (receipt['object_name'],receipt['sha256'],receipt['size_bytes'],receipt['source_group'])!=PINNED[sid]:
            raise SensitivityError('Source differs from pinned source')
        frame,_=reader(str(cache/receipt['object_name']))
        expected_rows=next(h['row_count'] for h in r8['healthcare'] if h['source_id']==sid)
        if len(frame)!=expected_rows: raise SensitivityError('Changed source row count')
        frames[sid]=frame
    results=[]
    for pid in PAIRS:
        p=pmap[pid]
        source_id=p['source_id']
        prior_counts=prior_pairs[pid]['b3_counts']
        paired=r9_pairs[pid]['aggregates']['paired_nonmissing']
        if prior_pairs[pid]['evaluated_records']!=paired:
            raise SensitivityError('Previously evaluated count differs from B13.9')
        grid=execute_grid(frames[source_id],p,b1311_spec,'nhanes_2015_2016_cycle')
        expected=r9_pairs[pid]['aggregates']['absolute_residual_mmol_l']['threshold_counts_cumulative']
        for row in grid:
            if (row['satisfied'] != expected[row['tolerance_mmol_l']]
                or row['satisfied']+row['mismatched']!=paired
                or row['abstained']!=prior_counts['abstained']):
                raise SensitivityError('B3 tolerance outcome disagrees with B13.9 independent aggregate computation')
        if (prior_counts['satisfied'] > grid[0]['satisfied'] or
            any(a['satisfied']>b['satisfied'] for a,b in zip(grid,grid[1:]))):
            raise SensitivityError('Non-monotone B3 sensitivity counts')
        results.append({'pair_id':pid,'source_id':source_id,'previous_exact_counts':prior_counts,
                        'paired_nonmissing':paired,'grid':grid})
    for sid in frames:
        if sha256_file(cache/sources[sid]['object_name'])!=PINNED[sid][1]:
            raise SensitivityError('Source changed during sweep')
    if sha256_file(prior_path)!=prior_hash or any(sha256_file(cache/n)!=v for n,v in parent_hashes.items()):
        raise SensitivityError('Parent reports changed during sweep')
    return {'study_id':STUDY,'classification':'retrospective_numerical_sensitivity_not_precision_gold',
            'plan_sha256':canonical_sha(plan),'b13_11_parent_sha256':prior_hash,
            'one_source_cluster':'nhanes_2015_2016_cycle','pairs':results,
            'b4_compilations_for_grid':len(PAIRS)*len(BINS),'thresholds_independently_justified':False,
            'gold_rules':0,'prospective_candidates':0,'real_arm_comparative_accuracy_defined':False,
            'explanation':'Grid reuses predeclared B13.9 descriptive bins after data exposure; B3 mismatch sensitivity is not evidence of natural defects, source-qualified precision, or gate-effect improvement.'}


def render_tex(report:dict)->str:
    lines=['% B13.12 retrospective numeric sensitivity; NOT validated tolerances or gold.',
           r'\begin{tabular}{lrrrr}',r'\toprule',
           r'Pair & Tolerance (mmol/L) & B3 match & B3 mismatch & Abstain \\',r'\midrule']
    for p in report['pairs']:
        label=p['pair_id'].replace('_',r'\_')
        for v in p['grid']:
            lines.append(f"{label} & {v['tolerance_mmol_l']} & {v['satisfied']:,} & {v['mismatched']:,} & {v['abstained']:,} " + chr(92)*2)
    lines.extend([r'\bottomrule',r'\end{tabular}',
      '% The numerical grid was not independently justified; rows are not independent experiments.'])
    return '\n'.join(lines)+'\n'


def render_handover(report:dict)->str:
    note=['# B13.12 Numeric sensitivity — descriptive engineering results only','',
    'The three previously documented NHANES conversion rules were recompiled using B4 and executed by B3 under five previously declared numerical residual bins. These exploratory tolerances were not independently justified as semantic precision requirements. Counts were checked against an independent B13.9 aggregate residual implementation. Results illustrate the sensitivity of exact-equality mismatch counts to numerical tolerance choices, rather than validating any rule or detecting natural data errors.','',
    '| Pair | Tolerance (mmol/L) | B3 match | B3 mismatch | Abstain |','|---|---:|---:|---:|---:|']
    for p in report['pairs']:
        for v in p['grid']:
            note.append(f"| {p['pair_id']} | {v['tolerance_mmol_l']} | {v['satisfied']} | {v['mismatched']} | {v['abstained']} |")
    note.extend(['','**Cannot claim:** gold rounding, new discovery, false-positive reductions, superiority of A/B/C, or independent repetitions. All three pairs are previously exposed relationships from one survey-cycle cluster.'])
    return '\n'.join(note)+'\n'


def exclusive_save(cache:Path,root:Path,report:dict)->list[Path]:
    cache=assert_external_cache(cache,root)
    if not cache.is_dir():raise SensitivityError('External cache missing')
    destinations=[cache/n for n in OUTPUTS]
    if any(x.exists() for x in destinations):raise SensitivityError('Output exists; refusing overwrite')
    contents=[json.dumps(report,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n',render_tex(report),render_handover(report)]
    written=[]
    try:
        for dest,body in zip(destinations,contents):
            with dest.open('x',encoding='utf-8') as file:file.write(body)
            written.append(dest)
    except BaseException:
        for dest in written:
            if dest.exists():dest.unlink()
        raise
    return destinations
