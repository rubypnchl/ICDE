# MetaVerify B6 — Two-reviewer assessment audit (descriptive)

**Input:** completed `Reviewer_1(6).zip` and `Reviewer_2(6).zip`, kept OUTSIDE the Git checkout. The archives contain reviewer workbooks for five B6 constraints and row-level selected cases in four domains. Do not commit raw reviewer workbooks, source records, or reviewer rationales to public Git.

Run from the ICDE repository root using standard-library Python 3.10+ (no external spreadsheet dependencies):

```powershell
& $py .\scripts\analyze_b6_two_reviewer_audit.py `
  --reviewer1 "H:\path\to\Reviewer_1(6).zip" `
  --reviewer2 "H:\path\to\Reviewer_2(6).zip" `
  --output "H:\nrr136 data\ICDE-B13-Independent-Pilot\B6_Two_Reviewer_Audit_v1.json"

& $py -m unittest discover -s tests -p "test_b6_two_reviewer_audit.py" -v
```

## Results independently computed from the supplied review archives on 2026-11-11

* Five rule-level assessments; exact agreement of **3/5 (60%)** under minimal predeclared wording normalisation: `Not supported` = `Not supported as written`; `Supported with conditions` remains distinct from `Supported`.
* Cybersecurity rule: Reviewer 1 requests more evidence; Reviewer 2 supports with conditions. Finance rule 001: both conditionally support; finance rule 002 and healthcare rule 001: both reject; manufacturing rule: support vs support with conditions. These are reviewer opinions, not independently adjudicated source truth.
* Both reviewers' archives contain **87 row-level cases**: 20 cybersecurity, 20 finance, 20 healthcare and 27 manufacturing each. All 87 case IDs match. **85** case inputs match exactly; **two finance cases** (both CIK 19617) have different numerical fields and are excluded from identical-input analysis until reconciled to original source snapshots.
* On the identical-input subset: cybersecurity 20/20 both find no discrepancy, healthcare 20/20 both classify as unclear, finance 18/18 have a compatible *coarse observation* (not necessarily equivalent underlying validity), manufacturing 18/27 both identify a conflict with the documented one-way rule but disagree whether it establishes a genuine defect; the other nine reverse-direction cases are **unclear** to Reviewer 1 and **not violations of the one-way rule** to Reviewer 2.
* The 18 manufacturing conflicts are selected cases and do not imply all 18 are independently adjudicated natural errors. The review covers previously inspected B6 candidates; it is not an unseen prospective cohort.

**Do not report** precision, recall, F1, annotation accuracy, statistical superiority, semantic gate-effect improvement or SOTA performance from these files. A third adjudicator and compatible frozen A/B/C candidate inputs would be required for an admission-effectiveness comparison. Source workbooks include evidence URLs and rationales, but this script does not authenticate source contents or reviewer identity.

The script conservatively stops if unexpected rule categories or case labels appear, and provides hashes of the original reviewer ZIPs. Output contains aggregate and candidate-ID annotations only; no row-level values or private rationales are published.
