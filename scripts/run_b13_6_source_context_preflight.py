"""Read-only B13.6 source-context preflight (never calls remote sources)."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.b13_6_source_context_readiness import (ReadinessError,load_json,validate_readiness,
    validate_blank_template,sha256_file,canonical_sha)

def run():
    sr=ROOT/'data/evaluation/b13_6_source_context_questions_v1.json'
    pa=ROOT/'data/evaluation/b13_2_source_screening_v1.json'
    tm=ROOT/'data/evaluation/b13_6_manual_source_review_TEMPLATE.csv'
    old=ROOT/'data/evaluation/b13_5_context_policy_v2.json'
    register,shortlist=load_json(sr),load_json(pa)
    policy=load_json(old)
    if policy.get('study_id')!='b13_5_context_declaration_policy_v2' or policy.get('status')!='synthetic_scope_remediation_not_real_evaluation':
        raise ReadinessError('Missing unchanged B13.5 toy policy ancestry')
    validate_blank_template(tm)
    report=validate_readiness(register,shortlist)
    print('B13.6 PREFLIGHT PASS: source-specific eligibility questions only; NOT a qualified source cohort')
    print(json.dumps(report,indent=2))
    print('B13.2 canonical SHA-256:',canonical_sha(shortlist))
    print('B13.5 policy canonical SHA-256:',canonical_sha(policy))
    print('B13.6 registry SHA-256:',sha256_file(sr))
    print('No downloads, new candidates, B4 gate calls, reviewer truths, results, or manuscript changes')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--preflight',action='store_true',required=True)
    p.parse_args()
    try:run()
    except (OSError,ValueError,ReadinessError,json.JSONDecodeError) as exc:
        print('B13.6 STOP:',str(exc),file=sys.stderr)
        raise SystemExit(2)
