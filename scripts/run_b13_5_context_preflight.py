"""B13.5: offline, toy-only B4/B3 context-key remediation preflight."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.b13_5_context_gate_v2 import ContextPolicyError, replay_toy_v2, validate_versioned_policy
from src.rule_bridge import compile_proposal
from src.generic_verifier import validate_rule


def run_preflight() -> None:
    policy = json.loads((ROOT / "data/evaluation/b13_5_context_policy_v2.json").read_text(encoding="utf-8-sig"))
    old = json.loads((ROOT / "data/evaluation/b13_3_gate_policy_v1.json").read_text(encoding="utf-8-sig"))
    cases = json.loads((ROOT / "data/evaluation/b13_4_compiler_contract_toys_v1.json").read_text(encoding="utf-8-sig"))["fixtures"]
    validate_versioned_policy(policy, old)
    if len(cases) != 5 or len({c.get("id") for c in cases}) != 5:
        raise ContextPolicyError("Frozen B13.4 toy fixture list changed")
    r = [replay_toy_v2(c, policy=policy, previous_policy=old,
                      compile_fn=compile_proposal, validate_rule_fn=validate_rule) for c in cases]
    exp = {
        "B134-TOY-COMPILED": ("candidate_executable_unverified", {"A":"admit","B":"admit","C":"admit"}),
        "B134-TOY-UNRESOLVED": ("blocked_unresolved", {"A":"block","B":"block","C":"block"}),
        "B134-TOY-INVALID": ("rejected_invalid", {"A":"block","B":"block","C":"block"}),
        "B134-TOY-UNKNOWN-METADATA": ("candidate_executable_unverified", {"A":"admit","B":"abstain","C":"abstain"}),
        "B134-TOY-MISSING-SCOPE": ("candidate_executable_unverified", {"A":"admit","B":"admit","C":"block"}),
    }
    for x in r:
        if (x["b4_status"],x["v2_arm_decisions"]) != exp[x["candidate_id"]]:
            raise ContextPolicyError("Frozen expected toy outcomes changed")
    changed = [x for x in r if x["previous_arm_decisions"]["C"] != x["v2_arm_decisions"]["C"]]
    if [x["candidate_id"] for x in changed] != ["B134-TOY-MISSING-SCOPE"] or changed[0]["missing_required_context_keys"] != ["site"]:
        raise ContextPolicyError("Required missing-context remediation not demonstrated")
    print("B13.5 PREFLIGHT PASS: versioned toy scope correction exercised using actual B4 and B3")
    print("5 frozen B13.4 toy candidates; 1 Arm C correction: undeclared site => block")
    print("Arms A and B unchanged; original B13.3/B13.4 files unchanged")
    print("No real candidates, no downloaded data, no reviewer labels, no gold, no manuscript changes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true", required=True)
    args = parser.parse_args()
    try:
        run_preflight()
    except (ContextPolicyError, OSError, KeyError, ValueError, TypeError) as exc:
        print("B13.5 STOP:", exc, file=sys.stderr)
        raise SystemExit(2)
