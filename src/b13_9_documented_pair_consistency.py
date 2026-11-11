"""B13.9: read-only exploratory consistency of *already-documented* NHANES unit pairs.

Never emits source rows, SEQNs, participant values, predicted values, or violations.
Only aggregate residual summaries; not a source-qualified gold reference.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
import math
from pathlib import Path

from src.b13_7_source_acquisition import assert_external_cache, verify_existing, sha256_file, validate_registry
from src.b13_8_source_schema_audit import AuditError, PINNED, STUDY as PARENT_STUDY, canonical_sha, validate_plan as validate_b138_plan

STUDY = 'b13_9_documented_unit_pair_consistency_v1'
BINS = ('0.0005', '0.005', '0.01', '0.05', '0.1')
PAIRS = (
    ('TRIGLY_TR_UNIT', 'B13S-HLT-01', 'LBXTR', 'LBDTRSI', '0.01129', 'https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/TRIGLY_I.htm', 'Data Processing and Editing > LBDTRSI'),
    ('TRIGLY_LDL_UNIT', 'B13S-HLT-01', 'LBDLDL', 'LBDLDLSI', '0.02586', 'https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/TRIGLY_I.htm', 'Data Processing and Editing > LBDLDLSI'),
    ('TCHOL_TC_UNIT', 'B13S-HLT-02', 'LBXTC', 'LBDTCSI', '0.02586', 'https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/TCHOL_I.htm', 'Data Processing and Editing > LBDTCSI'),
)

class PairAuditError(ValueError):
    """Unexpected source object, schema, output or scientific claim."""


def validate_plan(plan: dict) -> None:
    if not isinstance(plan, dict) or plan.get('study_id') != STUDY:
        raise PairAuditError('Unrecognized B13.9 plan')
    if plan.get('phase') != 'retrospective_exploratory_after_source_exposure_not_confirmatory':
        raise PairAuditError('Must disclose previous documentary exposure')
    if plan.get('parent_study_id') != PARENT_STUDY or plan.get('source_group') != 'nhanes_2015_2016_cycle':
        raise PairAuditError('Wrong parent study/source group')
    if plan.get('input_policy') != 'only_exact_B13_7_receipt_verified_files_and_existing_B13_8_aggregate_report':
        raise PairAuditError('Source policy changed')
    if plan.get('output_policy') != 'exclusive_aggregate_json_in_external_cache_no_rows_or_identifiers':
        raise PairAuditError('Output policy changed')
    actual_pairs = plan.get('pairs')
    if not isinstance(actual_pairs, list) or len(actual_pairs) != len(PAIRS):
        raise PairAuditError('Wrong number of documented unit pairs')
    for p, expected in zip(actual_pairs, PAIRS):
        if not isinstance(p, dict) or tuple(p.get(k) for k in ('pair_id', 'source_id', 'left_column', 'right_column', 'factor', 'documentation_url', 'documentation_section')) != expected:
            raise PairAuditError('Documented source pair changed or unsupported')
        if p.get('units') != 'mg/dL_to_mmol/L':
            raise PairAuditError('Unexpected unit interpretation')
        if set(p) != {'pair_id', 'source_id', 'left_column', 'right_column', 'factor', 'units', 'documentation_url', 'documentation_section'}:
            raise PairAuditError('Unexpected pair fields')
    if plan.get('absolute_residual_thresholds_mmol_l') != list(BINS):
        raise PairAuditError('Exploratory bins changed')
    if plan.get('primary_purpose') != 'aggregate_empirical_consistency_with_published_unit_factors_without_fitting_precision':
        raise PairAuditError('Purpose changed')
    for key in ('cross_file_clinical_join_performed', 'fasting_age_or_morning_eligibility_verified',
                'fitted_rounding_or_tolerance', 'source_eligibility_confirmed',
                'independent_reference_truth_confirmed', 'real_gate_evaluation_allowed'):
        if plan.get(key) is not False:
            raise PairAuditError('Unsupported validation/gate claim: ' + key)
    if plan.get('allowed_claims') != ['documented_factors_exploratory_recorded_value_consistency']:
        raise PairAuditError('Claim set changed')
    if set(plan.get('disallowed_claims', [])) != {'blinded_discovery', 'source_authenticity_confirmed', 'clinical_reference_truth', 'precision_gold', 'natural_error_detection', 'prospective_gate_effect', 'independent_gold'}:
        raise PairAuditError('Disallowed claims changed')


def _number(value: object) -> Decimal | None:
    if value is None:
        return None
    # pandas/numpy missing scalars (np.nan, pd.NA, etc.)
    try:
        if bool(math.isnan(float(value))):
            return None
    except (ValueError, TypeError, OverflowError):
        pass
    if isinstance(value, bool):
        raise PairAuditError('Boolean value in clinical numeric field')
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PairAuditError('Unexpected nonnumeric source field') from exc
    if not result.is_finite():
        raise PairAuditError('Unexpected nonfinite source field')
    return result


def _percentile(sorted_values: list[Decimal], pct: int) -> str | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return str(sorted_values[0])
    pos = Decimal(len(sorted_values)-1) * Decimal(pct) / Decimal(100)
    lo, hi = int(pos), int(pos.to_integral_value(rounding='ROUND_CEILING'))
    return str(sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo))


def summarize_pair(left: object, right: object, factor: str, thresholds: tuple[str, ...] = BINS) -> dict:
    if len(left) != len(right):
        raise PairAuditError('Misaligned columns')
    conversion = Decimal(factor)
    if not conversion.is_finite() or conversion <= 0:
        raise PairAuditError('Bad documented conversion factor')
    bins = [Decimal(t) for t in thresholds]
    if not bins or any(not b.is_finite() or b <= 0 for b in bins) or bins != sorted(set(bins)):
        raise PairAuditError('Invalid exploratory descriptive bins')
    n = len(left)
    if n <= 0:
        raise PairAuditError('Empty source')
    missing_both = missing_left = missing_right = 0
    below = [0] * len(bins)
    residuals: list[Decimal] = []
    for lv, rv in zip(left, right):
        x, y = _number(lv), _number(rv)
        if x is None and y is None:
            missing_both += 1
        elif x is None:
            missing_left += 1
        elif y is None:
            missing_right += 1
        else:
            resid = abs(y - x * conversion)
            residuals.append(resid)
            for j, threshold in enumerate(bins):
                if resid <= threshold:
                    below[j] += 1
    residuals.sort()
    return {
        'rows_total': n,
        'paired_nonmissing': len(residuals),
        'both_missing': missing_both,
        'only_left_missing': missing_left,
        'only_right_missing': missing_right,
        'absolute_residual_mmol_l': {
            'median': _percentile(residuals, 50),
            'p95': _percentile(residuals, 95),
            'max': str(residuals[-1]) if residuals else None,
            'threshold_counts_cumulative': {s: below[i] for i, s in enumerate(thresholds)},
        },
        'precision_or_rounding_gold_established': False,
        'discrepancies_adjudicated_as_errors': 0,
    }


def _check_b138_report(report: dict, registry: dict, b138_plan: dict) -> None:
    if report.get('study_id') != PARENT_STUDY or report.get('classification') != 'exploratory_source_schema_characterization_only':
        raise PairAuditError('Unrecognized B13.8 report')
    if report.get('source_registry_canonical_sha256') != canonical_sha(registry) or report.get('b13_8_plan_canonical_sha256') != canonical_sha(b138_plan):
        raise PairAuditError('B13.8 source/plan ancestry differs')
    receipts = report.get('source_file_receipts')
    expected = [{'source_id': sid, 'source_group': tup[3], 'sha256': tup[1], 'size_bytes': tup[2]}
                for sid, tup in PINNED.items()]
    if receipts != expected:
        raise PairAuditError('B13.8 source receipts changed')
    if report.get('real_candidates_generated') != 0 or report.get('real_gate_executions') != 0 or report.get('independently_adjudicated_gold_rules') != 0:
        raise PairAuditError('Unexpected previous-stage claims')
    if report.get('source_semantic_eligibility_verified') is not False:
        raise PairAuditError('Unexpected source eligibility claim')
    healthcare = report.get('healthcare')
    if not isinstance(healthcare, list) or [h.get('source_id') for h in healthcare] != ['B13S-HLT-01', 'B13S-HLT-02']:
        raise PairAuditError('Wrong B13.8 healthcare records')
    if report.get('nhanes_cycle_join_inventory', {}).get('raw_identifiers_emitted') is not False:
        raise PairAuditError('B13.8 privacy status unexpected')


def audit_pairs(cache: Path, repo_root: Path, plan: dict, registry: dict, b138_plan: dict) -> dict:
    validate_plan(plan)
    validate_b138_plan(b138_plan, registry)
    validate_registry(registry)
    cache = assert_external_cache(cache, repo_root)
    b138_path = cache / 'B13_8_source_schema_audit_v1.json'
    b138_before = sha256_file(b138_path)
    report_b138 = json.loads(b138_path.read_text(encoding='utf-8'))
    _check_b138_report(report_b138, registry, b138_plan)
    originals = {x['source_id']: x for x in registry['source_ids']}
    for sid in ('B13S-HLT-01', 'B13S-HLT-02'):
        verify_existing(originals[sid], cache)
    try:
        import pyreadstat
    except ImportError as exc:
        raise PairAuditError('pyreadstat required for XPT source inspection') from exc
    frames = {}
    for sid in ('B13S-HLT-01', 'B13S-HLT-02'):
        frame, _ = pyreadstat.read_xport(str(cache / originals[sid]['object_name']))
        # Do not serialize frame/values.
        if len(frame) != next(h['row_count'] for h in report_b138['healthcare'] if h['source_id'] == sid):
            raise PairAuditError('XPT row count changed since B13.8')
        frames[sid] = frame
    summaries = []
    for item in plan['pairs']:
        f = frames[item['source_id']]
        if item['left_column'] not in f.columns or item['right_column'] not in f.columns:
            raise PairAuditError('Missing documented paired unit columns')
        pair = summarize_pair(f[item['left_column']], f[item['right_column']], item['factor'])
        summaries.append({'pair_id': item['pair_id'], 'source_id': item['source_id'],
                          'published_factor': item['factor'],
                          'documentation_url': item['documentation_url'],
                          'units': item['units'], 'aggregates': pair,
                          'interpretation': 'recorded_value_consistency_only_not_gold'})
    for sid in ('B13S-HLT-01', 'B13S-HLT-02'):
        if sha256_file(cache / originals[sid]['object_name']) != PINNED[sid][1]:
            raise PairAuditError('Source changed during B13.9 inspection')
    if sha256_file(b138_path) != b138_before:
        raise PairAuditError('B13.8 report changed during inspection')
    return {
        'study_id': STUDY,
        'classification': 'retrospective_documented_conversion_descriptive_audit_not_gold',
        'b13_9_plan_canonical_sha256': canonical_sha(plan),
        'b13_8_aggregate_sha256': b138_before,
        'source_group': 'nhanes_2015_2016_cycle',
        'conversion_pairs': summaries,
        'source_eligibility_confirmed': False,
        'fitted_tolerance_or_rounding': False,
        'cross_file_clinical_join_performed': False,
        'real_candidate_admission_runs': 0,
        'independently_adjudicated_gold_rules': 0,
        'known_limitation': 'The factors were read from official CDC documentation before this analysis; numeric residuals cannot identify independent reference precision, ground-truth defects or blinded rule discovery.'
    }


def exclusive_save(cache: Path, repo_root: Path, payload: dict) -> Path:
    cache = assert_external_cache(cache, repo_root)
    dest = cache / 'B13_9_documented_pair_consistency_v1.json'
    with dest.open('x', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        f.write('\n')
    return dest
