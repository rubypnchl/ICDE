"""Audit saved B7.1/B5.1 and B7.2/B7.3 decisions; no model or data calls."""
from pathlib import Path
import argparse
import csv
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.b8_1_gate_ablation import run,AuditError

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--preflight',action='store_true')
    parser.add_argument('--outdir',type=Path,default=Path('data/evaluation/b8_1_gate_ablation'))
    args=parser.parse_args()
    root=args.root.resolve()
    try:
        result=run(root,preflight=args.preflight)
        print('B8.1 inputs PASS: B5.1, B7.1, B7.2 and B7.3 match frozen SHA-256 chain')
        a=result['llm_pilot']; b=result['legacy_data_only']
        print(f"SAVED LLM: {a['candidates']} hypotheses, {a['original_compiler_executable_unverified']} original compiler-executable, {a['posthoc_safe_to_deploy']} safely deployed")
        print(f"DATA ONLY: {b['candidates']} candidates, {b['apparent_positive_decisions_legacy']} legacy source-supported, {b['independently_verified_positive_decisions_strict']} independently verified by strict policy")
        print('CAUTION: retrospective reconstructed decisions, NOT an isolated gate ablation or accuracy comparison')
        if args.preflight:
            print('PREFLIGHT PASS; no output files written')
            return 0
        out=args.outdir if args.outdir.is_absolute() else root/args.outdir
        if out.exists():
            raise AuditError('Refusing to overwrite prior B8.1 output directory: '+str(out))
        out.mkdir(parents=True)
        (out/'summary.json').write_text(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')
        items=[]
        for a in result['llm_pilot']['proposal_details']:
            items.append({'cohort':'saved_llm','domain':a['domain'],'candidate_id':a['proposal_id'],
                          'ungated_hypothesis_present':'yes','compiler_only_status':a['original_compiler_status'],
                          'posthoc_gate_status':a['posthoc_evidence_status'],
                          'strict_context_decision':'not_deployable_unverified','catalogue_decision':'not_scored',
                          'independent_gold':'no'})
        for a in result['legacy_data_only']['candidate_details']:
            items.append({'cohort':'data_only','domain':a['dataset_id'],'candidate_id':a['candidate_id'],
                          'ungated_hypothesis_present':'yes','compiler_only_status':'not_comparable_legacy_schema',
                          'posthoc_gate_status':a['legacy_decision'],
                          'strict_context_decision':a['strict_context_decision'],
                          'catalogue_decision':a['strict_context_and_catalogue_decision'],
                          'independent_gold':'no'})
        fields=['cohort','domain','candidate_id','ungated_hypothesis_present','compiler_only_status',
                'posthoc_gate_status','strict_context_decision','catalogue_decision','independent_gold']
        with (out/'paired_saved_decisions.csv').open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(items)
        md='''# B8.1 — Retrospective saved-decision comparison (exploratory only)

Two non-equivalent cohorts are analysed *separately*; 30 candidates are not a single comparable benchmark.

| Cohort | Historical observations | Conservative interpretation |
|---|---|---|
| Saved LLM pilot (n=2; finance/healthcare) | Finance original B4 executable-unverified; healthcare blocked unresolved; post-hoc curator-enabled healthcare compile, finance blocked scope | 0 independently verified deployable rules; not an isolated gate effect |
| Data-only miner (n=28; AI4I/SEC) | 27 abstained, 1 parent-equity SEC candidate labelled documented support after 41/41 held-out arithmetic matches | 0 independently verified positive decisions after conservative context review; 1 historical label changes to abstain/blocked |

No gold rule precision, accuracy improvement, published method superiority or natural-error performance is estimated. B5.1 and B7.3 policies are retrospective and after seeing outcomes; B5.1 also changed parameter availability. The strict 28-case analysis is a conservative reassessment of existing evidence, not a prospective execution of a new gate on unseen proposals.

Source: `summary.json` + 30-row `paired_saved_decisions.csv`, with historical input-file SHA-256 records. For any ICDE paper, call this a *retrospective decision audit*, not a controlled gate-on/gate-off benchmark.
'''
        (out/'README.md').write_text(md,encoding='utf-8')
        print('Saved:',out)
        return 0
    except (AuditError,ValueError,KeyError,TypeError,OSError) as e:
        print('B8.1 STOPPED:',e,file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
