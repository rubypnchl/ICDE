# B13.9 — Exploratory consistency of already-documented NHANES unit conversions

**Date:** 11 November 2026. **Status:** engineering package; no local real-source results included. This is a *retrospective*, non-blinded feasibility check of three formulae taken from CDC documentation; it is **not rule discovery, a source-qualified gold standard, or an evidence-gate efficacy study**.

## Scientific rationale

The B13.8 schema inspection established (operator-reported) 3,191 TRIGLY_I rows, 8,021 TCHOL_I rows and 3,191 shared SEQNs. Both files are from **one** NHANES 2015–16 cycle and **not two independent domains/cohorts**. The UCI Steel Plates 1,941/1,941 one-positive-fault-label observation is a descriptive property only; B13.9 deliberately does not refit or test any manufacturing constraint.

The CDC NHANES descriptions explicitly document three numeric unit-conversion factors:

| File | mg/dL field | mmol/L field | Published factor | Official evidence |
|---|---|---|---|---|
| TRIGLY_I | LBXTR | LBDTRSI | 0.01129 | [CDC TRIGLY_I, Data Processing and Editing](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/TRIGLY_I.htm) |
| TRIGLY_I | LBDLDL | LBDLDLSI | 0.02586 | [CDC TRIGLY_I, Data Processing and Editing](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/TRIGLY_I.htm) |
| TCHOL_I | LBXTC | LBDTCSI | 0.02586 | [CDC TCHOL_I, Data Processing and Editing](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/TCHOL_I.htm) |

For each pair, the script reports only the number of complete pairs, missingness categories and **absolute residuals** `|recorded_mmol_L - published_factor * recorded_mg_dL|`: median, interpolated p95, maximum and counts within **fixed exploratory** residual bins of 0.0005, 0.005, 0.01, 0.05 and 0.1 mmol/L. The bins are *not* approved equality tolerances. No rounding specification is inferred, fitted or asserted; discrepancies are not labelled defects. If there are no paired observations, quantiles are `null`, not zero.

The TRIGLY_I codebook describes morning examination eligibility, age and fasting restrictions for analytical interpretation, and a separate LDL Friedewald calculation that would require additional HDL and context variables. **B13.9 does not assess the LDL calculation, age/fasting status, clinical accuracy, subsample weights or survey inference.** It merely compares stored unit pairs using the documented multipliers. No clinical values or individual SEQN identifiers leave process memory.

## Exact ancestry and execution

Requires previously extracted B13.7/B13.8 packages and a completed `B13_8_source_schema_audit_v1.json` in the external cache. The B13.9 script validates pinned B13.7 source receipts and parent B13.8 hashes/plan, reads exact original XPT objects from the external cache, checks row-count consistency and computes counts. It performs no downloads, LLM calls, rule discovery, admissions, raw row exports or manuscript edits. Its one output is exclusive-write to the cache (not Git):

`H:\nrr136 data\ICDE-B13-Source-Cache\B13_9_documented_pair_consistency_v1.json`

From `H:\nrr136 data\ICDE` in VS Code PowerShell:

```powershell
$py = 'C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe'
$cache = 'H:\nrr136 data\ICDE-B13-Source-Cache'
& $py -m unittest discover -s tests -p 'test_b13_9_documented_pair_consistency.py' -v
& $py .\scripts\run_b13_9_documented_pairs.py --preflight
& $py .\scripts\run_b13_9_documented_pairs.py --inspect --cache-dir $cache
```

The last command writes a new aggregate report; subsequent `--inspect` is deliberately rejected to prevent overwrites. If requirements are absent, use the same interpreter to install `pyreadstat` and `pandas` explicitly. A source hash mismatch, an altered B13.8 report or missing required columns must stop the run; do not bypass checks.

## Interpretation and next decision

This is an exploratory *documented relationship consistency* check using datasets already seen during source screening; its paired counts must **not** be interpreted as confirmed natural errors, rule precision, or independent observations of a learned constraint. The stronger next milestone is a source-qualified review of *context requirements and exception handling*, with blinded adjudication on new candidates before three-arm matched gate comparison. Only externally established source support and correct applicability can turn a structural proposal into an eligible rule.

**Publication caution:** the three factors are published derivations, not automatically discovered constraints; do not count these three checks as independent blind rule-discovery successes or multiple independent cohorts.

Only the five B13.9 research files may eventually be staged selectively on `b13-prospective-gate`; never commit the external cache, receipts or participant-level values. The package never touches `main` or Overleaf.
