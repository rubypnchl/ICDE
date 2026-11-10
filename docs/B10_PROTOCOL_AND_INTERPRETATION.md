# B10: matched-input *retrospective* gate decision replay

## Research question and honest scope

What decision changes occur when the **same saved typed constraint hypotheses** are routed through (a) candidate-only, (b) B4 safe compilation with a fixed curator parameter registry, and (c) the existing B5.1 evidence policy?

**This is not an independent or prospective gate-effect benchmark.** The two B5 model opportunities were selected by hand. B5.1 policies and the glucose coefficient/precision binding were created **after seeing** the original model hypotheses. Holding them fixed across arms eliminates parameter-registry confounding *within the replay*, but cannot make the policy unbiased or establish accuracy gains.

## Fixed inputs and outcome definitions

- Exactly two original B5 typed **Luna** proposals: `glucose_unit_conversion` (healthcare), `balance_sheet_equation` (finance). No new prompt, API call or new candidate generation.
- Verify exact source SHA-256 fingerprints using existing `b7_1_pilot_comparison.json`; also verify saved B5.1 evaluation, B5.1 policy and grant structure. Refuse any mismatches.
- Arm A (ungated) simply lists the two candidates. **Candidate exposure is not a rule acceptance decision.**
- Arm B passes the unmodified proposal assertions and original context keys to the existing `src.rule_bridge.compile_proposal`. Where the original B5 model did not supply a parameter, the **same pre-existing, retrospectively authorised B5.1 registry binding** is passed to both Arm B and Arm C. Thus B4 structural status can be compared while holding the binding constant.
- Arm C invokes the existing `src.evidence_gate.review_report` on the **exact saved B5 report** and the fixed existing B5.1 policy and registry. The gate reports its own recorded status and safe-to-deploy flag. A compiled healthcare rule is still **unverified**; finance is blocked for reporting context/scope.
- Separately record original B5 structural compilation without curator intervention, so curator assistance is never mislabelled as an effect of evidence gating.
- When both stages compile the healthcare candidate, ensure executable assertions/context are exactly the same, allowing only the provenance/origin label to differ.
- A hard failure aborts before reporting results. The runner refuses to overwrite prior results. Original source files are never modified.

## Metrics and limitations

- Candidate presence, originally compilable, compilable with identical curator binding, saved evidence review outcome, and accepted for safe deployment. Report only **counts**, not precision, recall, p-values or confidence intervals.
- All proposal inputs and any aliasing are identical across compiler and evidence-stage observations; however they are not prospective, blinded or gold-validated.
- No source fact-level accounting context is independently established by this study.
- No full comparative implementation of Auto-Test/Guardrail/Metanome is run, and the independent 28-candidate B7.2 data-only group is *not combined* with this two-proposal study.
- The private B6.4 reviews cannot automatically be transformed into an independent gold set; reviewer decisions and policy ancestry must be reported separately.

## Execute (Windows PowerShell, from repo root)

```powershell
$py = 'C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe'
& $py -m unittest discover -s tests -p 'test_b10_matched_gate_pilot.py' -v
& $py .\scripts\run_b10_matched_gate_pilot.py --check-inputs
& $py .\scripts\run_b10_matched_gate_pilot.py
```

Or use `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_b10_one_step.ps1` after expanding the ZIP into the root of the repository.

The script saves `data/evaluation/b10_matched_gate_pilot/{summary.json,paired_decisions.csv,README.md}` and never runs a model, downloads datasets, or pushes to GitHub.

## Scientific interpretation for ICDE

The same previously saved finance rule is executable under B4 but withheld under B5.1 because its reporting context and parent-only equity semantics were unresolved. The previously saved healthcare conversion requires curator-supplied parameters and, although it compiles after that intervention, has no independently validated precision specification. Both demonstrate stage differentiation, not a measured general accuracy improvement.

**Do not present 2/2 curated compiler success as automatically discovered correct rules.** The original B5 compiler admitted 1/2 before curator assistance, and B5.1 semantically approved none for deployment.
