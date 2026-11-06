"""B7.2: preflight or execute transparent 4-domain candidate pair screen."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.b7_2_candidate_screen import ScreenError, extract_metadata, json_read, save_results

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=ROOT)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--check-inputs',action='store_true')
    group.add_argument('--run',action='store_true')
    args=p.parse_args()
    try:
        root=args.root.resolve()
        if args.check_inputs:
            state=extract_metadata(root,json_read(root/'data/evaluation/b7_2_plan_v1.json'))
            print('B7.2 preflight PASS: 4 metadata sources, frozen plan, B7.1 result verified')
            for domain, dataset in state['datasets'].items():
                print(f"  {domain}: {dataset['total_metadata_columns']} columns, {len(dataset['numeric_columns'])} unique numeric columns")
            print('No files written and no network/API/raw-row access')
        else:
            result=save_results(root)
            for item in result['domain_summaries']:
                print(f"{item['domain']}: {item['numeric_pair_universe']} eligible numeric pairs; "
                      f"{item['candidate_budget_each_arm']} pairs per arm; "
                      f"masked-description Jaccard {item['description_masked_jaccard']:.3f}")
            print('Saved data/evaluation/b7_2_candidate_screen/{rankings.csv,blind_review_unfilled.csv,summary.json,README.md}')
            print('No gold labels, no semantic precision, no original data changes, no API calls')
        return 0
    except (OSError,KeyError,TypeError,ValueError,ScreenError) as exc:
        print(f'B7.2 ERROR: {exc}',file=sys.stderr)
        return 2

if __name__=='__main__':
    raise SystemExit(main())
