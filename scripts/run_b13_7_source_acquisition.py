"""B13.7 explicit source object acquisition; --preflight makes no writes/network calls."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.b13_7_source_acquisition import SourceError, validate_registry, assert_external_cache, acquire, verify_existing

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--preflight', action='store_true')
    actions.add_argument('--acquire', choices=['B13S-HLT-01','B13S-HLT-02','B13S-MAN-01'])
    actions.add_argument('--verify', choices=['B13S-HLT-01','B13S-HLT-02','B13S-MAN-01'])
    parser.add_argument('--cache-dir', type=Path, default=Path.home()/'Downloads'/'ICDE-B13-Source-Cache')
    args = parser.parse_args()
    registry = json.loads((ROOT/'data/evaluation/b13_7_source_objects_v1.json').read_text(encoding='utf-8'))
    items = validate_registry(registry)
    if args.preflight:
        print('B13.7 PREFLIGHT PASS: 3 versioned official public-source URLs registered; NO downloads or results')
        print('NHANES source objects share one cycle; UCI object is a separate source family')
        print('Source eligibility: 0; candidates: 0; gold: 0; gate executions: 0')
        return
    cache = assert_external_cache(args.cache_dir, ROOT)
    sid = args.acquire or args.verify
    item = next(i for i in items if i['source_id'] == sid)
    if args.acquire:
        print('B13.7 MANUAL ACQUISITION:', sid, '=>', str(cache))
        receipt = acquire(item, cache)
    else:
        receipt = verify_existing(item, cache)
    print(json.dumps(receipt, indent=2))
    print('File identity and local fingerprint only; source eligibility, semantic constraints and gold remain unverified')

if __name__ == '__main__':
    try:
        main()
    except (SourceError, OSError, ValueError, json.JSONDecodeError, Exception) as exc:
        print('B13.7 STOP:', type(exc).__name__ + ':', exc, file=sys.stderr)
        sys.exit(2)
