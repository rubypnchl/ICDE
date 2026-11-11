# B13.6 — Source-specific evidence and context readiness (preflight only)

**11 November 2026.** This stage is a read-only preparation of *questions that must be resolved* for the five B13.2 source entries. It neither verifies eligibility nor freezes a real source policy. The B13.5 context guard exists for the **toy** `b134-toy` dataset only; never reuse `site` or automatically translate the questions below into an Arm C context policy.

## Why this stage matters

A source URL is not independent proof of a constraint. A source may have documented derived variables but ambiguous rounding, a release may use a different feature extractor, or a filing may omit necessary consolidation context. B13 requires evidence for the specific **candidate × source/version × applicability context**, independent of numeric agreement on observed records. The five entries below are a *convenience shortlist*. They are not five statistically independent cohorts: the two NHANES files share one 2015–16 survey cycle, and cybersecurity generator families may overlap.

## Source-specific readiness questions

- **Finance, SEC EDGAR:** fix a previously unexamined issuer and filing accession; verify taxonomy tags, unit, entity, period, instant/duration, original filing dimensions and noncontrolling-interest treatment. The SEC's Companyfacts APIs aggregate noncustom, entity-wide facts. Arithmetic equality in the aggregated API is **not** itself proof of compatible filing scopes. See https://www.sec.gov/search-filings/edgar-application-programming-interfaces .
- **Healthcare, TRIGLY_I:** verify the XPT release, SEQN, analyte variables, fasting/sample eligibility, derived-variable rules, units and precision; CDC documentation describes triglyceride conversions and LDL calculations with restrictions (e.g., fasting and triglycerides <=400 mg/dL). These descriptions were already seen during screening, and cannot be portrayed as unseen discovery. See https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/TRIGLY_I.htm .
- **Healthcare, TCHOL_I:** verify the XPT source, measured variables, units and participant eligibility. If joining to TRIGLY_I or other cycle files, verify SEQN alignment, eligible subpopulations, and survey-cycle dependence. This is **not** an independent second cycle. See https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/TCHOL_I.htm .
- **Cybersecurity, CSE-CIC-IDS2018:** select an exact capture-day object and check the extractor code/version, header mapping, direction definitions, packet-count applicability and data-object hash. The official documentation discusses CICFlowMeter-V3; source CSV naming and version must be verified locally. Do not download the entire S3 repository during screening. See https://www.unb.ca/cic/datasets/ids-2018.html .
- **Manufacturing, Steel Plates Faults:** verify the original `Faults.NNA` or official packaged object, schema and hash, label semantics and documented feature meanings. UCI lists 1,941 instances, 27 features, seven fault classes and CC BY 4.0 licensing. Neither a field named `X_Minimum` nor a class label automatically proves a safe rule. See https://archive.ics.uci.edu/dataset/198/steel%2Bplates%2Bfaults .

## Critical distinction: three different types of context

1. **Per-field equality context:** keys the B3 verifier can actually compare via `context_keys` and `_field_context` for compatible fields (for example reporting period, entity, currency, capture group). These require a frozen source-specific implementation and evidence that the attributes are present in actual records.
2. **Rule applicability conditions:** explicit typed `when` predicates for eligible subpopulations or nonempty packet sets. A source-review note about fasting or nonempty packet counts is **not** automatically executable as B4/B3 DSL logic.
3. **Documentary provenance and sampling controls:** official evidence locators, file hashes, version, licensing, cluster independence. These generally do **not** belong as B3 `context_keys`. A URL or a supported flag is not semantic entailment.

The `potential_b4_context_key` field contains *questions, not obligations*. Real required contexts, mappings, missing-data policy, evidence-gate extraction and parameter registry must be separately specified and frozen before collecting prospective outcomes. Any post-hoc scope change is a protocol deviation.

## Contents / handling

- `data/evaluation/b13_6_source_context_questions_v1.json` — 5 source entries and open source-specific questions. Zero eligible cohorts or real rules.
- `data/evaluation/b13_6_manual_source_review_TEMPLATE.csv` — **blank** worksheet for later source-qualified verification. Never commit filled reviews with potentially identifying details, private paths, or unpublished source notes to a public repository.
- `src/b13_6_source_context_readiness.py` — checks linkage to the committed B13.2 shortlist, B13.5 ancestry and strict unverified states. Does not fetch URLs or evaluate their contents.
- `scripts/run_b13_6_source_context_preflight.py` — prints counts and canonical parent hashes; no file output, downloads, calls or Git writes.
- `tests/test_b13_6_source_context_readiness.py` — mutation and privacy/template tests; no real data.

## Run from existing branch (Windows PowerShell)

```powershell
cd 'H:\nrr136 data\ICDE'
$py = 'C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe'
& $py -m unittest discover -s tests -p 'test_b13_6_source_context_readiness.py' -v
& $py .\scripts\run_b13_6_source_context_preflight.py --preflight
```

Expected: 19 tests `OK`; `B13.6 PREFLIGHT PASS`; five entries with all questions unresolved, no eligibility/gate/gold counts. The program does not create or overwrite a real candidate manifest. Do not run B13 `--lock` yet. Do not edit or merge the manuscript.

## Next meaningful work (requires independent manual evidence)

Select exact source objects and source groups, independently document release/version/hash and provenance, and resolve each source's eligible rule families, context-applicability conditions and cluster independence. Log exclusion of previously used groups and prior documentation exposure. Obtain an independent source-qualified review of documentary entailment; do not fill the review worksheet using model guesses. After review, implement/freeze a **new versioned real-source policy** with the existing B13.5 fail-closed rule declaration concept, a common B4 compiler and independent reference adjudication. Only then freeze genuinely new proposals and execute the three matched arms. Report any departure from the original 8-per-domain target, and keep retrospective development sources out of confirmatory outcomes.

**Scientific interpretation:** this B13.6 package adds a reproducible *eligibility-question register*, not five validated rule sources or a measured benefit for evidence gating.
