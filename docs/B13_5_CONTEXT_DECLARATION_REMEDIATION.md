# B13.5 — Versioned fail-closed required-context declaration check (toy-only)

**Status: 11 November 2026; synthetic remediation preflight, not prospective results.**

## Trigger and rationale

B13.4 used the actual B4 `compile_proposal` and B3 `validate_rule` and found a case where B13.3's Arm C admitted a candidate despite a mandatory source context (`site`) being absent from the compiled executable rule's `context_keys`. The rule's independently supplied evidence-status flags were marked supported, but that **does not imply the executable rule enforces the missing reporting context**. The original B13.3 and B13.4 packages are intentionally unchanged to retain the audit trail.

## v2 policy correction

- An **external, predeclared** source-context policy defines mandatory keys for each dataset. The policy is not inferred from a proposal or its asserted evidence; the toy example freezes `b134-toy` → `site`. It cannot be used as-is for real domains, which need their own source-qualified requirements before new candidate/reference outcomes.
- B4 compiles a typed candidate **once** using the same frozen registry for all three arms. B13.4 validates its result against the actual B3 executable DSL. B13.3 supplies the baseline three decisions.
- For a compiled rule, Arm C **blocks** if any policy-required context key is absent from the *compiled rule*; Arm A (compiler-only) and Arm B (metadata gate) retain their original decisions. Missing documentary/context evidence still yields abstention absent an explicit contradiction. If a compiled rule declares an additional unreviewed context, Arm C abstains unless it is already blocked. Explicit documented contradiction blocks Arm C.
- The v2 policy records B13.3's **canonical JSON SHA-256** to preserve ancestry across Windows line endings; `B13.3` is not modified. All new files are additive.
- Here `admit` is an **experimental arm outcome only**, not independently verified semantic correctness or production deployment approval.

## Test and preflight (VS Code Windows PowerShell)

From the original repo root, after extracting the package into `H:\nrr136 data\ICDE`:

```powershell
$py = "C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe"
& $py -m unittest discover -s tests -p "test_b13_5_context_gate_v2.py" -v
& $py .\scripts\run_b13_5_context_preflight.py --preflight
```

Expected: 25 tests passed; `B13.5 PREFLIGHT PASS`, five original B13.4 fixtures, and one context omission changed from Arm C `admit` to `block`. No outputs written, source downloads, API/model calls, manuscript edits, new candidate evaluation or reviewer labels.

For a strong local regression check, also rerun `test_b13_3_admission_policy.py` and `test_b13_4_b4_adapter.py`; the old B13.4 diagnostic **should continue to report its historical blocker**, since it is deliberately unchanged. This is not a failure of the v2 correction.

## Limitations and future scientific prerequisites

The policy's frozen `site` context is synthetic; it does not establish valid context applicability for SEC filings, NHANES, cybersecurity captures or manufacturing data. It also does not prove documentary support or source authenticity. Before real candidate admission: source-qualified required-context policies and parameter bindings, independent and disjoint sources, an evidence-extraction protocol and blind adjudication must be frozen; then real implementation must be integrated in an expressly authorized *new driver*. The B13.5 driver refuses non-toy inputs.

Do **not** infer semantic gate effectiveness, false-positive reduction, source-dependent safety or measured quality gain from synthetic remediation tests.

## Commit scope

On `b13-prospective-gate`, first verify previous B13.3/B13.4 work and ensure the branch is current. This package contains five new research files, all names start with `b13_5` except the titled documentation. Do not `git add .`; stage only the explicit B13.5 files after tests and `git diff --cached --check`. The package itself does not git commit or push. The B13.4 package should remain unchanged and separately reviewed or committed before B13.5, so the discovery and correction have a clear chronological record.
