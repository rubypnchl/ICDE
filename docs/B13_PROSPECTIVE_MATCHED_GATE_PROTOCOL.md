# B13 — Prospective matched-input evidence-gate study (design-only package)

**Status (11 November 2026): protocol preparation only. No candidate run, no independent adjudicated labels, no new gate-effect estimates.** Do not describe this package as an experiment result, a pre-registration accepted by a third party, or a modification of the manuscript.

## Research question

For the **same previously frozen typed constraint candidate and source/context snapshot**, does adding documentary evidence and source-specific contextual applicability to safe compilation reduce admission of *independently adjudicated unsupported* rules while retaining eligible supported rules?

The primary unit is the typed **candidate × source/context snapshot**. A numeric agreement on a data sample is not sufficient proof of a semantically supported constraint. A candidate can be executable yet not safe to admit. Reviewers evaluate source-specific claims, not model popularity or observed fit.

## Prior development / novelty guardrail

B5/B5.1: two manually selected Luna proposals; B5.1 policy and healthcare parameter registry were constructed post-hoc. B6/B7/B8/B10: previously inspected or retrospectively reclassified proposals; B6.3 case review exists and should not be duplicated. B9: same-rule runtime and parity; B12: manufacturing/cyber source lineage, not natural-error truth. **None of these previously seen materials is a new untouched confirmatory cohort.** Prior reports should be used to debug implementation, not score B13 confirmatory admission quality.

The UCI AI4I description asserts random-failure (RNF) count of five; the retained B12 source contains 19 RNF flags, 18 forward-implication mismatches and nine reverse exploratory cases. This is a *documentation-versus-data conflict* to reconcile, not 18 independently proven defects. The nine reverse cases are not B6-MAN-001 violations.

## Freeze order: mandatory

1. Finalise study design, all gate policies and parameter registry and commit them **before seeing new candidate reference outcomes**. Write down exclusions, budgets and eligibility criteria.
2. Identify new source groups and source versions. New NHANES cycle, unseen SEC entities/filings, disjoint cybersecurity source captures with verified feature provenance, and an independent manufacturing dataset would provide stronger tests. Merely repartitioning AI4I 2020 does **not** become external manufacturing generalisation. Confirm licensing and source terms.
3. Derive candidate opportunities without exposing reviewer truth. Freeze candidate IDs, source hashes, typed proposals, context snapshots and the shared parameter registry. The provided manifest stores local paths and hashes; never publish paths pointing to private material. The input locker records **hashes only**, not rows or document text.
4. Run *the same* candidate list through all three frozen admission procedures. A: safe compiler only. B: compiler + metadata evidence. C: compiler + metadata + documentary/context applicability. Keep compilation code, input rules, parameters, candidate order, missing-data handling and evaluation budget identical. Any design intervention differing between arms must be recorded as a confound, not gate effect.
5. Supply reviewer 1 and reviewer 2 with blinded identical source-qualified candidate packets, absent arm decisions or model endorsements. Ask separately for `supports_as_written`, `supports_with_conditions`, `not_supported` or `needs_more_evidence` with evidence URL, locator and rationale. Conditional support requires an explicit machine-checkable scope before admitted as eligible. Independently lock reviewer votes; adjudicator resolves disagreement, with unknowns remaining unknown.
6. Compare arm decisions only for **eligible adjudicated** cases. Preserve missing/ambiguous denominators separately and abstentions explicitly. A post-hoc source search or a reviewer agreement score cannot be called prospective gold.

## Candidate inclusion / denominators

The target is eight new typed candidates per domain (32 total), **an engineering target, not a power calculation**. If the target cannot be met before the deadline, disclose as an incomplete study rather than padding the sample with old hypotheses. Candidates sourced from a single issuer, measurement cycle or network capture are not independent clusters even if they create many row-level decisions.

Admission: a rule is admitted only if the arm's documented checks all pass. Rejection, abstention and not-applicable are different statuses. The primary endpoint is `unsupported rules admitted / all adjudicated unsupported rules` per arm, defined **only if** the denominator is nonzero. Secondary endpoints: eligible supported rules admitted / all adjudicated supported rules, candidate coverage, abstention, and conditional admitted precision. Unknown and unreviewed candidates do not count as true positives or true negatives. Use paired candidate comparisons and source-group-aware uncertainty; if too few independent source groups exist, report descriptive counts rather than unsupported inferential claims. A source with 100,000 rows is not 100,000 independent rules.

Document the exact differences A→B and B→C. Any source-specific property that was created with knowledge of candidate labels should be disclosed as a retrospective adjustment, not a blinded independent effect.

## The offline package (no actual gate execution)

- `data/evaluation/b13_plan_v1.json`: frozen design intent, not results.
- `data/evaluation/b13_candidate_manifest_template.csv`: blank typed-candidate and source snapshot registry.
- `data/evaluation/b13_reference_review_template.csv`: blank independent review form; do **not** complete on behalf of any reviewer.
- `src/b13_protocol_validation.py`: fail-closed manifest, hash and design checks.
- `scripts/run_b13_protocol_check.py`: `--preflight` read-only; `--lock` only when new candidate inputs exist and hashes match.
- `tests/test_b13_protocol_validation.py`: offline tests.

This package **does not yet contain** new sources, source documents, typed proposals, context snapshots, gate implementations, reviewers, reviewer decisions, adjudicator outcomes, baseline comparisons or statistical results. It must not be cited as having those things.

## Local PowerShell procedure

From the `ICDE` repository root after extracting this archive with directory preservation:

```powershell
$py = 'C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe'
& $py -m unittest discover -s tests -p 'test_b13_protocol_validation.py' -v
& $py .\scripts\run_b13_protocol_check.py --preflight
```

The expected starting message is `B13 PREFLIGHT PASS: design valid; candidate manifest has 0 rows; NOT RUN`. Do **not** use `--lock` on an empty template: it intentionally fails. When genuinely new, predeclared source/proposal/context snapshots are available, copy the template to `data/evaluation/b13_candidate_manifest.csv`, fill it with verified paths + SHA-256 values, then run:

```powershell
& $py .\scripts\run_b13_protocol_check.py --lock
```

A successful lock produces `data/evaluation/b13_frozen_input_lock_v1.json` without raw rows, personal review comments or source paths. The script refuses to overwrite and has **no network calls**. The lock alone does **not** execute gates or establish ground truth.

Review locally before any commit:

```powershell
git status --short
git add docs/B13_PROSPECTIVE_MATCHED_GATE_PROTOCOL.md data/evaluation/b13_plan_v1.json data/evaluation/b13_candidate_manifest_template.csv data/evaluation/b13_reference_review_template.csv src/b13_protocol_validation.py scripts/run_b13_protocol_check.py tests/test_b13_protocol_validation.py
git diff --cached --check
git diff --cached --name-only
```

Commit only these named **design files** after checking. Do not `git add .` or push private review forms, raw data or absolute local-path manifest entries. No automatic Git operation is performed by this package.

## Hand-off criterion, without manuscript editing

Before telling a manuscript coauthor B13 has measured a prospective effect, require (1) registered source/candidate/policy snapshots, (2) matched three-arm decision files, (3) completed genuinely independent reviews and adjudication, (4) no leakage, (5) valid denominators and uncertainty. Until then, B13 is **prepared, not run**, and the best defensible ICDE claims remain those supported by earlier audits and source-lineage experiments.
