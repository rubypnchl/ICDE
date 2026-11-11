"""B13.9 read-only empirical audit of documented NHANES conversion pairs."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.b13_9_documented_pair_consistency import PairAuditError, audit_pairs, exclusive_save, validate_plan
from src.b13_8_source_schema_audit import validate_plan as validate_b138_plan


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight', action='store_true')
    mode.add_argument('--inspect', action='store_true')
    ap.add_argument('--cache-dir', type=Path, default=Path.home() / 'Downloads' / 'ICDE-B13-Source-Cache')
    args = ap.parse_args()
    plan = json.loads((ROOT / 'data/evaluation/b13_9_documented_pair_plan_v1.json').read_text(encoding='utf-8'))
    reg = json.loads((ROOT / 'data/evaluation/b13_7_source_objects_v1.json').read_text(encoding='utf-8'))
    b138 = json.loads((ROOT / 'data/evaluation/b13_8_schema_audit_plan_v1.json').read_text(encoding='utf-8'))
    validate_plan(plan)
    validate_b138_plan(b138, reg)
    if args.preflight:
        print('B13.9 PREFLIGHT PASS: 3 previously documented NHANES unit-pairs, one source cycle; NO source read')
        print('No rule discovery, no fitted tolerance/precision, no real gates and no gold')
        return
    result = audit_pairs(args.cache_dir, ROOT, plan, reg, b138)
    from src.b13_7_source_acquisition import assert_external_cache
    path = exclusive_save(assert_external_cache(args.cache_dir, ROOT), ROOT, result)
    print('B13.9 EXPLORATORY DOCUMENTED PAIR AUDIT COMPLETE')
    print(json.dumps([{'pair_id': x['pair_id'], 'paired_nonmissing': x['aggregates']['paired_nonmissing'],
                       'median_absolute_residual_mmol_l': x['aggregates']['absolute_residual_mmol_l']['median'],
                       'p95_absolute_residual_mmol_l': x['aggregates']['absolute_residual_mmol_l']['p95'],
                       'max_absolute_residual_mmol_l': x['aggregates']['absolute_residual_mmol_l']['max']}
                      for x in result['conversion_pairs']], indent=2))
    print('Aggregate-only external output:', path)
    print('No SEQN, participant-level values, fitted rounding, rule discovery, adjudicated errors, or gate outcomes emitted')

if __name__ == '__main__':
    try:
        main()
    except (PairAuditError, OSError, ValueError, TypeError, ImportError) as exc:
        print('B13.9 STOP:', type(exc).__name__, str(exc), file=sys.stderr)
        raise SystemExit(2)
