# MetaVerify: submission-day descriptive metrics and next-step admission reference protocol

**Scope:** Retrospective analysis of existing, pinned NHANES and SEC aggregate reports. This is **not** an independently labelled constraint-discovery benchmark, published Guardrail/Auto-Test baseline, or semantic-gate effectiveness study.

## One-command read-only reproducible summary

Run from `ICDE/` using your already-installed Python (e.g. `& $py` in PowerShell). Requires the locally generated and retained B13.11, B13.12, perturbation, numerical-baseline and SEC-control JSON files. No new source downloads, row-level exports, ZIPs or additional dependencies.

```powershell
& $py .\scripts\summarize_submission_metrics.py `
  --source-cache "H:\nrr136 data\ICDE-B13-Source-Cache" `
  --sec-controls "H:\nrr136 data\ICDE-B13-Independent-Pilot\CMG_Deadline_Control_Study\controls.json" `
  --output "H:\nrr136 data\ICDE-B13-Source-Cache\Submission_Metrics_Overview_v1.json"
```

The result is an aggregate JSON report in the **external cache**. The script refuses to overwrite it; omit `--output` for a read-only console print on subsequent runs.

Run focused tests:

```powershell
& $py -m unittest discover -s tests -p "test_submission_metrics.py" -v
```

## Exact metric definitions

* **Coverage:** `(satisfied + violated) / (satisfied + violated + abstained + not_applicable)` for each pre-curated NHANES pair-record check. A participant can appear in multiple pairs; this is *not* the number of independent participants.
* **Abstention:** `abstained / all pair-record checks`.
* **Strict numeric mismatch rate:** `strict violated / evaluated`. This is an arithmetic expression inequality, **not** a natural data-error false-positive rate.
* **Exploratory within-tolerance fraction:** `satisfied at given tolerance / evaluated`, with *same data used for exploratory tolerance bins*, not independently justified rounding semantics.
* **Controlled-shift flagged rate:** `shifted violated / evaluated shifted pair-record checks`; **new-flags conditional rate:** `satisfied → violated / initially satisfied`. Modifications are *synthetic numeric perturbations of the same tested expression*; not a true defect recall estimate.
* **Matched numeric baseline results:** same B4/B3 executable constraint and held-out participant partition; only the coefficient changes between CDC-documented, training median-ratio and train-only zero-intercept least-squares methods. This is **not** a published SOTA method reproduction. Report baseline-original violations separately from new flags.
* **SEC arm rates:** `admit`, `abstain`, `block` counts divided by 17 **repeated configurations of one candidate**, including seven with simulated approval. These are decisions under controlled input perturbation, not admission correctness or 17 independent samples.

No precision, recall, F1, admission-benefit odds ratios, p-values, confidence intervals, real-world false-positive reduction, or production runtime can be established from these aggregates. These are explicitly `null` in the JSON output.

## Independently labelled admission study — required future input

To estimate the central scientific benefit of evidence-grounded admission, first freeze a diverse set of **new candidate constraints** with independent sources and explicit context/applicability. Record the original proposal, source-document locator, metadata and test data before looking at arm decisions. Two reviewers, **not involved in candidate proposal or evidence-policy implementation**, independently label each candidate `valid`, `invalid`, or `context-dependent/uncertain`, recording source support and applicable contexts. A third independent adjudicator resolves disagreements; preserve raw votes, reason codes and unresolved cases. Obtain reviewer consent/permissions where applicable.

Run arms A, B and C on **exactly the same frozen candidates and policy**, then join decisions to adjudicated reference labels by candidate ID. Exclude uncertain labels from binary accuracy calculations but report them, along with abstentions and coverage, separately. Recommended metrics:

* **Valid admission precision** = valid reference candidates admitted / all admitted candidates with adjudicated valid/invalid reference.
* **Invalid admission rate** = invalid reference candidates admitted / all adjudicated invalid candidates; do not drop arm abstentions from the denominator.
* **Valid retention** = valid reference candidates admitted / all adjudicated valid candidates.
* **Decision coverage** = (admitted + blocked) / all candidates; **abstention** = abstained / all candidates.
* **False-admission count**, decisions by domain, and a paired per-candidate comparison of A/B/C are essential; only test inferential hypotheses if independence, sampling and a preregistered analysis justify it.

**Do not** relabel the existing NHANES codebook coefficients, the 17 simulated SEC variants, or automated decisions as independent human gold. The present data contain *zero* independent adjudicated admission cases, so all corresponding correctness metrics are **not estimable**.

## Current descriptive findings already observed in source-run logs

* NHANES B13.11: 12,678 evaluated of 14,403 pair-record checks; 1,725 abstentions. Exactly 66 strict matches and 12,612 strict numeric mismatches.
* NHANES B13.12: 6,201 of 12,678 within the exploratory `0.0005` tolerance; 12,678 of 12,678 within `0.005`.
* Matched held-out numeric-baseline test under `+0.01 mmol/L`, tolerance `0.005`: 6,412 modified checks flagged using each of the three methods; 6,412 newly flagged for documented factor and least-squares, 6,404 newly flagged for median ratio (eight already violated before modification).
* SEC controlled policy stress: A 17 admit; B 15 admit, 1 abstain, 1 block; C 1 admit, 7 abstain, 9 block. **Only one underlying source-derived candidate**.

Results should be regenerated from saved JSON on the user's machine before insertion into the paper. The assistant did not directly access the external university-drive source data or result files.
