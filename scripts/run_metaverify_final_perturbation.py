"""Submission-day controlled numeric-perturbation analysis for MetaVerify.

Runs on the existing official NHANES source receipts and B13.8--B13.12 parent
reports. Reports changes in executable outcomes after deliberately adding fixed
amounts to the recorded SI-unit column. No claim of clinical error detection,
independent precision truth, semantic admission, independent samples, or gold.

Usage, from the repository root:
    python scripts/run_metaverify_final_perturbation.py --selftest
    python scripts/run_metaverify_final_perturbation.py --cache-dir <external-cache>
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import io
import csv
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

THRESHOLDS = ("0.0005", "0.005")
SHIFTS = ("0.001", "0.005", "0.01")
STUDY = "metaverify_submission_day_controlled_precision_perturbation_v1"
OUT_JSON = "Submission_Day_Precision_Perturbation_v1.json"
OUT_CSV = "Submission_Day_Precision_Perturbation_v1.csv"

class PerturbationError(ValueError):
    pass


def is_pair_numeric(left, right):
    try:
        return math.isfinite(float(left)) and math.isfinite(float(right))
    except (TypeError, ValueError, OverflowError):
        return False


def evaluate_condition(rule, columns, values, context, shift, *, evaluate_row, validate_rule):
    """Return original/modified confusion and four-state counts (no row exports)."""
    refs = validate_rule(rule)
    if refs != set(columns):
        raise PerturbationError("Compiled rule unexpectedly references different columns")
    left_col, right_col = columns
    matrix = Counter()
    source_numeric = 0
    for left, right in values:
        row = {"_field_context": context, left_col: left, right_col: right}
        original = evaluate_row(rule, row, _validated_refs=refs).status
        if is_pair_numeric(left, right):
            source_numeric += 1
            modified = dict(row)
            # Add a fixed amount to one recorded SI value. This is a deliberate
            # synthetic perturbation, not a measurement or source correction.
            modified[right_col] = Decimal(str(right)) + Decimal(shift)
            after = evaluate_row(rule, modified, _validated_refs=refs).status
        else:
            after = original
        matrix[(original, after)] += 1
    orig = Counter({k:sum(n for (before, _),n in matrix.items() if before == k) for k in ('satisfied','violated','abstained','not_applicable')})
    changed = Counter({k:sum(n for (_,after),n in matrix.items() if after == k) for k in ('satisfied','violated','abstained','not_applicable')})
    if (orig['satisfied']+orig['violated'] != source_numeric or
        changed['satisfied']+changed['violated'] != source_numeric or
        orig['abstained']!=changed['abstained'] or
        orig['not_applicable']!=changed['not_applicable'] or
        orig['not_applicable'] != 0):
        raise PerturbationError("Perturbation unexpectedly changed coverage or applicability")
    return {
        'paired_nonmissing':source_numeric,
        'unchanged':{k:orig[k] for k in ('satisfied','violated','abstained','not_applicable')},
        'shifted':{k:changed[k] for k in ('satisfied','violated','abstained','not_applicable')},
        'satisfied_to_violated':matrix[('satisfied','violated')],
        'violated_to_satisfied':matrix[('violated','satisfied')],
        'transitions_recorded':sum(matrix.values()),
    }


def selftest():
    from src.rule_bridge import compile_proposal
    from src.generic_verifier import evaluate_row, validate_rule
    ds='precision-fixture'
    proposal={
        'proposal_version':'metaverify-proposal-v0.1', 'id':'synthetic_test',
        'dataset_id':ds,'origin':'controlled_test_only',
        'assertions':[{'left':{'column':'a'},'op':'eq','right':{'column':'b'},
                       'abs_tolerance':{'parameter':'tol'}}],
        'context_keys':['survey_cycle'],
    }
    registry={f'{ds}:tol':{'kind':'number','value':'0.005',
                          'origin':'fixture_only','rationale':'synthetic test tolerance'}}
    result=compile_proposal(proposal,['a','b'],registry)
    assert result.status=='candidate_executable_unverified',result.as_dict()
    context={'a':{'survey_cycle':'fixture'},'b':{'survey_cycle':'fixture'}}
    pairs=[(5.0,5.0),(5.0,4.997),(5.0,float('nan'))]
    case=evaluate_condition(result.rule,['a','b'],pairs,context,'0.01',
                            evaluate_row=evaluate_row,validate_rule=validate_rule)
    assert case['paired_nonmissing']==2
    assert case['unchanged']=={'satisfied':2,'violated':0,'abstained':1,'not_applicable':0}
    assert case['shifted']=={'satisfied':0,'violated':2,'abstained':1,'not_applicable':0}
    assert case['satisfied_to_violated']==2
    assert case['violated_to_satisfied']==0
    assert case['transitions_recorded']==3
    print('PRECISION PERTURBATION SELFTEST PASS: B4/B3 interface and paired transitions')


def run(cache:Path):
    import pyreadstat
    from src.b13_12_fixed_grid_sensitivity import (
        make_tolerance_compilation, run as verify_parent_experiment,
    )
    from src.b13_11_retrospective_matched_replay import load_inputs
    from src.b13_7_source_acquisition import assert_external_cache,verify_existing,sha256_file
    from src.b13_8_source_schema_audit import PINNED
    from src.generic_verifier import evaluate_row,validate_rule

    cache = assert_external_cache(cache, ROOT)
    if not cache.is_dir():
        raise PerturbationError('External source cache not found')
    if any((cache/n).exists() for n in (OUT_JSON,OUT_CSV)):
        raise PerturbationError('Analysis outputs already exist; refusing to overwrite')

    plan_path=ROOT/'data/evaluation/b13_12_sensitivity_spec_v1.json'
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    # Verifies the full upstream lineage and independently re-executes all
    # original B13.12 bins; does not write or overwrite their saved outputs.
    parent=verify_parent_experiment(cache,ROOT,plan)
    saved_parent_path=cache/'B13_12_fixed_grid_sensitivity_v1.json'
    if not saved_parent_path.is_file() or json.loads(saved_parent_path.read_text(encoding='utf-8')) != parent:
        raise PerturbationError('Recomputed B13.12 does not match its retained source-based report')
    baseline_by_pair={x['pair_id']:x for x in parent['pairs']}
    b1311_spec,b137,b138,b139,b1310=load_inputs(ROOT)
    sources={x['source_id']:x for x in b137['source_ids']}
    frames={}
    for sid in ('B13S-HLT-01','B13S-HLT-02'):
        receipt=verify_existing(sources[sid],cache)
        if (receipt['object_name'],receipt['sha256'],receipt['size_bytes'],receipt['source_group']) != PINNED[sid]:
            raise PerturbationError('Pinned official source identity changed')
        frame,_=pyreadstat.read_xport(str(cache/receipt['object_name']))
        frames[sid]=frame
    output=[]
    context_group='nhanes_2015_2016_cycle'
    for pair in b139['pairs']:
        pid,sid=pair['pair_id'],pair['source_id']
        if pid not in baseline_by_pair or sid not in frames:
            raise PerturbationError('Unexpected pair or source ID')
        baseline=baseline_by_pair[pid]
        for tol in THRESHOLDS:
            rule,columns=make_tolerance_compilation(pair,context_group,b1311_spec,tol)
            frame=frames[sid]
            if not set(columns).issubset(frame.columns):
                raise PerturbationError('Missing expected real source columns')
            values=list(zip(frame[columns[0]],frame[columns[1]]))
            ctx={col:{'survey_cycle':context_group} for col in columns}
            expected=next(x for x in baseline['grid'] if x['tolerance_mmol_l']==tol)
            for shift in SHIFTS:
                result=evaluate_condition(rule,columns,values,ctx,shift,evaluate_row=evaluate_row,validate_rule=validate_rule)
                if (result['unchanged']['satisfied'] != expected['satisfied'] or
                    result['unchanged']['violated'] != expected['mismatched'] or
                    result['unchanged']['abstained'] != expected['abstained'] or
                    result['paired_nonmissing'] != baseline['paired_nonmissing']):
                    raise PerturbationError('Unmodified source counts disagree with audited B13.12 baseline')
                output.append({'pair_id':pid,'tolerance_mmol_l':tol,'added_to_recorded_right_mmol_l':shift,**result})
    for sid in frames:
        receipt=sources[sid]
        if sha256_file(cache/receipt['object_name'])!=PINNED[sid][1]:
            raise PerturbationError('Source changed during perturbation study')
    if len(output)!=len(b139['pairs'])*len(THRESHOLDS)*len(SHIFTS):
        raise PerturbationError('Experiment cells missing')
    report={
        'study_id':STUDY,
        'classification':'retrospective_controlled_numeric_perturbation_not_natural_errors_or_gold',
        'source_clusters':1,
        'hand_curated_previously_exposed_relationships':len(b139['pairs']),
        'exploratory_tolerances_mmol_l':list(THRESHOLDS),
        'positive_SI_unit_perturbations_mmol_l':list(SHIFTS),
        'parent_B13_12_report_study_id':parent['study_id'],
        'parent_B13_12_spec_sha256':hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        'independently_justified_precision':False,
        'independent_semantic_gold':0,
        'natural_errors_labelled':0,
        'candidate_admission_accuracy_measured':False,
        'published_baseline_measured':False,
        'experimental_unit':'controlled modification of source pair-records; repeated source rows across cells',
        'cells':output,
        'limitations':['Same previously examined NHANES survey cycle, not new validation cohort',
                       'Original rows are not guaranteed correct and altered rows are controlled interventions',
                       'The synthetic modifications target the same expressions tested; no independent natural-error detection recall',
                       'Reused exploratory tolerances do not prove official rounding conventions',
                       'Repeated cells are not independent samples; no inferential accuracy statistics justified'],
    }
    headers=['pair_id','tolerance_mmol_l','added_to_recorded_right_mmol_l','paired_nonmissing',
             'unmodified_violated','modified_violated','newly_flagged','previously_flagged_now_satisfied','abstained']
    buf=io.StringIO(newline='')
    wr=csv.DictWriter(buf,fieldnames=headers,lineterminator='\n')
    wr.writeheader()
    for item in output:
        wr.writerow({'pair_id':item['pair_id'],
                     'tolerance_mmol_l':item['tolerance_mmol_l'],
                     'added_to_recorded_right_mmol_l':item['added_to_recorded_right_mmol_l'],
                     'paired_nonmissing':item['paired_nonmissing'],
                     'unmodified_violated':item['unchanged']['violated'],
                     'modified_violated':item['shifted']['violated'],
                     'newly_flagged':item['satisfied_to_violated'],
                     'previously_flagged_now_satisfied':item['violated_to_satisfied'],
                     'abstained':item['unchanged']['abstained']})
    targets=(cache/OUT_JSON,cache/OUT_CSV)
    try:
        with targets[0].open('x',encoding='utf-8') as f:
            json.dump(report,f,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)
            f.write('\n')
        with targets[1].open('x',encoding='utf-8',newline='') as f:
            f.write(buf.getvalue())
    except BaseException:
        for p in targets:p.unlink(missing_ok=True)
        raise
    print('CONTROLLED PRECISION PERTURBATION COMPLETE; NOT INDEPENDENT GOLD OR NATURAL ERROR ACCURACY')
    print('source clusters:',report['source_clusters'],'pairs:',report['hand_curated_previously_exposed_relationships'],'cells:',len(output))
    for item in output:
        print(item['pair_id'],'tol',item['tolerance_mmol_l'],'shift',item['added_to_recorded_right_mmol_l'],
              'unmodified mismatch',item['unchanged']['violated'],
              'modified mismatch',item['shifted']['violated'],
              'newly flagged',item['satisfied_to_violated'])
    for p in targets:print('SAVED:',p)
    print('Do not report these controlled perturbations as naturally occurring defects or semantic gate accuracy.')


def main():
    arg=argparse.ArgumentParser(description=__doc__)
    arg.add_argument('--selftest',action='store_true')
    arg.add_argument('--cache-dir',type=Path)
    args=arg.parse_args()
    if args.selftest:
        selftest()
    else:
        if args.cache_dir is None:arg.error('--cache-dir is required')
        run(args.cache_dir)

if __name__=='__main__':
    try:main()
    except (PerturbationError,ValueError,OSError,ImportError,KeyError) as e:
        print('PERTURBATION STOP:',e,file=sys.stderr)
        raise SystemExit(2)
