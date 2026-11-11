# B13.13 — Frozen-input matched A/B/C pilot for real source-associated candidates

**Status: implementation ready for user-run integration checks; no new source cohort, independent source qualifications, human adjudications, or real matched-arm results have been claimed.** This is *additive* to B13.1–B13.12, on `b13-prospective-gate`. No code in B13.1–B13.12 is altered. Raw source files, private candidate packets and completed review forms stay **outside Git**, and nothing touches Overleaf or `main`.

## What this actually implements

1. `--freeze` requires a **nonempty** candidate packet with actual existing source files, SHA-256 receipts, typed B4 proposals, a single source-specific parameter registry, predeclared documentary/metadata evidence and predeclared source-applicability contexts. It verifies the source-file contents and stores an immutable input and compiler-file hash lock. It simultaneously writes a **blinded human-review packet** with no A/B/C results, source curator IDs, or generation-method names. The reviewer packet exposes proposed registered parameter values (not their curator-provided provenance) so reviewers can assess the concrete rule. Freeze is not source-authenticity proof.
2. `--run` requires the unchanged original packet, source bytes, code, and lock. For each candidate it calls the actual B4 compiler **exactly once**, normalizes and B3-validates that compilation, and evaluates arms A, B and C against exactly the same candidate. No candidate-level reference truth is opened. An existing run cannot be overwritten.
3. **Arm A** admits any compilable hypothesis *for experimental exposure*, regardless of supporting evidence; **Arm B** uses the supplied metadata signal; **Arm C** additionally checks documentary status and verification flag, source-context attestation, required compiled `context_keys`, an explicitly reviewed B3 `when` predicate (if required), and per-field context compatibility. Contradictions block; missing evidence or unreviewed extra applicability abstains. All source-policy evidence is externally attested, not authenticated by this program.
4. `--score` only after **two independently completed, privately stored** reviewer files and, when they disagree, a separately identified adjudicator. Software prevents reuse of declared source curators as reference reviewers. It excludes conditional/unresolved opinions, exposes zero denominators as `null`, and returns only descriptive arm-level rates conditioned on provided human votes. The software **cannot authenticate people, verify reviewers' actual independence or certify reference truth**.

## Why this is NOT the B13 confirmatory study

The original B13.1 confirmatory design specifies a separate, frozen four-domain study with an eight-per-domain engineering target, truly new sources and independent reference adjudication. This pilot **does not relax or replace that protocol**; it permits a small sample solely for wiring and readiness. Do not use previously exposed NHANES conversion rules or Steel Plates one-hot patterns as untouched candidates. The old B5.1 evidence gate was designed post hoc. Do not promote development examples, unverified source claims, manually supplied `verified:true`, or a two-reviewer opinion into independent gold automatically.

B13.13 does not run any published external discovery baseline, infer clinical truth, fetch sources, auto-generate model proposals, or compute cluster-aware confidence intervals. It cannot establish improved accuracy, precision, true-positive rates, p-values, false-positive reductions, or causal gate effects. In particular, B3 `context_keys` checks equality *between referenced fields* and cannot enforce fasting, eligibility, sampling, regulatory scope or other source conditions unless a separately source-supported B3 `when` predicate and the required record columns are genuinely available; even a matching `when` AST is not proof of semantic correctness. The per-field context snapshot is supplied input and must be independently validated.

## Windows PowerShell: validate implementation immediately

Save ZIP to `H:\Downloads`, then from `H:\nrr136 data\ICDE`:

```powershell
Expand-Archive -LiteralPath 'H:\Downloads\MetaVerify_B13_13_Real_Input_Matched_Pilot.zip' `
  -DestinationPath 'H:\nrr136 data\ICDE' -Force
