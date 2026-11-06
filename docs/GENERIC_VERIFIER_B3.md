# Milestone B3 — Domain-neutral constraint *execution* (v0.1)

This module is intentionally small and deterministic. It executes a limited typed
expression DSL over rows; it does **not** automatically discover constraints,
turn free-form LLM strings into executable code, verify citations, infer units,
or adjudicate actual data-quality defects.

## Scope and reproducibility

- Uses the exact four-domain **existing** metadata column names in
  `data/rules/generic_examples.json`.
- Four examples are manually structured *candidate* rules (not four discovered
  rules). Healthcare precision was selected on the same NHANES snapshot, so
  matching it again is reproduction, **not independent validation**.
- `data/rule.schema.json` remains unchanged. The typed DSL here is **not yet an
  adapter to that schema**. This is deliberate: do not silently claim schema compatibility.
- No OpenAI/other API use. `src/generic_verifier.py` is standard-library only.
- No raw datasets are added to Git. `--healthcare` reads local retained XPT and
  emits only aggregate statistics and the file checksum.

## Commands (repo root)

```
python -m unittest discover -s tests -p 'test_generic_verifier.py' -v
python scripts/run_generic_verifier.py --demo
python scripts/run_generic_verifier.py --healthcare
```

The `--demo` option uses invented **test fixtures only** for all four domains;
it is not cross-domain evaluation evidence. `--healthcare` evaluates actual
GLU_J.XPT records if the local file and pyreadstat are installed. The program
writes `data/evaluation/generic-nhanes-glucose.json`.

## Rule DSL (v0.1)

Each rule has `schema_version`, `id`, `dataset_id`, `assertions` (nonempty array),
optional `when` predicate, optional `context_keys`, and advisory `evidence_status`.
An assertion compares `left` and `right` expressions using `eq`, `ne`, `lt`,
`lte`, `gt`, `gte`. Expressions are typed JSON objects, not free-form Python:

- `{"column":"A"}`: field A; `{"constant":"0.05551"}`: numerical literal
- `{"add":[expression, expression, ...]}`
- `{"multiply":[expression, expression, ...]}`
- `{"subtract":[expression, expression]}`
- `round_right:{"mode":"significant_figures","digits":3}` or `decimal_places`
- optional `abs_tolerance` (nonnegative, for `eq`/`ne` only)
- `when:{"column":"Type","op":"eq","value":"L"}`; `all`/`any` groups allowed
- `context_keys:["entity", "reporting_date", "accounting_scope", "currency"]`
  requires that every referenced field have `_field_context[field][key]` and
  values match across those fields; missing or mismatched contexts **abstain**.

`_field_context` must be supplied by a **trusted ingestion adapter**; v0.1 does
not independently validate the factual correctness of context metadata.

## Outcomes

- `satisfied`: all executable assertions hold
- `violated`: at least one executable assertion conflicts with observed values
- `not_applicable`: condition false
- `abstained`: required fields, numeric values, or requested context are missing,
  incompatible, or invalid

The output distinguishes raw row count, eligible rows (`total - not_applicable`),
evaluated rows (`satisfied + violated`) and eligible-row coverage. A `violated`
outcome is **not** equivalent to independently verified dataset corruption.
The verifier makes no claim about evidence validity from `evidence_status`.

## Research-critical next steps

1. Define a **validated parser/compiler** from LLM proposals to this typed DSL;
   the current LLM produces *free-text expressions* and is not executable.
2. Separate candidate **generation** from independent documentary
   entailment/adjudication; preserve reason for abstention.
3. Replace manually selected columns with unbiased candidate retrieval on
   complete metadata (or honestly label focused proposals).
4. Add adapters for real held-out data and ground-truth defects in finance,
   manufacturing, cybersecurity, and healthcare.
5. Establish published baselines and an independent reference-rule catalogue.

## Known limits

No automatic inference of units, percentage/scaling, schema mapping, semantic
context, source truthfulness, or rounding precision. `ROUND_HALF_UP` is an
explicit choice and not universally valid. General execution over different
names is **not** evidence of general *discovery* across domains.
