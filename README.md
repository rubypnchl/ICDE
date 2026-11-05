# MetaVerify Module 1: Metadata Parser

Parses retained official dataset/API snapshots into `data/metadata/*.json`,
validating each output against `data/metadata.schema.json`. Downloaded source
files and URLs are recorded in `data/sources.json`; output provenance includes
SHA-256 hashes. `documented`, `inferred`, and `unknown` are kept distinct.

## Run

Python 3.10+:

```powershell
python -m pip install -r requirements.txt
python -m pip install pytest
python -m src.metadata_parser
python -m pytest
```

NHANES samples are bounded by `--sample-size` (default 1,000); AI4I is
intentionally processed in full (10,000 rows). CIC-IDS2017 and UNSW-NB15 use
fixed 50,000- and 100,000-row reservoir samples with documented seeds. The
retained snapshots make parsing repeatable without network access. NHANES XPT
parsing uses pyreadstat's dictionary mode and does not require pandas.

## Coverage

* **AI4I 2020:** Official UCI CSV and documentation; all 10,000 records.
* **SEC Company Facts:** Ten official SEC EDGAR Company Facts JSON responses.
  Six concepts are selected when available, retaining 2020-2025 facts and
  requiring at least five distinct end-years per reported concept. Quarterly
  facts and restatements may both occur.
* **NHANES 2017-2018:** Official DEMO_J demographics and CBC_J, HDL_J, GLU_J
  laboratory XPT files with their official codebooks. Up to 1,000 rows are
  inspected per file.
* **ToN_IoT:** The official UNSW page is retained. Unauthenticated SharePoint
  retries returned HTTP 403; authentication was not bypassed. The official
  UNSW-NB15 training and test files are instead retained from a pinned,
  publicly accessible Hugging Face mirror. A fixed-seed 100,000-row reservoir
  sample covers both files and all observed attack categories. The mirror labels
  its files `train.csv` (82,332 rows) and `test.csv` (175,341 rows), opposite
  the official page's declared split counts; original names are preserved.
  Its README declares GPL-3.0; no separate license file was present.
* **World Bank WDI:** Official API snapshots for GDP per capita and population
  (2020-2024), retaining all API responses and summarizing ten selected
  countries.
* **NIST NVD:** Official paginated API and documentation; 4,000 CVEs from the
  first two 2,000-record pages for January 2025 are retained (4,415 matching
  records). Pagination offsets and class/status coverage are recorded.
* **CIC-IDS2017:** 50,000 deterministic, fixed-seed reservoir-sampled flows
  from the pinned public-mirror Friday afternoon DDoS and PortScan CSVs
  (512,212 source rows; 79 columns; BENIGN, DDoS, and PortScan labels).
  Full source CSVs, hashes, sample file, class counts, and sampling settings
  are retained. The older three-row sample remains as a historical snapshot.
  Feature types and missingness are inferred from the retained sample; feature
  descriptions, units, and constraints remain unknown where source documentation
  does not specify them.

No undocumented units, constraints, or descriptions are synthesized. Sources
not available to this environment are noted in provenance and `data/sources.json`.

## Redistribution and reproducibility

Raw dataset payloads are ignored by Git and kept locally because this review
could not verify redistribution permission for every original or mirror. This
does not delete local files. Per-source URLs, SHA-256 hashes, license notices,
sampling seeds, counts, and limitations remain in the generated metadata and
`data/sources.json`. Download each ignored source to its listed path before
running `python -m src.metadata_parser`; mirror revisions and paginated NVD
URLs are pinned in the manifest. The parser recreates the CIC-IDS2017 and
UNSW-NB15 samples with fixed seeds.

The full-data integration tests are marked `requires_data` and need the
locally retained source files. GitHub Actions runs the fixture-backed suite
with `python -m pytest -m "not requires_data" -q`, so CI does not require or
download datasets. Redistribution status and the evidence reviewed are
recorded per dataset in `data/sources.json`; this is a conservative repository
policy, not a legal determination.
