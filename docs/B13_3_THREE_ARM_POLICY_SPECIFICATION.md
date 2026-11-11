# B13.3 — Three-arm decision semantics (synthetic-only preparation)

**Status, 11 November 2026:** This package specifies deterministic *research-arm admission decisions* and tests them on 9 made-up toy cases. It **does not connect to B4**, authenticate documentation, assess a real rule, confirm source independence, produce gold labels, or demonstrate a gate effect. No manuscript modification, network use, Git action or result-writing occurs.

## Why this is the next step

B13.1 describes A/B/C but does not contain implementable admission decisions. B13.2 establishes five *potential source leads*, zero eligible cohorts. Before inspecting new cohort outcomes, record and test the arm logic. The same frozen candidate, compiler outcome and parameter registry must feed all arms. A candidate is a rule with its source/context snapshot, **not** a dataset row. Existing B5–B12 materials are development only.

## Frozen policy decisions (toy adapter inputs)

| Stage | Signal | Decision |
|---|---|---|
| Compiler (A/B/C) | `blocked` | All `block` |
| Compiler (A/B/C) | `unknown` | All `abstain` |
| Compiler | `compiled` | A `admit` (research-only) |
| Metadata (B/C) | `contradicted` | B,C `block` |
| Metadata (B/C) | `unknown` | B,C `abstain` |
| Metadata | `supported` | B `admit`, C continues |
| Documentary / required context (C) | Any `contradicted` | C `block` |
| Documentary / required context (C) | Any `unknown` or missing required context | C `abstain` |
| Documentary (C) | `supported` but `verified=false` | C `abstain` |
| Documentary / required context | All `supported`, documentary `verified=true` | C `admit` |

If a contradiction and unknown context coexist, C `block`. Missing required contexts never default to supported. The list of context keys must be specified *before seeing outcomes*. `admit` is **an experimental admission label, not a safety or deployment approval**. If B admits a candidate, A must admit it; if C admits, B must admit. This nested property is built into the policy by design, so it is *not* evidence of improvement. Check coverage tradeoffs against independent reference labels later.

The `verified` Boolean is only an **input claim by a separately defined evidence processor**, not cryptographic authentication or human adjudication. URL + locator validation merely checks formatting. Using the same source adjudicators to set `verified` and supply the truth labels would produce label leakage. Before real evaluation, define separate roles and audit the evidence processor, provenance of documentary findings, and independence of reference reviewers. Further, freeze how each arm derives its input signals (not merely the decision table). Metadata support and contexts must not be chosen after viewing candidate outcomes.

## What remains before a real test

1. Finalize and freeze **B4-to-B13 compiler adapter**, evidence extractors, metadata and documentary policies, candidate selection, required context key lists and parameter registry. Document the exact handling of B4 blocked reasons and failure modes. Do not run real candidates using this toy interface alone.
2. Manually verify source eligibility (official versions, prior exposure, captures/CIKs, access terms) and choose genuinely new source groups.
3. Predeclare source groups and candidate-generation budgets; create candidate manifests with hash-verified rule, context and registry snapshots. B13.1 `--lock` should remain unused until the full new cohort is ready.
4. Obtain blinded, genuinely independent rule reference votes and adjudication. Do not use reference labels in C's documentary evidence input; isolate outputs and control source-document leakage.
5. Analyze paired *eligible* candidate decisions. Primary unsupported-admission-rate denominator must remain undefined if zero; report conditional coverage and uncertain source clustering. Eight per domain is an engineering target, not a powered comparison.

## Run (from existing ICDE repo root, after extracting package)

```powershell
$py = 'C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe'
& $py -m unittest discover -s tests -p 'test_b13_3_admission_policy.py' -v
& $py .\scripts\run_b13_3_policy_preflight.py --preflight
```

The preflight only reads B13.1, B13.2, B13.3 specifications and the synthetic fixtures; it writes nothing. The `example.org` URLs in toy fixtures are intentionally fictional and **must not be repurposed as source evidence**. Preserve the working B13 branch; do not merge to shared `main`, include raw datasets, commit private reviewer responses, or change Overleaf.
