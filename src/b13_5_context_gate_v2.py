"""B13.5: additive, toy-only remediation of missing B4 rule context declarations.

The original B13.3 policy and B13.4 diagnostic remain unchanged.
B13.5 does not verify documents, independent gold, or real candidates.
"""
from __future__ import annotations

import json
import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.b13_3_admission_policy import evaluate_three_arms, PolicyError
from src.b13_4_b4_adapter import AdapterError, normalize_b4_compilation

POLICY_ID = "b13_5_context_declaration_policy_v2"
ARMS = {"A":"compiler_only", "B":"compiler_plus_metadata", "C":"compiler_plus_metadata_plus_document_and_context"}
FIXTURE_CLASS = "toy_structure_only_not_real_source"

class ContextPolicyError(ValueError):
    """Inconsistent toy input, policy drift, or compiler contract violation."""


def canonical_sha256(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                  ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def validate_versioned_policy(policy: dict, previous_policy: dict) -> None:
    if not isinstance(policy, dict) or not isinstance(previous_policy, dict):
        raise ContextPolicyError("Versioned policy and original policy required")
    if policy.get("study_id") != POLICY_ID or policy.get("status") != "synthetic_scope_remediation_not_real_evaluation":
        raise ContextPolicyError("Unknown B13.5 version/status")
    if policy.get("parent_study_id") != "b13_prospective_matched_evidence_gate_v1":
        raise ContextPolicyError("Unexpected parent study")
    ancestry = policy.get("policy_ancestry", {})
    if (ancestry.get("b13_3_policy_study_id") != "b13_3_three_arm_admission_policy_spec_v1"
            or ancestry.get("b13_3_policy_canonical_sha256") != canonical_sha256(previous_policy)
            or ancestry.get("b13_4_adapter_finding") != "undeclared_required_rule_context_admitted_by_arm_C_in_synthetic_toy"):
        raise ContextPolicyError("Frozen B13.3 ancestry mismatch")
    if policy.get("arms") != ARMS:
        raise ContextPolicyError("Policy arm mapping changed")
    if policy.get("context_source") != "external_predeclared_policy_not_model_or_compiler_output":
        raise ContextPolicyError("Context source may not derive from candidate or compiler")
    if policy.get("frozen_toy_required_contexts_by_dataset") != {"b134-toy": ["site"]}:
        raise ContextPolicyError("Frozen toy context obligations changed")
    expected = {"missing_predeclared_required_compiled_context":"block",
                "unreviewed_extra_compiled_context":"abstain",
                "all_required_declared_with_explicit_supported_evidence":"retain_B13_3_evidence_decision",
                "contradicted_context_or_document":"block",
                "missing_context_evidence":"abstain"}
    if policy.get("arm_C_rule_context_policy") != expected:
        raise ContextPolicyError("Required B13.5 fail-closed behaviour changed")
    for key in ("original_policy_unchanged", "only_toy_b4_compiler_and_b3_validator_calls"):
        if policy.get(key) is not True:
            raise ContextPolicyError(f"Missing prerequisite: {key}")
    for key in ("real_candidate_execution_allowed", "reviewer_truth_read", "source_documents_verified"):
        if policy.get(key) is not False:
            raise ContextPolicyError(f"Unsupported evaluation claim: {key}")
    for key in ("source_cohorts_eligible", "adjudicated_gold_rules"):
        if type(policy.get(key)) is not int or policy[key] != 0:
            raise ContextPolicyError(f"Unexpected research status for {key}")
    if policy.get("allowed_claims") != ["synthetic_scope_gap_fixed_in_versioned_toy_policy"]:
        raise ContextPolicyError("Invalid permitted claim")
    required_denials = {"prospective_gate_effect", "source_document_truth", "natural_error_detection_accuracy", "production_safety", "adjudicated_gold", "real_candidate_gate_execution"}
    if set(policy.get("disallowed_claims", [])) != required_denials:
        raise ContextPolicyError("Invalid barred claims")


def replay_toy_v2(fixture: dict, *, policy: dict, previous_policy: dict,
                  compile_fn: Any, validate_rule_fn: Any) -> dict[str, Any]:
    """Compile once and apply B13.3 decisions plus B13.5 context-key guard.

    The policy's external (toy) context requirement is not inferred from a model.
    Arm A and B decisions remain exactly those of B13.3.
    """
    validate_versioned_policy(policy, previous_policy)
    if not isinstance(fixture, dict) or set(fixture) != {
            "id", "classification", "proposal", "allowed_columns", "registry", "policy_evidence"}:
        raise ContextPolicyError("Invalid toy fixture keys")
    if fixture.get("classification") != FIXTURE_CLASS:
        raise ContextPolicyError("Refusing real or non-toy candidate evaluation")
    proposal = fixture.get("proposal")
    evidence = fixture.get("policy_evidence")
    if not isinstance(proposal, dict) or not isinstance(evidence, dict) or not isinstance(fixture.get("registry"), dict):
        raise ContextPolicyError("Missing typed proposal/evidence/registry")
    if proposal.get("id") != fixture.get("id"):
        raise ContextPolicyError("Candidate identity mismatch")
    dataset = proposal.get("dataset_id")
    required_by_dataset = policy["frozen_toy_required_contexts_by_dataset"]
    if dataset not in required_by_dataset:
        raise ContextPolicyError("Dataset not in predeclared toy source-context policy")
    required = required_by_dataset[dataset]
    if not isinstance(required, list) or len(set(required)) != len(required):
        raise ContextPolicyError("Invalid frozen required contexts")
    if set(evidence) != {"metadata", "documentary", "required_contexts", "context_evidence"}:
        raise ContextPolicyError("Unexpected policy evidence keys")
    if evidence.get("required_contexts") != required:
        raise ContextPolicyError("Candidate-supplied required contexts differ from frozen source policy")
    try:
        # Actual B4 call performed exactly once for all three arms.
        result = compile_fn(proposal, fixture["allowed_columns"], fixture["registry"])
        adapter = normalize_b4_compilation(result, proposal, fixture["allowed_columns"],
                                            validate_rule_fn=validate_rule_fn)
        base = evaluate_three_arms({"candidate_id":fixture["id"],
                                   "compiler":adapter["compiler"], **evidence})
    except (AdapterError, PolicyError, ValueError, TypeError, KeyError) as exc:
        raise ContextPolicyError("B4/B3/B13.3 contract failed closed") from exc
    decisions = dict(base)
    declared = []
    missing, extra = [], []
    reason = "compiled rule contexts evaluated under frozen toy source policy"
    if adapter["compiler"] == "compiled":
        rule = result.rule
        if not isinstance(rule, dict) or not isinstance(rule.get("context_keys"), list):
            raise ContextPolicyError("Compiled rule is missing context list")
        declared = rule["context_keys"]
        if any(not isinstance(k,str) or not k for k in declared) or len(declared) != len(set(declared)):
            raise ContextPolicyError("Compiled rule has malformed context keys")
        missing = sorted(set(required)-set(declared))
        extra = sorted(set(declared)-set(required))
        # Missing required keys is a structural scope mismatch, not merely an
        # absent documentary record; C may not admit, even when evidence says supported.
        if missing:
            decisions["C"] = "block"
            reason = "required context omitted from executable rule"
        elif extra and decisions["C"] != "block":
            # Extra keys may be legitimate, but no frozen source policy evaluates them.
            decisions["C"] = "abstain"
            reason = "extra executable context lacks frozen applicability review"
    if decisions["B"] != base["B"] or decisions["A"] != base["A"]:
        raise ContextPolicyError("Compiler-only/metadata arms must stay unchanged")
    if (decisions["C"] == "admit" and decisions["B"] != "admit"
            or decisions["B"] == "admit" and decisions["A"] != "admit"):
        raise ContextPolicyError("Nested admission invariant violated")
    return {
        "candidate_id": fixture["id"], "classification": "synthetic_scope_remediation_preflight_only",
        "b4_status": adapter["b4_status"], "previous_arm_decisions":base,
        "v2_arm_decisions":decisions, "frozen_required_contexts": list(required),
        "compiled_declared_contexts":list(declared),
        "missing_required_context_keys":missing, "unreviewed_extra_context_keys":extra,
        "arm_C_change_reason":reason if decisions["C"] != base["C"] else None,
        "input_sha256":canonical_sha256({"proposal":proposal,"allowed_columns":fixture["allowed_columns"],
                                            "registry":fixture["registry"],"policy_evidence":evidence}),
        "real_candidate_gate_runs":0, "adjudicated_gold_rules":0,
        "semantic_accuracy_defined":False, "study_ready":False,
    }
