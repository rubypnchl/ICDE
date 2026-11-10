"""Run B9 repeated fixed-rule timing on frozen AI4I and CIC development sources.

From project root: python scripts/run_b9_runtime_comparison.py --preflight
Then:             python scripts/run_b9_runtime_comparison.py --run
Non-destructive. Does not run published baselines or touch B6 saved reports.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.b9_runtime_comparison import BenchmarkError, ensure_row_parity, repeated_paired_timing
from src.b6_2_study import REQUIRED, rows_by_position, simple_rule_checker
from scripts.run_b6_1_real_baselines import prepare, _sha256
from scripts.run_b6_2_study import generic_b61_guarded

DOMAINS = ('manufacturing', 'cybersecurity')
PLAN = 'data/evaluation/b9_runtime_plan_v1.json'
B61 = 'data/evaluation/b6_1_real_baselines.json'
OUT = 'data/evaluation/b9_runtime_results_v1.json'


def fail(message: str):
    raise BenchmarkError(message)


def preflight(root: Path) -> tuple[dict, dict, dict]:
    plan_path = root / PLAN
    plan = json.loads(plan_path.read_text(encoding='utf-8-sig'))
    if plan.get('id') != 'b9-repeated-fixed-rule-timing-v1' or plan.get('domains') != list(DOMAINS):
        fail('Incorrect / changed B9 plan')
    reps = plan.get('repetitions')
    if type(reps) is not int or reps != 9 or plan.get('seed') != 902711:
        fail('B9 seed or fixed repetition count differs from plan')
    b61_path = root / B61
    baseline = json.loads(b61_path.read_text(encoding='utf-8-sig'))
    if baseline.get('mode') != 'development_only_no_independent_holdout_no_gold_scoring':
        fail('B6.1 evaluation provenance changed')
    if len(baseline.get('results', [])) != 2:
        fail('B6.1 must contain both expected domains')
    frozen = prepare(root, list(DOMAINS))
    for domain in DOMAINS:
        b = next((r for r in baseline['results'] if r.get('domain') == domain), None)
        if not b or b.get('source_file') != frozen[domain]['config']['source']:
            fail(f'No matching B6.1 report for {domain}')
        if _sha256(frozen[domain]['path']) != b['source_sha256']:
            fail(f'Source SHA drift for {domain}')
        if b['record_count'] != frozen[domain]['config']['expected_rows']:
            fail(f'Unexpected record count for {domain}')
    for f, key in [('data/evaluation/b6_reference_catalogue.json', 'catalogue_sha256'),
                   ('data/evaluation/b6_protocol_v1.json', 'protocol_sha256'),
                   ('data/sources.json', 'source_manifest_sha256')]:
        if _sha256(root / f) != baseline.get(key):
            fail(f'Frozen B6.1 input changed: {f}')
    return plan, baseline, frozen


def run(root: Path) -> dict:
    plan, baseline, frozen = preflight(root)
    report = {
        'study': plan['id'], 'classification': 'repeated_same_rule_engine_timing_not_semantic_accuracy',
        'run_provenance': {'b9_plan_sha256': _sha256(root / PLAN),
                           'b61_report_sha256': _sha256(root / B61),
                           'runner_sha256': _sha256(Path(__file__)),
                           'python_version': platform.python_version(),
                           'os': platform.system(), 'machine_architecture': platform.machine()},
        'source_files_modified': False, 'published_method_executed': False,
        'new_llm_queries': 0, 'independently_adjudicated_gold': False,
        'results': [],
    }
    for domain in DOMAINS:
        t0 = time.perf_counter()
        required = set(REQUIRED[domain]) | ({'UDI'} if domain == 'manufacturing' else set())
        # Positional reader prevents silent collision of unrelated duplicate CIC headers.
        rows = list(rows_by_position(frozen[domain]['path'], required))
        input_read_elapsed = time.perf_counter() - t0
        baseline_record = next(b for b in baseline['results'] if b['domain'] == domain)
        rule = frozen[domain]['rule']
        methods = {
            'metaverify_b3_generic': lambda row, _r=rule, _d=domain: generic_b61_guarded(_r, _d, row),
            'b6_same_rule_simple_checker': lambda row, _d=domain: simple_rule_checker(_d, row),
        }
        counts = ensure_row_parity(rows, *methods.values(), baseline_record['counts'])
        timing = repeated_paired_timing(rows, methods, repetitions=plan['repetitions'],
                                        seed=plan['seed'])
        if len(rows) != baseline_record['record_count'] or _sha256(frozen[domain]['path']) != baseline_record['source_sha256']:
            fail(f'Post-run source integrity or row count changed: {domain}')
        report['results'].append({'domain': domain,
                                  'source_sha256': baseline_record['source_sha256'],
                                  'record_count': len(rows), 'statuses_both_methods': counts,
                                  'source_csv_read_seconds_once': round(input_read_elapsed, 6),
                                  'checker_parity_at_each_record': True,
                                  'timing_excluding_read_and_hash': timing})
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    opts = ap.add_mutually_exclusive_group(required=True)
    opts.add_argument('--preflight', action='store_true')
    opts.add_argument('--run', action='store_true')
    ap.add_argument('--root', type=Path, default=ROOT)
    args = ap.parse_args()
    try:
        root = args.root.resolve()
        plan, baseline, frozen = preflight(root)
        print('B9 PREFLIGHT PASS: sources, B6.1 counts, catalogue and protocol match frozen chain')
        if args.preflight:
            print('No benchmark executed; no output files written')
            return 0
        out = root / OUT
        if out.exists():
            fail('Existing B9 result found; refuse overwrite. Preserve run provenance.')
        report = run(root)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        for item in report['results']:
            print(f"{item['domain']}: {item['record_count']} records, exact two-checker parity; nine repeated timings per method")
        print('SAVED:', out, '\nNo published-method or semantic-accuracy comparison claimed.')
        return 0
    except (BenchmarkError, OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        print('B9 FAIL CLOSED:', exc, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
