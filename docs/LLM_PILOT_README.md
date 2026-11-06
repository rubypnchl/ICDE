# MetaVerify — low-cost four-domain LLM feasibility pilot

## Research question
Does an LLM reading **only documented metadata** propose meaningful,
traceable cross-field constraints for finance, manufacturing, healthcare,
and cybersecurity, compared with our existing deterministic proposals?

**These outputs are candidates, not verified rules.** The models receive no
held-out dataset values or labelled reference constraints.

## Models
- GPT-6 Luna: `gpt-6-luna`, reasoning `none`
- GPT-6 Sol: `gpt-6-sol`, reasoning `low`

Both use identical source bundles and prompts; no automatic Sol escalation.
Use them as an independent model comparison. No model reviews the other model.

## How to use (VS Code Windows PowerShell, from ICDE root)
Place `src/llm_rule_pilot.py` and `tests/test_llm_rule_pilot.py` from the ZIP
into the correspondingly named folders in your working Git repository.

```powershell
$py = "C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe"
& $py -m unittest discover -s tests -p "test_llm_rule_pilot.py" -v
& $py .\src\llm_rule_pilot.py                 # DRY RUN, no API charge
Get-Content .\data\llm_pilot\input_bundles.json -TotalCount 45
& $py .\src\llm_rule_pilot.py --model luna --run
& $py .\src\llm_rule_pilot.py --model sol --run
```

API key: if `OPENAI_API_KEY` is not set, the script prompts for it invisibly
at runtime, without writing it to files. API access and billing must be set up
separately from ChatGPT/Codex. **Do not paste keys into the chat or GitHub.**

Costs: four calls per run, 1,000-token response cap per request; approximate
local soft budget 8 cents per model run; **not a guaranteed API account cap**.
Check provider project budgeting/alerts. Uses no web/search tools or file
attachments and sends only compact public metadata descriptions.

The input bundles are intentionally sparse: finance uses available embedded
SEC concept descriptions; healthcare uses the NHANES glucose codebook;
manufacturing and cyber inputs have almost no documented descriptions in the
current MetaVerify metadata. Empty proposals for these domains are honest.

## Dataset and evidence limitations
- Selected column groups are prespecified for a feasibility test. Do **not**
  report unconstrained discovery recall or cross-domain generalisation.
- A cited passage ID is validated to exist but **not** verified to entail the
  formula. Human/independent evidence checking remains necessary.
- Symbolic verification and numeric evaluation are **not integrated** in
  this pilot. This is deliberate to keep the research experiment isolated.
- API model outputs are cached locally by model/domain to prevent repeat
  charges. Delete only a specific cache file if a deliberate rerun is needed.
- Raw data and held-out labels are never sent.
- The output includes model ID, prompt hash, inputs, token usage and a warning.

## Git workflow
First review staged paths for secrets or restricted data:

```powershell
git add src/llm_rule_pilot.py tests/test_llm_rule_pilot.py docs/LLM_PILOT_README.md data/llm_pilot
git diff --cached --name-only
git commit -m "Add reproducible four-domain LLM constraint proposal pilot"
git push origin main
```

## Next experiments (not completed here)
1. Add authoritative, licence-safe documentation snippets for manufacturing
   and cyber sources, without including labelled rules or solutions.
2. Adjudicate candidate meaning independently with citations; do not rely on
   GPT-6 Sol as an oracle for Luna.
3. Evaluate rule precision, evidence support, coverage, cost, and stability.
4. Compare to deterministic rule proposals on identical dataset scope and
   equivalent verification families.

## Version 2 — strict baseline vs hypothesis discovery

The first strict-evidence Luna run (6 November 2026) returned an empty rule
list on all four datasets. That is **not** an API error: completed requests
consumed 16 output tokens apiece. Preserve the original `luna_*.json`
results. Missing documented cross-attribute relationships may explain the
empty responses, but this is an interpretation until the original `output`
objects are inspected.

This update adds an *experimental treatment*, not a looser verification gate:

- `--mode strict` (default): retains the original policy requiring documentary
  evidence for a candidate relationship; outputs `luna_finance.json` etc.
- `--mode hypothesis`: allows unverified, labelled hypotheses from column
  names/types/units/descriptions. Missing coefficients are unknown symbols,
  never invented as numeric constants. Citation IDs are optional and existing
  reference IDs are checked. Outputs use distinct names like
  `luna_hypothesis_healthcare.json` to preserve the strict baseline.
- `--domains healthcare finance` runs only those two chosen domains (default
  is all four). The file `input_bundles_hypothesis.json` holds the selection.

### Cost-aware experiment sequence

From the ICDE root:

```powershell
$py = "C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe"
& $py -m unittest discover -s tests -p "test_llm_rule_pilot.py" -v
& $py .\src\llm_rule_pilot.py --model luna --mode hypothesis --domains healthcare finance
# Inspect data/llm_pilot/input_bundles_hypothesis.json; this is a FREE dry run.
& $py .\src\llm_rule_pilot.py --model luna --mode hypothesis --domains healthcare finance --run
```

Review results before paying for the other two domains or for Sol.
For an apples-to-apples Luna/Sol comparison, pass the same `--mode` and
`--domains` arguments and compare the resulting identical input bundles.

### Scientific distinction

`syntax_and_reference_check=pass` is **not** a validated integrity constraint.
A referenced column or documentary description may exist without implying the
suggested relation. All generated candidates must be independently adjudicated
against official relationship documentation and/or data with held-out testing.
Neither the LLM's confidence nor a different LLM's opinion establishes ground
truth. The prompt-selected attribute groups are not an unbiased cross-domain
recall benchmark.

No API key is stored. The API `--run` flag must be supplied explicitly.
