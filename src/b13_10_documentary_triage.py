"""B13.10: aggregate-only retrospective source-documentation/applicability triage.

No raw participant rows, source downloads, discovery, fitted precision, gate calls,
or independent reference adjudication. The dossier is NOT evidence of causal effect.
"""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from src.b13_7_source_acquisition import assert_external_cache, validate_registry, sha256_file
from src.b13_8_source_schema_audit import canonical_sha, validate_plan as validate_b138_plan, PINNED
from src.b13_9_documented_pair_consistency import validate_plan as validate_b139_plan, _check_b138_report

STUDY = 'b13_10_documentary_evidence_and_applicability_triage_v1'
ORDER = ('TRIGLY_TR_UNIT', 'TRIGLY_LDL_UNIT', 'TCHOL_TC_UNIT', 'STEEL_FAULT_ONEHOT')
STATUSES = ('explicit_published_factor', 'seven_categories_described_not_exactly_one_axiom')
EXPECTED_SOURCE_IDS = {
    'TRIGLY_TR_UNIT': ('B13S-HLT-01',),
    'TRIGLY_LDL_UNIT': ('B13S-HLT-01',),
    'TCHOL_TC_UNIT': ('B13S-HLT-02',),
    'STEEL_FAULT_ONEHOT': ('B13S-MAN-01',),
}

class TriageError(ValueError):
    """Source lineage, data integrity or claim boundaries failed."""


def _decimal_nonnegative(value: object) -> Decimal:
    if not isinstance(value, str):
        raise TriageError('Residual is not a decimal string')
    try:
        x = Decimal(value)
    except InvalidOperation as exc:
        raise TriageError('Malformed residual') from exc
    if not x.is_finite() or x < 0:
        raise TriageError('Nonfinite or negative residual')
    return x


def validate_register(reg: dict, b137: dict, b139: dict) -> None:
    validate_registry(b137)
    validate_b139_plan(b139)
    if not isinstance(reg, dict) or reg.get('study_id') != STUDY:
        raise TriageError('Wrong study identifier')
    if reg.get('phase') != 'retrospective_source_documentation_triage_not_gold_not_confirmatory':
        raise TriageError('B13.10 must remain exploratory')
    if reg.get('parent_b13_9_plan_canonical_sha256') != canonical_sha(b139):
        raise TriageError('B13.9 study plan ancestry changed')
    if reg.get('parent_b13_7_registry_canonical_sha256') != canonical_sha(b137):
        raise TriageError('B13.7 source registry ancestry changed')
    for flag in ('independent_review_performed', 'real_candidate_gates_performed',
                 'source_authenticity_independently_confirmed', 'context_policy_frozen_for_real_source'):
        if reg.get(flag) is not False:
            raise TriageError('Unsupported independent assessment claim: '+flag)
    if reg.get('previously_exposed_documents') is not True:
        raise TriageError('Missing previous-exposure disclosure')
    if reg.get('research_claims_allowed') != ['documented_factors_recorded',
                                              'observed_representational_pattern',
                                              'limitations_of_current_executable_context_guard']:
        raise TriageError('Permitted claim list altered')
    if set(reg.get('research_claims_forbidden', [])) != {'independently_adjudicated_gold',
            'novel_rule_discovery','precision_truth','confirmed_data_error',
            'prospective_three_arm_effect','source_eligibility_confirmed'}:
        raise TriageError('Forbidden claim set altered')
    items = reg.get('evidence_items')
    if not isinstance(items, list) or [v.get('item_id') for v in items if isinstance(v, dict)] != list(ORDER):
        raise TriageError('Wrong frozen evidence item list')
    plan_pairs = {x['pair_id']:x for x in b139['pairs']}
    known_source = {x['source_id']:x for x in b137['source_ids']}
    for row in items:
        item_id = row['item_id']
        if row.get('source_ids') != list(EXPECTED_SOURCE_IDS[item_id]):
            raise TriageError('Source identity changed: '+item_id)
        src = known_source[row['source_ids'][0]]
        if row.get('source_group') != src['source_group'] or row.get('documentation_url') != src['documentation_url']:
            raise TriageError('Source documentation provenance changed: '+item_id)
        for field in ('documentation_locator','applicability_note','eligibility_evidence_gap','b3_execution_gap'):
            if not isinstance(row.get(field), str) or len(row[field]) < 12:
                raise TriageError('Missing source-specific rationale: '+field)
        if item_id in plan_pairs:
            p = plan_pairs[item_id]
            if (row.get('kind'),row.get('documentary_status'),row.get('documented_factor'),
                row.get('documentation_locator'),row.get('recommendation')) != (
                'published_unit_conversion','explicit_published_factor',p['factor'],p['documentation_section'],
                'retrospective_documented_consistency_only'):
                raise TriageError('Published-factor evidence contract changed: '+item_id)
        elif (row.get('kind'),row.get('documentary_status'),row.get('documented_factor'),
              row.get('recommendation')) != (
              'observed_multiclass_label_structure','seven_categories_described_not_exactly_one_axiom',None,
              'do_not_treat_observed_onehot_as_independent_gold'):
            raise TriageError('One-hot observation misrepresented as universal constraint')


