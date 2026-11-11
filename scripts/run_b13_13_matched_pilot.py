"""B13.13: explicitly frozen, source-associated *non-confirmatory* three-arm pilot."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.b13_7_source_acquisition import assert_external_cache
from src.b13_13_matched_pilot import (
    STUDY, PHASE, PilotError, read_json, canonical_hash, freeze, validate_lock,
    run_matched, exclusive_json, read_reviews, score_reviews)
from src.rule_bridge import compile_proposal
from src.generic_verifier import validate_rule

LOCK='B13_13_frozen_input_lock_v1.json'
BLIND='B13_13_blinded_review_packet_v1.json'
GATES='B13_13_matched_gate_pilot_v1.json'
SCORE='B13_13_human_vote_scoring_pilot_v1.json'


def check_spec() -> dict:
    spec=read_json(ROOT/'data/evaluation/b13_13_pilot_spec_v1.json')
    if (spec.get('study_id')!=STUDY or spec.get('phase')!=PHASE or
        spec.get('confirmatory_protocol_replaced') is not False or
        spec.get('real_independent_gold_available') is not False or
        spec.get('claims_allowed')!=['frozen_input_matched_pilot_when_source_and_votes_supplied'] or
        spec.get('comparison_arms')!=['A','B','C']):
        raise PilotError('B13.13 pilot specification mutated')
    return spec


def preflight() -> None:
    check_spec()
    toy={'proposal_version':'metaverify-proposal-v0.1','id':'B13-13-PREFLIGHT',
         'dataset_id':'preflight-ONLY','origin':'fixture_only',
         'assertions':[{'left':{'column':'x'},'op':'eq','right':{'column':'y'}}],
         'context_keys':[]}
    compiled=compile_proposal(toy,['x','y'],{})
    if compiled.status!='candidate_executable_unverified' or validate_rule(compiled.rule)!={'x','y'}:
        raise PilotError('B4/B3 preflight contract changed')
    print('B13.13 PREFLIGHT PASS: actual B4/B3 imported; separate-source input lock, blind review, A/B/C and scoring interfaces ready')
    print('No candidate cohort supplied; no gate result, reviewer label, independent gold or confirmatory metric')


def run_command(args) -> None:
    check_spec()
    if args.preflight:
        preflight(); return
    if args.packet is None or args.out_dir is None:
        raise PilotError('--packet and --out-dir are required for freeze/run/score')
    out=assert_external_cache(args.out_dir,ROOT)
    packet_path=args.packet.expanduser().resolve()
    if ROOT.resolve()==packet_path or ROOT.resolve() in packet_path.parents:
        raise PilotError('Candidate packet with raw local source paths must stay outside Git')
    packet=read_json(packet_path)
    lock_path=out/LOCK
    if args.freeze:
        locked,blind=freeze(packet,ROOT)
        out.mkdir(parents=True,exist_ok=True)
        paths=[lock_path,out/BLIND]
        if any(p.exists() for p in paths):
            raise PilotError('Existing pilot lock/blinded packet: no overwriting')
        created=[]
        try:
            for path,payload in zip(paths,[locked,blind]):
                exclusive_json(path,payload);created.append(path)
        except BaseException:
            for path in created:
                path.unlink(missing_ok=True)
            raise
        print('B13.13 PILOT INPUT FREEZE COMPLETE:',len(packet['candidates']),'candidates; not confirmatory')
        print('Frozen lock:',paths[0]);print('Reviewer-blinded packet:',paths[1]);return
    lock=read_json(lock_path)
    validate_lock(packet,lock,ROOT)
    if args.run:
        target=out/GATES
        if target.exists():
            raise PilotError('Existing matched gate file cannot be overwritten')
        report=run_matched(packet,lock,ROOT)
        exclusive_json(target,report)
        print('B13.13 REAL-INPUT MATCHED DEVELOPMENT PILOT COMPLETE')
        print(json.dumps({'candidate_count':report['candidate_count'],'compiler_invocations':report['compiler_invocations'],
                         'arm_counts':report['arm_counts'],'confirmatory':False},indent=2))
        print('Pilot output:',target);return
    if args.score:
        for path in (args.reviewer1,args.reviewer2,args.adjudicator):
            if path is not None and (path.expanduser().resolve()==ROOT.resolve() or ROOT.resolve() in path.expanduser().resolve().parents):
                raise PilotError('Completed private reviewer forms must remain outside Git')
        if args.reviewer1 is None or args.reviewer2 is None:
            raise PilotError('Two independently completed review files required')
        target=out/SCORE
        if target.exists():
            raise PilotError('Existing scoring file cannot be overwritten')
        gates=read_json(out/GATES)
        # Re-run the same frozen input to detect tampered gate result files.
        if gates!=run_matched(packet,lock,ROOT):
            raise PilotError('Gate output differs from deterministic frozen candidate replay')
        ids={c['candidate_id'] for c in packet['candidates']}
        r1,id1=read_reviews(args.reviewer1,ids,'reviewer1')
        r2,id2=read_reviews(args.reviewer2,ids,'reviewer2')
        adj,adid=(None,None)
        if args.adjudicator is not None:
            adj,adid=read_reviews(args.adjudicator,ids,'adjudicator')
        scores=score_reviews(packet,lock,gates,r1,r2,adj,(id1,id2),adid)
        exclusive_json(target,scores)
        print('B13.13 CONDITIONAL HUMAN-VOTE PILOT SCORING COMPLETE (not independently authenticated)')
        print(json.dumps({'denominators':scores['reference_denominators'],
                          'arm_metrics':scores['arm_metrics'],'source_group_count':scores['source_group_count']},indent=2))
        print('Pilot scoring output:',target);return


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    g=ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--preflight',action='store_true')
    g.add_argument('--freeze',action='store_true')
    g.add_argument('--run',action='store_true')
    g.add_argument('--score',action='store_true')
    ap.add_argument('--packet',type=Path)
    ap.add_argument('--out-dir',type=Path)
    ap.add_argument('--reviewer1',type=Path)
    ap.add_argument('--reviewer2',type=Path)
    ap.add_argument('--adjudicator',type=Path)
    ns=ap.parse_args()
    try:run_command(ns)
    except (PilotError,OSError,ValueError,TypeError,KeyError,ImportError,IndexError,OverflowError) as exc:
        print('B13.13 STOP:',type(exc).__name__,str(exc),file=sys.stderr)
        sys.exit(2)
