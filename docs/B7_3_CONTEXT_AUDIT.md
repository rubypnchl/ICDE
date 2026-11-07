# B7.3 — Retrospective SEC context-evidence audit

**Status:** prepared protocol and deterministic diagnostic implementation. This is **not** independently reviewed constraint truth, production remediation, natural-defect accuracy, or published-method superiority.

## Why B7.3, rather than another generic ranking experiment?

The saved B7.2 data-only miner yielded **17 AI4I candidates (17 abstentions)** and **11 SEC candidates (10 abstentions and 1 labelled `documented_support`)**. That single accepted financial candidate is `Assets = Liabilities + StockholdersEquity` with a zero tolerance on aligned data. The saved held-out computation had **41/41 arithmetic matches**, but the code `src/rule_discovery.py` sets `same-accounting-scope` and `same-reporting-date` to literal `True` in the `context` mapping. SEC records are grouped upstream by reporting end date and other filing keys, so the hard-coded date flag may reflect that grouping; however, the report has no independent proof of consolidated/parent-only scope compatibility. Matching historical numbers cannot create missing semantic evidence. This also overlaps the **excluded unqualified identity** `B6-FIN-002` in the frozen reference catalogue.

## What this study actually measures

- A **static Python AST audit** of the exact code path that constructed the older context dictionary. This detects the source-level hard-coded flags, not inferred correctness of every individual SEC filing.
- Cross-checks the frozen B7.2 candidate, its 41/41 held-out observation, the legacy SEC evidence registry and prior B6-FIN-002 exclusion. Refuses to proceed if the pinned structure changes.
- A **fail-closed three-state policy** on the same required contexts: `supported` only if an independent reviewer establishes specific evidence, `unknown` if no proof, `contradicted` for demonstrated mismatch. The policy abstains on unknowns and blocks contradictions. Even all-supported contexts produce only `candidate_only_unverified`, never an independently established valid rule.
- **Ten transparent counterfactual controls:** one hypothetical all-supported, eight single-attribute unknown/contradicted perturbations, one conservative all-unknown representation of the saved candidate's unproven contexts. These are controlled policy probes **not real SEC data rows**, and the resulting decision counts are by design.
- Separate frozen-catalogue exclusion: the broadly applied parent-only-equity formula is excluded as an unrestricted identity; this does not mean observed arithmetic equality is a data defect.

Two separate **blank finance review templates** accompany this package (`data/evaluation/b7_3_review/reviewer_1_finance.csv` and `reviewer_2_finance.csv`). Independent humans should evaluate full context and documentary applicability, record a source locator and rationale, and select one of `supports_as_written`, `supports_with_conditions`, `not_supported`, or `needs_more_evidence`. Do not fill these automatically. Do not publicly commit completed private reviews without consent. No review decision is used by the B7.3 diagnostic.

**Critical:** The legacy SEC registry has a URL and a `documented_reference` label but the script does not verify its contents. An official documentation link is not independently authenticated semantic entailment. Rule precision and natural defect rates remain *undefined*.

## Execution from VS Code PowerShell (repo root)

```powershell
cd "H:\nrr136 data\ICDE"
$py = "C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe"
& $py -m unittest discover -s tests -p 'test_b7_3_context_audit.py' -v
& $py .\scripts\run_b7_3_context_audit.py --preflight
```

**Commit B7.3 design/code before generating result**:

```powershell
git add src/b7_3_context_audit.py scripts/run_b7_3_context_audit.py tests/test_b7_3_context_audit.py data/evaluation/b7_3_plan_v1.json docs/B7_3_CONTEXT_AUDIT.md data/evaluation/b7_3_review/reviewer_1_finance.csv data/evaluation/b7_3_review/reviewer_2_finance.csv
git diff --cached --check
git diff --cached --name-only
git commit -m 'Predefine B7.3 SEC context-assumption audit'
git push origin main
```

Then run:

```powershell
& $py .\scripts\run_b7_3_context_audit.py
```

New file: `data/evaluation/b7_3_context_audit.json`. Script **refuses to overwrite** previous B7.3 output; it reads only the five pinned original source/report files and the B7.3 plan. Inspect output before committing separately. Nothing sends source material to external APIs or changes old data, thresholds, references, or the manuscript.

## Scientific interpretation

The gap **41/41 arithmetic matches versus uncertain applicability** illustrates exactly why numerical fit is insufficient as a semantic validity test. The strict diagnostic is not a prospective comparison, is not blinded and uses prior B6 exclusion. It cannot demonstrate improvement in independent rule precision. Source-specific truth requires actual filing/XBRL context checks and human judgement; independently reviewed rules and a matched real discovery baseline are still necessary for a credible ICDE contribution.

## Reporting to manuscript co-author

> Our retrospective SEC audit found that the legacy data-only miner marked an unqualified parent-only equity identity as documented support after 41 exact held-out arithmetic matches, while its code hard-coded reporting-date and accounting-scope flags. A strict evidence policy abstains when source-specific proof is unavailable, and the pre-existing B6 catalogue excludes that universal identity. This is a demonstrated implementation assumption and policy difference, **not** measured semantic precision, true defects or a published-baseline superiority claim.
