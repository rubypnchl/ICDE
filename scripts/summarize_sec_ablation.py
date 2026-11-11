"""Read-only paired A/B/C transition analysis of the saved SEC control study.

This analyses 17 intentionally constructed configurations of ONE source-derived
candidate, including seven simulated approval states. It is NOT a SOTA baseline,
independent reference evaluation, or an estimate of accuracy/gate effect.

Usage:
  python scripts/summarize_sec_ablation.py --input <external-cache>/CMG_Deadline_Control_Study/controls.json
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

STUDY = "metaverify_deadline_single_source_controlled_policy_stress_test_v1"
STATES = ("admit", "abstain", "block")
CATEGORIES = ("real_unqualified", "controlled_negative", "synthetic_credential_control")


def summarize(report: dict) -> dict:
    if not isinstance(report, dict) or report.get("study") != STUDY:
        raise ValueError("Unexpected control study or input schema")
    cases = report.get("cases")
    if (not isinstance(cases, list) or len(cases) != 17 or
            report.get("controlled_scenarios_total") != 17 or
            report.get("candidate_count_independent") != 1 or
            report.get("scenarios_simulated_evidence_not_real") != 7 or
            report.get("human_reviewer_decisions") != 0 or
            report.get("gold_rules") != 0 or
            report.get("measured_accuracy_or_gate_effect") is not False):
        raise ValueError("Required non-confirmatory safeguards or expected counts changed")
    seen = set()
    for row in cases:
        if not isinstance(row, dict):
            raise ValueError("Malformed scenario")
        sid = row.get("scenario_id")
        if not isinstance(sid, str) or not sid or sid in seen:
            raise ValueError("Missing or duplicate scenario ID")
        seen.add(sid)
        if row.get("classification") not in CATEGORIES or not row.get("C_reason"):
            raise ValueError("Missing scenario classification or C decision reason")
        if any(row.get(arm) not in STATES for arm in "ABC"):
            raise ValueError("Unexpected arm decision")
        if (row["B"] == "admit" and row["A"] != "admit") or (row["C"] == "admit" and row["B"] != "admit"):
            raise ValueError("Non-nested admission decisions")
    arm_counts = {arm: {state: sum(r[arm] == state for r in cases) for state in STATES}
                  for arm in "ABC"}
    if arm_counts != report.get("arm_counts_over_repeated_scenarios_not_independent_samples"):
        raise ValueError("Stored arm totals disagree with per-scenario outcomes")
    categories = Counter(r["classification"] for r in cases)
    if (categories != {"real_unqualified": 1, "controlled_negative": 9,
                       "synthetic_credential_control": 7} or
            report.get("scenarios_unqualified_real_evidence") != 10):
        raise ValueError("Source-versus-synthetic evidence strata do not match the recorded protocol")
    return {
        "candidate_count_independent": 1,
        "controlled_scenario_count": 17,
        "simulated_evidence_scenarios": 7,
        "arm_counts": arm_counts,
        "A_to_B": {f"{a} -> {b}": n for (a, b), n in sorted(
            Counter((r["A"], r["B"]) for r in cases).items())},
        "B_to_C": {f"{b} -> {c}": n for (b, c), n in sorted(
            Counter((r["B"], r["C"]) for r in cases).items())},
        "C_reason_counts": dict(sorted(Counter(r["C_reason"] for r in cases).items())),
        "C_by_classification": {category: {
            state: sum(r["classification"] == category and r["C"] == state for r in cases)
            for state in STATES} for category in CATEGORIES},
        "interpretation": "Controlled policy transitions on one candidate; no independent gold or effect estimate",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Existing external-cache controls.json")
    args = parser.parse_args()
    report = json.loads(args.input.read_text(encoding="utf-8-sig"))
    result = summarize(report)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
