"""B13.4: fail-closed B4->B13.3 bridge for TOY contract checks ONLY.

Does not establish semantic validity, documentary truth, source eligibility,
independent reference labels, or actual prospective experiment results.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from src.b13_3_admission_policy import PolicyError, evaluate_three_arms

KNOWN_B4 = {
    "candidate_executable_unverified": "compiled",
    "blocked_unresolved": "blocked",
    "rejected_invalid": "blocked",
}

class AdapterError(ValueError):
    """B4 compilation cannot be safely interpreted for B13."""


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def normalize_b4_compilation(result: Any, proposal: Mapping[str, Any],
                              allowed_columns: list[str], *, validate_rule_fn: Any) -> dict[str, Any]:
    """Map the actual B4 Compilation contract. Unexpected statuses fail closed."""
    if not isinstance(proposal, Mapping) or not isinstance(proposal.get("id"), str):
        raise AdapterError("Expected a versioned typed B4 proposal")
    if not isinstance(allowed_columns, list) or not allowed_columns or len(set(allowed_columns)) != len(allowed_columns):
        raise AdapterError("Allowed columns must be a nonempty unambiguous list")
    status = getattr(result, "status", None)
    if status not in KNOWN_B4:
        raise AdapterError(f"Unrecognized B4 status: {status!r}; no permissive fallback")
    payload = result.as_dict() if callable(getattr(result, "as_dict", None)) else None
    if not isinstance(payload, dict) or payload.get("status") != status:
        raise AdapterError("Missing/contradictory B4 compilation audit payload")
    if payload.get("semantic_verified") is not False or payload.get("data_errors_adjudicated") is not False:
        raise AdapterError("B4 compiled output must not claim semantic truth or adjudicated data errors")
    if getattr(result, "proposal_id", None) != proposal["id"]:
        raise AdapterError("B4 proposal ID changed between input and compilation")
    rule = getattr(result, "rule", None)
    if status == "candidate_executable_unverified":
        if not isinstance(rule, dict):
            raise AdapterError("B4 claimed compilation but provided no typed executable rule")
        if rule.get("id") != proposal["id"] or rule.get("dataset_id") != proposal.get("dataset_id"):
            raise AdapterError("Compiled rule's identity differs from source proposal")
        if rule.get("context_keys") != proposal.get("context_keys", []):
            raise AdapterError("Compiled rule's reporting contexts differ from proposal")
        if rule.get("evidence_status") != "candidate_unverified":
            raise AdapterError("B4 rule must remain explicitly semantically unverified")
        try:
            refs = validate_rule_fn(rule)
        except (ValueError, TypeError, KeyError) as exc:
            raise AdapterError("B3 rejected B4 compiled rule") from exc
        if not isinstance(refs, set) or not refs.issubset(set(allowed_columns)):
            raise AdapterError("B3 returned unexpected referenced columns")
    elif rule is not None:
        raise AdapterError("B4 blocked/rejected result contains a compiled rule")
    return {"compiler": KNOWN_B4[status], "b4_status": status,
            "has_executable_rule": status == "candidate_executable_unverified",
            "semantic_truth_established": False,
            "reference_labels_present": False}


def toy_three_arm_replay(fixture: dict, *, compile_fn: Any, validate_rule_fn: Any) -> dict[str, Any]:
    """Call B4 exactly once, then feed one unchanged result to three B13.3 arms.

    The fixture-only guard deliberately prevents accidental candidate evaluation.
    Future real evaluation requires a separately reviewed protocol and driver.
    """
    if not isinstance(fixture, dict) or set(fixture) != {
        "id", "classification", "proposal", "allowed_columns", "registry", "policy_evidence"
    }:
        raise AdapterError("Invalid toy fixture schema")
    if fixture["classification"] != "toy_structure_only_not_real_source":
        raise AdapterError("Refusing real input: B13.4 is synthetic interface preflight only")
    proposal = fixture["proposal"]
    allowed = fixture["allowed_columns"]
    registry = fixture["registry"]
    evidence = fixture["policy_evidence"]
    if not isinstance(proposal, dict) or not isinstance(registry, dict) or not isinstance(evidence, dict):
        raise AdapterError("Expected typed dictionaries in toy input")
    expected_evidence = {"metadata", "documentary", "required_contexts", "context_evidence"}
    if set(evidence) != expected_evidence:
        raise AdapterError("Policy evidence fields differ from frozen B13.3 contract")
    if proposal.get("id") != fixture["id"]:
        raise AdapterError("Toy case ID differs from proposal ID")
    # B4 has explicit no-API/no-eval compilation and remains the only AST compiler.
    result = compile_fn(proposal, allowed, registry)
    adapter = normalize_b4_compilation(result, proposal, allowed, validate_rule_fn=validate_rule_fn)
    case = {"candidate_id": fixture["id"], "compiler": adapter["compiler"], **evidence}
    try:
        outcomes = evaluate_three_arms(case)
    except PolicyError as exc:
        raise AdapterError("B13.3 rejected adapter-generated decision inputs") from exc
    if outcomes["C"] == "admit" and outcomes["B"] != "admit":
        raise AdapterError("Nested B13.3 arm invariant failed")
    if outcomes["B"] == "admit" and outcomes["A"] != "admit":
        raise AdapterError("Nested B13.3 arm invariant failed")
    # Guard against false equivalence: context evidence != B4 context fields.
    required = set(evidence["required_contexts"])
    declared = set(proposal.get("context_keys", []))
    scope_mismatch = sorted(required - declared)
    return {"id": fixture["id"], "classification": "toy_compiler_adapter_contract_only",
            "b4_status": adapter["b4_status"], "b13_compiler": adapter["compiler"],
            "arm_decisions": outcomes, "context_key_gap": scope_mismatch,
            "study_ready": False, "semantic_accuracy_defined": False,
            "fixture_input_sha256": _stable_hash({"proposal": proposal, "allowed_columns": allowed,
                                                   "registry": registry, "policy_evidence": evidence})}
