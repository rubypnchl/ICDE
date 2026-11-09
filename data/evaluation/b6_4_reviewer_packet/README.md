# MetaVerify — Independent human-review worksheets across four domains

## What is ready

- Five **proposed rule** worksheets (1 AI4I, 1 CIC, 1 NHANES, 2 SEC) in separate reviewer-1 and reviewer-2 files.
- Original, auditable **27 AI4I cases** (18 violations of the provisional one-way implication, plus 9 reverse-direction exploratory cases). Source snapshots and reviewer votes remain unchanged.
- A **local source-verified export** that creates **20 CIC**, **20 NHANES** and **up to 20 SEC** cases from the *existing raw files in your local ICDE clone*, along with both reviewers' completed (but decision-blank) spreadsheets in CSV format. No source record is fabricated.

The downloadable Excel workbook is a *starter*: it has genuine manufacturing rows and all five rule prompts; cyber, health and finance row-level sheets do not contain verified source values until the local generator is run. Do **not** send those empty starter case sheets to reviewers. The new CSVs produced by the generator are the complete reviewer packets.

## Run on your existing Windows machine

Extract `MetaVerify_All_Four_Domain_Review_Package.zip` into `H:\nrr136 data\ICDE`. Its only executable is `scripts/prepare_four_domain_review.py`.

```powershell
cd 'H:\nrr136 data\ICDE'
$py = 'C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe'
& $py .\scripts\prepare_four_domain_review.py --dry-run
& $py .\scripts\prepare_four_domain_review.py
```

Expected output: `data/evaluation/b6_4_four_domain_review/` containing **16 CSVs** (`reviewer_1/2` × `rules/cases` × 4 domains), `review_manifest.json`, and `README.txt`. The output folder must not pre-exist; the script refuses to overwrite it. A preflight failure means an exact source is missing or has a different hash; **do not force or invent data to make it pass**.

## Original files checked by SHA-256

| Domain | Source used | Selection |
|---|---|---|
| Manufacturing | B6.3 frozen 27-row reviewer source, bound to UCI original SHA | all 18 forward + all 9 reverse exploratory |
| Cybersecurity | `data/samples/cic_ids2017/flows-50000.csv` | deterministic stratification over ` Label`: 20 original flows, exact header strings preserved |
| Healthcare | `data/originals/nhanes/GLU_J.XPT` | 16 original complete records across 4 fasting-glucose quartiles + 4 missingness controls |
| Finance | `data/originals/sec/companyfacts/*.json`, each checked against its own `data/metadata/sec-companyfacts-*.json` | up to 10 exact reporting contexts for each of two candidate rule forms, diverse issuers |

Original CIC sample SHA-256 `3ee83d5ecbfd50541b0205293a462643309e253e095c41c82cc5c37cf6aef2d5`, NHANES `5b38897d0d7bfbc69dd9ca74ffdaf2f6a9bed5a91d4a7bf46e07f1332cc3379e`. Finance requires actual source-level accession/date/unit/form/filing alignment, but **Companyfacts does not independently establish consolidated/parent-only accounting scope**; the reviewers must resolve that from filing context and source evidence. Context checks are NOT gold labels.

## Reviewer assignment and decision vocabulary

Give reviewer 1 only `reviewer_1_*` files, and reviewer 2 only `reviewer_2_*` files. Do not show reviewer 1 the other's decisions. Both independently consult source links and fill `reviewer_id`, `decision`, `evidence_url`, `evidence_locator`, `rationale`.

Rule decisions (original B6 policy): `supports_as_written`, `supports_with_conditions`, `not_supported`, `needs_more_evidence`.

Record decisions (expanded B6.4 protocol for ordinary as well as discrepant records): `consistent_with_rule`, `supported_discrepancy`, `explainable_exception`, `ambiguous`, `source_version_mismatch`, `not_applicable`, `insufficient_record_evidence`.

**Do not classify every sampled record as a defect.** Manufacturer reverse-direction cases are NOT violations of the frozen one-way rule. CIC has no B6.1 observed rule mismatches. NHANES three-significant-figure expression was chosen post-hoc on the same source; the official codebook instead says rounded to three decimals. Finance includes a deliberately excluded unqualified parent-only-equity candidate for source-based negative review.

## Reviewer questions and source URLs

- AI4I UCI: https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset
- CIC feature generator: https://github.com/ahlashkari/CICFlowMeter/blob/master/ReadMe.txt
- NHANES GLU_J: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/GLU_J.htm
- Finance US-GAAP elements: https://xbrl.us/data-rule/dqc_0015-le-V2pr/
- SEC Companyfacts: https://www.sec.gov/search-filings/edgar-application-programming-interfaces

## Scientific limits

The package prepares assignments; **no decisions or reviewer agreement are filled**. It does not produce independent gold, natural defect precision/recall, representative sampling of the full original CIC-IDS2017 corpus, an independently verified accounting scope, or a prospective constraint-discovery benchmark. Existing B6/B7 scripts and results are not modified. Keep completed human reviews out of public GitHub unless reviewers consent and personal details are redacted. Also do not publicly commit new raw-record case extracts until the relevant source redistribution rights have been checked.
