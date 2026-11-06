# B6.2 — Independent same-rule checker, controlled injections, and review worksheet

**Classification:** DEVELOPMENT / ENGINEERING SANITY CHECK / ZERO GOLD REFERENCES. Not a new data-quality discovery result, not independent defect detection accuracy, and not a comparison with published rule-*discovery* algorithms.

**Locked baseline:** `1d0bed572f1e37e0f306bb81abe66bb538b9e645` (B6.1); catalogue/protocol are unmodified. B6.2 is an **additive retrospective development experiment**, not a claim that the B6 protocol was registered before the already-observed discrepancies. The additional design is saved in `data/evaluation/b6_2_design_v1.json` and should be committed before changing its choices.

## What is compared

- **Existing B3 generic verifier + B6.1's invalid-field guard:** previously evaluated on 10,000 AI4I and 50,000 CIC sampled rows.
- **Independent hand-coded simple rule checker:** evaluates *the identical two candidate rules* over *the identical files* without calling B3 code, and asserts exact agreement with the B6.1 aggregate report.
- **Controlled copies:** deterministic reservoir selection of 64 originally satisfying records per domain. For each original, create one in-memory violating copy and one unmodified control. Also check condition-false and missing-field copies. Never modify source CSVs.

The injected examples are *constructed to violate the same given rule*. Consequently, even 100% injected recall here is a tautological execution sanity check, **not evidence of natural defect detection precision, semantic rule precision, or MetaVerify superiority**. A simple deterministic checker may correctly achieve identical counts with less engineering. Measuring discovery quality requires independent gold constraints and matched candidate-generation budgets.

## Known AI4I reference ambiguity

The official UCI page states that `Machine failure = 1` if any of TWF/HDF/PWF/OSF/RNF occurs. The page also says **random failures occurred in five points**. The retained 10,000-row CSV yielded **18 one-way forward mismatches, all RNF-only**, and **9 converse mismatches**. The frozen B6-MAN-001 checks ONLY forward implication; do not count the 9 converse cases as violations of the frozen constraint. These are **candidate discrepancies**, not confirmed label errors. A reviewer must compare version, label-generation description, and actual data, noting any inconsistency or exception.

Official source: https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset

## Run from repository root (VS Code / PowerShell)

```powershell
$py = "C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe"
& $py -m unittest discover -s tests -p "test_b6_2_study.py" -v
& $py .\scripts\run_b6_2_study.py --check-inputs
& $py .\scripts\run_b6_2_study.py
```

The report is saved as `data/evaluation/b6_2_development_study.json` and the **blank-review worksheet** as `data/evaluation/b6_2_ai4i_independent_review.csv`. Only the UDI, binary indicators, case label, source hash and empty review slots are retained (not the raw source CSVs). Inspect for confidentiality before pushing. The original B6.1 results remain unchanged.

## Independent human source adjudication procedure

Two reviewers separately receive the **same frozen worksheet and official UCI documentation** before seeing each other's labels. Each must record a judgment about the *rule's scope* and each of the 27 cases with specific justification: `supported_discrepancy`, `explainable_exception`, `ambiguous`, or `source_version_mismatch`. Reviewer 1 and reviewer 2 use their own individual copies of the worksheet. A third adjudicator resolves disagreements; do not overwrite raw individual judgments. We cannot complete those reviews automatically; no values are pre-filled.

Questions to resolve include whether RNF is truly included in the released `Machine failure` target construction, why the source reports five RNF events, whether there are version/encoding differences and whether the nine converse cases have unreported modes. Do not silently modify B6-MAN-001 in place to fit observed cases: a revision must be explicitly versioned and classified exploratory.

## Metrics and denominator limits

- Raw agreement and coverage follow the exact B6.1 denominators; B6.2 checks they have not changed.
- Injection matrices are reported **only on constructed positives and by-rule-clean controls**, with denominators shown. Separate condition-false and missing-field probes are not labelled defect negatives.
- Each run records its source file fingerprints (checked against B6.1), design/report hashes, complete aggregate counts, selection seeds and wall-clock timings. Timing is single-pass and is **not** a statistically valid cross-implementation performance comparison.
- The 50,000 CIC flows are a prior deterministic reservoir of only two Friday CSV files. AI4I is synthetic. Neither source is untouched evaluation data.
- For future ICDE claims, acquire and adjudicate independent reference constraints, run matched discovery baselines, and evaluate on genuinely unseen group-held-out sources; record costs and uncertainty.

## Research decision after B6.2

If the baseline equals MetaVerify, that is **expected and important**: the same encoded rule should have the same row-level decision. The value to test is **rule generation, evidence resolution, contextual applicability, calibrated abstention and correct rule selection**—not simple execution of a known inequality. This milestone should be treated as an audit/infrastructure step, not an additional technical novelty claim.
