# B5.1 — Post-hoc evidence binding, applicability and audit gate

This milestone **reviews saved B5 structured outputs** and never changes those
outputs or requests another model completion. It introduces a separate,
auditable, curator-controlled layer between model proposal and B4/B3 execution.

## Current findings on the two observed Luna proposals

- **Healthcare `glucose_unit_conversion`**: The model requested parameters
  `k1` (factor) and `t1` (rounding). A **manual, exact-structure binding**
  maps them to the existing B4 registry names `glucose_factor` and
  `glucose_rounding`. B4 can now compile the same proposal, but the result is
  `compiled_unverified_posthoc`, not a verified scientific rule. The factor's
  registry entry cites CDC; the entry is **not document-content verified by
  this software**. Three-significant-figure precision was identified from
  *the same NHANES snapshot*; it cannot count as independently validated.
- **Finance `balance_sheet_equation`**: B4 originally accepted the typed AST as
  `candidate_executable_unverified`. B5.1 blocks it because `context_keys: []`
  omits curator-required entity/date/accounting-scope/currency checks. Even
  adding those names cannot establish `Assets = Liabilities + StockholdersEquity`
  generically: this SEC concept describes *parent* equity and can exclude
  noncontrolling interests. Both the fact-level contexts and accounting scope
  need trustworthy verification. No observed numeric mismatch is called an
  independently confirmed financial metadata defect.

## Files

- `src/evidence_gate.py`: no-network evidence/semantic-scope gate.
- `data/rules/b5_1_review_policy.json`: transparent domain-policy and
  **manual post-hoc exact-structure** authorization for one Luna hypothesis.
- `scripts/review_structured_pilot.py`: runs against locally cached B5 JSON.
- `tests/test_evidence_gate.py`: offline tests for exact bindings, blocking,
  fail-closed behaviour, finance veto and preservation of model outputs.
- `data/evaluation/b5_1_evidence_review.json`: produced locally by the script;
  model output files remain unchanged.

## Windows VS Code PowerShell

From the repository root:

```powershell
$py = "C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe"
& $py -m unittest discover -s tests -p "test_evidence_gate.py" -v
& $py .\scripts\review_structured_pilot.py
```

The review consumes the existing `data/rules/b4_example_proposals.json` registry
and `data/llm_pilot/structured/luna_{healthcare,finance}.json` files. It makes
**no API calls**, uses **no Codex credits**, and does not read raw health or
finance records. You can inspect the output with:

```powershell
Get-Content .\data\evaluation\b5_1_evidence_review.json -Raw
```

## Scientific boundary / fair comparison

This policy was deliberately developed **after seeing Luna's output** and
contains an exact manual mapping for that output. It demonstrates the mechanics
of human-curated evidence resolution, **not automatically discovered parameter
bindings** and **not a blinded or statistically fair Luna-versus-Sol win rate**.
Record the original B5 compile status separately from the B5.1 reviewed status.
Do not use B5.1 post-hoc compiled counts to compare models. A future comparison
needs a *frozen, model-independent* pre-registered policy and equivalent
untouched inputs, plus independently adjudicated reference rules and test data.

## Research next step

Generalise evidence acquisition from vetted sources without leaking target
relationships, add trusted fact-level financial context from the ingestion
adapter, and establish held-out evaluation and domain-independent baselines.
Don't turn an automatically compilable AST into a claim of valid constraint.
