# B13.12 — Retrospective fixed-grid B4/B3 numerical-sensitivity audit

**Research scope:** Read-only sensitivity, not a prospective gate-effect experiment, independent evidence review, natural-error benchmark, or gold-standard constraint study. The three NHANES 2015–16 conversion relationships were selected from previously consulted CDC codebooks and belong to **one source-cycle cluster**.

## Why this stage is necessary

B13.11 executed typed, provenance-registered conversion expressions under strict (`abs_tolerance=0`) equality and returned high mismatch counts. B13.9 independently measured small numerical residuals against documented conversion factors. Since no independent rounding or tolerance specification was established, exact-expression mismatches must **never** be labelled verified data errors.

B13.12 exercises B4's typed `abs_tolerance` parameter and B3's row interpreter on the **same** record pairs using the complete, previously declared B13.9 exploratory grid `0.0005`, `0.005`, `0.01`, `0.05`, `0.1` mmol/L. The grid is reused **after seeing the source data**, and is not a new pre-registered confirmatory tolerance test; it was initially declared as descriptive residual bins in B13.9. Each threshold is registered with `empirical_same_dataset` provenance, **not** `documented_reference` provenance. The documented conversion multiplier remains separately provenance-registered.

Each threshold compiles to a distinct B3 executable rule, but this only tests interpreter behaviour; it does not modify or infer the B13.11 Arm A/B/C outcomes. The B3 cumulative satisfied counts **must exactly agree** with the corresponding independent B13.9 residual-bin counts. Otherwise B13.12 aborts without writing outputs. Source receipts and B13.8–B13.11 ancestry are checked again.

## Inputs

- Exact locally receipt-verified `TRIGLY_I.XPT` and `TCHOL_I.XPT` in the B13 external source cache.
- B13.8, B13.9 and B13.10 aggregate reports; B13.11 previously generated real-data diagnostic report.
- Unchanged B13.7 through B13.11 scripts and versioned data/evaluation specifications.
- No new source objects, private SEQNs, independent reference labels or model calls.

## Installation and commands (Windows PowerShell)

Extract the B13.12 ZIP into `H:\nrr136 data\ICDE`, then from that root:

```powershell
& $py -m unittest discover -s tests -p 'test_b13_12_fixed_grid_sensitivity.py' -v
& $py .\scripts\run_b13_12_fixed_grid_sensitivity.py --preflight
$cache = 'H:\nrr136 data\ICDE-B13-Source-Cache'
& $py .\scripts\run_b13_12_fixed_grid_sensitivity.py --run --cache-dir $cache
```

The local package tests use **interface stand-ins** for earlier modules; the user's test/preflight is required for validation with their actual B4/B3 modules. **Do not run on a different source cohort or treat a successful unit test as experimental evidence.**

Outputs, using exclusive file creation, are only placed in the external cache:

- `B13_12_fixed_grid_sensitivity_v1.json`
- `B13_12_sensitivity_table_v1.tex`
- `B13_12_handover_v1.md`

Any existing output causes a refusal to overwrite. The script reads original source files but emits **only aggregate counts**, not participant IDs, original raw rows or participant-level residuals. No Overleaf, Git operations or manuscript edits are performed automatically.

## Research interpretation

If numerical sensitivity decreases mismatches, it demonstrates a known property of numerical comparison under varying tolerance, **not** correct tolerance selection, a validated source rule, false-positive reduction by the evidence gate, or detection of real natural errors. The three candidates and one survey-cycle cluster are insufficient to estimate a causal effect of the three admission arms. Arm C remains unreviewed; no real source policy is independently frozen and no gold labels exist. A fresh cohort with independently justified precision/applicability, source-qualified documentary evidence and blinded adjudication remains necessary before effectiveness claims.
