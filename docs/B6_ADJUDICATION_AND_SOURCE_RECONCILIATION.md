# MetaVerify B6 — documented adjudication evidence and finance source cross-check

**Status (11 November 2026): analytical reconciliation completed; independent third-reviewer adjudication NOT completed.** This document does **not** rewrite either reviewer's original vote or create new independent gold labels.

## Input integrity and independent assessment results

- Original completed archives: `Reviewer_1(6).zip` and `Reviewer_2(6).zip` (retain outside the Git checkout); SHA-256 values retained in the B6 two-reviewer analysis output.
- Rule proposals: **5** (cybersecurity 1; finance 2; healthcare 1; manufacturing 1). Direct rule-category agreement **3/5 = 60%**. Two differences remain recorded in the original assessment record.
- Case records: **87 case identifiers common to both reviewers**, including **85 identical underlying input rows** and **2 finance input-value discrepancies**. All original reviewer decisions and case worksheets remain unchanged.

## Disputed rule B6-CYB-001 — forward packet min/mean/max

**Exact proposed implication:** If `Total Fwd Packets > 0`, then `Fwd Packet Length Min <= Mean <= Max` for the same flow and the same forward-direction packet population.

- **Reviewer 1:** `Needs more evidence`. Accepts the statistical reasoning but could not confirm the generator/column mapping for the retained 50,000-row CIC-IDS2017 sample.
- **Reviewer 2:** `Supported with conditions`. Accepts the same mathematical reasoning; also explicitly requires confirmation of the exact generator version and feature mapping before treating this retained dataset as fully verified.
- **Independent public-source cross-check:** CICFlowMeter's ReadMe defines forward-packet minima, maxima and mean; the CIC-IDS2017 original dataset page confirms CICFlowMeter was used to extract flow features. Neither source proves the specific repository's retained `flows-50000.csv` matches an identified generator build and field mapping.
- **Evidence-based recommendation (NOT a third vote):** `formula supported by definitions; application to this retained CSV unresolved / conditional`. Keep the rule-specific admission decision pending evidence. **Do not recode the raw 3/5 agreement.**
- **To resolve fully:** Verify original retained CSV hash/lineage, exact headers (including whitespace), packet-count semantics and the generator version from the actual data-generation or retained-source manifests.

Public evidence:
- https://github.com/ahlashkari/CICFlowMeter/blob/master/ReadMe.txt
- https://www.unb.ca/cic/datasets/ids-2017.html

## Disputed rule B6-MAN-001 — five failure flags imply Machine failure

**Exact one-way implication:** `(TWF=1 OR HDF=1 OR PWF=1 OR OSF=1 OR RNF=1) => Machine failure=1`.

- **Reviewer 1:** `Supported`. Agrees the UCI description states the implication, but acknowledges RNF-positive rows with `Machine failure=0` and unresolved provenance/discrepancy.
- **Reviewer 2:** `Supported with conditions`. Accepts the *documented implication*, but explicitly withholds a natural-data-defect judgement until RNF semantics and file release discrepancies are resolved.
- **Independent public-source cross-check:** The official UCI AI4I 2020 description explicitly states the one-way implication and reports five random failures; the reviewer sheets show 18 selected RNF-positive forward-rule conflicts, e.g. `UDI=1222` (`RNF=1`, `Machine failure=0`). This establishes a reviewer-recorded **documentation-to-data conflict** but does not establish its cause or independently authenticate the case file against the UCI release.
- **Evidence-based recommendation (NOT a third vote):** `documentary one-way rule supported; flagged cases are unresolved source/documentation conflicts, not validated natural defects`. Prefer conditional support/abstention for *semantic verification on this particular CSV* until file version and RNF meanings are reconciled. The nine selected reverse-direction cases are **not violations of the stated one-way implication**.
- **To resolve fully:** Recheck the pinned UCI CSV and its SHA-256, count all RNF flags by Machine failure value, investigate generator/source documentation, and have a third independent reviewer record a separate decision.

Public evidence:
- https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+data

## Finance data-entry/source-fact discrepancy cross-check

