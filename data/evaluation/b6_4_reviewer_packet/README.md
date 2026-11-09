# MetaVerify B6.4 â€” Four-domain reviewer worksheets (source-populated)

The following original-source case rows have been checked against the locally retained datasets and are available as two *blank* reviewer copies. No reviewer opinions, human adjudications, confirmed defects or gold labels are contained in these files.

| Domain | Proposed rules | Case rows per reviewer | Selection |
|---|---:|---:|---|
| Manufacturing / AI4I 2020 | 1 | 27 | All 18 original forward discrepancies and 9 reverse-direction exploratory cases |
| Cybersecurity / CIC-IDS2017 | 1 | 20 | Stratified from the frozen 50,000-flow local sample |
| Healthcare / NHANES GLU_J | 1 | 20 | 16 measured cases across glucose quartiles, 4 missingness controls |
| Finance / SEC EDGAR | 2 | 20 | 10 exact-record-aligned contexts per candidate rule |

**For reviewers:** Reviewer 1 downloads only `reviewer_1_*`, Reviewer 2 only `reviewer_2_*`. Work independently. Complete `reviewer_id`, `decision`, `evidence_url`, `evidence_locator` and `rationale`. The source observations and code-derived statuses are not adjudications. The 9 manufacturing reverse-direction cases are not violations of the frozen one-way rule. Finance `accounting_scope_evidence_status=UNKNOWN` must not be treated as established scope. Healthcare 3-significant-figure precision was chosen after viewing data and is not confirmed by the CDC documentation.

**Rule decisions:** `supports_as_written`, `supports_with_conditions`, `not_supported`, `needs_more_evidence`.
**Case decisions:** `consistent_with_rule`, `supported_discrepancy`, `explainable_exception`, `ambiguous`, `source_version_mismatch`, `not_applicable`, `insufficient_record_evidence`.

**Evidence and code:** The script `scripts/prepare_four_domain_review.py` verifies the original file SHA-256 hashes and deterministically selects these rows. The `review_manifest.json` lists selection strata, frozen source file SHA-256 hashes and counts. All samples are derived from previously explored development data and do not constitute an unseen evaluation set.

**Dataset attribution:** CIC-IDS2017 by the Canadian Institute for Cybersecurity, University of New Brunswick; cite: Iman Sharafaldin, Arash Habibi Lashkari and Ali A. Ghorbani, *Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization*, ICISSP 2018. The official CIC FAQ expressly permits redistribution with citation: https://www.unb.ca/cic/datasets/ . Dataset landing page: https://www.unb.ca/cic/datasets/ids-2017.html . AI4I: https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset . NHANES: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/GLU_J.htm . SEC: https://www.sec.gov/search-filings/edgar-application-programming-interfaces .

**Privacy:** All reviewer-vote columns are blank. Do not commit completed reviews or private reviewer identities to public GitHub without permission.
