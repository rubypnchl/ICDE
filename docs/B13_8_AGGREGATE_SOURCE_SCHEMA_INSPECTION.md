# B13.8 — Exact-source schema and aggregate label-shape inspection

**Date:** 11 November 2026. **Classification:** development-stage source feasibility and audit only. No prospective admission-effect estimate, no independently adjudicated gold rules, no rule discovery, and no manuscript updates.

## Why this is the next useful step

B13.7 acquired and locally reverified exactly three public objects. B13.8 is the first **read-only inspection of their actual source data** for schema feasibility. It does not turn their prior documentary exposure into a blinded cohort. In particular, TRIGLY_I and TCHOL_I belong to a single NHANES 2015–2016 survey cycle and should **never** be scored as two independently sampled source cohorts.

B13.7 receipt fingerprints reported by the acquisition operator (not independently signed by CDC/UCI):

| ID | Local object | Bytes | SHA-256 |
|---|---|---:|---|
| B13S-HLT-01 | TRIGLY_I.XPT | 154800 | `dd5a24f7b3bff19f899db38b766445bc4217b6ec6d1bd1accf7065a037e8a59d` |
| B13S-HLT-02 | TCHOL_I.XPT | 193760 | `e7f51cf7c002db01d023278922d89d72318c679967e72ff259ba532b2d72e54d` |
| B13S-MAN-01 | steel_plates_faults.zip | 100890 | `cb8eb9859198b63f053e443513036b401746fa517ef58bd17c846c6741c93919` |

The read-only inspector rejects a different hash, file size, B13.7 registry, missing acquisition receipt or unexpected schema. Do not weaken checks simply to make a nonmatching source pass; version and review deviations separately.

## What B13.8 reports (aggregate only)

- **TRIGLY_I and TCHOL_I SAS transport files:** row count, variable names and local storage types, per-column missing/present counts, and aggregate SEQN missing/duplicate counts. A join **inventory** counts the overlap of participant IDs *in memory*; it does not join clinical values or disclose any IDs or individual rows. The SEQN overlap is not a correctness verdict.
- **UCI Steel Plates ZIP:** archive member names and SHA-256, the declared 34 names in `Faults27x7_var`, numeric row count and observed seven binary fault-column frequencies/row label-sums in `Faults.NNA`. Observed one-hot or multi-hot patterns are not source adjudication, defects, or independently supported constraints.
- **Audit lineage:** the exact B13.7 canonical source-registry hash, prior observed file digests, the versioned B13.8 plan digest, and explicit non-gold/non-gate limitations.

No raw participant values, full dataset copies, raw SEQN values, instance-level predictions, source paths or private reviewer information are written. The aggregate output uses exclusive creation in the external cache; the original three source files and their receipts remain unmodified. A second `--inspect` intentionally fails if the report already exists.

## Requirements

Run in `H:\nrr136 data\ICDE` on branch `b13-prospective-gate`. **B13.7 must already be extracted** in this same working tree, especially `src/b13_7_source_acquisition.py` and `data/evaluation/b13_7_source_objects_v1.json`.

NHANES inspection uses `pyreadstat.read_xport` (already declared in the repository `requirements.txt`). Check installation with `& $py -m pip show pyreadstat`; if missing, install to the existing interpreter with `& $py -m pip install -r requirements.txt` after reviewing dependencies. Offline unit tests do not need real XPT files. The script itself makes **zero network calls**.

## Execute from PowerShell

Extract the B13.8 ZIP into `H:\nrr136 data\ICDE`, preserving directory paths. It adds only new `b13_8`-named files and leaves B13.7 source/receipts untouched.

```powershell
cd "H:\nrr136 data\ICDE"
$py = "C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe"
$cache = "H:\nrr136 data\ICDE-B13-Source-Cache"

& $py -m unittest discover -s tests -p "test_b13_8_source_schema_audit.py" -v
& $py .\scripts\run_b13_8_source_schema_audit.py --preflight
& $py .\scripts\run_b13_8_source_schema_audit.py --inspect --cache-dir $cache
```

The first two commands are offline and read no source records. The third verifies all three B13.7 source receipts, performs the aggregate inspection, hashes sources again, then writes one report to:

`H:\nrr136 data\ICDE-B13-Source-Cache\B13_8_source_schema_audit_v1.json`

The expected high-level report is `B13.8 EXPLORATORY SOURCE SCHEMA AUDIT COMPLETE` plus computed actual counts. **Do not assume** any particular row, missingness or one-hot count before seeing the local result. A missing pyreadstat dependency, unrecognized ZIP member, or hash mismatch must be investigated rather than bypassed.

## Scientific status and next decision

1. All three source objects remain **not independently authenticated** (their local identities are pinned, but no signed authoritative checksums are provided).
2. Neither source eligibility nor documentary entailment has been established; no real gate policy is frozen for these sources.
3. Previously exposed formulas (CDC LDL/triglycerides/cholesterol) cannot be labelled blind discoveries. Even valid arithmetic agreement alone is not a gold constraint.
4. Source-group independence is not the same as the number of rows, labels, or source files. NHANES's two files are one survey-cycle cluster.
5. The Steel Plates fault indicators may supply a structural *screening question* about target encoding. Do not assert all valid plates must obey a specific one-hot rule without independent documentation and adjudication of any exceptions.
6. After inspecting aggregate results, review the source-specific B13.6 questions, resolve genuine feasibility concerns, and **then** decide whether new proposals and a separate confirmatory cohort are justified. Do not run real B13 policy arms in B13.8.

## Git hygiene

No Git changes are made automatically. **Do not commit the B13.8 output JSON, source cache, acquisition receipts, private clinical data or an absolute-path manifest.** If tests pass and the package files are reviewed, the five new source/plan/test/docs/script files can later be committed selectively on `b13-prospective-gate`. Do not merge to `main` or edit Overleaf during this preparation.

Official reference pages (used for schema scope but not as gold labels):
- CDC: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/TRIGLY_I.htm
- CDC: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/TCHOL_I.htm
- UCI: https://archive.ics.uci.edu/dataset/198/steel%2Bplates%2Bfaults
