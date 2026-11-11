"""Matched *numeric coefficient* baseline study for MetaVerify (not SOTA reproduction).

Compares the identical restricted B4/B3 executable unit-conversion predicate
using (1) the previously documented CDC coefficient, (2) a training-only
median-ratio coefficient, and (3) a training-only zero-intercept least-squares
coefficient. Uses a fixed SEQN-hash 50/50 participant split within the same
previously inspected NHANES cycle; tests two exploratory tolerances and fixed
positive/negative SI-unit perturbations on *test* records only. Every method
uses the same source rows, B4 compiler, B3 verifier, and tolerance.

NOT: Auto-Test/Guardrail implementation, novel discovery, independent semantic
truth, natural-error accuracy, new source cohorts, or statistical superiority.

Run from ICDE repository root:
  python scripts/run_metaverify_matched_numeric_baselines.py --selftest
  python scripts/run_metaverify_matched_numeric_baselines.py --cache-dir "H:\\nrr136 data\\ICDE-B13-Source-Cache"
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
STUDY = "metaverify_matched_numeric_coefficient_baselines_v1"
OUT_JSON = "Submission_Day_Matched_Numeric_Baselines_v1.json"
OUT_CSV = "Submission_Day_Matched_Numeric_Baselines_v1.csv"
SPLIT_SALT = "metaverify_numeric_baseline_2026_11_11_v1"
TOLERANCES = ("0.0005", "0.005")  # exploratory, source precision NOT certified
SHIFTS = ("-0.01", "-0.005", "-0.001", "0.001", "0.005", "0.01")
METHODS = ("documented_cdc_factor", "train_median_ratio", "train_least_squares")

class BaselineError(ValueError):
    pass


def is_finite_num(x):
    try:
        return x is not None and not isinstance(x, bool) and math.isfinite(float(x))
    except (TypeError, ValueError, OverflowError):
        return False


def participant_partition(seqn):
    """Freeze participant partition independent of numerical columns or outcomes."""
    if not is_finite_num(seqn) or float(seqn) != int(float(seqn)):
        raise BaselineError("Missing/noninteger SEQN cannot be assigned a participant partition")
    token = (SPLIT_SALT + ':' + str(int(float(seqn)))).encode('ascii')
    digest = hashlib.sha256(token).digest()
    return 'train' if (int.from_bytes(digest[:8], 'big') % 2) == 0 else 'test'


def coefficients(train_pairs):
    """Fit on frozen training records only; no test-dependent tuning."""
    usable = [(float(x), float(y)) for x, y in train_pairs
              if is_finite_num(x) and is_finite_num(y) and float(x) > 0]
    if len(usable) < 12:
        raise BaselineError("Too few finite positive training pairs")
    ratios = [y / x for x, y in usable]
    denom = math.fsum(x*x for x, _ in usable)
    if denom <= 0 or not math.isfinite(denom):
        raise BaselineError("Invalid regression denominator")
    median = statistics.median(ratios)
    ls = math.fsum(x*y for x, y in usable) / denom
    if not all(math.isfinite(x) and x > 0 for x in (median, ls)):
        raise BaselineError("Fitted coefficients were not finite and positive")
    # Preserve sufficient precision for registration and deterministic reuse.
    return {'train_median_ratio': format(median,'.17g'),
            'train_least_squares': format(ls,'.17g')}, len(usable)


def compile_typed_rule(pair, coefficient, method, tol, *, compiler):
    """Identical B4/B3 rule form across methods, changing only the coefficient."""
    ds = 'matched_numeric_' + pair['pair_id'] + '_' + method + '_' + tol.replace('.', 'p')
    left, right = pair['left_column'], pair['right_column']
    proposal = {
        'proposal_version': 'metaverify-proposal-v0.1',
        'id': ds, 'dataset_id': ds,
        'origin': 'pre_exposed_exploratory_matched_numeric_baseline_not_confirmatory',
        'assertions': [{'left': {'column': right}, 'op': 'eq',
                        'right': {'multiply': [{'column': left}, {'parameter': 'factor'}]},
                        'abs_tolerance': {'parameter': 'tolerance'}}],
        'context_keys': ['survey_cycle'],
    }
    documented = (method == 'documented_cdc_factor')
    factor_entry = {
        'kind': 'number', 'value': coefficient,
        'origin': 'documented_reference' if documented else 'empirical_same_dataset',
        'rationale': ('Previously exposed CDC-documented conversion factor; no confirmed rounding'
                      if documented else 'Coefficient fitted only on frozen same-cycle training participant partition'),
    }
    if documented:
        factor_entry['source_url'] = pair['documentation_url']
    registry = {ds + ':factor': factor_entry,
                ds + ':tolerance': {
                    'kind': 'number', 'value': tol, 'origin': 'empirical_same_dataset',
                    'rationale': 'Fixed exploratory grid from B13.12, not a validated source precision requirement',
                }}
    compilation = compiler(proposal, [left, right], registry)
    if compilation.status != 'candidate_executable_unverified' or compilation.rule is None:
        raise BaselineError('B4 rejected frozen baseline hypothesis: ' + compilation.reason)
    return compilation.rule


def evaluate_comparable(rule, left, right, records, shift, *, eval_row, validate_rule):
    refs = validate_rule(rule)
    if refs != {left, right}:
        raise BaselineError('Compiled rule changed the referenced columns')
    ctx = {left: {'survey_cycle': 'nhanes_2015_2016_cycle'},
           right: {'survey_cycle': 'nhanes_2015_2016_cycle'}}
    matrix = {}
    complete = 0
    for x, y in records:
        row = {left: x, right: y, '_field_context': ctx}
        before = eval_row(rule, row, _validated_refs=refs).status
        if is_finite_num(x) and is_finite_num(y):
            complete += 1
            modified = {**row, right: Decimal(str(y)) + Decimal(shift)}
            after = eval_row(rule, modified, _validated_refs=refs).status
        else:
            after = before
        matrix[before, after] = matrix.get((before,after), 0) + 1
    original_viol = sum(v for (b,a),v in matrix.items() if b == 'violated')
    shifted_viol = sum(v for (b,a),v in matrix.items() if a == 'violated')
    originally_pass = sum(v for (b,a),v in matrix.items() if b == 'satisfied')
    abstain = sum(v for (b,a),v in matrix.items() if b == 'abstained')
    assert complete + abstain == len(records), 'Unexpected applicability or record outcomes'
    assert originally_pass + original_viol == complete
    return {
       'test_nonmissing': complete, 'test_abstained': abstain,
       'unmodified_satisfied': originally_pass,
       'unmodified_violated': original_viol,
       'modified_violated': shifted_viol,
       'newly_flagged': matrix.get(('satisfied','violated'),0),
       'violated_to_satisfied': matrix.get(('violated','satisfied'),0),
       'unchanged_pass': matrix.get(('satisfied','satisfied'),0),
       'both_violations': matrix.get(('violated','violated'),0),
    }


def selftest():
    from src.rule_bridge import compile_proposal
    from src.generic_verifier import evaluate_row, validate_rule
    assert participant_partition(123456) == participant_partition(123456)
    sample = [(100,2.50),(200,5.00),(80,2.00)]*12
    fitted,n = coefficients(sample)
    assert n == 36
    assert abs(float(fitted['train_median_ratio']) - .025) < 1e-12
    assert abs(float(fitted['train_least_squares']) - .025) < 1e-12
    pair = {'pair_id':'TEST','left_column':'mg','right_column':'si','documentation_url':'https://example.org/source'}
    rule=compile_typed_rule(pair,'0.025','documented_cdc_factor','0.005',compiler=compile_proposal)
    records=[(100,2.5),(100,2.499),(100,None)]
    r=evaluate_comparable(rule,'mg','si',records,'0.01',eval_row=evaluate_row,validate_rule=validate_rule)
    assert r['test_nonmissing'] == 2 and r['test_abstained'] == 1 and r['unmodified_violated'] == 0
    assert r['newly_flagged'] == 2 and r['modified_violated'] == 2,r
    print('MATCHED BASELINES SELFTEST PASS: split, training-only fitting, actual B4/B3 comparison')


def run(cache):
    import pyreadstat
    from src.rule_bridge import compile_proposal
    from src.generic_verifier import evaluate_row, validate_rule
    from src.b13_11_retrospective_matched_replay import load_inputs, validate_spec
    from src.b13_7_source_acquisition import verify_existing, assert_external_cache, sha256_file
    from src.b13_8_source_schema_audit import PINNED

    cache = assert_external_cache(cache, ROOT)
    if not cache.is_dir():
        raise BaselineError('External NHANES source cache absent')
    for name in (OUT_JSON,OUT_CSV):
        if (cache/name).exists():
            raise BaselineError('Output exists, refusing to overwrite: '+name)

    spec,b137,b138,b139,b1310=load_inputs(ROOT)
    validate_spec(spec,b137,b138,b139,b1310)
    receipts={}
    sources={x['source_id']:x for x in b137['source_ids']}
    for sid in ('B13S-HLT-01','B13S-HLT-02'):
        receipt = verify_existing(sources[sid],cache)
        if (receipt['object_name'],receipt['sha256'],receipt['size_bytes'],receipt['source_group']) != PINNED[sid]:
            raise BaselineError('Source registry mismatch: '+sid)
        receipts[sid]=receipt
    # Recheck output lineage, not just source names.
    original = cache/'B13_11_retrospective_matched_replay_v1.json'
    if not original.is_file():
        raise BaselineError('Audited B13.11 parent report missing')
    parent=json.loads(original.read_text(encoding='utf-8'))
    if parent.get('study_id')!='b13_11_real_xpt_matched_compiler_diagnostic_v1':
        raise BaselineError('Wrong B13.11 parent report')
    frames={sid:pyreadstat.read_xport(str(cache/receipt['object_name']))[0] for sid,receipt in receipts.items()}
    expected_count={x['pair_id']:x['aggregates']['paired_nonmissing'] for x in
        json.loads((cache/'B13_9_documented_pair_consistency_v1.json').read_text(encoding='utf-8'))['conversion_pairs']}
    results=[]
    fit_summaries=[]
    for item in b139['pairs']:
        pid,sid=item['pair_id'],item['source_id']
        df=frames[sid]
        left,right=item['left_column'],item['right_column']
        if any(c not in df.columns for c in (left,right,'SEQN')):
            raise BaselineError('Source columns/participant ID absent: '+pid)
        train,test=[],[]
        seen=set()
        for seqn,x,y in zip(df['SEQN'],df[left],df[right]):
            if not is_finite_num(seqn) or float(seqn) != int(float(seqn)):
                raise BaselineError('Invalid SEQN identifier')
            key=int(float(seqn))
            if key in seen:
                raise BaselineError('Duplicate participant ID within file: '+pid)
            seen.add(key)
            (train if participant_partition(seqn)=='train' else test).append((x,y))
        if not train or not test:
            raise BaselineError('Empty participant partition')
        fit,n=coefficients(train)
        observed_paired=sum(is_finite_num(x) and is_finite_num(y) for x,y in train+test)
        if observed_paired!=expected_count[pid]:
            raise BaselineError('Pair count differs from audited B13.9 result: '+pid)
        factor_values={'documented_cdc_factor':item['factor'],**fit}
        fit_summaries.append({'pair_id':pid,'train_rows':len(train),'train_nonmissing':n,
                              'test_rows':len(test),'test_nonmissing':sum(is_finite_num(x) and is_finite_num(y) for x,y in test),
                              'factors':factor_values})
        for method in METHODS:
            for tol in TOLERANCES:
                rule=compile_typed_rule(item,factor_values[method],method,tol,compiler=compile_proposal)
                baseline_unmodified=None
                for shift in SHIFTS:
                    r=evaluate_comparable(rule,left,right,test,shift,eval_row=evaluate_row,validate_rule=validate_rule)
                    anchor=(r['test_nonmissing'],r['test_abstained'],r['unmodified_satisfied'],r['unmodified_violated'])
                    if baseline_unmodified is None:
                        baseline_unmodified=anchor
                    elif anchor!=baseline_unmodified:
                        raise BaselineError('Observed baseline changed across shifts')
                    results.append({'pair_id':pid,'method':method,'tolerance_mmol_l':tol,
                                    'synthetic_shift_mmol_l':shift, **r})
    for sid,receipt in receipts.items():
        if sha256_file(cache/receipt['object_name']) != receipt['sha256']:
            raise BaselineError('Source changed during evaluation: '+sid)
    if len(results)!=3*len(METHODS)*len(TOLERANCES)*len(SHIFTS):
        raise BaselineError('Incomplete comparison grid')
    report={'study_id':STUDY,'classification':'retrospective_matched_numeric_rule_coefficient_comparison_not_published_sota',
            'source_group_count':1,'participant_split':'fixed_SHA256_of_NHANES_SEQN_disjoint_within_pair',
            'split_salt':SPLIT_SALT,
            'verified_source_sha256_by_id':{sid:receipt['sha256'] for sid,receipt in receipts.items()},
            'parent_b13_11_sha256':sha256_file(original),
            'pairs':fit_summaries,'cells':results,
            'methods':{'documented_cdc_factor':'previously exposed CDC factor (MetaVerify B4/B3)',
                       'train_median_ratio':'data-only, fitted from train, same MetaVerify B4/B3',
                       'train_least_squares':'data-only, zero-intercept OLS from train, same MetaVerify B4/B3'},
            'exploratory_tolerances_mmol_l':list(TOLERANCES),'test_only_shifts_mmol_l':list(SHIFTS),
            'real_sota_guardrail_run':False,'real_sota_autotest_run':False,'independent_semantic_gold':0,
            'notes':['All method comparisons run on identical test participants and verifier; coefficients differ',
                     'Data-only coefficients see training records only; existing NHANES cycle was previously exposed',
                     'No claim original records are valid or perturbed records constitute natural errors',
                     'Newly flagged transitions are conditional on the same method passing the original record',
                     'The comparison does not estimate semantic quality, accuracy, precision, recall or admission effect',
                     'Same underlying cycle across three pairs; rows and perturbation cells are not independent trials',
                     'The common tolerance choices were previously explored; no holdout-based hyperparameter tuning'],
            }
    headers=['pair_id','method','tolerance_mmol_l','synthetic_shift_mmol_l','test_nonmissing',
             'test_abstained','unmodified_satisfied','unmodified_violated','modified_violated',
             'newly_flagged','violated_to_satisfied','unchanged_pass','both_violations']
    buf=io.StringIO(newline='')
    writer=csv.DictWriter(buf,fieldnames=headers,lineterminator='\n');writer.writeheader()
    for row in results:writer.writerow({k:row[k] for k in headers})
    files=[cache/OUT_JSON,cache/OUT_CSV]
    written=[]
    try:
        with files[0].open('x',encoding='utf-8') as handle:
            json.dump(report,handle,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)
            handle.write('\n')
        written.append(files[0])
        with files[1].open('x',encoding='utf-8',newline='') as handle:handle.write(buf.getvalue())
        written.append(files[1])
    except BaseException:
        for f in written:f.unlink(missing_ok=True)
        raise
    print('MATCHED NUMERIC BASELINE COMPARISON COMPLETE — NOT SOTA, GOLD, OR NATURAL-ERROR ACCURACY')
    print('One previously inspected NHANES cycle; three pairs, 3 coefficient methods, 2 tolerances, 6 signed shifts')
    for s in fit_summaries:
        print(s['pair_id'],'train',s['train_nonmissing'],'test',s['test_nonmissing'],
              'published',s['factors']['documented_cdc_factor'],
              'median',s['factors']['train_median_ratio'],
              'OLS',s['factors']['train_least_squares'])
    for row in results:
        if row['synthetic_shift_mmol_l']=='0.01' and row['tolerance_mmol_l']=='0.005':
            print('RESULT',row['pair_id'],row['method'],'tol',row['tolerance_mmol_l'],
                  '+shift',row['synthetic_shift_mmol_l'],
                  'original_mismatches',row['unmodified_violated'],
                  'shifted_mismatches',row['modified_violated'],
                  'new_flags',row['newly_flagged'])
    for path in files:print('SAVED:',path)


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--selftest',action='store_true')
    cli.add_argument('--cache-dir',type=Path)
    args=cli.parse_args()
    if args.selftest:
        selftest()
    else:
        if args.cache_dir is None:cli.error('--cache-dir required')
        run(args.cache_dir)

if __name__=='__main__':
    try:main()
    except (BaselineError,ValueError,OSError,ImportError,KeyError,AssertionError) as e:
        print('MATCHED BASELINE STOP:',e,file=sys.stderr)
        raise SystemExit(2)
