"""Read-only B7.1 saved-pilot opportunity audit; no model/API calls."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.b7_1_pilot_comparison import PilotAuditError, read_json, validate_inputs, run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--check-inputs', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.check_inputs:
            plan = read_json(root / 'data/evaluation/b7_1_comparison_plan_v1.json')
            validate_inputs(root, plan)
            print('B7.1 preflight PASS: same two saved B5 bundles, Luna proposals and B5.1 gate; zero new model calls')
            print('No results written')
            return 0
        output = run(root)
        dest = root / 'data/evaluation/b7_1_pilot_comparison.json'
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(output, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        for row in output['results']:
            print(f"{row['domain']}: lexical hypotheses={row['lexical_heuristic']['candidate_count']}; "
                  f"saved Luna hypotheses={row['saved_luna_pilot']['hypothesis_count']}; "
                  'gold precision=UNAVAILABLE')
        print(f'Saved {dest.relative_to(root)} (RETROSPECTIVE PILOT; NOT A DISCOVERY-QUALITY BENCHMARK)')
        return 0
    except (OSError, ValueError, TypeError, KeyError, PilotAuditError) as exc:
        print(f'B7.1 ERROR (no valid comparison claimed): {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
