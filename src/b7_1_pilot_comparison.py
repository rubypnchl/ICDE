"""B7.1 audit of two ALREADY-SAVED, manually selected B5 pilot opportunities.

This is NOT a published-method reproduction, unbiased model benchmark, evidence
acceptance test, rule precision estimate, or full four-domain discovery comparison.
All model and posthoc decisions come from committed, immutable B5/B5.1 files.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import itertools
import json
from pathlib import Path
import re
from typing import Any

DATASETS = ("healthcare", "finance")
VALID_B4 = {"blocked_unresolved", "candidate_executable_unverified", "rejected_invalid"}
VALID_B51 = {"compiled_unverified_posthoc", "blocked_applicability_or_scope", "blocked_unresolved", "rejected_invalid", "blocked_no_curator_policy"}

class PilotAuditError(ValueError):
    """A required correspondence/invariant was violated; no result is defensible."""


def hash_file(path: Path) -> str:
    h = sha256()
    with path.open('rb') as file:
        for part in iter(lambda: file.read(65536), b''):
            h.update(part)
    return h.hexdigest()


def object_hash(obj: Any) -> str:
    return sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(obj, dict):
        raise PilotAuditError(f'Expected JSON object: {path}')
    return obj


def _description_unit(description: Any) -> tuple[str, str] | None:
    """Strict generic lexical extraction; never infer a conversion factor."""
    if not isinstance(description, str):
        return None
    match = re.fullmatch(r'\s*(.*?)\s*\(([^()]*)\)\s*', description)
    if not match:
        return None
    stem = ' '.join(match.group(1).casefold().split())
    unit = ' '.join(match.group(2).casefold().split())
    if not stem or not unit or not re.search('[a-z]', unit):
        return None
    return stem, unit


def lexical_candidates(bundle: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    """Metadata-only rule *hypotheses* for matched description stems.

    This simple original heuristic is a LOCAL baseline, not Metanome/Auto-Test,
    Guardrail or the repository's existing data-only mining implementation.
    Its output does not assert equality, conversion direction, coefficient,
    rounding, or an accepted rule.
    """
    passages = bundle.get('passages')
    if not isinstance(passages, list) or not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise PilotAuditError('Missing passages or invalid opportunity budget')
    seen_ids: set[str] = set()
    seen_columns: set[str] = set()
    grouped: dict[str, list[tuple[dict[str, Any], str]]] = {}
    for p in passages:
        if not isinstance(p, dict):
            raise PilotAuditError('Malformed passage')
        pid, col = p.get('id'), p.get('column')
        if not isinstance(pid, str) or not pid or pid in seen_ids or not isinstance(col, str) or not col or col in seen_columns:
            raise PilotAuditError('Missing or duplicate passage/column identifier')
        seen_ids.add(pid)
        seen_columns.add(col)
        dtype = str(p.get('type', '')).casefold()
        if not any(t in dtype for t in ('number', 'integer', 'decimal', 'float')):
            continue
        parsed = _description_unit(p.get('description'))
        if parsed is None:
            continue
        stem, unit = parsed
        grouped.setdefault(stem, []).append((p, unit))
    results = []
    for stem in sorted(grouped):
        group = sorted(grouped[stem], key=lambda part: part[0]['column'])
        for (left, lu), (right, ru) in itertools.combinations(group, 2):
            if lu == ru:
                continue
            results.append({
                'kind': 'possible_paired_measurement_different_unit',
                'columns': [left['column'], right['column']],
                'passage_ids': [left['id'], right['id']],
                'description_stem': stem,
                'observed_unit_strings': [lu, ru],
                'status': 'hypothesis_only_parameters_and_direction_unresolved',
                'executable_rule': None,
                'semantic_verified': False,
            })
    return results[:limit]


def validate_inputs(root: Path, plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if (plan.get('study_id') != 'b7_1_saved_pilot_opportunity_audit_v1'
            or plan.get('opportunity_domains') != list(DATASETS)
            or plan.get('max_hypotheses_per_opportunity') != 2
            or plan.get('previously_observed_pilot') is not True
            or plan.get('score_semantic_rule_precision') is not False):
        raise PilotAuditError('Study plan changed/unsupported; do not silently change opportunity set')
    paths = plan.get('input_paths')
    if not isinstance(paths, dict) or set(paths) != {'input_bundles', 'llm_reports', 'posthoc_gate'}:
        raise PilotAuditError('Invalid or incomplete input paths')
    expected_reports = {
        'healthcare': 'data/llm_pilot/structured/luna_healthcare.json',
        'finance': 'data/llm_pilot/structured/luna_finance.json',
    }
    if paths['llm_reports'] != expected_reports or paths['input_bundles'] != 'data/llm_pilot/structured/inputs.json' or paths['posthoc_gate'] != 'data/evaluation/b5_1_evidence_review.json':
        raise PilotAuditError('Input file mapping changed; version plan for any substitution')
    bundles = read_json(root / paths['input_bundles'])
    reports = {k: read_json(root / name) for k, name in expected_reports.items()}
    gate = read_json(root / paths['posthoc_gate'])
    if not isinstance(gate.get('model_reports'), list) or len(gate['model_reports']) != len(DATASETS):
        raise PilotAuditError('B5.1 saved gate report missing or incomplete')
    gates = {}
    for x in gate['model_reports']:
        if not isinstance(x, dict) or x.get('domain') in gates:
            raise PilotAuditError('Duplicate/malformed gate entry')
        gates[x.get('domain')] = x
    if set(gates) != set(DATASETS) or set(bundles) != set(DATASETS):
        raise PilotAuditError('Dataset opportunity mismatch')
    for domain in DATASETS:
        report, bundle, gate_entry = reports[domain], bundles[domain], gates[domain]
        if (not isinstance(bundle, dict) or report.get('domain') != domain
                or report.get('dataset_id') != bundle.get('dataset_id')
                or report.get('input_bundle') != bundle
                or gate_entry.get('dataset_id') != bundle.get('dataset_id')
                or gate_entry.get('domain') != domain
                or gate_entry.get('request_sha256') != report.get('request_sha256')
                or gate_entry.get('input_bundle_sha256') != object_hash(bundle)
                or gate_entry.get('policy_development_stage') != 'posthoc_case_study_policy_developed_after_inspecting_luna_outputs'
                or report.get('response_status') != 'completed' or report.get('error') is not None
                or report.get('model_id_requested') != 'gpt-6-luna'):
            raise PilotAuditError(f'Pilot/gate/source snapshot mismatch for {domain}')
        proposal_list = (report.get('output') or {}).get('rules')
        compiled = report.get('compile_results')
        decisions = gate_entry.get('decisions')
        if not isinstance(proposal_list, list) or not isinstance(compiled, list) or not isinstance(decisions, list) or len(proposal_list) > 2:
            raise PilotAuditError(f'Missing pilot proposals or posthoc decisions for {domain}')
        proposal_ids = [item.get('id') for item in proposal_list]
        b4_ids = [item.get('id') for item in compiled]
        b51_ids = [item.get('proposal_id') for item in decisions]
        if not all(isinstance(x, str) and x for x in proposal_ids) or len(set(proposal_ids)) != len(proposal_ids) or sorted(proposal_ids) != sorted(b4_ids) or sorted(proposal_ids) != sorted(b51_ids):
            raise PilotAuditError(f'Proposal ID mismatches for {domain}')
        for item in compiled:
            if (item.get('compilation') or {}).get('status') not in VALID_B4:
                raise PilotAuditError(f'Unrecognized B4 compiler status in {domain}')
        for item in decisions:
            if item.get('status') not in VALID_B51 or item.get('semantically_verified') is not False or item.get('independently_validated') is not False:
                raise PilotAuditError(f'Unrecognized/unjustified B5.1 acceptance in {domain}')
    return bundles, reports, gates


def run(root: Path) -> dict[str, Any]:
    plan_path = root / 'data/evaluation/b7_1_comparison_plan_v1.json'
    plan = read_json(plan_path)
    bundles, reports, gates = validate_inputs(root, plan)
    results = []
    paths = plan['input_paths']
    for domain in DATASETS:
        bundle = bundles[domain]
        report = reports[domain]
        gate = gates[domain]
        heuristic = lexical_candidates(bundle, plan['max_hypotheses_per_opportunity'])
        llm = (report['output'] or {})['rules']
        b4 = {x['id']: x['compilation']['status'] for x in report['compile_results']}
        b51 = {x['proposal_id']: x['status'] for x in gate['decisions']}
        results.append({
            'domain': domain,
            'dataset_id': bundle['dataset_id'],
            'scope': 'manually_focused_prior_B5_pilot_not_unseen',
            'input_bundle_sha256': object_hash(bundle),
            'metadata_column_count': len(bundle['passages']),
            'lexical_heuristic': {'candidate_count': len(heuristic), 'candidates': heuristic,
                                  'verified_rules': 0, 'independently_adjudicated': False},
            'saved_luna_pilot': {
                'hypothesis_count': len(llm),
                'proposals': [{'id': p['id'], 'passage_ids': p.get('passage_ids'),
                               'b4_status': b4[p['id']], 'b5_1_posthoc_status': b51[p['id']]}
                              for p in llm],
                'estimated_nominal_api_cost_usd_from_saved_report': report.get('estimated_cost_usd'),
                'new_model_calls': 0,
                'independently_adjudicated': False,
            },
            'rule_precision': None,
            'rule_recall': None,
            'confidence_interval': None,
            'reason_metrics_unavailable': 'No independently adjudicated reference rules; convenience selected pilots and retrospective gate',
        })
    return {
        'study_id': plan['study_id'],
        'type': 'retrospective_metadata_only_opportunity_accounting_not_published_baseline_replication',
        'plan_sha256': hash_file(plan_path),
        'input_sha256': {name: hash_file(root / rel) for name, rel in {
            'input_bundles': paths['input_bundles'],
            'luna_healthcare': paths['llm_reports']['healthcare'],
            'luna_finance': paths['llm_reports']['finance'],
            'b5_1_review': paths['posthoc_gate'],
        }.items()},
        'opportunities_total': len(DATASETS),
        'manual_selection_acknowledged': True,
        'independent_gold_rule_count': 0,
        'independent_gold_precision': None,
        'published_method_reproduction': False,
        'prospective_comparison': False,
        'new_api_calls': 0,
        'results': results,
        'limits': [
            'Manually selected two earlier-pilot metadata bundles; not a random sample and no untouched test set.',
            'A generic lexical paired-unit heuristic is an original LOCAL baseline, not Metanome, Guardrail, Auto-Test or Deequ.',
            'The saved Luna proposals came before this posthoc analysis; B5.1 policy was written after viewing Luna outputs.',
            'Hypothesis yield/status do not measure semantic correctness, precision, recall or improvement.',
            'The discovery baseline in src/rule_discovery.py uses a different data regime and cannot be scored as matched metadata-only here.',
            'No independent gold adjudication and no four-domain automated discovery benchmark.',
        ],
    }
