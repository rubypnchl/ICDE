"""B13.11 retrospective B4/B3 source execution; not prospective gate-effect inference."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.b13_11_retrospective_matched_replay import (
    ReplayError,load_inputs,validate_spec,make_candidate,diagnostic_admission,run_replay,exclusive_write_outputs)
from src.rule_bridge import compile_proposal


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight',action='store_true')
    mode.add_argument('--run',action='store_true')
    parser.add_argument('--cache-dir',type=Path,default=Path.home()/'Downloads'/'ICDE-B13-Source-Cache')
    args=parser.parse_args()
    spec,b137,b138,b139,b1310=load_inputs(ROOT)
    validate_spec(spec,b137,b138,b139,b1310)
    for item in b139['pairs']:
        proposal,registry,columns=make_candidate(item,'nhanes_2015_2016_cycle',spec)
        compiled=compile_proposal(proposal,columns,registry)
        _,decisions=diagnostic_admission(proposal,compiled,columns,item,spec)
        if decisions!={'A':'admit','B':'admit','C':'abstain'}:
            raise ReplayError('B4/B3 policy preflight diverged')
    if args.preflight:
        print('B13.11 PREFLIGHT PASS: actual B4/B3 compile validated on 3 previously documented pairs; no source read')
        print('Diagnostic A/B admit; C abstain because independent documentary review is absent')
        print('0 source-eligible candidates; 0 gold; 0 prospective evaluations; no output written')
        return
    report=run_replay(args.cache_dir,ROOT,spec,b137,b138,b139,b1310)
    output=exclusive_write_outputs(args.cache_dir,ROOT,report)
    print('B13.11 RETROSPECTIVE REAL-DATA EXECUTABLE DIAGNOSTIC COMPLETE')
    print(json.dumps({'pair_candidates_hand_curated':report['pair_candidates_hand_curated'],
                      'source_clusters':report['source_clusters'],
                      'B4_compiler_invocations':report['B4_compiler_invocations'],
                      'arm_counts':report['arm_counts'],
                      'pair_outcomes':[{'pair_id':x['pair_id'],'record_count':x['record_count'],
                                        'evaluated_records':x['evaluated_records'],'B3_counts':x['b3_counts']}
                                       for x in report['pair_outcomes']],
                      'gold_rules':report['gold_rules'],'confirmatory_candidates':report['confirmatory_candidates']},indent=2))
    print('Manuscript-ready descriptive table and handover OUTSIDE Git:')
    for p in output:print(' ',p)
    print('Exact-equality differences are NOT errors; A/B/C outcomes are only diagnostic; NO scientific gate-effect estimate')

if __name__=='__main__':
    try:main()
    except (ReplayError, ValueError, TypeError, KeyError, FileNotFoundError, OSError, ImportError) as exc:
        print('B13.11 STOP:',type(exc).__name__,str(exc),file=sys.stderr)
        raise SystemExit(2)
