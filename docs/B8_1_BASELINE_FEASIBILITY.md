# B8.1 — Published-baseline feasibility and fair-comparison assessment (10 Nov 2026)

**Evidence status:** repository/manual availability assessed; no published baseline installed or executed, so no head-to-head performance claim.

| Published artifact | Task/output | Reproduction/compatibility assessment | Decision for ICDE 11 Nov deadline |
|---|---|---|---|
| Auto-Test (SIGMOD 2025) | Learned Semantic-Domain Constraints; pretrained SDC application expects input CSV plus SDC file | SDC constraint type differs from the targeted multi-attribute, source-scoped XBRL equalities and rule-level evidentiary verification; large pretrained artifacts and input preparation needed | Do not mislabel it as an executable equality-baseline; no claim of head-to-head evaluation |
| Guardrail (SIGMOD 2026 artifact) | Constraint synthesis from noisy data integrated with downstream SQL/ML queries; Python/conda setup | Different data/input and operator regime; repository includes an experimental codebase and dependencies but no compatible frozen MetaVerify benchmark adapter | Do not claim comparison without actual installed run and task mapping |
| Metanome (platform and profiling algorithms) | Classical dependency discovery and profiling | Java/Maven platform and algorithm plugins; functional dependencies differ semantically from source-qualified numeric/conditional constraints | Could become future method-appropriate data profiling baseline, but not already measured |
| Deequ | Data-quality validation given supplied constraints | Good *execution* comparison when supplying an identical rule, not an autonomous semantic-rule discovery baseline | Do not present a same-rule checker as discovery baseline |

Sources (public project pages):
- https://github.com/qixuchen/AutoTest
- https://github.com/pckennethma/guardrail
- https://github.com/HPI-Information-Systems/Metanome
- https://github.com/awslabs/deequ

**Conclusion:** A fair published baseline is a material outstanding evaluation gap. For this deadline, report it transparently, rather than running a mismatched tool and implying superiority.
