# B13.15 — Original SEC filing XBRL structural audit

**Purpose.** Continue B13.14's already locally fingerprinted, newly identified Chipotle 2025 Form 10-K SEC *source lead* with an original-filing-byte acquisition and narrowly scoped Inline XBRL structural check. This stage **does not** create a semantic candidate, LLM discovery, human reference label, confirmatory evaluation, or A/B/C result.

## Frozen source selection

Issuer: Chipotle Mexican Grill, CIK `0001058090`; 10-K filed `2026-02-04`, report period `2025-12-31`, accession `0001058090-26-000009`, primary document `cmg-20251231.htm`. The filing URL is checked against the independently downloaded B13.14 SEC submissions receipt before download. Previous 10 SEC development issuer CIKs are excluded by the B13.14 validator. Other prior exposure remains unchecked.

## What is checked

- Parent B13.14 raw SEC submissions object and intake receipt are reverified before all operations, including SHA-256 and accession metadata. 
- The original official 10-K HTML is fetched over HTTPS, with the SEC contact User-Agent, a strict exact official host/path check, limited response size, and no redirects to unknown hosts. Raw bytes and a SHA-256 receipt are stored outside Git, with exclusive-create and no overwrite.
- Inline numeric facts (`ix:nonFraction`) and XBRL contexts are scanned without transforming, interpreting, publishing, or comparing financial numbers. For an exploratory `Assets` / `LiabilitiesAndStockholdersEquity` structural pair, the program counts occurrences sharing **the same contextRef and unitRef**, restricting to SEC CIK and the filing's report-period instant and excluding segment/scenario/member-marked contexts.
- A screened structural opportunity is created only if both concepts appear with a common context and unit. Duplicates and unresolved context references are flagged. No balance-sheet equality is asserted by software.

## Important boundaries

The SEC HTML source receipt plus fact co-location are necessary but **not sufficient** for source semantic eligibility. Accounting scope, entity consolidation, document narrative, XBRL transformation registry, custom extensions, units, filing amendments, duplicate facts, and overall measurement method still require review. The pair is a **preselected accounting relationship**, not a discovered LLM rule or independent gold.

`HTMLParser` performs a conservative structural scan, not a complete Inline XBRL processor. In particular `scale`, `sign`, precision, decimals and taxonomy calculation-linkbases are deliberately not interpreted. No record-level defect conclusions are allowed. If the filing lacks parsable inline facts/contexts, the program stops rather than silently treating it as qualified.

## Run after B13.14 acquisition + verification

```powershell
cd 'H:\nrr136 data\ICDE'
$pilot = 'H:\nrr136 data\ICDE-B13-Independent-Pilot'
& $py -m unittest discover -s tests -p 'test_b13_15_sec_filing_context_audit.py' -v
& $py .\scripts\run_b13_15_sec_filing_context_audit.py --preflight
$env:SEC_USER_AGENT = Read-Host 'Research institution and real contact email for SEC fair access'
& $py .\scripts\run_b13_15_sec_filing_context_audit.py --acquire --cache-dir $pilot
& $py .\scripts\run_b13_15_sec_filing_context_audit.py --audit --cache-dir $pilot
& $py .\scripts\run_b13_15_sec_filing_context_audit.py --verify --cache-dir $pilot
Remove-Item Env:SEC_USER_AGENT
```

`--acquire` saves `B13_15_CMG_2025_10K_original_inline.html` and a SHA-256 receipt. `--audit` saves an aggregate JSON report and structural opportunity CSV (no financial amounts). `--verify` reruns all integrity checks and detects changed audit bytes. If the SEC refuses a download or returns an unexpected document, stop; no mirror workaround is silently substituted.

Do **not** push raw HTML, accession-specific private intake or generated reports into the repository; stage only the code, tests, and this documentation. Do not use B13.13 `--freeze` on the placeholder candidate packet. A subsequent stage must first build a **real typed, source-context-qualified candidate**, separately from reference review.
