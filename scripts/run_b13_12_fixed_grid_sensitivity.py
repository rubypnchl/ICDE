"""B13.12 fixed B13.9 numerical-bin sensitivity on real NHANES XPT (retrospective)."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.b13_12_fixed_grid_sensitivity import validate_plan,make_tolerance_compilation,run,exclusive_save,SensitivityError
from src.b13_11_retrospective_matched_replay import load_inputs,validate_spec
from src.b13_11_retrospective_matched_replay import ReplayError

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    modes=ap.add_mutually_exclusive_group(required=True)
    modes.add_argument('--preflight',action='store_true')
    modes.add_argument('--run',action='store_true')
    ap.add_argument('--cache-dir',type=Path,default=Path.home()/'Downloads'/'ICDE-B13-Source-Cache')
    args=ap.parse_args()
    plan=json.loads((ROOT/'data/evaluation/b13_12_sensitivity_spec_v1.json').read_text(encoding='utf-8'))
    previous,b137,b138,b139,b1310=load_inputs(ROOT)
    validate_spec(previous,b137,b138,b139,b1310)
    validate_plan(plan,b139)
    for pair in b139['pairs']:
        for threshold in plan['tolerance_grid_mmol_l']:
            make_tolerance_compilation(pair,plan['source_group'],previous,threshold)
    if args.preflight:
        print('B13.12 PREFLIGHT PASS: actual B4/B3 interfaces compiled 15 grid rules; NO real source read')
        print('Exploratory B13.9 bins only; no independent precision, no gold, no claims about errors or gate effect')
        return
    result=run(args.cache_dir,ROOT,plan)
    paths=exclusive_save(args.cache_dir,ROOT,result)
    print('B13.12 RETROSPECTIVE B4/B3 TOLERANCE SENSITIVITY COMPLETE')
    for pair in result['pairs']:
        print(pair['pair_id'],'strict satisfied',pair['previous_exact_counts']['satisfied'],
              'grid satisfied',[(v['tolerance_mmol_l'],v['satisfied']) for v in pair['grid']])
    for p in paths:print('Output:',p)
    print('NOT independently justified tolerances, natural errors, gold or prospective comparative gains')

if __name__=='__main__':
    try:main()
    except (SensitivityError,ReplayError,ValueError,TypeError,KeyError,OSError,ImportError) as exc:
        print('B13.12 STOP:',type(exc).__name__,str(exc),file=sys.stderr)
        raise SystemExit(2)
