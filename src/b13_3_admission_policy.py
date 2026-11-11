"""B13.3 synthetic-only three-arm decision semantics; NO real source or B4 adapter.

A decision of 'admit' means inclusion by an experimental arm only, NEVER
production deployment or independently validated semantic truth.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

STUDY = "b13_3_three_arm_admission_policy_spec_v1"
ARMS = {"A": "compiler_only", "B": "compiler_plus_metadata", "C": "compiler_plus_metadata_plus_document_and_context"}
SIGNALS = {"supported", "unknown", "contradicted"}
COMPILER = {"compiled", "blocked", "unknown"}
DECISIONS = {"admit", "abstain", "block"}


class PolicyError(ValueError):
    """Invalid input or a nonconforming policy specification."""


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def validate_spec(spec: dict) -> None:
    if not isinstance(spec, dict) or spec.get("study_id") != STUDY:
        raise PolicyError("Incorrect policy study ID")
    if spec.get("parent_study") != "b13_prospective_matched_evidence_gate_v1":
        raise PolicyError("Incorrect parent study")
    if spec.get("phase") != "synthetic_protocol_validation_only":
        raise PolicyError("Spec is not synthetic-only")
    if spec.get("status") != "not_integrated_with_real_compiler_or_source_evidence":
        raise PolicyError("Cannot mark adapter integrated")
    if spec.get("arm_order") != list(ARMS):
        raise PolicyError("Arm order modified")
    if spec.get("arm_definitions") != ARMS:
        raise PolicyError("Arm definitions modified")
    for name in ("input_truth_not_available", "known_development_inputs_excluded_from_confirmatory_scoring", "same_candidate_compiler_and_registry_all_arms", "policy_evidence_separate_from_blinded_reference_adjudication"):
        if spec.get(name) is not True:
            raise PolicyError(f"Required safeguard not asserted: {name}")
    if spec.get("statuses") != {"signal": ["supported", "unknown", "contradicted"], "compiler": ["compiled", "blocked", "unknown"], "decision": ["admit", "abstain", "block"]}:
        raise PolicyError("Status vocabulary modified")
    integrity = spec.get("evidence_integrity", {})
    for name in ("documentary_requires_https_url_and_locator", "documentary_supported_requires_separate_verified_flag", "every_required_context_must_have_an_explicit_signal", "context_names_frozen_before_candidate_outcomes", "evidence_verification_flag_does_not_prove_semantic_truth"):
        if integrity.get(name) is not True:
            raise PolicyError("Missing evidence safeguard")
    if spec.get("allowed_claims") != ["synthetic_policy_behavior_locally_tested"]:
        raise PolicyError("Invalid allowed claims")
    required_denials = {"prospective_accuracy_result", "real_candidate_gate_executed", "independent_source_evidence_verified", "adjudicated_reference_truth_available", "clinical_or_financial_validity_established", "published_discovery_baseline_beaten"}
    if not required_denials.issubset(set(spec.get("disallowed_claims", []))):
        raise PolicyError("Missing claim prohibitions")


def _signal(value: object, field: str) -> str:
    if not isinstance(value, str) or value not in SIGNALS:
        raise PolicyError(f"Invalid {field} signal")
    return str(value)


def validate_case(case: dict) -> None:
    if not isinstance(case, dict) or set(case) != {"candidate_id", "compiler", "metadata", "documentary", "required_contexts", "context_evidence"}:
        raise PolicyError("Invalid synthetic case shape")
    if not isinstance(case["candidate_id"], str) or not case["candidate_id"].strip():
        raise PolicyError("Candidate ID missing")
    if case["compiler"] not in COMPILER:
        raise PolicyError("Unknown compiler result")
    _signal(case["metadata"], "metadata")
    doc = case["documentary"]
    if not isinstance(doc, dict) or set(doc) != {"status", "verified", "evidence_url", "evidence_locator"}:
        raise PolicyError("Documentary structure invalid")
    _signal(doc["status"], "documentary")
    if type(doc["verified"]) is not bool:
        raise PolicyError("Documentary verification flag invalid")
    if doc["verified"] and doc["status"] != "supported":
        raise PolicyError("Only supported documentary evidence can be marked verified")
    if not isinstance(doc["evidence_url"], str) or not isinstance(doc["evidence_locator"], str):
        raise PolicyError("Documentary locator types invalid")
    if doc["status"] == "supported":
        parsed = urlparse(doc["evidence_url"])
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or not doc["evidence_locator"].strip()):
            raise PolicyError("Supported documentary signal requires HTTPS URL and locator")
    req = case["required_contexts"]
    if not isinstance(req, list) or not req or any(not isinstance(x, str) or not x.strip() for x in req) or len(req) != len(set(req)):
        raise PolicyError("Required contexts must be a nonempty unique list")
    ctx = case["context_evidence"]
    if not isinstance(ctx, dict) or not set(ctx).issubset(set(req)):
        raise PolicyError("Context evidence keys differ from frozen required contexts")
    for name, status in ctx.items():
        _signal(status, f"context {name}")


def evaluate_three_arms(case: dict) -> dict[str, str]:
    """Deterministic *toy-adapter* policy evaluation. Does not invoke a compiler."""
    validate_case(case)
    compilation = case["compiler"]
    if compilation == "blocked":
        return {a: "block" for a in ARMS}
    if compilation == "unknown":
        return {a: "abstain" for a in ARMS}
    decisions = {"A": "admit", "B": "admit", "C": "admit"}
    m = case["metadata"]
    if m == "contradicted":
        decisions["B"] = "block"
        decisions["C"] = "block"
        return decisions
    if m == "unknown":
        decisions["B"] = "abstain"
        decisions["C"] = "abstain"
        return decisions
    # Preserve contradictions over unknowns, including when both occur.
    doc = case["documentary"]
    required = case["required_contexts"]
    values = [case["context_evidence"].get(name, "unknown") for name in required]
    if doc["status"] == "contradicted" or "contradicted" in values:
        decisions["C"] = "block"
    elif doc["status"] == "unknown" or not doc["verified"] or "unknown" in values:
        decisions["C"] = "abstain"
    return decisions


def check_policy_invariants(cases: list[dict]) -> dict:
    if not isinstance(cases, list) or not cases:
        raise PolicyError("Synthetic cases missing")
    observed = set()
    aggregate = {arm: {status: 0 for status in ("admit", "abstain", "block")} for arm in ARMS}
    for case in cases:
        if case.get("candidate_id") in observed:
            raise PolicyError("Duplicate synthetic candidate ID")
        observed.add(case["candidate_id"])
        outcomes = evaluate_three_arms(case)
        if not (set(outcomes) == set(ARMS) and all(x in DECISIONS for x in outcomes.values())):
            raise PolicyError("Invalid outcomes")
        # Nested admission sets are structural policy invariants, not measured accuracy.
        if outcomes["C"] == "admit" and outcomes["B"] != "admit":
            raise PolicyError("Arm C admitted where B did not")
        if outcomes["B"] == "admit" and outcomes["A"] != "admit":
            raise PolicyError("Arm B admitted where A did not")
        for arm, outcome in outcomes.items():
            aggregate[arm][outcome] += 1
    return {"toy_case_count": len(cases), "toy_decision_counts": aggregate,
            "real_source_inputs": 0, "real_candidate_gate_runs": 0,
            "adjudicated_gold_rules": 0, "semantic_accuracy_defined": False}
