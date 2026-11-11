"""Run an actual B4->B13.3 interface smoke test with toy inputs only."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.b13_3_admission_policy import load_json, validate_spec  # noqa E402
from src.b13_4_b4_adapter import AdapterError, toy_three_arm_replay  # noqa E402
from src.rule_bridge import compile_proposal  # noqa E402
from src.generic_verifier import validate_rule  # noqa E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true", required=True)
    args = parser.parse_args()
    validate_spec(load_json(ROOT / "data/evaluation/b13_3_gate_policy_v1.json"))
    payload = json.loads((ROOT / "data/evaluation/b13_4_compiler_contract_toys_v1.json").read_text(encoding="utf-8"))
    if payload.get("study_id") != "b13_4_b4_compiler_adapter_toy_contract_v1" or payload.get("status") != "synthetic_only_no_real_candidates":
        raise AdapterError("B13.4 fixture provenance mismatch")
    fixtures = payload.get("fixtures")
    if not isinstance(fixtures, list) or len(fixtures) != 5 or len({x.get("id") for x in fixtures}) != 5:
        raise AdapterError("Expected 5 unique frozen toy fixture IDs")
    results = [toy_three_arm_replay(f, compile_fn=compile_proposal, validate_rule_fn=validate_rule) for f in fixtures]
    expected = {
        "B134-TOY-COMPILED": ("candidate_executable_unverified", {"A":"admit", "B":"admit", "C":"admit"}, []),
        "B134-TOY-UNRESOLVED": ("blocked_unresolved", {"A":"block", "B":"block", "C":"block"}, []),
        "B134-TOY-INVALID": ("rejected_invalid", {"A":"block", "B":"block", "C":"block"}, []),
        "B134-TOY-UNKNOWN-METADATA": ("candidate_executable_unverified", {"A":"admit", "B":"abstain", "C":"abstain"}, []),
        "B134-TOY-MISSING-SCOPE": ("candidate_executable_unverified", {"A":"admit", "B":"admit", "C":"admit"}, ["site"]),
    }
    for r in results:
        exp = expected[r["id"]]
        if (r["b4_status"], r["arm_decisions"], r["context_key_gap"]) != exp:
            raise AdapterError("B13.4 toy replay drift from frozen expectations")
    print("B13.4 PREFLIGHT PASS: actual B4 and B3 interfaces exercised on 5 toy candidates")
    print("B4 statuses: 3 compiled; 1 unresolved; 1 invalid; real candidates: 0")
    print("SAFETY BLOCKER: one toy shows Arm C can admit despite undeclared required rule context")
    print("No new source data, independent documentary evidence, real gate results, or gold labels")
    print("No file written; no model call; Overleaf and shared main untouched")

if __name__ == "__main__":
    try:
        main()
    except (AdapterError, ValueError, OSError, KeyError) as exc:
        print("B13.4 STOP:", exc, file=sys.stderr)
        raise SystemExit(2)
