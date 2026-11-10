# B10 matched-input retrospective compilation and evidence decision replay

This is **not** a prospective gate ablation or gold accuracy experiment.

- Same original saved LLM proposal expressions in all three conceptual stages: 2.
- Original B5 compilation without human curator aliases: 1 executable-unverified.
- Recompiled B4 with the exact frozen B5.1 curator aliases held fixed: 2 executable-unverified.
- B5.1 evidence policy with that same curator registry: {'blocked_applicability_or_scope': 1, 'compiled_unverified_posthoc': 1}.
- Rules established safe to deploy by the existing gate: 0.

The original B5.1 policy and glucose rounding authorization were constructed *after* seeing the proposals. This replay isolates identical proposal and binding inputs inside a procedural decision comparison, **not** a causal generalisation. Only two previously handpicked opportunities exist; no true precision/recall or published baselines were measured.

Full source hashes, reasons and candidate-level decisions: `summary.json`, `paired_decisions.csv`.
