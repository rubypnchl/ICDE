# B7.1 — Retrospective metadata-only pilot accounting + ICDE manuscript scaffold

**Scientific classification:** Not a published-baseline reproduction, not an unbiased two-model comparison, not four-domain discovery-quality evidence. This is a **small, matched-input descriptive audit** of the previously saved B5 Luna hypotheses (healthcare and finance) and an original generic lexical paired-unit hypothesis generator.

## Why this stage is necessary

The B6.2 deterministic checker used the **same hand-coded reference rule** as B3: agreement was an expected execution test. B7.1 begins comparing **what is proposed from the same metadata**, not just execution. However, the original B5 opportunities were *manually selected before this stage* and the B5.1 policy was configured *after viewing the two Luna outputs*. Accordingly, no result at B7.1 is a generalizable precision/recall or evidence-gating superiority claim.

The generic heuristic only matches numerical fields with exactly matching normalized descriptions but different parenthesized units (e.g. "Fasting Glucose (mg/dL)" vs "Fasting Glucose (mmol/L)"). It proposes an **unordered, uncalibrated relationship hypothesis**, never a runnable equality or conversion factor. There are no model calls, no source-row reads and no modifications to previous artifacts.

**Other established work to compare later:** Auto-Test (SIGMOD 2025; https://github.com/qixuchen/AutoTest), Guardrail (PACMMOD 2025; https://github.com/pckennethma/guardrail), Metanome (profiling dependencies; https://github.com/HPI-Information-Systems/Metanome), Deequ (constraint validation; https://github.com/awslabs/deequ). These have different constraint languages, capabilities and input regimes. Do not say we have run them or compare their reported numbers as head-to-head outcomes.

## Install & run: VS Code PowerShell from repo root

```powershell
cd "H:\nrr136 data\ICDE"
$py = "C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe"
& $py -m unittest discover -s tests -p "test_b7_1_pilot_comparison.py" -v
& $py .\scripts\run_b7_1_comparison.py --check-inputs
```

**Commit the implementation + plan BEFORE running the comparison**. Stage only the new files:

```powershell
git add src/b7_1_pilot_comparison.py scripts/run_b7_1_comparison.py tests/test_b7_1_pilot_comparison.py data/evaluation/b7_1_comparison_plan_v1.json docs/B7_1_PILOT_AUDIT_AND_PAPER.md paper/metaverify_icde2027_draft.tex paper/references.bib
git diff --cached --check
git diff --cached --name-only
git commit -m "Predefine B7.1 pilot discovery audit and start ICDE manuscript"
git push origin main
```

**Then** run:

```powershell
& $py .\scripts\run_b7_1_comparison.py
```

This saves `data/evaluation/b7_1_pilot_comparison.json`. Inspect the JSON, especially `limits`, and commit that result separately. The report computes no rule precision, recall or competitive improvement metric. If the preflight fails, **do not edit past B5/B5.1 files** to make it pass; send the exact error for provenance debugging.

## Manuscript workflow (in parallel)

- `paper/metaverify_icde2027_draft.tex` and `paper/references.bib` form an **initial IEEEtran draft**, not a submission-ready paper. They can be uploaded to Overleaf together; use the conference IEEE template.
- Real, verified experiment counts from B3/B6.1/B6.2 are explicitly distinguished from independent gold outcomes. The B7.1 result is a future insertion point, not a fabricated table.
- Authors, ORCIDs, exact dataset provenance, source quotations, implementation-specific technical details, novelty claim, genuine matched published baselines, and a completed independent review are pending. The draft openly indicates those limitations.
- ICDE 2027 research-track deadline: **11 November 2026 at 5:00 p.m. Pacific Time**, and **12 pages excluding references and the AI-generated-content acknowledgement**. Check the official live instructions: https://icde2027.github.io/submission-guidelines.html
- Do not submit the draft without manual verification and substantial scientific completion. The system is a prototype, not yet a demonstrated state-of-the-art improvement.

## Next scientific experiment (do NOT invent its outputs)

Construct a prospectively frozen, balanced opportunity set with complete documentary contexts, plus two independent reviewers. Compare candidate rule discovery and context acceptance on identical opportunities and budgets, with abstention and per-class support. A published method should only be called a baseline once its own implementation actually runs (or a carefully justified compatible task mapping is documented). Annotator agreement alone is not ground truth.
