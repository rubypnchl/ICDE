# B6 — Pre-registered reference-rule catalogue and evaluation protocol (seed v0.1)

**Baseline Git commit:** `b68e3be3c8ab832a6b550545121187970b0a7672`  
**Created:** 2026-11-06 UTC  
**Evaluation protocol:** `b6-frozen-protocol-v1`  
**Experiment status:** *methodology and source-supported candidate catalogue only.* **No** new independent held-out study, real-world defect labels, or cross-domain outcome is claimed here.

## Deliverables

- `data/evaluation/b6_reference_catalogue.json` — five entries with exact column names, limited B3-compatible rule ASTs, per-entry evidence URLs, status, applicability, caveats.
- `data/evaluation/b6_protocol_v1.json` — preregistered splits, leakage controls, baselines, metrics, reference review, cost reporting, and injection rules.
- `scripts/audit_b6_catalogue.py` — local structural validation and deterministic audit report generation; **no network/model calls**.
- `tests/test_reference_catalogue.py` — 15 offline regression tests; metadata fixture tests are *not* real-data experiments.
- `data/evaluation/b6_reviewer_template.csv` — blank independent source-review worksheet (do not fill decisions before actual review).

## Starting status — important

| ID | Domain | Source-backed component | Status | Final gold? |
|---|---|---|---|---|
| `B6-HLT-001` | Healthcare | CDC factor 0.05551 and paired glucose variables | Partially supported: exact numerical precision unverified | No |
| `B6-FIN-001` | Finance | XBRL US total liabilities + equity concept | Scope pending: align actual taxonomy concepts, entity, reporting period, accession, currency, consolidation | No |
| `B6-FIN-002` | Finance | Naive parent-equity balance sheet equality | Excluded: noncontrolling/redeemable equity can be omitted | No |
| `B6-MAN-001` | Manufacturing | AI4I machine failure whenever any failure-mode flag is true | Provisional source support; synthetic data | No |
| `B6-CYB-001` | Cybersecurity | CICFlowMeter forward packet min ≤ mean ≤ max, provided count > 0 | Provisional support from definitions and implementation | No |

**Two** entries are *provisionally source-supported*; **zero** have undergone an independent two-reviewer adjudication and therefore **zero** enter the final gold-rule precision denominator today. Proposed ≠ structurally valid ≠ source-supported ≠ independently adjudicated ≠ empirically consistent.

### Why the healthcare rounding case is not gold yet

CDC GLU_J documents the factor `0.05551` and says “rounded to 3 decimals”. Earlier exploration over all 2,891 complete GLU_J rows found that **three significant figures** reproduces all values, whereas three decimal places does not. This is **post-hoc model selection**, not independent external validation. The exact numerical rounding interpretation must be frozen and tested on an untouched, non-overlapping cycle (or otherwise independently established) before it can count as an independently supported full rule. Do not re-label the 2017–18 reproducibility result as held-out evaluation.

### Why the finance simple equality is unsafe

`StockholdersEquity` in the B5 source descriptions is attributable to the parent and may exclude noncontrolling interest. `Assets = Liabilities + StockholdersEquity` therefore is **not a universal consolidated companyfacts rule**. The alternate `Assets = LiabilitiesAndStockholdersEquity` uses a more complete XBRL concept, but is **pending** exact tag availability, compatible company filing contexts, and independent adjudication. In the currently retained summary metadata, finance columns are lowercase summaries, so B6 explicitly marks this concept `external_taxonomy_pending` rather than misreporting column-validation success.

### Why the manufacturing and cybersecurity entries are provisional

UCI explicitly says AI4I is **synthetic** and describes how its machine-failure target is constructed from five failure-mode indicators. B6 encodes only the safe **one-way** implication (some mode is 1 ⇒ `Machine failure` is 1). Do **not** infer the converse from this entry alone. This is referenceable label-generation logic, **not an independently observed physical law**.

CICFlowMeter documents feature names, direction and min/mean/max definitions; for a populated packet set, the ordering follows mathematically. Its validity on the retained CIC-IDS2017 mirror still requires verifying exact column mapping and generator version; expression mismatches are not adjudicated real attacks or defects.

## PowerShell instructions (repository root)

```powershell
cd "H:\nrr136 data\ICDE"
$py = "C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe"
& $py -m unittest discover -s tests -p "test_reference_catalogue.py" -v
& $py .\scripts\audit_b6_catalogue.py --write-report
Get-Content .\data\evaluation\b6_catalogue_audit.json
```

The audit checks metadata column names (spaces/case are meaningful), structural B3 DSL compatibility, evidence URL formatting, protocol identity, and gold-status exclusions. **It does not fetch sources or determine whether their wording logically entails the rule.** The evidence links are human-review tasks, not automatically verified claims.

## Freeze and independence rules

The frozen protocol is **prospective from this B6 step onward**, not retroactive to past Luna and dataset exploration. Run future Sol/Luna on identical *predeclared* input bundles and budgets, logging hashes/cost/status. Do not paste source/reference equations into model input as an answer key. Curator-written test fixtures must be excluded from model-discovery recall denominators.

Previously examined NHANES GLU_J, Apple/other explored companyfacts, AI4I, and sampled CIC-IDS2017 cannot suddenly be called untouched confirmatory data. Use a new non-overlapping NHANES cycle (document any laboratory method changes), unseen SEC CIKs with filing-context alignment, and capture/day-grouped cyber testing where provenance exists. For AI4I, call any new within-dataset partition *internal validation*; external industrial generalisation requires a separate dataset.

## Reviewer adjudication

Two independent reviewers must record their own decisions before viewing one another's assessments. For each entry, check original official documentation, mathematical entailment, field names and versions, full applicability context, rounding/tolerance, potential exceptions, and whether any rule is defined by a synthetic label-generation process. Record unresolved disagreements and an adjudicator's final decision in a separate versioned report. No provisional rule is automatically gold by appearing in this catalogue.

## Metrics and baselines

All denominators and formulas are frozen in `b6_protocol_v1.json`. Distinguish rule-level source precision from row-level detection precision, report abstentions and conditional non-applicability separately, and report injected defects apart from naturally adjudicated anomalies. Compare a matched opportunity budget across MetaVerify, deterministic discovery, an LLM without evidence gating, and B4-only compilation. Record token spend and runtime independently.

## Source documentation used for this initial catalogue

- CDC NHANES GLU_J: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/GLU_J.htm
- UCI AI4I 2020: https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset
- SEC APIs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- XBRL US standard financial concept definitions: https://xbrl.us/data-rule/dqc_0015-le-V2pr/
- CICFlowMeter documentation: https://github.com/ahlashkari/CICFlowMeter/blob/master/ReadMe.txt
- CICFlowMeter implementation: https://github.com/ahlashkari/CICFlowMeter/blob/master/src/main/java/cic/cs/unb/ca/jnetpcap/BasicFlow.java

These URLs were reviewed while constructing the seed catalogue; the offline audit **only checks their URL syntax**, not live contents.

## Next implementation milestone

**B6.1:** Independently adjudicate the two provisional source-supported entries, build the SEC filing-context adapter, and run a read-only **real-data baseline** for AI4I and CIC using existing local files, with explicit file checksums and split provenance. Do not start by spending more on models.