& $py -m unittest discover -s tests -p 'test_b13_13_matched_pilot.py' -v
& $py .\scripts\run_b13_13_matched_pilot.py --preflight
```

Expected: **37 tests OK**; `B13.13 PREFLIGHT PASS` with the actual installed B4/B3 engines. This test phase does not generate any research results or access source files.

## Prepare genuinely new candidate inputs (outside repo)

Create a separate cache directory, for example:

```powershell
$pilot = 'H:\nrr136 data\ICDE-B13-Independent-Pilot'
New-Item -ItemType Directory -Force -Path $pilot
Copy-Item .\docs\B13_13_CANDIDATE_PACKET_EXAMPLE_NOT_RUNNABLE.json "$pilot\candidate_packet.json"
```

Edit **only the external copy** to use actual new source objects and SHA-256 hashes, source groups and eligibility assertions supported by independently inspected source documentation. Source paths must point *outside the repo*. Replace the clearly fictitious example values with genuinely documented source-specific values. The example is **not runnable** and is not evidence. Multiple candidates can be placed in `candidates` with unique candidate IDs; do not duplicate one source group to pretend to increase independent sample count. `source_context_policy.required_when` must be the **expected compiled B3 predicate** if one is required. Never fill `source_eligibility_review=supported`, `documentary.verified=true` or `context_evidence=supported` based solely on arithmetic fit.

To compute a source file SHA-256 in PowerShell:

```powershell
(Get-FileHash -Algorithm SHA256 -LiteralPath 'H:\PATH_TO_NEW_SOURCE\source.csv').Hash.ToLowerInvariant()
```

If source policy semantics are not independently assessed, record `unknown`. The program then abstains instead of assuming the missing information.

## Freeze and run the same candidates through A/B/C

Only after genuine candidate/source packet preparation:

```powershell
& $py .\scripts\run_b13_13_matched_pilot.py --freeze `
  --packet "$pilot\candidate_packet.json" --out-dir $pilot

# Give only the *blinded* JSON packet to independent reviewers.
# Do not share B13_13_matched_gate_pilot_v1.json or review each other's votes.
& $py .\scripts\run_b13_13_matched_pilot.py --run `
  --packet "$pilot\candidate_packet.json" --out-dir $pilot
```

The frozen candidate lock and the reviewer packet are written *only* outside Git; you must keep the candidate packet, sources and unchanged engine files intact. The outputs refuse overwrite. Hash drift is a hard stop, not a reason to bypass checks.

## Independent private reference reviews

Each reviewer receives the same `B13_13_blinded_review_packet_v1.json` and prepares a **separate CSV** using the header from `data/evaluation/b13_13_independent_review_TEMPLATE.csv`:

`candidate_id,reviewer_id,decision,evidence_url,evidence_locator,rationale`

`decision` must be exactly one of `supports_as_written`, `supports_with_conditions`, `not_supported`, `needs_more_evidence`. A reviewer must cite a verifiable source and locator and give rationale for *every* candidate. The two reviewers' IDs must differ from each other and from the source curator and gate evidence curator IDs. When reviewers disagree, a separate adjudicator resolves using the **same CSV schema**. If there is no adjudicator, disagreements remain **unresolved**, not silently supported. Conditional support also remains unresolved until documented executable conditions are independently established. Completed reviewer forms must not be pushed to GitHub.

After both reviews are complete:

```powershell
& $py .\scripts\run_b13_13_matched_pilot.py --score `
  --packet "$pilot\candidate_packet.json" --out-dir $pilot `
  --reviewer1 "$pilot\reviewer_1_PRIVATE.csv" `
  --reviewer2 "$pilot\reviewer_2_PRIVATE.csv" `
  --adjudicator "$pilot\adjudicator_PRIVATE.csv"
```

Omit `--adjudicator` only if agreement is complete or you accept disagreement cases remaining unresolved. Software checks all recorded review IDs for role separation, replays the frozen gate run before scoring, and writes a new aggregate-only `B13_13_human_vote_scoring_pilot_v1.json` without printing private reviewer rationales.

## Handoff to Mahender

Only after **real source-eligible new candidates**, a locked packet, real gate output, blinded source-specific reference opinions and manually verified role independence should a results handoff be attempted. Record source-group counts, not just candidate counts, and explicitly label output as *exploratory pilot* unless the original confirmatory protocol is separately fulfilled. Until then B13.13 is new engineering infrastructure, **not additional empirical evidence for the current manuscript**.

## Proposed next scientific step

Obtain one genuinely new, disjoint source object from finance or cybersecurity that was not used in B5/B6/B7/B10/B12, freeze source-specific applicability context, and have an independent source expert evaluate the evidence. Do not select rules based on observed downstream gate results. On that basis, create the first real source-qualified candidate packet and test B13.13 end-to-end. If independent review or source support cannot be obtained by the paper deadline, use B13.7–B13.12 strictly as retrospective feasibility and narrow the claims accordingly.
