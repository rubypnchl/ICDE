# MetaVerify B13.10 — Documentary evidence vs. executable applicability (retrospective triage)

**11 November 2026. Status: source-documentation synthesis of already examined materials, not independent source adjudication, no new rules or gate outcomes.** Keep on `b13-prospective-gate`, do not merge shared `main` or edit Overleaf. The evidence register is curated **after** B13.8/B13.9 outputs and after consultation of published documentation. It is not prospective rule discovery or a truth dataset.

## Source-level evidence table (not gold)

| Item | Official source locator | What the document establishes | What remains unresolved |
| --- | --- | --- | --- |
| `TRIGLY_TR_UNIT` | [CDC TRIGLY_I](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/TRIGLY_I.htm), *Data Processing and Editing > LBDTRSI* | Published mg/dL to mmol/L multiplier `0.01129`. | Exact precision/rounding not separately specified as gold; individual sample eligibility must not be inferred from conversion agreement. |
| `TRIGLY_LDL_UNIT` | Same CDC TRIGLY_I page, *Data Processing and Editing > LBDLDLSI* | Published multiplier `0.02586` applied to **reported** LDL-cholesterol. | Conversion is not a test of the underlying LDL Friedewald derivation or of sample/fasting restrictions. |
| `TCHOL_TC_UNIT` | [CDC TCHOL_I](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/TCHOL_I.htm), *Data Processing and Editing > LBDTCSI* | Published multiplier `0.02586` for total cholesterol. | Reported SI precision is not an independently adjudicated rounding rule. |
| `STEEL_FAULT_ONEHOT` | [UCI dataset 198](https://archive.ics.uci.edu/dataset/198/steel%2Bplates%2Bfaults), *Dataset Information > Type of dependent variables* | UCI lists seven classes; local B13.8 source audit found exactly one positive target among the seven for all 1,941 observed rows. | The page does **not expressly establish** a universal formal exactly-one-label axiom for arbitrary future records. Additional source semantics and exceptions require independent verification. |

### Important distinction: two different notions of applicability

CDC `TRIGLY_I` reports an **eligible sample** of morning-examined participants aged at least 12; it discusses ≥8.5 and <24 fasting hours for certain distributions. The page separately states that the *Friedewald LDL calculation* is valid for triglycerides ≤400 mg/dL, and that the formula uses total cholesterol, HDL, and triglycerides. The documented **unit conversion of an already-reported paired value** is not equivalent to a new claim that the Friedewald formula holds everywhere or that the survey's statistical weights and fasting conditions were rechecked in the XPT. See [CDC TRIGLY_I, Eligible Sample, Data Processing and Editing, Analytic Notes](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/TRIGLY_I.htm).

CDC `TCHOL_I` eligibility is examined participants aged six or older. The XPT's laboratory codebook does not supply all external survey eligibility covariates; CDC points readers to Demographics and Fasting Questionnaire files for further variables. See [CDC TCHOL_I, Eligible Sample and Analytic Notes](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/TCHOL_I.htm). The two laboratory releases are the **same survey cycle**, not independent cohorts.

### Critical B3/B4 implementation boundary

As implemented in `src/generic_verifier.py`, B3 `context_keys` demand matching **per-field context values** (via the record's `_field_context`); merely declaring a context key **does not check** whether a participant's age, fasting hours, collection session, or triglyceride threshold meets a numeric eligibility criterion. `when` can evaluate specific predicates only when the required joined/source-backed columns are present and the predicate is compiled with registered parameters. If they are absent, the evaluator may abstain. The B13.5 structural `context_keys` correction should never be described as verification of clinical eligibility. Additionally, a sum-to-one rule alone does not imply each input target label is binary; binary-domain checks are separate.

Before a real source-qualified B4/B3 rule, evidence must distinguish: (1) scope-alignment keys, (2) row eligibility/applicability predicates, (3) data-availability and missingness handling, (4) documented expression and parameter provenance, (5) externally supported rounding/tolerance (if any), and (6) independent reference labels. **None of these four known relationships qualifies as untouched confirmatory discovery in B13.10.**

## Repeatable read-only lineage assessment

1. B13.7 has three local receipts, all in a source cache outside the repository. B13.8 produced `B13_8_source_schema_audit_v1.json`; B13.9 produced `B13_9_documented_pair_consistency_v1.json`, also outside the repo.
2. The B13.10 script checks frozen B13.7–B13.9 plan/registry fingerprints, links the B13.9 report to the B13.8 report **by byte SHA-256**, validates aggregate row and pair counts, verifies documentary URL/factors against frozen plans, and verifies the manufacturing histogram. It does not read XPT rows or manufacturing raw ZIP bytes. It does not independently access/verify the current CDC/UCI websites.
3. A successful assessment writes one **aggregate-only** `B13_10_documentary_applicability_triage_v1.json` in the external cache using exclusive create. It cannot overwrite an existing result. It records **zero** independent reviewers, **zero** confirmed gold constraints, **zero** real candidate gate runs, and **zero** confirmed confirmatory candidates. No user identifiers or individual values are written.
4. Any mismatch is a STOP, not a prompt to change the underlying source receipts or relax study controls.

### PowerShell usage

From `H:\nrr136 data\ICDE`, after extracting the ZIP:

```powershell
& $py -m unittest discover -s tests -p "test_b13_10_documentary_triage.py" -v
& $py .\scripts\run_b13_10_documentary_triage.py --preflight
$cache = "H:\nrr136 data\ICDE-B13-Source-Cache"
& $py .\scripts\run_b13_10_documentary_triage.py --assess --cache-dir $cache
```

Expected from offline fixture suite: **26 tests pass**; preflight prints four registered relationships. Real assessment must be verified using your actual parent JSONs; it is not assumed passed on your machine in advance.

## Independent review workflow — *not yet performed*

`data/evaluation/b13_10_manual_independent_review_TEMPLATE.csv` contains blank forms for two independent reviewers and a distinct adjudicator, grouped by relationship. Human reviewers need to check **exact official passages, source release and hashes, applicability, binary/label semantics, parameter precision, opposing evidence and source-level prior exposure**. The form is a template, **not** a completed review, and is not consumed by the executable. Completed review material should be independently collected and retained securely; do not push identifiable reviewer notes or raw participant data to the public repository.

A later, genuinely independent prospective experiment needs new/disjoint source objects and frozen candidate/analysis plans before truth labels and arm results. No prospectively matched three-arm effect can be estimated from these already-inspected source relationships.