Two JPMorgan case inputs have the **same identity and source SHA-256** in both reviewer workbooks but different recorded numerical values. The public *period balance-sheet figures* have now been cross-checked against original filings. This does not authenticate the specific `companyfacts` snapshot or the chosen accession's XBRL dimension scope.

| Reference | Period | Field | Reviewer 1 (USD millions) | Reviewer 2 (USD millions) | Original period filing (USD millions) | Assessment |
|---|---|---|---:|---:|---:|---|
| B6-FIN-001 | 2013-12-31 | Assets | 2,415,690 | 2,415,689 | 2,415,689 | R2 matches period filing |
| B6-FIN-001 | 2013-12-31 | Liabilities | 2,204,510 | 2,204,511 | 2,204,511 | R2 matches period filing |
| B6-FIN-001 | 2013-12-31 | Liabilities and equity | 2,415,690 | 2,415,689 | 2,415,689 | R2 matches period filing |
| B6-FIN-002 | 2013-03-31 | Liabilities | 2,182,263 | 2,182,260 | 2,182,263 | R1 matches period filing |
| B6-FIN-002 | 2013-03-31 | Liabilities and equity | 2,389,350 | 2,389,350 | 2,389,349 | **Both differ** from period filing |

**Additional data-consistency warning:** In B6-FIN-002, both sheets carry `arithmetic_difference_USD=0` and `observed_arithmetic_status=equal_numbers_unverified_scope`. These fields represent the selected formula `Assets = Liabilities + StockholdersEquity` in Reviewer 1's numbers, but Reviewer 2's Liabilities entry gives an actual gap of USD **3,000,000**, while both reviewers' stored `LiabilitiesAndStockholdersEquity` exceeds the official total by USD **1,000,000**. The workbook's recorded status must **not** be treated as an independently recomputed correctness label for these entries.

Official period references:
- JPMorgan 2013-12-31 period: https://www.sec.gov/Archives/edgar/data/19617/000001961714000289/R218.htm
- JPMorgan 2013-03-31 period: https://www.sec.gov/Archives/edgar/data/19617/000001961713000300/corpq12013.htm

**Source-specific follow-up:** Before overwriting/correcting any reviewer workbook, independently re-extract the original pinned `0000019617_jpmorgan.json` facts by accession, end date, tag, fiscal period and USD unit, including context metadata. Archive a new, versioned corrected *analysis copy* and its provenance. Do not edit the two original signed/received reviewer files or silently change 85/87 in the prior report.

## Independent adjudicator form and boundary of completion

`MetaVerify_B6_Independent_Adjudicator_Form.csv` is intentionally **blank**. A distinct qualified reviewer should complete one line each for `B6-CYB-001` and `B6-MAN-001`, with evidence locations and reasons, after reviewing the original files and source limitations. Possible `independent_vote` values should match the existing B13 vote vocabulary (`supports_as_written`, `supports_with_conditions`, `not_supported`, `needs_more_evidence`). Record conditions separately from general documentary plausibility.

No adjudicator ID, vote, source-eligibility certificate, or human review can be invented by software. Without these signed votes, this document reports a **reasoned desk reconciliation**, not an adjudicated gold set or A/B/C semantic effectiveness estimate.

## Manuscript-ready cautious wording

> Two independent assessment files covered five previously inspected candidate rules and 87 matched case identifiers across four domains. Exact category agreement was three of five rule decisions (60%). In both disagreements, reviewers agreed on the underlying documentary or mathematical relation but differed in their required source-eligibility conditions. A source-based reconciliation identified unresolved generator-version qualification for the CIC-IDS2017 packet-length rule and documentation-to-record conflicts involving the AI4I RNF failure flag. Of the 87 matched case identities, 85 contained identical input values; two JPMorgan cases differed between reviewers, and cross-checking period disclosures identified inconsistent transcribed numbers. These findings characterise documentary uncertainty and review disagreements, not adjudicated correctness, admission precision, or causal improvement from evidence gating.

**Research boundary:** B6 review files were not collected as a new, fully frozen B13.13 matched A/B/C trial. Do not derive gate-effect precision, F1, or claims of superiority from these assessments.
