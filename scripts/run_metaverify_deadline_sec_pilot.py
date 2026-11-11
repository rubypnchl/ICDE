"""One-step local SEC source-verified candidate freeze and B13.13 A/B/C run."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.metaverify_deadline_sec_pilot import run

if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cache-dir',type=Path,required=True)
    args=ap.parse_args()
    try:
        report,paths=run(args.cache_dir,ROOT)
        print('DEADLINE SEC MATCHED PILOT COMPLETE — DEVELOPMENT DIAGNOSTIC ONLY')
        print('B4 compiler calls:',report['compiler_invocations'])
        print('Arm decisions:',report['arm_counts'])
        print('NOT independent gold, source qualification, accuracy or prospective effect')
        for path in paths: print('Saved:',path)
    except Exception as e:
        print('PILOT STOP:',type(e).__name__,str(e),file=sys.stderr)
        raise SystemExit(2)
