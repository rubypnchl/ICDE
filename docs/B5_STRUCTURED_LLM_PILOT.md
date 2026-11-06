# B5 — Minimal-cost structured rule proposal pilot

**Research status: feasibility only.** This pilot uses the existing B4/B3 modules and sends *compact metadata*, not dataset rows, to GPT-6 Luna or GPT-6 Sol. It requests typed JSON expressions and immediately performs offline safety checks. It **does not** verify real-data correctness, independently check source-document content, or establish domain-independent automatic discovery.

## Method and safeguards

1. Both models receive the **same selected metadata column bundles**, prompt and JSON schema; model identity, reasoning setting and output token budgets are logged. This pilot is *not* a matched equal-token study, and focused columns bias discovery.
2. The model produces up to two typed expression trees per domain, with cited passage IDs and brief uncertainty. No free-form code, numerical literals or unregistered numeric parameters are accepted.
3. B5 checks cited passage IDs exist and include documented definitions. Those passages **do not** independently prove the proposed relationship.
4. B4 compiles each proposal using an **empty numeric parameter registry**. Thus unknown conversion factors, thresholds, rounding and tolerances are *blocked*, not guessed. An expression requiring only existing columns may become `candidate_executable_unverified`.
5. B3 validates the resulting structure. Neither B4 nor B3 assesses semantic correctness or data corruption.
6. Each model response is cached under `data/llm_pilot/structured/{model}_{domain}.json`. The SHA-256 hash covers model, settings, prompt, output format and input. Changed inputs or requests block cached reuse. API failures are not auto-retried.
7. API cost figures are **estimates only**; the local soft spending guard is not a provider billing cap. The API key is collected through a hidden terminal prompt if not in the environment; it is never saved in output files.

## Recommended sequence (VS Code PowerShell at repository root)

```powershell
$py = "C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe"
& $py -m unittest discover -s tests -p "test_structured_rule_pilot.py" -v
& $py .\src\structured_rule_pilot.py --model luna --domains healthcare finance
& $py .\src\structured_rule_pilot.py --model luna --domains healthcare finance --run
& $py .\src\structured_rule_pilot.py --model sol --domains healthcare finance --run
& $py .\scripts\summarize_structured_pilot.py
```

The **first** model run makes two paid API calls. The Sol call is optional, and should happen only once Luna's output has been examined. The default CLI is always a **dry run**. The dry run uses no API key.

Do not remove cached response files or edit the metadata inputs without treating the next run as a separate experiment. In particular, do not add a human reference rule into the input bundle before comparing model performance.

`manufacturing` and `cybersecurity` are supported as model inputs, but current metadata contains no documented field descriptions. Run those domains only after documenting input completeness limitations; do not call them validated four-domain experiments.

### Interpretation

Possible statuses: `candidate_executable_unverified`, `blocked_unresolved`, `rejected_invalid`. These are syntax/availability distinctions, not rule precision or detection F1. The next research stage needs an independently constructed reference catalogue and data adapters for real held-out records. Do not conflate finding a candidate with proving a novel algorithm.

### Compatibility

This bundle adds **three** files: `src/structured_rule_pilot.py`, `tests/test_structured_rule_pilot.py`, `scripts/summarize_structured_pilot.py`, plus this documentation. It does not change the existing B4 compiler, B3 verifier, legacy rule schema or LLM pilot results. All model outputs are kept under a new folder.
