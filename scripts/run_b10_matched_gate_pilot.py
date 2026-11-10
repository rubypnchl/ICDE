"""Run reproducible B10 same-input retrospective compiler / evidence comparison."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.b10_matched_gate_pilot import B10Error, OUTPUT_DIR, preflight, run

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check-inputs', action='store_true')
    p.add_argument('--root', type=Path, default=ROOT)
    args = p.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.check_inputs:
            prepared = preflight(root)
            print('B10 PREFLIGHT PASS: 2 original B5 LLM proposals, B5.1 policy, B7.1 source hash chain')
            print('Same proposal AST and fixed curator parameters in B4 and B5.1 arms; no files written')
            return 0
        target = root / OUTPUT_DIR
        files = [target / 'summary.json', target / 'paired_decisions.csv', target / 'README.md']
        if any(f.exists() for f in files):
            raise B10Error('B10 outputs already exist; refusing overwrite. Inspect first.')
        summary, rows = run(root)
        # Check before any write, including for conflicting outputs or altered source files.
        for relative, digest in summary['input_sha256'].items():
            from src.b10_matched_gate_pilot import sha_file
            if sha_file(root / relative) != digest:
                raise B10Error('Source changed during run: '+relative)
        target.mkdir(parents=True,exist_ok=True)
        (target/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        with (target/'paired_decisions.csv').open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]))
            w.writeheader();w.writerows(rows)
        report = summary['results']
        readme = f'''# B10 matched-input retrospective compilation and evidence decision replay\n\nThis is **not** a prospective gate ablation or gold accuracy experiment.\n\n- Same original saved LLM proposal expressions in all three conceptual stages: {report['candidate_proposals_present']}.\n- Original B5 compilation without human curator aliases: {report['original_compiler_executable_without_curator_binding']} executable-unverified.\n- Recompiled B4 with the exact frozen B5.1 curator aliases held fixed: {report['compiler_executable_with_fixed_curator_binding']} executable-unverified.\n- B5.1 evidence policy with that same curator registry: {report['evidence_gate_status_counts']}.\n- Rules established safe to deploy by the existing gate: {report['safe_for_deployment_according_to_existing_gate']}.\n\nThe original B5.1 policy and glucose rounding authorization were constructed *after* seeing the proposals. This replay isolates identical proposal and binding inputs inside a procedural decision comparison, **not** a causal generalisation. Only two previously handpicked opportunities exist; no true precision/recall or published baselines were measured.\n\nFull source hashes, reasons and candidate-level decisions: `summary.json`, `paired_decisions.csv`.\n'''
        (target/'README.md').write_text(readme,encoding='utf-8')
        print('B10 SUCCESS: retrospective matched-input decision comparison')
        print('SAVED LLM PROPOSALS:',report['candidate_proposals_present'])
        print('ORIGINAL (unassisted) COMPILER-EXECUTABLE:',report['original_compiler_executable_without_curator_binding'])
        print('WITH IDENTICAL CURATOR BINDINGS, COMPILER-EXECUTABLE:',report['compiler_executable_with_fixed_curator_binding'])
        print('EVIDENCE REVIEW DECISIONS:',report['evidence_gate_status_counts'])
        print('SAFE TO DEPLOY BY SAVED POLICY:',report['safe_for_deployment_according_to_existing_gate'])
        print('RESULT:',str(target))
        print('CAUTION: no independent gold, causal effectiveness, or published-method comparison')
        return 0
    except (B10Error,OSError,ValueError,KeyError,TypeError) as exc:
        print('B10 STOP (no valid results claimed):',exc,file=sys.stderr)
        return 2

if __name__=='__main__':
    raise SystemExit(main())