def summarize_existing_reports(reg: dict, b137: dict, b138_plan: dict, b139_plan: dict,
                               b138_report: dict, b139_report: dict, *, b138_sha256: str,
                               b139_sha256: str) -> dict:
    validate_register(reg, b137, b139_plan)
    validate_b138_plan(b138_plan, b137)
    _check_b138_report(b138_report, b137, b138_plan)
    if (b139_report.get('study_id') != b139_plan['study_id'] or
        b139_report.get('classification') != 'retrospective_documented_conversion_descriptive_audit_not_gold' or
        b139_report.get('b13_9_plan_canonical_sha256') != canonical_sha(b139_plan) or
        b139_report.get('b13_8_aggregate_sha256') != b138_sha256 or
        b139_report.get('source_group') != 'nhanes_2015_2016_cycle'):
        raise TriageError('B13.9 aggregate provenance does not match source history')
    if b139_report.get('source_eligibility_confirmed') is not False or b139_report.get('fitted_tolerance_or_rounding') is not False:
        raise TriageError('B13.9 report claims unwarranted source eligibility/precision')
    if (b139_report.get('real_candidate_admission_runs') != 0 or
            b139_report.get('independently_adjudicated_gold_rules') != 0 or
            b139_report.get('cross_file_clinical_join_performed') is not False):
        raise TriageError('B13.9 unexpectedly claims gate/gold/clinical join')
    health = {x['source_id']:x for x in b138_report['healthcare']}
    pairs = b139_report.get('conversion_pairs')
    if not isinstance(pairs,list) or len(pairs) != 3 or [x.get('pair_id') for x in pairs] != list(ORDER[:3]):
        raise TriageError('B13.9 pair IDs/count/order changed')
    output_items = []
    for item, empirical in zip(reg['evidence_items'][:3], pairs):
        parent = health[item['source_ids'][0]]
        p = next(x for x in b139_plan['pairs'] if x['pair_id'] == item['item_id'])
        if (empirical.get('source_id') != p['source_id'] or empirical.get('published_factor') != p['factor']
            or empirical.get('documentation_url') != p['documentation_url'] or empirical.get('units') != p['units']
            or empirical.get('interpretation') != 'recorded_value_consistency_only_not_gold'):
            raise TriageError('B13.9 source/interpretation tampered')
        a = empirical.get('aggregates',{})
        counts = [a.get(k) for k in ('paired_nonmissing','both_missing','only_left_missing','only_right_missing')]
        if any(type(v) is not int or v<0 for v in counts) or a.get('rows_total') != parent['row_count'] or sum(counts)!=parent['row_count']:
            raise TriageError('Inconsistent B13.9 source counts')
        res = a.get('absolute_residual_mmol_l',{})
        if counts[0] == 0:
            raise TriageError('No nonmissing pair data in previously reported result')
        vals = [_decimal_nonnegative(res.get(k)) for k in ('median','p95','max')]
        if vals != sorted(vals):
            raise TriageError('Out-of-order residual summaries')
        if a.get('precision_or_rounding_gold_established') is not False or a.get('discrepancies_adjudicated_as_errors') != 0:
            raise TriageError('Unsupported precision or error truth')
        output_items.append({'item_id':item['item_id'],'source_ids':item['source_ids'],
                'documentary_status':item['documentary_status'], 'published_factor':p['factor'],
                'paired_count':counts[0], 'observed_max_absolute_residual_mmol_l':res['max'],
                'precision_gold_established':False,'independent_reviewer_decisions':0,
                'enforceable_real_context_policy_proven':False,
                'confirmatory_accuracy_denominator_eligible':False,
                'recommended_use':item['recommendation'],
                'unresolved_requirement':item['eligibility_evidence_gap']})
    man = b138_report.get('manufacturing', {})
    counts = man.get('label_positive_count_per_row', {})
    if not isinstance(counts,dict) or set(counts) != set(str(x) for x in range(8)) or any(type(v) is not int or v<0 for v in counts.values()):
        raise TriageError('Malformed manufacturing one-hot histogram')
    if (man.get('source_id')!='B13S-MAN-01' or man.get('feature_column_count')!=27 or
            man.get('label_column_count')!=7 or man.get('total_column_count')!=34 or
            sum(counts.values())!=man.get('row_count')):
        raise TriageError('Manufacturing shape/count mismatch')
    item=reg['evidence_items'][3]
    output_items.append({'item_id':item['item_id'],'source_ids':item['source_ids'],
        'documentary_status':item['documentary_status'], 'observed_row_count':man['row_count'],
        'observed_exactly_one_positive_label_rows':counts['1'],
        'independent_reviewer_decisions':0,'binary_domain_and_universal_semantics_adjudicated':False,
        'enforceable_real_context_policy_proven':False, 'confirmatory_accuracy_denominator_eligible':False,
        'recommended_use':item['recommendation'], 'unresolved_requirement':item['eligibility_evidence_gap']})
    return {'study_id':STUDY, 'classification':'retrospective_documentary_and_executability_gaps_only',
            'evidence_register_canonical_sha256':canonical_sha(reg),
            'parent_B13_8_report_sha256':b138_sha256, 'parent_B13_9_report_sha256':b139_sha256,
            'source_groups': ['nhanes_2015_2016_cycle','uci_steel_plates_2010_release'],
            'source_relationships_screened':len(output_items), 'source_documentary_reviews_independently_adjudicated':0,
            'eligible_confirmatory_relationships':0, 'real_source_context_policies_frozen':0,
            'real_candidate_gate_runs':0,'independent_gold_rules':0,
            'evidence_items':output_items,
            'verifier_contract_limitation':'B3 context_keys checks per-field matching; sample/threshold eligibility requires a separately source-supported when predicate and available columns.',
            'privacy':'aggregate_no_SEQN_or_individual_records',
            'next_action':'independent human source-evidence and applicability adjudication before real-arm runs'}


def assess_external_cache(cache: Path, root: Path, reg: dict, b137: dict, b138_plan: dict, b139_plan: dict) -> dict:
    cache = assert_external_cache(cache, root)
    b138_path = cache/'B13_8_source_schema_audit_v1.json'
    b139_path = cache/'B13_9_documented_pair_consistency_v1.json'
    # Read aggregate-only prior reports; no XPT/ZIP record inspection.
    h8=sha256_file(b138_path); h9=sha256_file(b139_path)
    r8=json.loads(b138_path.read_text(encoding='utf-8'))
    r9=json.loads(b139_path.read_text(encoding='utf-8'))
    result=summarize_existing_reports(reg,b137,b138_plan,b139_plan,r8,r9,
                                     b138_sha256=h8,b139_sha256=h9)
    if sha256_file(b138_path)!=h8 or sha256_file(b139_path)!=h9:
        raise TriageError('Aggregate evidence changed during assessment')
    return result


def exclusive_save(cache: Path, root: Path, report: dict) -> Path:
    cache=assert_external_cache(cache,root)
    target=cache/'B13_10_documentary_applicability_triage_v1.json'
    with target.open('x',encoding='utf-8') as f:
        json.dump(report,f,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)
        f.write('\n')
    return target
