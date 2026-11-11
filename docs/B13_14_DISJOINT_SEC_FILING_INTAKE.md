# B13.14 — New SEC filing-source intake (source lead only)

**11 November 2026.** This is a narrowly scoped acquisition of one *new prospective source lead*, not B13.13 source qualification and **not a matched-arm or confirmatory experiment**. It does not alter earlier B13 code, raw data, or the manuscript.

## Selection frozen before reading accounting facts

- Filer: **Chipotle Mexican Grill**, CIK `0001058090`. This CIK was not among the ten development SEC CIKs listed in the repository's `data/sources.json`. **Broader prior researcher/model exposure has not been assessed.** This is a predeclared trial issuer, not a scientifically random sample.
- Filing: the **latest 10-K filed on or before 2026-11-11**, with a tie broken by accession number. Filing selection uses only the official SEC submissions metadata, not the balance-sheet figures, hypothesis results or gate decisions.
- API object: `https://data.sec.gov/submissions/CIK0001058090.json`. Source is an official SEC JSON endpoint; downloader accepts only exactly this HTTPS URL, rejects redirects to a different host/path, caps downloads at 10 MiB, and preserves the raw object and a SHA-256 receipt **outside Git**.
- The receipt records one original `www.sec.gov/Archives/edgar/data/...` filing document URL, accession, filing date and reporting date for subsequent **manual XBRL-context review**. This stage does not download the filing's full XBRL package or adjudicate any accounting relation.
- One company/filer = **one source group** for independence bookkeeping. Multiple fact rows or filings do not become independent trials.

## Run in your existing VS Code PowerShell

From `H:\nrr136 data\ICDE` after ZIP extraction:

```powershell
& $py -m unittest discover -s tests -p 'test_b13_14_sec_intake.py' -v
& $py .\scripts\run_b13_14_sec_intake.py --preflight
```

Expected **20 tests OK** and `B13.14 PREFLIGHT PASS`. No network access at this stage.

The SEC asks for an identifying User-Agent containing a real organisation/contact email. Set that **locally** (do not post the contact value into the chat or Git repository):

```powershell
$env:SEC_USER_AGENT = 'Your Research Organisation research-contact@your-real-domain.ac.uk'
$pilot = 'H:\nrr136 data\ICDE-B13-Independent-Pilot'
& $py .\scripts\run_b13_14_sec_intake.py --acquire --cache-dir $pilot
& $py .\scripts\run_b13_14_sec_intake.py --verify --cache-dir $pilot
Remove-Item Env:SEC_USER_AGENT
```

**Replace both example organisation and address** before running. If SEC denies automated access or the response differs, stop and inspect rather than bypassing access protections or switching to an unverified mirror. Respect SEC fair access (at most 10 requests/sec overall; this script makes only a single official submissions request per acquisition). Do not include the real contact value in command output sent to others.

The raw source and receipt are saved outside Git as:

- `B13_14_SEC_CIK0001058090_submissions.json`
- `B13_14_SEC_CIK0001058090_intake_receipt_v1.json`

If both exist, acquisition intentionally refuses overwrite; use `--verify` to check local fingerprints. No field data or reviewer results are collected by B13.14.

## What to do next (do not skip)

1. Independently review the **actual 10-K source filing and its XBRL contexts**, including instant/duration, reporting period, entity, unit, taxonomy and dimensional/consolidation scope; do not assume the Companyfacts API contains all needed context.
2. Before freezing candidate outcomes, document new candidate sourcing methodology, source and policy hashes, prior exposure audit, rights/access, source-specific applicability and **independent documentary entailment**. If provenance is uncertain, leave evidence statuses `unknown`.
3. Only then create real typed candidate packets for B13.13. Do **not** copy the B13.13 example placeholders into a supposedly frozen cohort, do not turn B13.14 submissions metadata into a balance-sheet constraint, and do not infer labels from data agreement.
4. Two genuinely independent blinded reviewer votes and a separate adjudicator remain necessary before scoring. This first issuer alone is inadequate for cluster-aware comparative effectiveness.

## Reproducibility and limits

The 20 tests are offline interface and tamper checks with fake submissions metadata; they **do not assert that the official SEC API has actually been downloaded** or that any filing was qualified. The official SEC source endpoint and fair-access/user-agent policy are documented at `https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data`. All recorded receipts are local content fingerprints, not publisher-signed authenticity.

Allowed claims: `source-lead-acquisition-and-local-fingerprint` after successful user-run acquisition. Forbidden: `new-independent-gold`, `admission-accuracy`, `frozen-confirmatory-cohort`, `real-SEC-XBRL-context-proven`, `matched-three-arm-effect`.
