# B7.2 — Auditable four-domain candidate screening and bounded local batch

## What is and is not accomplished

**This stage generates a transparent set of possible relationships between numeric columns.** It does not infer an executable equality/implication, identify any authentic defect, or establish that MetaVerify beats a published method. There is **no labelled ground truth** and no independent reviewers yet. The prior B5/B5.1 policy is **post-hoc**. These sources were previously inspected. The selected pairs must be judged by real reviewers before they can contribute to accuracy metrics.

There are two simple, original local methods, applied to the **same numeric-pair universe within each domain** and with **the same top-12 ceiling**:

1. `token_similarity_rank`: score unordered pairs by overlap in field names and available descriptions, with an extra weight if two documented descriptions have the same stem but different parenthesized units. The score is an **ordering heuristic only**. The code and scoring formula are visible in `src/b7_2_candidate_screen.py`.
2. `seeded_uniform_random_pairs`: sample the same number of unordered numeric pairs without replacement, using deterministic seeds 72026–72029. This is a chance baseline for **candidate surfacing**, not an integrity-constraint discovery algorithm.

An internal **description-mask sensitivity test** reranks candidates while ignoring descriptions and reports the Jaccard overlap of top-k selected pairs. This measures dependence on metadata, **not** whether evidence gating improves correctness. Missing source definitions remain missing; we do not fabricate descriptions. Duplicate column names are excluded from pair pools rather than overwritten. All field strings, including leading spaces in CIC headers, are preserved.

The four metadata snapshots are: SEC Apple companyfacts (finance), NHANES GLU_J (healthcare), UCI AI4I (manufacturing), and the retained CIC-IDS2017 sample (cybersecurity). No original CSV/XPT/SEC facts are read for the four-domain screen; only committed JSON metadata and the B7.1 report are used.

### Optional existing two-domain *data-only* discovery run

The batch also invokes the repository's **existing** `src.rule_discovery` on local AI4I and SEC Companyfacts snapshots, producing `data/evaluation/b7_2_existing_dataonly_discovery.json`. This is a **separate, older data-mining experiment with a different input budget**. Do not pool or compare its proposal precision with the metadata-only pair screen, or present it as a matched published baseline. This action is harmless to source CSVs but requires the existing locally retained AI4I and Apple SEC files. The script is already in the repository; no algorithm changes or new calls are hidden.

## Installation and pre-commit (before launching)

From PowerShell in `H:\nrr136 data\ICDE`:

```powershell
$py = "C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe"
Expand-Archive -LiteralPath 'H:\Downloads\MetaVerify_B7_2_Auditable_Unattended_Batch.zip' -DestinationPath . -Force
& $py -m unittest discover -s tests -p 'test_b7_2_candidate_screen.py' -v
& $py .\scripts\run_b7_2_candidate_screen.py --check-inputs

git add src/b7_2_candidate_screen.py scripts/run_b7_2_candidate_screen.py scripts/run_b7_2_unattended.ps1 tests/test_b7_2_candidate_screen.py docs/B7_2_UNATTENDED_EVIDENCE_BATCH.md data/evaluation/b7_2_plan_v1.json
git diff --cached --check
git diff --cached --name-only
git commit -m 'Predefine B7.2 four-domain candidate screening and unattended batch'
git push origin main
```

**Inspect the staged names and commit only if checks pass.** Do NOT automatically commit generated results before reading them. Original datasets, keys and raw rows must remain out of GitHub.

## Start one bounded batch before leaving the computer

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_b7_2_unattended.ps1 -Python $py
```

If local SEC input is missing, use `-SkipExistingDataMiner` to run only the four-domain screen. The script runs the dedicated offline tests, checks all metadata input provenance, runs the candidate screen, then optionally runs **the existing two-domain data miner**. It logs stdout/stderr to `data/evaluation/b7_2_batch_run.log`, stops if any process exits nonzero, and **refuses to overwrite previous outputs or logs**. The code makes **zero network/API/LLM calls**, does not change any source dataset and has no hidden background operations. It is not a job scheduler: it only continues if the local PowerShell process and PC remain running. You can lock the screen, but do not shut down or put the PC to sleep. There is no benefit to burning four hours on meaningless repeated computation; it may finish much sooner.

## What to inspect when you return

- `data/evaluation/b7_2_batch_run.log`: step-by-step progress and PASS/STOP.
- `data/evaluation/b7_2_candidate_screen/summary.json`: domain-wise candidate-universe counts, chosen budgets, method overlap, source hashes, missing metadata, sensitivity to description masking, zero gold rules.
- `data/evaluation/b7_2_candidate_screen/rankings.csv`: each pair, input fields, transparent ranking signal, documentary provenance, status explicitly `not executable` and `not verified`.
- `data/evaluation/b7_2_candidate_screen/blind_review_unfilled.csv`: unique pairs, no arm/ranking labels, blank human judgment fields. **Do not fabricate reviews or put personal reviewer comments on a public repo.**
- `data/evaluation/b7_2_candidate_screen/README.md`: concise summary for paper coordination.
- Optional `data/evaluation/b7_2_existing_dataonly_discovery.json`: separate legacy AI4I+SEC data-derived candidate mining, NOT comparable precision on the current pool.

After inspecting, stage only non-sensitive generated aggregates/blank forms and log if it exposes no private paths or keys. The batch does **not** git commit, push, download or modify `paper/`.

## What is still essential for an ICDE-level scientific claim

1. Independent assessment of exact source applicability and candidate semantics, including B6.3 RNF anomalies and CIC generator lineage; complete reviewer worksheets with two actual independent humans.
2. Comparable **constraint** proposals on a prospectively declared opportunity set, not simply unordered column pairs. The existing Luna pilot has two manually selected opportunities and B5.1 was post-hoc.
3. Real published-method comparisons where task/constraint languages are compatible (Auto-Test, Guardrail, Metanome); document adaptations, budgets and fairness. Never say a third-party method ran merely because a local heuristic did.
4. Controlled evidence/context ablation on independently assigned correct/incorrect opportunities; then a genuinely disjoint evaluation split or independent dataset. Report costs, unsupported cases and uncertainty.

There is **no guarantee of acceptance** from completing this stage or any fixed number of experiments. ICDE 2027's guidelines require strong originality and reproducible evidence; experiments/benchmark papers must provide all artifacts to reproduce results. See https://icde2027.github.io/submission-guidelines.html. The deadline is Nov 11, 2026 at 5pm PT. Keep Mahender's manuscript chat separate; share only verified outputs.
