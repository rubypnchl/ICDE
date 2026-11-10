# B8.1 — Frozen saved-decision audit (exploratory)

This is the **submission-deadline feasible** replacement for the originally planned, but still unavailable, prospective matched evaluation of data quality constraint discovery. It **does not close** the independent gold or published-method benchmark gap.

## Execute (Windows PowerShell)

From the root of `H:\nrr136 data\ICDE` after extracting this package into the repo:

```powershell
$py = 'C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe'
& $py .\scripts\check_b8_1_tests.py
& $py .\scripts\run_b8_1_gate_ablation.py --preflight
```

**Commit the B8.1 plan and code BEFORE executing the non-preflight run:**

```powershell
git add src/b8_1_gate_ablation.py scripts/run_b8_1_gate_ablation.py scripts/check_b8_1_tests.py tests/test_b8_1_gate_ablation.py data/evaluation/b8_1_plan_v1.json docs/B8_1_GATE_ABLATION.md docs/B8_1_BASELINE_FEASIBILITY.md
git diff --cached --check
git diff --cached --name-only
git commit -m 'Define B8.1 retrospective matched-proposal decision audit'
git push origin main
& $py .\scripts\run_b8_1_gate_ablation.py
```

**Then** inspect `data/evaluation/b8_1_gate_ablation/summary.json` and `paired_saved_decisions.csv`; if accurate, commit only the three result files. The runner refuses to overwrite an existing result directory. It never modifies old reports, uses raw data, makes network requests or calls an LLM.

## Evaluation interpretation

**Two cohorts remain distinct.** Saved Luna pilot has two manually selected candidate proposals (healthcare and finance). Original B4 compilation gives 1 executable-but-unverified and 1 blocked for unresolved parameters. Retrospective B5.1 gives a curator-enabled healthcare compiled-unverified status and a finance blocked-for-scope status; none is independently verified safe to deploy. B4 versus B5.1 is **not an isolated gate switch**, because parameter availability changed.

The 28 previously mined candidates are 17 AI4I ranges and 11 SEC sum identities. Existing legacy evidence procedure supported 1 SEC parent-equity rule after 41/41 held-out arithmetic matches; 27 abstained. B7.3 established this one apparent support was based partly on hardcoded accounting scope and the preexisting frozen B6-FIN-002 universal exclusion. Conservative context re-evaluation therefore abstains or blocks this one; it cannot demonstrate better precision without gold labels. The remaining 27 continue to abstain because no documentary rule support is in the saved evidence records. **No new source check or direct prospective execution of a gate is performed for those 27.**

**No comparison with Auto-Test, Guardrail or Metanome has been run.** This procedure is a retrospective *decision reconstruction*, useful only as an auditable limitations-aware case study. Do not aggregate 2+28 as matched proposals, compute semantic accuracy, claim error prevention rate or depict ablation as statistically independent.

## Authorship and reviewer data

The independent review worksheets are separate, private assessments of **five proposed source rules** and 87 selected records. They are not the same candidate sample as the 28 mined rules and must not be silently treated as gold outcomes. Preserve the two original reviewer ZIPs and reconciled analysis copies privately. Reviewer independence was confirmed by research coordination, but discrepancies and final source applicability still need adjudication. No private reviewer texts are ingested into this batch.
