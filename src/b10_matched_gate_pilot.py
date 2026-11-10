"""B10: same-saved-input, fixed-parameter comparison of compiler and evidence decisions.

Retrospective two-opportunity pilot; NOT unbiased efficacy/gold/baseline evaluation.
No network, model calls, raw source rows or modifications to frozen inputs.
"""
from __future__ import annotations
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORTS = {
    'healthcare': 'data/llm_pilot/structured/luna_healthcare.json',
    'finance': 'data/llm_pilot/structured/luna_finance.json',
}
BASELINE_PILOT = 'data/evaluation/b7_1_pilot_comparison.json'
SAVED_REVIEW = 'data/evaluation/b5_1_evidence_review.json'
POLICY = 'data/rules/b5_1_review_policy.json'
REGISTRY = 'data/rules/b4_example_proposals.json'
PLAN = 'data/evaluation/b10_plan_v1.json'
OUTPUT_DIR = 'data/evaluation/b10_matched_gate_pilot'
EXPECTED_IDS = {'healthcare': 'glucose_unit_conversion', 'finance': 'balance_sheet_equation'}
EXPECTED_ORIGINAL = {'healthcare': 'blocked_unresolved', 'finance': 'candidate_executable_unverified'}
EXPECTED_REVIEW = {'healthcare': 'compiled_unverified_posthoc', 'finance': 'blocked_applicability_or_scope'}

class B10Error(ValueError):
    pass

def load_json(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(result, dict):
        raise B10Error(f'Expected JSON object: {path}')
    return result

def sha_file(path: Path) -> str:
    h = sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(65536), b''):
            h.update(b)
    return h.hexdigest()

def matches_frozen_hash(path: Path, expected: str) -> bool:
    raw = path.read_bytes()

    if sha256(raw).hexdigest() == expected:
        return True

    # Accept only the original Windows CRLF representation.
    if b'\r' in raw or b'\n' not in raw:
        return False

    return sha256(
        raw.replace(b'\n', b'\r\n')
    ).hexdigest() == expected

def stable_hash(obj: Any) -> str:
    return sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()

