# MetaVerify B9 — nine-repetition real-source checker benchmark

Versioned overlay, designed to extract into the **existing** GitHub repository checkout without overwriting B6/B7/B8 artifacts. The optional benchmark is *not* a published discovery-method comparison or prospective evidence-gate ablation.

## Run on Windows

From `H:\nrr136 data\ICDE`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_b9_one_step.ps1
```

This runs 10 new tests, checks frozen inputs, and (if the local original sources are available) records 9 independent timing passes for MetaVerify's generic verifier and the B6 same-rule checker over 10,000 AI4I and 50,000 CIC flows. No source files or historic outputs are overwritten; no Git commit/push, API, or network request occurs.

Output: `data/evaluation/b9_runtime_results_v1.json`.

**Local status (10 Nov 2026):** 10 dedicated tests pass; real-source timing not executed here because frozen source CSVs reside on the author's local machine.

See `docs/B9_EXPERIMENT_PROGRAM.md` for remaining ICDE-quality scientific experiments and limitations.
