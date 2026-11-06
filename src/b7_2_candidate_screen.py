"""B7.2: deterministic, evidence-limited 4-domain *pair-surfacing* audit.

No model calls, no raw-row reads, no false claims of learning executable rules.
Two transparent candidate-ranking baselines share each domain's numeric-pair pool
and budget. Unseen ground truth, rule semantics and precision are NOT supplied.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from itertools import combinations
from pathlib import Path
from typing import Any
import copy
import csv
import hashlib
import io
import json
import random
import re
import time

STUDY = 'b7_2_four_domain_pair_screen_v1'
PATHS = {
    'finance': 'data/metadata/sec-companyfacts-0000320193.json',
    'healthcare': 'data/metadata/nhanes-glu-j.json',
    'manufacturing': 'data/metadata/ai4i-2020.json',
    'cybersecurity': 'data/metadata/cic-ids2017.json',
}
DOMAINS = tuple(PATHS)
FIELDS = ('domain', 'dataset_id', 'arm', 'rank', 'candidate_pair_id', 'left_column', 'right_column',
          'score', 'signal', 'left_description_status', 'right_description_status',
          'left_description', 'right_description', 'left_source_url', 'right_source_url',
          'is_executable_constraint', 'is_independently_verified')
REVIEW_FIELDS = ('domain', 'dataset_id', 'candidate_pair_id', 'left_column', 'right_column',
                 'left_description', 'right_description', 'left_source_url', 'right_source_url',
                 'reviewer_id', 'relationship_decision', 'relationship_type',
                 'required_context', 'evidence_url', 'evidence_locator', 'rationale')

class ScreenError(ValueError):
    pass


def json_read(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(obj, dict):
        raise ScreenError(f'Expected JSON object: {path}')
    return obj


def file_hash(path: Path) -> str:
    h = sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def validate_plan(plan: dict[str, Any]) -> None:
    if (plan.get('study_id') != STUDY or plan.get('metadata_paths') != PATHS
            or plan.get('domain_order') != list(DOMAINS)
            or plan.get('max_candidates_per_method_per_domain') != 12
            or plan.get('fixed_seed') != 72026
            or plan.get('methods') != ['token_similarity_rank', 'seeded_uniform_random_pairs']
            or plan.get('gold_labels_available') is not False
            or plan.get('model_calls_allowed') is not False
            or plan.get('scope') != 'retrospective_previously_inspected_metadata_not_unseen'):
        raise ScreenError('B7.2 plan differs from predefined v1; version any changes')


def normalize_tokens(s: Any) -> set[str]:
    if not isinstance(s, str):
        return set()
    parts = re.findall(r'[a-z]+|\d+', s.casefold())
    stops = {'of', 'a', 'the', 'to', 'in', 'for', 'and', 'per', 'total', 'sum', 'amount',
             'as', 'at', 'on', 'by', 'with', 'from', 'that', 'is', 'are'}
    return {p for p in parts if p not in stops and len(p) > 1}


def description_unit(value: Any) -> tuple[str, str] | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r'\s*(.*?)\s*\(([^()]*)\)\s*', value)
    if not match:
        return None
    stem = ' '.join(match.group(1).casefold().split())
    unit = ' '.join(match.group(2).casefold().split())
    return (stem, unit) if stem and unit and re.search('[a-z]', unit) else None


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def extract_metadata(root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    validate_plan(plan)
    saved_b71_path = root / 'data/evaluation/b7_1_pilot_comparison.json'
    saved_b71 = json_read(saved_b71_path)
    if (saved_b71.get('study_id') != 'b7_1_saved_pilot_opportunity_audit_v1'
            or saved_b71.get('independent_gold_rule_count') != 0
            or saved_b71.get('published_method_reproduction') is not False):
        raise ScreenError('B7.1 historical anchor missing or claims altered')
    datasets = {}
    for domain, rel in PATHS.items():
        source = root / rel
        metadata = json_read(source)
        if not isinstance(metadata.get('columns'), list) or not isinstance(metadata.get('dataset'), dict):
            raise ScreenError(f'Invalid metadata columns for {domain}')
        entries = metadata['columns']
        names = [x.get('name') for x in entries if isinstance(x, dict)]
        if len(names) != len(entries) or not all(isinstance(x, str) and x for x in names):
            raise ScreenError(f'Invalid metadata column names for {domain}')
        duplicates = sorted(n for n, count in Counter(names).items() if count > 1)
        usable = {}
        for x in entries:
            name = x['name']
            if name in duplicates:
                continue  # Never guess which occurrence an ambiguous name means.
            type_info = x.get('type', {})
            t = str(type_info.get('value', '')).lower() if isinstance(type_info, dict) else ''
            if not any(y in t for y in ('integer', 'number', 'float', 'decimal', 'numeric')):
                continue
            description = x.get('description')
            if not isinstance(description, dict):
                description = {}
            usable[name] = {
                'name': name,
                'description': description.get('value') if isinstance(description.get('value'), str) else '',
                'description_status': str(description.get('status') or 'unknown'),
                'source_url': description.get('source') if isinstance(description.get('source'), str) else '',
            }
        if len(usable) < 2:
            raise ScreenError(f'Fewer than two unambiguous numeric columns in {domain}')
        datasets[domain] = {
            'dataset_id': metadata['dataset'].get('id'),
            'numeric_columns': usable,
            'duplicate_column_names_excluded': duplicates,
            'total_metadata_columns': len(entries),
            'source_sha256': file_hash(source),
            'source_path': rel,
        }
    return {'datasets': datasets,
            'historical_b7_1_sha256': file_hash(saved_b71_path),
            'predefined_plan_sha256': file_hash(root / 'data/evaluation/b7_2_plan_v1.json')}


def score_pair(left: dict[str, Any], right: dict[str, Any], *, mask_descriptions: bool = False) -> tuple[float, str]:
    nd = jaccard(normalize_tokens(left['name']), normalize_tokens(right['name']))
    if mask_descriptions:
        return round(2 * nd, 6), 'column_name_similarity_only' if nd else 'no_lexical_signal'
    ld, rd = left['description'], right['description']
    dd = jaccard(normalize_tokens(ld), normalize_tokens(rd))
    lu, ru = description_unit(ld), description_unit(rd)
    pair_unit = bool(lu and ru and lu[0] == ru[0] and lu[1] != ru[1])
    score = round(4 * int(pair_unit) + 2 * nd + dd, 6)
    signal = 'same_measurement_different_unit_hypothesis' if pair_unit else (
        'name_or_description_overlap' if score else 'no_lexical_signal')
    return score, signal


def pair_id(domain: str, left: str, right: str) -> str:
    assert left < right
    return domain[:3].upper() + '-' + hashlib.sha256((domain+'\0'+left+'\0'+right).encode()).hexdigest()[:14]


def choose_candidates(domain: str, info: dict[str, Any], *, budget: int, seed: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cols = info['numeric_columns']
    pool = list(combinations(sorted(cols), 2))
    if not pool:
        raise ScreenError(f'No eligible candidate pairs for {domain}')
    quota = min(len(pool), budget)
    scored = [(score_pair(cols[a], cols[b])[0], a, b, score_pair(cols[a], cols[b])[1]) for a, b in pool]
    rank = sorted(scored, key=lambda item: (-item[0], item[1], item[2]))[:quota]
    rng = random.Random(seed)
    control_pairs = rng.sample(pool, quota)
    arms = [('token_similarity_rank', [(a, b) for _,a,b,_ in rank]),
            ('seeded_uniform_random_pairs', control_pairs)]
    rows = []
    for arm, selected in arms:
        for idx, (a, b) in enumerate(selected, 1):
            l, r = cols[a], cols[b]
            score, signal = score_pair(l, r)
            rows.append({
                'domain': domain, 'dataset_id': info['dataset_id'], 'arm': arm,
                'rank': idx, 'candidate_pair_id': pair_id(domain, a, b),
                'left_column': a, 'right_column': b, 'score': score, 'signal': signal,
                'left_description_status': l['description_status'],
                'right_description_status': r['description_status'],
                'left_description': l['description'], 'right_description': r['description'],
                'left_source_url': l['source_url'], 'right_source_url': r['source_url'],
                'is_executable_constraint': 'false', 'is_independently_verified': 'false',
            })
    masked = sorted(pool, key=lambda pair: (-score_pair(cols[pair[0]], cols[pair[1]],mask_descriptions=True)[0], pair[0], pair[1]))[:quota]
    base = { (a,b) for _, a,b,_ in rank }
    maskset = set(masked)
    randomset = set(control_pairs)
    summary = {
        'domain': domain, 'dataset_id': info['dataset_id'],
        'total_metadata_columns': info['total_metadata_columns'],
        'unambiguous_numeric_columns': len(cols),
        'duplicate_column_names_excluded': info['duplicate_column_names_excluded'],
        'numeric_pair_universe': len(pool),
        'candidate_budget_each_arm': quota,
        'token_ranked_pairs': len(base),
        'random_ranked_pairs': len(randomset),
        'pair_overlap_between_arms': len(base & randomset),
        'description_masked_topk_overlap': len(base & maskset),
        'description_masked_topk_union': len(base | maskset),
        'description_masked_jaccard': len(base & maskset) / len(base | maskset),
        'documented_descriptions_available': sum(x['description_status'] == 'documented' and bool(x['description']) for x in cols.values()),
        'unit_pair_hypotheses_in_token_rank': sum(score_pair(cols[a], cols[b])[1]=='same_measurement_different_unit_hypothesis' for a,b in base),
        'interpretation': 'Pair surfacing and metadata dependence only. Neither arm discovers an executable, independently verified integrity rule.',
    }
    return rows, summary


def generate(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    start = time.perf_counter()
    plan = json_read(root / 'data/evaluation/b7_2_plan_v1.json')
    snapshot = extract_metadata(root, plan)
    candidate_rows = []
    summaries = []
    for offset, domain in enumerate(DOMAINS):
        rows, summary = choose_candidates(domain, snapshot['datasets'][domain],
            budget=plan['max_candidates_per_method_per_domain'], seed=plan['fixed_seed'] + offset)
        candidate_rows.extend(rows)
        summary['metadata_sha256'] = snapshot['datasets'][domain]['source_sha256']
        summary['metadata_path'] = snapshot['datasets'][domain]['source_path']
        summaries.append(summary)
    # Exact pair appears once in blinded worksheet even if both arms ranked it.
    seen = set()
    reviews = []
    for row in sorted(candidate_rows, key=lambda r: (r['domain'],r['left_column'],r['right_column'])):
        k = (row['domain'],row['candidate_pair_id'])
        if k in seen:
            continue
        seen.add(k)
        reviews.append({key: row.get(key,'') for key in REVIEW_FIELDS} |
                       {key:'' for key in ('reviewer_id', 'relationship_decision', 'relationship_type',
                                           'required_context', 'evidence_url', 'evidence_locator', 'rationale')})
    report = {
        'study_id': STUDY,
        'scope': plan['scope'],
        'plan_sha256': snapshot['predefined_plan_sha256'],
        'historical_b7_1_sha256': snapshot['historical_b7_1_sha256'],
        'source_metadata_hashes': {d: snapshot['datasets'][d]['source_sha256'] for d in DOMAINS},
        'comparison': 'Two original, fully disclosed LOCAL pair-ranking methods; not published method reimplementations',
        'arms': plan['methods'],
        'domain_summaries': summaries,
        'rankings_rows': len(candidate_rows),
        'unique_blinded_review_pairs': len(reviews),
        'reviewer_votes_completed': 0,
        'independently_qualified_gold_constraints': 0,
        'semantic_precision': None, 'semantic_recall': None, 'context_recall': None,
        'new_llm_calls': 0, 'network_calls': 0, 'raw_data_rows_read': 0,
        'elapsed_seconds_one_run': round(time.perf_counter()-start, 6),
        'limitations': [
            'Retrospective, previously inspected metadata sources; candidates are exploratory unordered column pairs, not executable constraint hypotheses.',
            'Both methods access the same numeric-pair universe and budget, but no human correctness labels have been collected.',
            'Description masking measures ranking dependence, NOT ablation of MetaVerify evidence gate or change in semantic accuracy.',
            'Different domains contain unequal numbers of numeric pairs; candidate ceilings are equal, actual quotas may be lower.',
            'Prior Luna only covers two manually selected opportunities and is not a four-domain head-to-head method in this study.',
            'The separately run existing data-only miner uses a different input regime (AI4I+SEC), so cross-arm precision cannot be computed.',
            'Do not claim prospective holdout, significant improvement or published-method benchmarking.'
        ]
    }
    return report, candidate_rows, reviews


def csv_string(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> str:
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fields, extrasaction='raise', lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def save_results(root: Path) -> dict[str, Any]:
    dest = root / 'data/evaluation/b7_2_candidate_screen'
    # Don't replace earlier runs, especially a human-completed review.
    names = ('rankings.csv','blind_review_unfilled.csv','summary.json','README.md')
    for name in names:
        if (dest / name).exists():
            raise ScreenError(f'Output exists, refusing overwrite: {dest / name}')
    report, rankings, reviews = generate(root)
    dest.mkdir(parents=True, exist_ok=True)
    ranking_csv = csv_string(rankings, FIELDS)
    review_csv = csv_string(reviews, REVIEW_FIELDS)
    summary = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    text = '# B7.2 output — candidate pair screening, NOT gold accuracy\n\n'
    text += 'Metadata-only, four domains; no paid calls, source records, confirmed rules, semantic precision or true unseen data.\n\n'
    text += '| Domain | Pair universe | Each arm | Documented numeric descriptions | Description-masking top-k Jaccard |\n|---|---:|---:|---:|---:|\n'
    for s in report['domain_summaries']:
        text += f"| {s['domain']} | {s['numeric_pair_universe']} | {s['candidate_budget_each_arm']} | {s['documented_descriptions_available']} | {s['description_masked_jaccard']:.3f} |\n"
    text += '\nBoth methods only rank possible column pairs. Review forms are blank. Human judgement and source conditions are required before claiming a supported constraint.\n'
    for name, content in [('rankings.csv',ranking_csv), ('blind_review_unfilled.csv',review_csv),('summary.json',summary),('README.md',text)]:
        (dest/name).write_text(content, encoding='utf-8', newline='')
    return report
