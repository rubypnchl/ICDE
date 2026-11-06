# B6.1 — Read-only development baseline (manufacturing and cybersecurity)

**Status:** executable *candidate-rule agreement* on retained source CSVs, not reference precision, held-out validation, independently verified defects, or a four-domain benchmark.

## Dataset plan (fixed)

| Domain | Local input | Expected rows | Rule | Limitation |
|---|---|---:|---|---|
| Manufacturing | `data/originals/ai4i/ai4i2020.csv` | 10,000 | `B6-MAN-001` | UCI's AI4I is **synthetic**, its target is defined from failure labels, and the records were already inspected. |
| Cybersecurity | `data/samples/cic_ids2017/flows-50000.csv` | 50,000 | `B6-CYB-001` | Fixed-seed (2017) reservoir sample from two Friday afternoon CSVs; **not** the entire CIC-IDS2017 dataset, not a held-out test. |

The catalogue rules come from `data/evaluation/b6_reference_catalogue.json`. The runner never introduces hidden thresholds, performs row sampling, discovers new rules, mutates the inputs, or accesses a network. It checks the manifest paths and the exact header names (including leading spaces in CIC features). Source CSVs stay local, in accordance with the repository's redistribution precautions.

## Run on the user's VS Code PowerShell machine

```powershell
cd "H:\nrr136 data\ICDE"
$py = "C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe"
& $py -m unittest discover -s tests -p "test_b6_1_real_baselines.py" -v
& $py .\scripts\run_b6_1_real_baselines.py --check-inputs
& $py .\scripts\run_b6_1_real_baselines.py
```

If a source is missing or a manifest/header/count differs, the runner **fails closed** rather than silently substituting a file. All the new unit tests are generated from **synthetic fixtures**; they are not real-data results. The real-data command saves **only aggregate statistics** to `data/evaluation/b6_1_real_baselines.json`. Do not add raw CSVs to Git.

To run only one domain, use `--domains manufacturing` or `--domains cybersecurity`. The JSON report is replaced each successful run and its `results` array describes exactly which domains were evaluated.

## Definitions and caveats

- Eligible = total − not_applicable. Evaluated = satisfied + violated. Coverage = evaluated / eligible.
- Abstained = invalid/missing binary failure label in AI4I, missing/invalid packet count, or an unset/nonfinite required comparison feature. Invalid binary labels are explicitly withheld rather than treated as ordinary failures of the condition.
- `B6-MAN-001` is a one-way implication: **if a mode flag is 1, `Machine failure` must be 1**. It does not enforce the converse; all-zero mode records are not applicable.
- `B6-CYB-001`: if forward packet count > 0, forward packet length min <= mean <= max. Count zero is not applicable; negative/noninteger counts abstain. Exact source feature mappings and generator versions still need review.
- The runner reports `reason_counts` without raw row identifiers. It hashes local input CSVs, protocol, catalogue, source manifest and runner for reproducibility.
- No independently qualified gold rule exists in B6 yet. Any `violated` count is an **expression disagreement**, not independently adjudicated data corruption. Synthetic AI4I label-generation agreement is not evidence of real manufacturing physical law.
- A single elapsed time is descriptive; it is **not** the preregistered median/p95 timing benchmark. No precision, recall, F1 or false-positive rate is computed without independently labelled examples.

## Scientific next actions

1. Have two reviewers independently adjudicate `B6-MAN-001` and `B6-CYB-001` using exact official source versions. Record disagreements before adding either to a gold denominator.
2. Investigate observed mismatches and missingness without retroactively tuning these development results.
3. Implement finance filing-context compatibility and obtain an untouched NHANES cycle for confirmatory evaluation. Preserve the existing B6 protocol or explicitly version any amendment.
4. Run baseline methods on matched, predeclared discovery opportunities and measure rule-level precision using the reviewed reference catalogue. The current runner is **not** an inter-method comparison.

## v2 correction: duplicate **unreferenced** CSV headers

The first runner refused any duplicate CSV header, even when the duplicated
field was not referenced by either B6 candidate rule. This prevented the
CIC-IDS2017 development evaluation before any rows were counted. The v2
runner uses a positional `csv.reader` to avoid `DictReader` overwriting
same-named columns. A required field must still occur exactly once, with
its exact leading spaces/case; missing or duplicate **required** fields,
short/long CSV records, mismatched source counts, and changed hashes still
fail closed. Duplicated unrelated field names and blank headers are retained
in `csv_header_diagnostics` in the output report.

This is a format-compatibility correction, not an alteration of the frozen
B6 rule catalogue, decision criteria, or applicability conditions. The
report includes a new `runner_sha256` and `runner_revision`. Any new data
results remain exploratory development-baseline outcomes until independent
reference adjudication. Source CSV files are never edited.
