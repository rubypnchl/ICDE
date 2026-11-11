# B13.11 — Retrospective executable comparison and coauthor handoff

**Engineering status:** Source-dependent output requires an explicit local `--run`. The package is additive and does not edit B13.3 through B13.10, shared `main`, or Overleaf.

## Goal and scope

B13.11 replays *three known, previously exposed* published conversion relationships through the **actual B4 compiler and B3 row evaluator**. The same frozen compilation is used for policy A (compiler-only), B (compiler plus supplied metadata) and C (compiler plus supplied metadata, documentary and context verification). The A/B/C decisions here use B13.3 deterministic research semantics only as a retrospective **diagnostic**, not as a confirmed real-source policy. B13.5's toy-only `site` context policy is **not** misapplied to real datasets.

The predeclared `survey_cycle` per-field context is mechanically checked across the two fields within a single XPT source object, but this cannot verify age, fasting, laboratory eligibility, sample selection, clinical validity or rounding. The numerical assertion deliberately uses **exact equality** and no undocumented tolerance. B3 `violated` status is therefore an **exact-equality mismatch**, never an independently adjudicated natural data error. Fields with missing values abstain.

The three sources are **one** NHANES 2015–16 survey cycle, not three independent confirmatory observations. No new proposal discovery, independently reviewed gold, published baseline comparison, causal gate effect, false-positive reduction, precision or recall is measured.

## Outputs, outside Git

Running `--run` writes four files **only** to the existing external source cache; exclusive creation prevents accidental overwrites:

- `B13_11_retrospective_matched_replay_v1.json`: provenance hashes, B4 statuses, B3 counts, and the explicit three-arm decisions.
- `B13_11_candidate_outcomes_v1.csv`: compact descriptive paired outcomes.
- `B13_11_manuscript_table_v1.tex`: LaTeX row-count and arm-decision table for review; **not** automatically to be inserted as evidence-gate effectiveness.
- `B13_11_handover_v1.md`: ready-to-adapt discussion for Mahender with limitations.

For source-level provenance it rechecks local B13.7 receipts and SHA-256, B13.8 report, B13.9 report, B13.10 report and parent registry/plan hashes. It reads XPT in-memory, never exports individual `SEQN` or clinical values, and checks parent reports and source file hashes after execution. It does not run an LLM or download data.

## Commands (existing VS Code PowerShell)

```powershell
cd 'H:\nrr136 data\ICDE'
$cache = 'H:\nrr136 data\ICDE-B13-Source-Cache'
& $py -m unittest discover -s tests -p 'test_b13_11_retrospective_replay.py' -v
& $py .\scripts\run_b13_11_retrospective_replay.py --preflight
& $py .\scripts\run_b13_11_retrospective_replay.py --run --cache-dir $cache
```

If an output file exists, the program refuses to overwrite it. **Do not delete it without checking its contents and retaining the original.** Do not publish aggregate results before the local execution is completed and inspected. Only the new B13.11 code/spec/doc/tests (not output files) should eventually be added to `b13-prospective-gate`.

## What Mahender can legitimately use

From B13.8 and B13.9 (already run by the user): 3,191 TRIGLY XPT records; 8,021 TCHOL XPT records; 3,191 overlapping identifiers; 1,941 UCI Steel Plates records with exactly one positive fault indicator in each; three published conversion factors with paired completeness 2,723, 2,699 and 7,256 and maximum absolute residuals 0.0005, 0.0005 and 0.005 mmol/L respectively. These figures describe exploratory source analysis only. B13.10 assessed four previously inspected relationships; none has an independent reviewer decision or qualified confirmatory gold.

Upon successful local B13.11 execution, the generated `B13_11_handover_v1.md` and `B13_11_manuscript_table_v1.tex` provide a reproducible retrospective engineering result. Do not interpret deterministic A/B/C differences as accuracy effects or generalize to the other three domains.

## Remaining highest-priority research work

Independent source and applicability review; properly frozen fresh candidates from disjoint source groups; implementation of source-specific applicability contexts (B3 `context_keys` alone is insufficient); matched A/B/C evaluation against reference labels; method ablations/baselines and cluster-aware uncertainty. If time or reviewer availability prevents those, narrow the paper to a feasibility/assurance-workflow claim and disclose limitations explicitly.
