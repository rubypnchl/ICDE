# B13.2 — source eligibility shortlist (NOT an experiment)

**11 November 2026**. This is a read-only, offline, screening-stage package. It records five *potential source entries* in four domains. It does not assert independence, collect candidate rules, execute a gate, download any dataset, adjudicate gold, or produce a B13 result. The branch `b13-prospective-gate` retains the earlier B13.1 protocol. No PR merge or Overleaf updates are needed.

## Sources requiring manual vetting

- Finance: official SEC EDGAR APIs, with new CIKs/accessions **not yet selected**. Previously studied Apple Companyfacts must be excluded; check all other prior issuer exposure before selection. Inspect filing XBRL contexts, accession, units, dates and equity scope, not only arithmetic matches. https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- Healthcare: NHANES 2015–16 TRIGLY_I and TCHOL_I, official CDC page and source files. Check sample/derivation validity and precise rounding semantics. These two are **not two independent survey-cycle clusters**. Documentation describing derivations was already consulted during screening and that exposure must be logged; it is not blinded discovery. https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/TRIGLY_I.htm and https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/TCHOL_I.htm
- Cybersecurity: official CSE-CIC-IDS2018, separately from CIC-IDS2017. Must specify capture days and generator/header mapping. Sharing the CICFlowMeter family is a methodological dependency. Do not download the massive S3 bucket as a screening step. https://www.unb.ca/cic/datasets/ids-2018.html
- Manufacturing: UCI Steel Plates Faults (dataset 198), distinct from AI4I 2020. Real candidate suitability is **unknown**; feature names alone do not entail integrity constraints. https://archive.ics.uci.edu/dataset/198/steel%2Bplates%2Bfaults

## Freeze and selection order

1. Preserve B13.1 branch and existing development outputs. Do not merge to shared main without coordination.
2. Use this shortlist only to establish which datasets *could* furnish candidates. Log exact versions, access terms, prior exposure, selection rationale and candidate group IDs. Confirm whether each has source-level admissibility evidence, not just numerical patterns.
3. **Implement and freeze arm A/B/C logic, all parameters, exclusion rules, budgets, scoring, conflict handling and an analysis plan before inspecting the new cohort's reviewer truths or checking gate decisions.** B13.1's plan specifies arms but does not itself implement them. This package does not fill that gap.
4. Obtain independent proposal generation on predeclared new source/context snapshots, recording that CDC formula documentation was previously inspected. Freeze candidates and hashes under the existing B13 manifest only after relevant source eligibility is confirmed.
5. Obtain independent blinded reviews, with a separate adjudicator. Do not reuse B6 adjudication, B12 lineages or source-screening opinions as truth labels.

## Local commands in VS Code PowerShell

Extract B13.2 ZIP into the current ICDE root, preserving paths, and from the repository root run:

```powershell
$py = 'C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe'
& $py -m unittest discover -s tests -p 'test_b13_2_source_screening.py' -v
& $py .\scripts\run_b13_2_source_screen.py --preflight
```

Expected: **9 tests OK** and `B13.2 SOURCE SCREEN PASS`. The return value is only a schema/shortlist check, not a scientific eligibility finding. No new source data, review form or rule is generated. Review `git status --short` before staging only these five new files. No automatic push/commit is performed.

## Scientific risk

This shortlist is convenience sampling informed by known public documentation and previously explored constraint families. If these sources are later used to estimate causal gate improvements without a separate locked candidate generation procedure and blinded reference process, selection bias remains. The B13 protocol's 8-per-domain engineering quota is not a power calculation. Do not inflate sample sizes by treating multiple rows, rules from one issuer, or multiple analytes in the same NHANES cycle as independent source groups.
