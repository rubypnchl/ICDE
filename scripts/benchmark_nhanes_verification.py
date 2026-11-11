"""Read-only B4 + B3 runtime profile on the previously verified NHANES XPT data.

From the ICDE repository root:
  python scripts/benchmark_nhanes_verification.py --selftest
  python scripts/benchmark_nhanes_verification.py \
      --cache-dir '<external B13 source cache>' --output '<external cache>/B4_B3_Runtime_v1.json'

Reports timings for executing ONE pre-curated relationship on the same in-memory
source frame. Includes B4 compile + policy diagnostic + B3 row iteration, but
EXCLUDES XPT file reading, source verification, source acquisition, model calls,
and independent documentary review. This is NOT end-to-end system latency or a
matched published baseline comparison. Source records and identifiers are never
included in outputs. Existing experiment files are not modified.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PAIRS = ('TRIGLY_TR_UNIT', 'TRIGLY_LDL_UNIT', 'TCHOL_TC_UNIT')
STUDY = 'metaverify_b4_b3_in_memory_nhanes_runtime_v1'


class BenchmarkError(ValueError):
    pass


def describe_times(times: list[float], eligible: int) -> dict:
    """Nearest-rank empirical p95; sample count always exposed."""
    if not times or eligible <= 0 or any(not math.isfinite(t) or t <= 0 for t in times):
        raise BenchmarkError('Invalid duration samples or eligible count')
    ordered = sorted(times)
    p95_index = max(0, math.ceil(0.95 * len(times)) - 1)
    return {
        'repetitions': len(times),
        'median_seconds': round(statistics.median(ordered), 8),
        'p95_nearest_rank_seconds': round(ordered[p95_index], 8),
        'min_seconds': round(ordered[0], 8),
        'max_seconds': round(ordered[-1], 8),
        'median_evaluated_checks_per_second': round(statistics.median([eligible / t for t in times]), 2),
    }


def validate_outcome(actual: dict, expected: dict, pid: str) -> None:
    if (actual.get('pair_id') != pid or actual.get('record_count') != expected.get('record_count')
            or actual.get('evaluated_records') != expected.get('evaluated_records')
            or actual.get('b3_counts') != expected.get('b3_counts')
            or (actual.get('A'), actual.get('B'), actual.get('C')) != ('admit', 'admit', 'abstain')
            or actual.get('b4_compiler_calls') != 1):
        raise BenchmarkError(f'Timed execution deviated from pinned B13.11 counts for {pid}')


def selftest():
    s = describe_times([0.2, 0.1, 0.3, 0.5, 0.4], 100)
    assert s['median_seconds'] == 0.3
    assert s['p95_nearest_rank_seconds'] == 0.5
    assert s['median_evaluated_checks_per_second'] == round(100/0.3, 2)
    try:
        describe_times([0.0], 1)
    except BenchmarkError:
        pass
    else:
        raise AssertionError('Zero runtime was not rejected')
    print('NHANES B4/B3 RUNTIME SELFTEST PASS')


def run(cache: Path, repetitions: int = 15, warmups: int = 2) -> dict:
    if repetitions < 5 or repetitions > 30 or warmups < 1 or warmups > 5:
        raise BenchmarkError('Use 5-30 repetitions and 1-5 warmups')

    from src.b13_7_source_acquisition import assert_external_cache, verify_existing
    from src.b13_8_source_schema_audit import PINNED
    from src.b13_11_retrospective_matched_replay import (
        load_inputs, validate_spec, execute_pair,
    )

    cache = assert_external_cache(cache.resolve(), ROOT)
    assert cache.is_dir(), 'External cache does not exist'
    spec, b137, b138, b139, b1310 = load_inputs(ROOT)
    validate_spec(spec, b137, b138, b139, b1310)
    stored_path = cache / 'B13_11_retrospective_matched_replay_v1.json'
    if not stored_path.is_file():
        raise BenchmarkError('Saved B13.11 replay output is missing')
    stored = json.loads(stored_path.read_text(encoding='utf-8'))
    if (stored.get('study_id') != 'b13_11_real_xpt_matched_compiler_diagnostic_v1'
            or stored.get('source_clusters') != 1 or stored.get('gold_rules') != 0
            or stored.get('pair_candidates_hand_curated') != 3):
        raise BenchmarkError('Unexpected parent B13.11 study')
    expected_pairs = {row['pair_id']: row for row in stored.get('pair_outcomes', [])}
    if set(expected_pairs) != set(PAIRS):
        raise BenchmarkError('Unexpected B13.11 candidates')

    receipts = {}
    sources = {item['source_id']: item for item in b137['source_ids']}
    for sid in ('B13S-HLT-01', 'B13S-HLT-02'):
        receipt = verify_existing(sources[sid], cache)
        if ((receipt['object_name'], receipt['sha256'], receipt['size_bytes'], receipt['source_group'])
                != PINNED[sid]):
            raise BenchmarkError(f'Pinned source mismatch: {sid}')
        receipts[sid] = receipt
    import pyreadstat
    frames = {}
    for sid, receipt in receipts.items():
        frame, _ = pyreadstat.read_xport(str(cache / receipt['object_name']))
        frames[sid] = frame

    report_pairs = []
    for pair in b139['pairs']:
        pid = pair['pair_id']
        if pid not in expected_pairs:
            raise BenchmarkError('Unexpected pair in source registry')
        sid = pair['source_id']
        frame = frames[sid]
        group = receipts[sid]['source_group']
        expected = expected_pairs[pid]
        def once():
            out = execute_pair(frame, pair, group, spec)
            validate_outcome(out, expected, pid)
            return out
        for _ in range(warmups):
            once()
        samples = []
        for _ in range(repetitions):
            begin = time.perf_counter()
            once()
            samples.append(time.perf_counter() - begin)
        report_pairs.append({
            'pair_id': pid, 'record_count': expected['record_count'],
            'evaluated_record_count': expected['evaluated_records'],
            'source_group': group,
            'runtime': describe_times(samples, expected['evaluated_records']),
        })

    if len(report_pairs) != 3:
        raise BenchmarkError('Expected exactly three published relationships')
    return {
        'study': STUDY,
        'label': 'read_only_engineering_profile_not_end_to_end_nor_SOTA',
        'parent_study': stored['study_id'],
        'python_version': platform.python_version(),
        'operating_system': platform.platform(),
        'cpu_logical_count': os.cpu_count(),
        'warmups_per_pair': warmups,
        'repetitions_per_pair': repetitions,
        'timed_scope': 'B4_compile + diagnostic_A_B_C + B3_evaluate_rows on frames already in RAM',
        'excluded': ['XPT disk I/O', 'source download', 'metadata ingestion',
                     'document review', 'source authentication', 'model inference'],
        'source_clusters': 1, 'previously_inspected_pairs': 3,
        'independent_gold': 0, 'matched_published_sota': False,
        'pairs': report_pairs,
        'interpretation': 'Descriptive wall-clock performance on previously inspected NHANES 2015-2016 pairs; not full workflow time or independent effectiveness.',
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--selftest', action='store_true')
    p.add_argument('--cache-dir', type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--repetitions', type=int, default=15)
    p.add_argument('--warmups', type=int, default=2)
    args = p.parse_args()
    if args.selftest:
        selftest()
        return
    if args.cache_dir is None:
        p.error('--cache-dir is required without --selftest')
    result = run(args.cache_dir, args.repetitions, args.warmups)
    payload = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n'
    if args.output:
        output = args.output.resolve()
        if output.parent == ROOT or ROOT in output.parents or not output.parent.is_dir():
            raise BenchmarkError('Output must be in an existing external directory')
        with output.open('x', encoding='utf-8') as f:
            f.write(payload)
        print('SAVED:', output)
    print(payload, end='')


if __name__ == '__main__':
    try:
        main()
    except (BenchmarkError, ValueError, OSError, KeyError, ImportError, AssertionError) as e:
        print('BENCHMARK STOP:', type(e).__name__, str(e), file=sys.stderr)
        raise SystemExit(2)
