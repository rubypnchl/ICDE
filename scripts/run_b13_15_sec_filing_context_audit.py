"""B13.15 source-only SEC Inline XBRL audit; NO candidate or confirmatory claims."""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.b13_14_sec_intake import validate_source_selection
from src.b13_15_sec_filing_context_audit import (FilingAuditError, acquire, audit, verify,
    RAW,RECEIPT,AUDIT,OPPORTUNITIES)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    g=p.add_mutually_exclusive_group(required=True)
    for option in ('preflight','acquire','audit','verify'):
        g.add_argument('--'+option,action='store_true')
    p.add_argument('--cache-dir',type=Path,default=Path.home()/'Downloads'/'ICDE-B13-Independent-Pilot')
    args=p.parse_args()
    plan=json.loads((ROOT/'data/evaluation/b13_14_sec_intake_plan_v1.json').read_text(encoding='utf-8'))
    prior=json.loads((ROOT/'data/sources.json').read_text(encoding='utf-8'))
    validate_source_selection(plan,prior)
    if args.preflight:
        print('B13.15 PREFLIGHT PASS: B13.14 lead and source exclusion checked; no filing downloaded or audit written')
        print('No source qualified; no candidate or gate result generated')
        return
    if args.acquire:
        r=acquire(args.cache_dir,ROOT,plan,prior,os.environ.get('SEC_USER_AGENT',''))
        print('B13.15 ORIGINAL SEC FILING ACQUIRED, NOT QUALIFIED')
        print(json.dumps(r,indent=2))
        return
    if args.audit:
        r,rows=audit(args.cache_dir,ROOT,plan,prior)
    else:
        r=verify(args.cache_dir,ROOT,plan,prior)
    print('B13.15 '+('SOURCE STRUCTURE AUDIT COMPLETE' if args.audit else 'SOURCE RECEIPT / AUDIT VERIFIED'))
    print(json.dumps({k:r[k] for k in ('accession','xbrl_context_count','numeric_ix_fact_count',
          'dimensionless_expected_entity_instant_contexts','target_concept_mention_counts',
          'same_context_same_unit_target_pair_instances','target_pair_ambiguous_duplicate_instances',
          'structural_opportunity_count','independent_gold_rules','real_gate_executions')},indent=2))
    print('No source qualification, candidate freeze, reference truth or A/B/C effectiveness result')
    if args.audit:
        for n in (AUDIT,OPPORTUNITIES):print('Output outside Git:',args.cache_dir/n)

if __name__=='__main__':
    try:main()
    except (FilingAuditError, ValueError, OSError, KeyError, ImportError) as e:
        print('B13.15 STOP:',type(e).__name__,str(e),file=sys.stderr)
        raise SystemExit(2)