def proposal_to_b4(report: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    """Canonicalise null optional fields WITHOUT changing expressions/contexts."""
    from src.rule_bridge import PROPOSAL_VERSION
    if not isinstance(item.get('assertions'), list) or not isinstance(item.get('context_keys'), list):
        raise B10Error('Invalid saved proposal structure')
    assertions = []
    for expr in item['assertions']:
        if not isinstance(expr, dict):
            raise B10Error('Invalid saved assertion')
        assertions.append({k: deepcopy(v) for k, v in expr.items() if v is not None})
    value = {
        'proposal_version': PROPOSAL_VERSION,
        'id': item['id'],
        'dataset_id': report['dataset_id'],
        'origin': 'B10_replay_of_saved_' + report['model_id_requested'],
        'assertions': assertions,
        'context_keys': deepcopy(item['context_keys']),
    }
    if item.get('when') is not None:
        value['when'] = deepcopy(item['when'])
    return value

def fixed_curator_registrations(report: dict[str, Any], item: dict[str, Any],
                                policy: dict[str, Any], registrations: dict[str, Any]) -> dict[str, Any]:
    """Replicate B5.1 EXACT-STRUCTURE binding, identically for both B10 arms.

    This binding was calibrated after seeing the hypothesis; it is not new source proof.
    """
    dataset, pid = report['dataset_id'], item['id']
    applicable = [a for a in policy.get('binding_authorizations', [])
                  if a.get('dataset_id') == dataset and a.get('rule_id') == pid]
    if len(applicable) > 1:
        raise B10Error('Ambiguous manual binding grants')
    if not applicable:
        return {}
    grant = applicable[0]
    shape = {k: item.get(k) for k in ('assertions', 'when', 'context_keys', 'passage_ids')}
    if shape != grant.get('expected_structure'):
        raise B10Error('Frozen binding structure mismatch')
    passages = {p['id']: p for p in report['input_bundle']['passages']}
    expected = grant.get('expected_evidence_passages', [])
    if not expected:
        raise B10Error('Missing documented binding passages')
    for p in expected:
        if any(passages.get(p['id'], {}).get(k) != p[k] for k in ('column','description','source')):
            raise B10Error('Bound documentary passage changed')
    mapping = grant.get('parameter_map', {})
    if not isinstance(mapping, dict) or not mapping:
        raise B10Error('Invalid authorization parameter map')
    aliases: dict[str, Any] = {}
    for target, old in mapping.items():
        if not isinstance(target, str) or not isinstance(old, str) or not old.startswith(dataset + ':'):
            raise B10Error('Cross-dataset or invalid parameter alias')
        if old not in registrations:
            raise B10Error('Curator registration missing: '+old)
        aliases[dataset + ':' + target] = deepcopy(registrations[old])
    return aliases

def summarize_decisions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 2 or {r['domain'] for r in rows} != {'finance','healthcare'}:
        raise B10Error('Exactly two saved opportunities expected')
    return {
        'candidate_proposals_present': len(rows),
        'original_compiler_executable_without_curator_binding': sum(r['original_compiler_status']=='candidate_executable_unverified' for r in rows),
        'compiler_executable_with_fixed_curator_binding': sum(r['fixed_compiler_status']=='candidate_executable_unverified' for r in rows),
        'evidence_gate_status_counts': dict(sorted(Counter(r['evidence_review_status'] for r in rows).items())),
        'safe_for_deployment_according_to_existing_gate': sum(r['gate_safe_to_deploy'] for r in rows),
        'is_independent_accuracy_benchmark': False,
        'accuracy': None,
        'rule_precision': None,
    }

def preflight(root: Path) -> dict[str, Any]:
    b71 = load_json(root / BASELINE_PILOT)
    saved = load_json(root / SAVED_REVIEW)
    policy = load_json(root / POLICY)
    registryfile = load_json(root / REGISTRY)
    plan = load_json(root / PLAN)
    if (plan.get('study_id') != 'b10_same_input_fixed_parameter_retrospective_gate_pilot_v1'
            or plan.get('approved_domains') != ['healthcare','finance']
            or plan.get('source_code_form') != 'saved_B5_typed_Luna_proposals'
            or plan.get('design_class') != 'retrospective_not_blinded_not_gold'
            or plan.get('curator_binding_held_fixed') is not True):
        raise B10Error('Unexpected or altered B10 plan')
    if (b71.get('study_id') != 'b7_1_saved_pilot_opportunity_audit_v1'
            or b71.get('opportunities_total') != 2
            or saved.get('stage') != 'B5.1'
            or policy.get('development_stage') != 'posthoc_case_study_policy_developed_after_inspecting_luna_outputs'):
        raise B10Error('Expected frozen B5.1/B7.1 source lineage missing')
    hashes = b71.get('input_sha256', {})
    if not matches_frozen_hash(root / SAVED_REVIEW, hashes.get('b5_1_review')):
        raise B10Error('Frozen B5.1 report checksum mismatch')
    model_reports = saved.get('model_reports', [])
    if len(model_reports) != 2:
        raise B10Error('Expected exactly two B5.1 saved reports')
    if stable_hash(policy) != model_reports[0].get('policy_sha256') or any(
        x.get('policy_sha256') != model_reports[0].get('policy_sha256') for x in model_reports
    ):
        raise B10Error('Frozen B5.1 policy differs from saved review')
    reports = {}
    for domain, path in REPORTS.items():
        if sha_file(root / path) != hashes.get('luna_' + domain):
            raise B10Error('Frozen LLM proposal file checksum mismatch: '+domain)
        raw = load_json(root / path)
        items = raw.get('output', {}).get('rules', [])
        comps = raw.get('compile_results', [])
        if (raw.get('domain') != domain or raw.get('response_status') != 'completed'
                or raw.get('error') is not None or len(items) != 1 or len(comps) != 1
                or items[0].get('id') != EXPECTED_IDS[domain]
                or (comps[0].get('compilation') or {}).get('status') != EXPECTED_ORIGINAL[domain]):
            raise B10Error('Changed original model proposal or original compiler status: '+domain)
        matching = [m for m in model_reports if m.get('domain') == domain]
        if len(matching) != 1 or len(matching[0].get('decisions', [])) != 1:
            raise B10Error('B5.1 per-domain review missing: '+domain)
        d = matching[0]['decisions'][0]
        if d.get('proposal_id') != items[0]['id'] or d.get('status') != EXPECTED_REVIEW[domain]:
            raise B10Error('B5.1 frozen gate result changed: '+domain)
        reports[domain] = raw
    regs = registryfile.get('registrations')
    if not isinstance(regs, dict):
        raise B10Error('B4 registration registry missing')
    return {'reports':reports, 'model_reviews':model_reports, 'policy':policy, 'registrations':regs,
            'input_sha256': {path:sha_file(root / path) for path in
                             [BASELINE_PILOT,SAVED_REVIEW,POLICY,REGISTRY,PLAN,*REPORTS.values()]}}

def run(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    # Import real B4+B5.1 implementations; never emulate a decision.
    from src.rule_bridge import compile_proposal
    from src.evidence_gate import review_report
    ready = preflight(root)
    rows = []
    for domain in ('healthcare','finance'):
        raw = ready['reports'][domain]
        item = raw['output']['rules'][0]
        columns = [p['column'] for p in raw['input_bundle']['passages']]
        proposed = proposal_to_b4(raw, item)
        fixed_registry = fixed_curator_registrations(raw, item, ready['policy'], ready['registrations'])
        # Same typed proposal, same parameter binding; only decision policy differs.
        compiler = compile_proposal(proposed, columns, fixed_registry)
        if compiler.status != 'candidate_executable_unverified' or compiler.rule is None:
            raise B10Error(f'Fixed-registry compiler unexpectedly blocked {domain}: {compiler.status}')
        gate_report = review_report(raw, ready['policy'], ready['registrations'])
        if len(gate_report['decisions']) != 1:
            raise B10Error('Gate decision cardinality changed')
        gate = gate_report['decisions'][0]
        original_review = next(x for x in ready['model_reviews'] if x['domain']==domain)['decisions'][0]
        if gate.get('status') != original_review.get('status') or gate.get('safe_to_deploy_as_integrity_constraint') is not False:
            raise B10Error('Gate result differs from frozen saved B5.1 report')
        # When the gate happens to compile, it must preserve the SAME rule expression.
        if gate.get('compiled_rule') is not None:
            a = deepcopy(gate['compiled_rule'])
            b = deepcopy(compiler.rule)
            for v in (a,b):
                v.pop('proposal_origin',None)
            if a != b:
                raise B10Error('Gating changed the executable constraint: '+domain)
        rows.append({
            'domain': domain,
            'proposal_id': item['id'],
            'candidate_only_no_gate': 'proposed_unverified',
            'original_compiler_status': (raw['compile_results'][0].get('compilation') or {})['status'],
            'fixed_compiler_status': compiler.status,
            'fixed_curator_registry_entries': len(fixed_registry),
            'evidence_review_status': gate['status'],
            'gate_safe_to_deploy': gate['safe_to_deploy_as_integrity_constraint'],
            'evidence_gate_reasons': ' | '.join(gate['reasons']),
            'rule_expression_unchanged_where_both_compiled': gate.get('compiled_rule') is not None,
            'gold_label_available': False,
            'actual_data_errors_established': False,
        })
    summary = {
        'study_id': 'b10_same_input_fixed_parameter_retrospective_gate_pilot_v1',
        'classification': 'paired_fixed_inputs_fixed_curator_binding_retrospective_not_prospective_gate_effect',
        'input_sha256': ready['input_sha256'],
        'same_saved_candidate_input_in_each_arm': True,
        'parameter_binding_identical_in_compiler_and_gate_arms': True,
        'curator_registration_posthoc': True,
        'original_compiler_without_curator_registration_is_separate_sensitivity': True,
        'saved_proposals_created_in_earlier_manually_selected_two_opportunities': True,
        'new_llm_calls': 0,
        'new_raw_record_reads': 0,
        'new_human_gold_labels': 0,
        'published_baseline_executed': False,
        'results': summarize_decisions(rows),
        'candidate_details': rows,
        'limitations': [
            'Only two manually selected previously inspected LLM hypotheses (healthcare and finance).',
            'The B5.1 source policy and parameter authorization were designed after viewing these hypotheses.',
            'A fixed binding isolates decision stages within this replay, but cannot remove post-hoc selection or establish causal efficacy.',
            'Without-gate candidate exposure and compiler execution are not verified acceptance or deployment.',
            'No adjudicated rule gold labels, so semantic accuracy/precision/recall and gating improvement are undefined.',
            'The distinct B7.2 data-only 28-candidate cohort is excluded; this is not a published-method comparison.',
            'The B10 output is a retrospective operational control comparison, not a prospective test-set experiment.',
        ]
    }
    return summary, rows
