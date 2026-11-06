# B6.3 — Independent source review and discrepancy adjudication (workflow v1)

**Classification:** Review preparation and audit infrastructure, not completed independent adjudication. Source-rule gold count = **0** and confirmed naturally occurring defect count = **0** until independent human assessments and resolution. This is additive to the frozen B6 protocol and does **not** edit the B6 catalogue or the B6.1/B6.2 results.

## Scientific question and the source conflict

AI4I 2020 is a **synthetic** manufacturing dataset. Its official UCI description says that a machine-failure label is set when one of five failure modes is active; the same description reports **five random-failure (RNF) cases**. The retained UCI CSV produced 18 rows with `RNF = 1`, all other mode flags zero and `Machine failure = 0`, plus nine rows with `Machine failure = 1` and all mode flags zero. The 18 rows violate the frozen **one-way** B6-MAN-001 implication; the nine are **reverse-direction exploratory cases**, *not* violations of B6-MAN-001. These observations are not adjudicated defects. Establish exact released version, intended RNF semantics and annotation exceptions before drawing conclusions.

- Official AI4I UCI source: https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset
- CICFlowMeter feature descriptions: https://github.com/ahlashkari/CICFlowMeter/blob/master/ReadMe.txt
- CICFlowMeter implementation reference: https://github.com/ahlashkari/CICFlowMeter/blob/master/src/main/java/cic/cs/unb/ca/jnetpcap/BasicFlow.java

CICFlowMeter describes minimum, mean and maximum forward-packet sizes. The B6-CYB-001 min ≤ mean ≤ max relation follows for a nonempty set of comparable packets, but reviewers must verify the **specific retained mirror, generator version, flow direction and CSV column mapping**. The existing 50,000-row agreement alone does not certify a gold reference.

## Sources and frozen materials

The tool reads (without modifying) these committed artifacts:

- `data/evaluation/b6_2_ai4i_independent_review.csv` (27 rows, originally blank reviews)
- `data/evaluation/b6_1_real_baselines.json` (source fingerprints, 10,000 AI4I and 50,000 CIC counts)
- `data/evaluation/b6_2_development_study.json` (original results and design lineage)
- `data/evaluation/b6_reference_catalogue.json` (unchanged provisional rules)
- `data/evaluation/b6_protocol_v1.json` (frozen evaluation definitions)
- `data/evaluation/b6_3_review_policy_v1.json` (new review *procedure*, not an edited rule)

Inputs are checked against the B6.1 and B6.2 hash chain. The expected source CSV hashes are retained, but this stage **does not need or modify raw CSV data**. The form generator does not make paid calls, fetch sources or fabricate decisions.

## Commands — Windows PowerShell from repository root

```powershell
cd "H:\nrr136 data\ICDE"
$py = "C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe"
& $py -m unittest discover -s tests -p "test_b6_3_review.py" -v
& $py .\scripts\run_b6_3_review.py --check-inputs
& $py .\scripts\run_b6_3_review.py --prepare
& $py .\scripts\run_b6_3_review.py --audit
```

A successful initial audit must say **0/27 cases jointly reviewed**, **0/2 reference rules jointly reviewed**, **0 adjudicated gold rules**. The script refuses to overwrite a previously generated reviewer file: do not rerun `--prepare` after reviewers begin, or delete their work.

## Human-review procedure

A research coordinator gives **reviewer 1** only `reviewer_1_cases.csv` + `reviewer_1_rules.csv` and **reviewer 2** only `reviewer_2_cases.csv` + `reviewer_2_rules.csv`. Reviewers read the actual source documentation independently, examine source/version matches and fill only `reviewer_id`, `decision`, `evidence_url`, `evidence_locator`, `rationale`. They must not copy, infer or inspect each other's responses until both submissions are locked. Pseudonymous IDs are acceptable but must identify distinct humans to the research team. The script checks that reported IDs differ but cannot authenticate human identity or actual independence.

**For rule-level review:** `supports_as_written`, `supports_with_conditions`, `not_supported`, `needs_more_evidence`. Review the entire condition, source version and semantic implication, **not** whether the rule happened to match data. If source scope is narrower than the encoded rule, select `supports_with_conditions` and describe the missing constraints. Review CIC source compatibility separately from AI4I.

**For row discrepancy review:** `supported_discrepancy`, `explainable_exception`, `ambiguous`, `source_version_mismatch`. Only a human with adequate independent evidence should choose `supported_discrepancy`; detecting a Boolean mismatch alone is insufficient. The reverse nine records must not be presented as violations of the frozen one-way rule. If source evidence cannot distinguish defect versus dataset-generation convention, use `ambiguous`.

All five vote fields are mandatory when a decision is supplied, including an https URL, locator in a source and substantive rationale; incomplete votes fail the audit rather than counting as reviews. Blank votes remain allowed. Evidence links are **not automatically fetched or verified**; audit results are completeness and vote-agreement metrics, not correctness metrics.

After both reviewers submit, rerun `--audit`. Disagreements require **human adjudicator**, with the source version and any exceptions recorded in a *new* versioned final adjudication artifact. This first B6.3 script **does not finalise gold**, even when both reviewers agree, and does not change the original frozen catalogue. Before manuscript scoring, independently inspect source quotations/locators, handle uncertainties, declare final eligible rule versions, and preserve reviewer votes and adjudication separately.

## Files generated by --prepare

```text
data/evaluation/b6_3_review/
    review_manifest.json
    reviewer_1_cases.csv
    reviewer_2_cases.csv
    reviewer_1_rules.csv
    reviewer_2_rules.csv
```

`--audit` additionally writes `review_audit.json` with response completion and agreement counts, **not** final truth labels.

## Reproducibility and privacy

Original case rows (UDI, binary flags, case type, source SHA) are locked by hash. Proposed rule names, official URLs and frozen statuses are carried into blank forms without copying model outputs or predicting answers. Do not commit real reviewers' personal information or unpublished assessment notes to a public repository without their consent; keep completed review forms private and commit only redacted aggregate summaries as appropriate. It is safe to commit blank review forms and the generated audit stating zero decisions.

## Limitations and next steps

This is an **independent-review workflow**, not evidence that independent review has been conducted. The 18+9 AI4I cases may reflect provenance, dataset-generation semantics, recording or documentation errors. No natural defect precision, domain transfer, unpublished dataset novelty or ICDE-level improvement claim follows from completing forms. After adjudication, compare **rule discovery** on a fair opportunity set with published baselines, not only execution of the same hand-coded rule. Record all protocol deviations prospectively rather than altering B6 hindsight.
