# MetaVerify — submission-day evaluation summary (11 November 2026)

This summary transcribes completed source-derived **aggregate** outputs. Before publication, regenerate the numbers using `scripts/summarize_submission_metrics.py` and retain the actual saved JSON with the submission materials. This summary is **not** an independent reference benchmark, published SOTA reproduction, or semantic gate accuracy result.

## Metrics from existing verified experiments

| Study | Metric | Observed result | Denominator and scope |
| --- | --- | ---: | --- |
| NHANES B13.11 | Evaluated coverage | 12,678 / 14,403 = 88.02% | Pair-record checks from three known conversion relationships, one survey cycle |
| NHANES B13.11 | Abstention | 1,725 / 14,403 = 11.98% | Pair-record checks, not independent people |
| NHANES B13.11 | Exact numeric expression mismatch | 12,612 / 12,678 = 99.48% | **Not** a natural error rate; strict equality ignores documented rounding specification |
| NHANES B13.12 | Within exploratory tolerance 0.0005 mmol/L | 6,201 / 12,678 = 48.91% | Tolerance not independently verified |
| NHANES B13.12 | Within exploratory tolerance 0.005 mmol/L | 12,678 / 12,678 = 100% | Tolerance not independently verified |
| NHANES controlled perturbation | +0.01 mmol/L flagged at 0.005 tolerance | 12,678 / 12,678 = 100% | Artificially shifted recorded SI values, same previously inspected rows; NOT natural error recall |
| NHANES matched held-out baseline | Documented factor / least-squares new flags | 6,412 / 6,412 each | Same B4/B3 engine; trained numeric coefficients only, **not** published SOTA |
| NHANES matched held-out baseline | Median-ratio new flags | 6,404 / 6,412; 8 previously violated | Same held-out test records; distinct newly-flagged denominator when reporting conditional rates |
| SEC controlled A/B/C | Arm A (admit / abstain / block) | 17 / 0 / 0 | 17 designed configurations of **one** candidate |
| SEC controlled A/B/C | Arm B (admit / abstain / block) | 15 / 1 / 1 | Same configurations |
| SEC controlled A/B/C | Arm C (admit / abstain / block) | 1 / 7 / 9 | Includes seven simulated approval states; no independent review |

## New optional wall-clock profile

`python scripts/benchmark_nhanes_verification.py --cache-dir <external-source-cache> --output <external-cache>/B4_B3_Runtime_v1.json`

This runner reloads the original XPT files, validates source receipts, and times repetitions of the same **B4 compile + deterministic A/B/C diagnostic + B3 row-verification** using in-memory source frames. It checks that every repeat reproduces the saved B13.11 outcome counts. Report median time, observed nearest-rank p95, checks/second, runtime repetitions, Python environment and excluded costs. **The timings omit I/O, ingestion, documentary review and model calls, so they are not full system latency.** No runtime values should be inserted until the user runs the command on the verified source data.

## Primary scientific gaps, explicitly unresolved

- No independently adjudicated valid, invalid or context-dependent **candidate-constraint reference set**. Admission precision, invalid-admission rate, valid retention and binary F1 therefore remain **undefined**, rather than zero.
- No execution of Guardrail/Auto-Test or another comparable published baseline on a common benchmark. A methodological capability comparison is suitable for related work, not a quantitative performance table.
- Previous source exposure, one NHANES cycle, a single structurally screened SEC candidate and constructed policy controls prevent claims of broad generalisation or causal admission benefit.
- No statistical significance testing should treat repeated observations of the same survey records or SEC candidate as independent samples.

## Suggested concise manuscript interpretation

> Across three previously documented NHANES conversion relationships, MetaVerify evaluated 12,678 of 14,403 pair-record checks (88.0% coverage) and abstained on 1,725 (12.0%). Strict expression equality was sensitive to numeric representation: only 66 evaluated checks were exactly equal, while all 12,678 fell within an exploratory 0.005 mmol/L absolute tolerance. Under a controlled +0.01 mmol/L perturbation, all 12,678 shifted checks violated the corresponding tolerant predicate; this is controlled expression sensitivity, not recall for natural defects. In a separate participant-partitioned numerical comparison, documented and least-squares coefficients newly flagged 6,412 of 6,412 held-out checks, while a training-median coefficient newly flagged 6,404, with eight originally violating the predicate. A 17-configuration SEC screening stress test demonstrated A/B/C decision transitions on a single pre-inspected candidate, including synthetic evidence approvals. These experiments establish reproducible execution and screening behaviour, but not independently verified semantic correctness, error-detection accuracy or published-baseline superiority.

For any final manuscript wording, verify current Overleaf content to avoid duplicating reported results; this paragraph is an optional drafting aid, **not** an automatic manuscript modification.
