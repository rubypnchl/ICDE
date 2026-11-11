# B13.7 — Public source-object acquisition and hash receipts

**Status: source acquisition only, no eligible cohorts or model/gate runs.** This package performs meaningful, user-triggered collection of three exact public objects from the existing B13.2 shortlist. It is not another pass/fail claim about documentary entailment and does not claim gold. Original B13.6 questions remain open.

## Documented identities (official web pages checked 11 November 2026)

- NHANES 2015–16 `TRIGLY_I.XPT` (CDC file release January 2019): <https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/TRIGLY_I.htm>. Official derived-variable descriptions include LBXTR -> LBDTRSI factor **0.01129** and LDL relation with fasting/eligibility restrictions. The exact rounding policy requires separate assessment. The document has been inspected during experiment design: **not blind/unseen rule discovery**.
- NHANES 2015–16 `TCHOL_I.XPT` (CDC release September 2017): <https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/TCHOL_I.htm>. Official factor `LBXTC * 0.02586` for `LBDTCSI`. Both XPTs are **one NHANES cycle**; independent source-group count is not two.
- UCI Steel Plates Faults `steel_plates_faults.zip` (dataset ID 198): <https://archive.ics.uci.edu/dataset/198/steel%2Bplates%2Bfaults>. Dataset licence CC BY 4.0. UCI lists 1941 instances and 27 features, but **the page does not establish a safe nontrivial semantic rule**. Archive content and feature definitions need inspection before candidate construction.

The three file URLs are pinned in `data/evaluation/b13_7_source_objects_v1.json`. A response digest is a *local fingerprint*, not an independent signed publisher hash. If a public server blocks automation or redirects away from the approved host, the tool refuses and reports failure; don't silently substitute a mirror.

## Privacy, reproducibility and source isolation

This stage does not edit B13.1–B13.6 files, datasets or the manuscript. The download cache is explicitly **outside the ICDE Git repository**, defaults to `~/Downloads/ICDE-B13-Source-Cache`, and is checked before any file writes. Downloads occur only with `--acquire`, one explicit source ID at a time. `--preflight` does **not** call the network or create output. Each `--acquire` writes the data object and `B13S-*.receipt.json` to the cache using exclusive (no overwrite) paths; checks basic file format, a maximum of 64 MiB, and cryptographic SHA-256. An existing file is never replaced: `--verify` checks the saved file against its original receipt. Do not commit raw XPT/ZIP files, local path receipts or participant rows; keep the cache private.

## Execute (Windows PowerShell)

From `H:\nrr136 data\ICDE` after extracting the ZIP, with the existing Python 3.12 `$py`:

```powershell
& $py -m unittest discover -s tests -p 'test_b13_7_source_acquisition.py' -v
& $py .\scripts\run_b13_7_source_acquisition.py --preflight
```

Only after inspecting registry and choosing to fetch the specific official files:

```powershell
$cache = 'H:\nrr136 data\ICDE-B13-Source-Cache'
& $py .\scripts\run_b13_7_source_acquisition.py --acquire B13S-HLT-01 --cache-dir $cache
& $py .\scripts\run_b13_7_source_acquisition.py --acquire B13S-HLT-02 --cache-dir $cache
& $py .\scripts\run_b13_7_source_acquisition.py --acquire B13S-MAN-01 --cache-dir $cache
```

Each may fail depending on the external website's policies. Run independently and inspect every output. To check existing bytes without network:

```powershell
& $py .\scripts\run_b13_7_source_acquisition.py --verify B13S-HLT-01 --cache-dir $cache
& $py .\scripts\run_b13_7_source_acquisition.py --verify B13S-HLT-02 --cache-dir $cache
& $py .\scripts\run_b13_7_source_acquisition.py --verify B13S-MAN-01 --cache-dir $cache
```

## What this adds / what it does not

- Adds exact object URLs, private downloadable source bytes and local SHA-256 receipts when downloads succeed. Enables a real provenance anchor for later source-specific qualification.
- Does not prove official file authenticity beyond live HTTPS retrieval, source-version comparability, candidate novelty, independent cohort eligibility, derivation precision, actual source-context semantics, gold constraints or evidence-gate effect.
- SEC issuer selection and CIC capture selection remain open; **do not treat this three-file acquisition as four-domain evaluation**. If these URLs are blocked, do not fabricate outcomes. Human source review/adjudication must still occur before prospective scoring.

## Git handling

Keep the original `b13-prospective-gate` branch. Only commit **new code/docs/registry/tests**, after checking the complete test output and staging names. Do not use `git add .`; do not merge into shared main or update Overleaf. A source receipt can be cited privately in future research work without placing raw data or absolute paths in public GitHub.
