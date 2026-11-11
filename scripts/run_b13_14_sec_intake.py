"""B13.14: explicit SEC 10-K metadata intake for a new potential source group."""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.b13_14_sec_intake import (IntakeError,validate_source_selection,acquire,verify,RECEIPT,OBJ,URL)

def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    m=p.add_mutually_exclusive_group(required=True)
    m.add_argument('--preflight',action='store_true')
    m.add_argument('--acquire',action='store_true')
    m.add_argument('--verify',action='store_true')
    p.add_argument('--cache-dir',type=Path,default=Path.home()/'Downloads'/'ICDE-B13-Independent-Pilot')
    args=p.parse_args()
    plan=json.loads((ROOT/'data/evaluation/b13_14_sec_intake_plan_v1.json').read_text(encoding='utf-8'))
    prior=json.loads((ROOT/'data/sources.json').read_text(encoding='utf-8'))
    excluded=validate_source_selection(plan,prior)
    if args.preflight:
        print('B13.14 PREFLIGHT PASS: SEC candidate issuer excluded from',len(excluded),'known development CIKs')
        print('Pinned selection: latest 10-K filed on/before 2026-11-11; one issuer/one source cluster')
        print('NO source downloaded, no reviewer, no XBRL context, no rule, no gold or matched gate results')
        return
    if args.acquire:
        receipt=acquire(args.cache_dir,ROOT,plan,prior,os.environ.get('SEC_USER_AGENT',''))
        print('B13.14 SEC SOURCE-LEAD ACQUISITION COMPLETE; NOT source qualified')
    else:
        receipt=verify(args.cache_dir,ROOT,plan,prior)
        print('B13.14 SEC SOURCE-LEAD RECEIPT VERIFIED; NOT source qualified')
    print(json.dumps({key:receipt[key] for key in ('source_cik','company_name_from_api','download_sha256','download_size_bytes','selected_filing','development_CIK_exclusion_count','source_semantic_eligibility_verified','real_candidate_count','independent_gold','real_gate_runs')},indent=2))
    print('Raw SEC submission object and receipt OUTSIDE Git:',args.cache_dir,OBJ,RECEIPT)

if __name__=='__main__':
    try:main()
    except (IntakeError,ValueError,TypeError,KeyError,OSError,ImportError) as exc:
        print('B13.14 STOP:',type(exc).__name__,str(exc),file=sys.stderr)
        raise SystemExit(2)
