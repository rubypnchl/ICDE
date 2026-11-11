"""One-step, offline controlled failure-mode evaluation of previously saved SEC candidate."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.metaverify_deadline_controls import run_real
from src.b13_13_matched_pilot import PilotError

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache-dir',type=Path,required=True)
    args=p.parse_args()
    try:
        report,files=run_real(args.cache_dir,ROOT)
        print('DEADLINE CONTROLLED SEC POLICY STRESS TEST COMPLETE — NOT GOLD OR CONFIRMATORY')
        print(json.dumps({k:report[k] for k in ('controlled_scenarios_total',
          'scenarios_simulated_evidence_not_real','b4_compiler_invocations',
          'arm_counts_over_repeated_scenarios_not_independent_samples','gold_rules')},indent=2))
        for path in files:print('Saved:',path)
        print('Controlled repeated configurations of ONE candidate; NOT independent candidates, accuracy or causal effect')
    except (PilotError,ValueError,TypeError,KeyError,OSError,ImportError) as e:
        print('STOP:',type(e).__name__,str(e),file=sys.stderr)
        sys.exit(2)
