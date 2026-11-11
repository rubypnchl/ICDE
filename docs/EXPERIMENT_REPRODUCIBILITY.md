# MetaVerify experiment reproducibility index

This index identifies the research implementations used for the ICDE prototype. It does **not** certify semantic rule correctness, independently labelled errors, improved precision/recall, a causal gating effect, or comparisons against published implementations of Guardrail/Auto-Test.

## Repository locations

- `src/`: compiler/verifier and reusable evaluation logic (`rule_bridge.py`, `generic_verifier.py`, `b13_*`, `metaverify_deadline_*`).
- `scripts/`: runnable experiments and **read-only** analysis entry points.
- `tests/`: small fixture-backed tests; real-data runs additionally require separately obtained source objects.
- `data/evaluation/` and `docs/`: frozen plans, manifests, protocols and interpretation, where tracked.
- `paper/`: separately maintained manuscript; do not automatically overwrite or regenerate it.

The historical ZIP files were delivery packages, **not** separate experiments or source-of-truth repositories. Do not repeatedly extract them over committed code. Preserve local scripts and compare against Git before making changes.

## Experiment entry points

| Experiment | Runner | Inputs and outputs | Interpretation |
| --- | --- | --- | --- |
| Source lineage and NHANES schema | `scripts/run_b13_7_source_acquisition.py`, `scripts/run_b13_8_source_schema_audit.py` | Original official source files and receipts in external cache | Provenance/schema checks only |
| NHANES conversion residual audit | `scripts/run_b13_9_documented_pairs.py` | 2015–16 TRIGLY_I and TCHOL_I XPT source objects | Three pre-documented relationships; no gold |
| NHANES documentary triage | `scripts/run_b13_10_documentary_triage.py` | Previously inspected candidate inventory | No independently adjudicated labels |
| NHANES strict B4/B3 replay | `scripts/run_b13_11_retrospective_replay.py` | External NHANES source cache | Exact expression mismatches are not confirmed errors |
| NHANES tolerance grid | `scripts/run_b13_12_fixed_grid_sensitivity.py` | Same one-cycle NHANES cluster | Tolerances are exploratory |
| New SEC source intake/audit | `scripts/run_b13_14_sec_intake.py`, `scripts/run_b13_15_sec_filing_context_audit.py` | Original filing outside Git | Structural co-location, not semantic qualification |
| SEC one-candidate A/B/C diagnostic | `scripts/run_metaverify_deadline_sec_pilot.py` | `CMG_Deadline_Pilot/` external-cache outputs | A admit, B admit, C abstain; not a confirmatory gate effect |
| SEC 17-scenario controlled screening | `scripts/run_metaverify_deadline_controls.py` | `CMG_Deadline_Control_Study/controls.json` outside Git | One previously inspected candidate; 7 synthetic approval scenarios |
| **SEC paired A/B/C transition summary** | **`scripts/summarize_sec_ablation.py`** | Existing `controls.json`; read-only, prints JSON | Breaks down each screening transition, not effect size or accuracy |
| NHANES controlled perturbation | `scripts/run_metaverify_final_perturbation.py` | External `ICDE-B13-Source-Cache` | Deliberate shifted values, not natural error labels |
| NHANES coefficient baselines | `scripts/run_metaverify_matched_numeric_baselines.py` | Same external NHANES cache; training/test partition within one cycle | CDC factor vs training median-ratio/OLS; **not** published SOTA |

All writers have existing no-overwrite guards. To reproduce a writer's run, use a fresh *external* cache containing the verified inputs but **not** its existing output files. Do not remove retained evidence just to rerun a script.

## Quick read-only ablation summary

From the repository root, with Python installed:

```powershell
python -m unittest discover -s tests -p 'test_sec_ablation_summary.py' -v
python scripts/summarize_sec_ablation.py --input '<absolute-path-to-external-SEC-pilot-cache>/CMG_Deadline_Control_Study/controls.json'
```

Expected observed results: 17 constructed configurations of one candidate; A 17 admits; B 15 admits/1 abstention/1 block; C 1 admit/7 abstentions/9 blocks. A→B and B→C are **paired code-path decisions**, not independent samples. The sole C admission uses a simulated approval configuration, not real reviewed evidence. No p-values, F1, or causal interpretation should be derived from these controls.

## NHANES follow-up checks

```powershell
python scripts/run_metaverify_final_perturbation.py --selftest
python scripts/run_metaverify_matched_numeric_baselines.py --selftest
```

Their real-data runs previously succeeded on an external NHANES cache; the raw XPT sources and generated JSON/CSV outputs are **not** included in the Git repository. The held-out coefficient comparison separates participants *within the same previously inspected survey cycle*, not independent source groups. See the source scripts for flags, output names and guards.

## Local-only legacy files and preservation

Some older B7/B12 READMEs, tests and scripts were reported **untracked in the Windows worktree**. Their current bytes have not been inspected by this consolidated GitHub update, so they are intentionally neither overwritten nor auto-committed. Before including them, compare each file with its tracked equivalents and ensure it is essential to reproduce a reported result. Never use `git add .` to stage raw source files, generated experiment outputs or private reviews. No changes are required to `main` or the Overleaf manuscript.
