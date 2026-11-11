# B13.4 — B4/B3 compiler integration smoke test (development only)

**Design-only status (11 Nov 2026).** This package connects the original B4 `compile_proposal` return contract to B13.3's A/B/C synthetic gate decisions. It calls the real B4 compiler and B3 validator **only on five hand-authored toy fixtures**, not on new source cohorts, not on B5–B12 real hypotheses, and not on prospective candidate manifests. No source download, network/model/API call, file writing, or Overleaf edit.

## Why this step matters

B13.3 accepted a string called `compiler` in a synthetic object; that is not proof that B4 actually returns those statuses. This adapter binds to the existing `src.rule_bridge.compile_proposal`, checks B4's three explicit statuses (`candidate_executable_unverified`, `blocked_unresolved`, `rejected_invalid`), validates the emitted B3 executable rule with `src.generic_verifier.validate_rule`, and refuses unknown statuses or inconsistent rule IDs. The same B4 result is passed to all arms; B4 is invoked exactly once per candidate.

**B13.3 policy has an unresolved scope-admission gap.** It permits Arm C to `admit` a toy case whose documentary/context signals are `supported` even though the compiled rule did not declare a required context key. B13.4 deliberately exposes and reports this issue rather than silently changing frozen B13.3 semantics. **Do not run real candidate admission or quote gate-effectiveness estimates until the scope rule is resolved in a new versioned policy, reviewed and frozen prior to labels.** Admitting a toy case is only an experimental decision, not an approved deployment rule or proof of applicability.

The package's tests include (a) actual B4 success, unresolved and invalid; (b) true B3 validation; (c) no automatic status permission; (d) one B4 call for three arms; (e) per-candidate input fingerprints; (f) synthetic-only safeguard; (g) missing-scope diagnostic. Fictional `example.org` HTTPS URLs are toy markers, NOT documentary evidence.

## Run in existing repository root (on `b13-prospective-gate`)

```powershell
$py = 'C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe'
& $py -m unittest discover -s tests -p 'test_b13_4_b4_adapter.py' -v
& $py .\scripts\run_b13_4_adapter_preflight.py --preflight
```

Expected 15 tests. The preflight must report `B13.4 PREFLIGHT PASS`, three B4 compiled examples, one B4 unresolved and one invalid, all toy. It **must also explicitly warn about the Arm C undeclared required-context gap**. The package makes no results file and does not alter prior frozen artifacts.

When tests pass, stage only the new files, inspect staged filenames and `git diff --cached --check`, commit on the B13 branch if desired; do not `git add .` or merge to `main`. Keep all old B5–B12 artifacts unmodified. At the next phase, version a **new policy** with explicit missing-scope treatment and corresponding tests; do not quietly modify the B13.3 frozen policy in place.

## Scientific status

B13.1 design prepared; B13.2 shortlist contains zero eligible new cohorts; B13.3 synthetic decision policy locally checked; B13.4 B4 adapter toy integration only. No matched prospective experiment, source-qualified gold truth, known natural defects, cross-domain rule discovery benchmark, or published-method superiority claim follows.
