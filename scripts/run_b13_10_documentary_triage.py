"""B13.10: read-only aggregate lineage and source applicability triage."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.b13_10_documentary_triage import (TriageError, validate_register,
    assess_external_cache, exclusive_save)
from src.b13_8_source_schema_audit import validate_plan as validate_b138_plan

def load(name):
    return json.loads((ROOT/'data/evaluation'/name).read_text(encoding='utf-8'))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight',action='store_true')
    mode.add_argument('--assess',action='store_true')
    parser.add_argument('--cache-dir',type=Path,default=Path.home()/'Downloads'/'ICDE-B13-Source-Cache')
    args=parser.parse_args()
    register=load('b13_10_evidence_applicability_register_v1.json')
    b137=load('b13_7_source_objects_v1.json')
    b138=load('b13_8_schema_audit_plan_v1.json')
    b139=load('b13_9_documented_pair_plan_v1.json')
    validate_register(register,b137,b139)
    validate_b138_plan(b138,b137)
    if args.preflight:
        print('B13.10 PREFLIGHT PASS: 4 previously examined relationships registered; no data or gates read')
        print('Three explicit CDC conversion factors; one observed UCI target encoding, not a gold constraint')
        print('Independent evidence decisions: 0; real context policies: 0; confirmatory candidates: 0')
        return
    report=assess_external_cache(args.cache_dir,ROOT,register,b137,b138,b139)
    path=exclusive_save(args.cache_dir,ROOT,report)
    print('B13.10 RETROSPECTIVE EVIDENCE AND APPLICABILITY TRIAGE COMPLETE')
    print(json.dumps({'screened':report['source_relationships_screened'],
         'documentary_review_decisions':report['source_documentary_reviews_independently_adjudicated'],
         'confirmatory_eligible':report['eligible_confirmatory_relationships'],
         'real_context_policies':report['real_source_context_policies_frozen'],
         'gold':report['independent_gold_rules'],
         'items':[{'item_id':x['item_id'],'documentary_status':x['documentary_status'],
                   'confirmatory_eligible':x['confirmatory_accuracy_denominator_eligible']}
                  for x in report['evidence_items']]},indent=2))
    print('Aggregate-only output outside Git:',path)
    print('No new source download, candidate, reviewer label, B4/B3 gate run, participant row, or precision gold')

if __name__=='__main__':
    try: main()
    except (TriageError,OSError,ValueError,TypeError,KeyError) as exc:
        print('B13.10 STOP:',type(exc).__name__,str(exc),file=sys.stderr)
        raise SystemExit(2)
