# MetaVerify: Strong-evidence experimental programme and B9 runtime benchmark

**Date:** 10 November 2026. **Status:** B9 benchmark implementation and helper tests completed; **not yet executed on the original AI4I/CIC CSVs** because those retained source CSVs exist on the user's Windows computer, not in this analysis environment.

The ICDE 2027 second-round research deadline is **11 November 2026 at 17:00 Pacific / 12 November 2026 at 01:00 GMT**. The research programme below cannot all be finished, validated and independently reviewed before that submission deadline. An additional experiment does not guarantee acceptance.

## Experimental questions: do not combine dissimilar tasks

- **Q1: Rule execution:** does the engine correctly evaluate a *given* executable rule on the same rows? Current B6.1/B6.2 and new B9 can test this. Checker agreement and fixed-rule performance are **not** rule-discovery accuracy.
- **Q2: Rule discovery:** does a model or miner propose the right *new rules* under a matched column, context and candidate budget? Current B7.1/B7.2 are not a full benchmark.
- **Q3: Admission / evidence gating:** given **identical proposed rules**, does context-aware acceptance produce fewer independently adjudicated unsupported acceptances while retaining useful coverage? Current B7.3/B8.1 are retrospective. This is the **most important missing controlled experiment**.
- **Q4: Data-quality detection:** do qualified rules identify real errors in genuinely unseen records? Controlled errors alone are not natural defect truth.
- **Q5: Efficiency:** median, p95 and throughput, with equal hardware, datasets and cold/warm policies; avoid comparing single runs.

## Completed / pending matrix

| Priority | Experiment | Evidence or execution | Honest status |
|---|---|---|---|
| P0 | Regression suite | 221 tests passed locally, 10 Nov | **Complete, code-level tests only** |
| P0 | 4-domain source review | Two independent reviewers × (5 rules + 87 cases); 6-source-cell reconciliation | **Completed qualitative opinions**, not final adjudicated gold |
| P0 | Saved LLM and data-only gate audit | B8.1 published; n=2 and n=28 kept separate | **Completed retrospective**, no isolated ablation |
| P1 | Repeated checker runtime / parity (this package) | 9 repetitions, full frozen source rows, per-row two-engine parity; cross-check B6.1 | **Code/test ready; needs user's source-local run** |
| P1 | Third-party baseline feasibility | Assess task language & operating system; run real code on a compatible benchmark only | **No published baseline has executed** |
| P1 | Prospective gate-on/off ablation | Lock same candidate set and documentation; same compiler; only evidence policy switches | **Not performed**; cannot reuse post-hoc B5.1 as prospective |
| P1 | Independent reference truth and adjudication | Resolve especially CIC generator provenance, AI4I RNF, NHANES precision and SEC filing contexts | **Not completed**; require actual domain/source adjudication |
| P2 | Four-domain matched discovery | New, predeclared opportunities; same input/budget; LLM and data-only output full executable constraints | **Not performed** |
| P2 | Unseen test data | NHANES distinct cycle; new SEC CIKs; CIC source-group splits; independent manufacturing dataset | **Not performed** |
| P2 | Real-data detection quality + uncertainty | Qualified row-level true positive/false positive reference and cluster-aware uncertainty | **Not measurable yet** |
| P2 | Multiple published method execution | Auto-Test/Guardrail/Metanome where language and objective align | **Not performed**; no fair head-to-head result |

## B9: repeated same-rule benchmark protocol (immediate runnable work)

**Inputs:** frozen AI4I 10,000-row CSV; frozen CIC 50,000-flow reservoir; original B6.1 report, source manifest, catalogue, protocol. Changes fail preflight. Both engines use the same exact frozen `B6-MAN-001` and `B6-CYB-001` rules.

**Methods:** (`metaverify_b3_generic`) the rule AST interpreter with existing B6.1 measurement validation; (`b6_same_rule_simple_checker`) pre-existing independent hard-coded interpretation. The latter is a same-rule baseline, **not a published discovery method**.

**Design:** first check row-by-row exact status parity and reference B6.1 totals. Load CSV data **before** timed loops. Run 9 alternating-order repetitions per engine and per domain, same rows; record median, interpolated p95, per-run times, throughput, CPU architecture and Python version. Distinguish CSV read time. Preflight and postflight source hashes. The runner never writes to source CSVs or historic reports. It refuses to overwrite a prior B9 output.

**Reporting:** mention all records and both source classifications (AI4I is synthetic, CIC 50k is a development reservoir), hardware/OS/Python, and the exclusion of filesystem I/O. Don't claim precision, semantic-rule correctness, speed superiority over published methods, cold-start latency, or independence of heldout data.

### One-step run (Windows PowerShell)

1. Extract the package into the existing repository root, preserving directory structure.
2. In repo root run `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_b9_one_step.ps1`.
3. Examine `data/evaluation/b9_runtime_results_v1.json`; share the terminal report and JSON. Do **not** edit or replace earlier B6 JSON output.

No automatic push/commit is performed. If results and sources are free of private information, commit **only the new B9 source, tests, plan, documentation, and aggregate output** after inspecting `git diff` and `git status`.

## How to run a genuinely strong matched scientific comparison later

1. Before generating proposals, lock a sufficiently broad *new* opportunity list and source snapshots, and specify the same candidate budget and time/token budget per method. Distinguish rule discovery from rule verification.
2. Obtain two source-qualified reviewers and an adjudicator to lock per-rule exact expressions, scope, and supported contexts; record raw individual votes. **Do not** automatically convert agreement into gold.
3. Compare on the *same proposal set*: syntax-only, metadata-only evidence, and metadata-plus-context policy. Freeze all gate code and thresholds **before** accessing independent evaluation labels.
4. Use a truly disjoint held-out source partition and separate error-free controls, controlled mutations (clearly marked), and independently established natural errors. Validate no source/row leakage.
5. Measure conditional rule precision (only adjudicated eligible items), proposal yield, unsupported-rule acceptance, conditional coverage, abstention, and paired confidence intervals on independent item clusters. If gold eligibility is 0, print `undefined`, never 0 or 100%.
6. Run a published baseline only after testing that it can express the same constraint family. Auto-Test's SDCs focus on semantic-domain anomalies, Metanome on dependency discovery, and Deequ on validation; they do not all solve identical tasks. Report non-comparable functions separately, not in an unfair accuracy leaderboard.
7. Freeze raw artifacts, environment versions, selection seeds, proposal budgets, results, and author-reviewed claims; preserve private review files outside public GitHub.

## Most important judgment for the current submission

The prototype has a reproducible verification pipeline and useful retrospective failure analysis. The missing *prospective, label-qualified, matched gate ablation* is a scientific limitation, not a software bug. The focus should be on a defensible verification/provenance contribution rather than an untested state-of-the-art discovery claim. The paper's acceptance cannot be guaranteed through adding more unverified experiment counts.
