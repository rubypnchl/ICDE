"""Offline B13.3 specification + synthetic control preflight only."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.b13_3_admission_policy import (PolicyError, check_policy_invariants,
                                        load_json, validate_spec)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true", required=True)
    args = parser.parse_args()
    plan = load_json(ROOT / "data/evaluation/b13_plan_v1.json")
    screening = load_json(ROOT / "data/evaluation/b13_2_source_screening_v1.json")
    spec = load_json(ROOT / "data/evaluation/b13_3_gate_policy_v1.json")
    examples = load_json(ROOT / "data/evaluation/b13_3_synthetic_cases_v1.json")
    if plan.get("study_id") != spec.get("parent_study") or plan.get("protocol_state") != "design_draft_not_run":
        raise PolicyError("B13.1 design not found as expected")
    if screening.get("phase") != "source_shortlist_only_not_a_candidate_cohort" or screening.get("candidate_set_frozen") is not False:
        raise PolicyError("B13.2 is no longer the unverified shortlist")
    validate_spec(spec)
    if examples.get("classification") != "hand_constructed_synthetic_policy_controls_not_independent_reference_truth":
        raise PolicyError("The cases must remain synthetic controls")
    summary = check_policy_invariants(examples.get("cases"))
    print("B13.3 PREFLIGHT PASS: three-arm *synthetic* policy behavior checked")
    print(f"Toy cases: {summary['toy_case_count']}; real candidate gate runs: 0; gold: 0")
    print("No B4 compiler integration; no source downloaded; no reviewer truth read; no results written")


if __name__ == "__main__":
    try:
        main()
    except (PolicyError, OSError, ValueError) as exc:
        print("B13.3 STOP:", exc, file=sys.stderr)
        raise SystemExit(2)
