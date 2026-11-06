"""B5.1: auditable *post-hoc* gate for B5 model hypotheses.

No API, raw-data access, document fetching, or model calls. The policy and
parameter registries are curator-provided and do not prove semantic entailment.
B4 remains the only compiler; B3 remains the only executable interpreter.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from src.rule_bridge import PROPOSAL_VERSION, compile_proposal
from src.generic_verifier import validate_rule

POLICY_VERSION = "metaverify-evidence-review-v0.1"


def _stable_hash(obj: Any) -> str:
    return sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False).encode("utf-8")).hexdigest()


def _output(status: str, pid: str, reasons: list[str], *, baseline: str | None,
            provenance: dict[str, Any] | None = None,
            compiled: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "proposal_id": pid,
        "status": status,
        "reasons": reasons,
        "b5_original_compilation_status": baseline,
        "compiled_rule": compiled,
        "parameter_provenance": provenance or {},
        "semantically_verified": False,
        "independently_validated": False,
        "confirmed_data_errors": False,
        "safe_to_deploy_as_integrity_constraint": False,
    }


def _literal_column_refs(value: Any, *, depth: int = 0) -> set[str]:
    if depth > 15:
        raise ValueError("overly nested proposal")
    if isinstance(value, dict):
        own = {value["column"]} if set(value) == {"column"} and isinstance(value["column"], str) else set()
        for child in value.values():
            own.update(_literal_column_refs(child, depth=depth + 1))
        return own
    if isinstance(value, list):
        refs: set[str] = set()
        for child in value:
            refs.update(_literal_column_refs(child, depth=depth + 1))
        return refs
    return set()


def _validate_passages(rule: Mapping[str, Any], bundle: Mapping[str, Any]) -> str | None:
    citations = rule.get("passage_ids")
    if not isinstance(citations, list) or not all(isinstance(p, str) for p in citations):
        return "invalid passage IDs"
    defined = {p["id"] for p in bundle["passages"]
               if p.get("description") != "NO DOCUMENTED DEFINITION"}
    if any(pid not in defined for pid in citations):
        return "citation references an unknown or undocumented passage"
    return None


def _assert_catalog(catalog: Mapping[str, Any], registry: Mapping[str, Any]) -> None:
    if catalog.get("policy_version") != POLICY_VERSION:
        raise ValueError("unsupported B5.1 policy version")
    if catalog.get("development_stage") != "posthoc_case_study_policy_developed_after_inspecting_luna_outputs":
        raise ValueError("policy must disclose post-hoc calibration")
    if not isinstance(catalog.get("domain_policies"), dict):
        raise ValueError("domain_policies required")
    if not isinstance(catalog.get("binding_authorizations"), list):
        raise ValueError("binding_authorizations required")
    if not isinstance(registry, dict):
        raise ValueError("B4 parameter registry required")


def review_report(report: Mapping[str, Any], catalog: Mapping[str, Any],
                  original_registry: Mapping[str, Any]) -> dict[str, Any]:
    """Review one saved B5 output, never rewriting the model output.

    A compiled rule remains unverified. No registration is inferred from a
    variable name, and required contexts come from external policy, not a model.
    """
    _assert_catalog(catalog, original_registry)
    if not isinstance(report, dict):
        raise ValueError("B5 report must be a dict")
    domain = report.get("domain")
    dataset = report.get("dataset_id")
    bundle = report.get("input_bundle")
    payload = report.get("output")
    if (report.get("response_status") != "completed" or report.get("error") is not None or
        not isinstance(bundle, dict) or bundle.get("dataset_id") != dataset or
        bundle.get("domain") != domain or not isinstance(bundle.get("passages"), list) or
        not isinstance(payload, dict) or not isinstance(payload.get("rules"), list)):
        raise ValueError("B5 response incomplete or inconsistent with its input bundle")
    if len(payload["rules"]) > 2:
        raise ValueError("B5 protocol permits at most two proposals per response")
    policy = catalog["domain_policies"].get(dataset)
    if policy is not None and not isinstance(policy.get("required_context_keys"), list):
        raise ValueError("policy requires explicit context list")
    allowed = [p["column"] for p in bundle["passages"]]
    if len(set(allowed)) != len(allowed):
        raise ValueError("ambiguous column names in input bundle")
    original = report.get("compile_results", [])
    if not isinstance(original, list):
        raise ValueError("invalid B5 compile_results")
    statuses = {}
    for item in original:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            statuses[item["id"]] = (item.get("compilation") or {}).get("status", item.get("status"))
    decisions = []
    for i, item in enumerate(payload["rules"]):
        if not isinstance(item, dict):
            decisions.append(_output("rejected_invalid", f"item-{i}", ["non-object rule"], baseline=None))
            continue
        pid = item.get("id")
        if not isinstance(pid, str) or not pid:
            decisions.append(_output("rejected_invalid", f"item-{i}", ["missing ID"], baseline=None))
            continue
        base = statuses.get(pid)
        citation_error = _validate_passages(item, bundle)
        if citation_error:
            decisions.append(_output("rejected_invalid", pid, [citation_error], baseline=base))
            continue
        if policy is None:
            decisions.append(_output("blocked_no_curator_policy", pid,
                                     [f"no curator applicability policy for {dataset}"], baseline=base))
            continue
        required = policy["required_context_keys"]
        model_context = item.get("context_keys")
        if not isinstance(model_context, list) or any(not isinstance(k, str) for k in model_context):
            decisions.append(_output("rejected_invalid", pid, ["invalid context key list"], baseline=base))
            continue
        reasons = []
        missing_context = [k for k in required if k not in model_context]
        if missing_context:
            reasons.append("model omitted required reporting contexts: " + ", ".join(missing_context))
        refs = _literal_column_refs(item.get("assertions"))
        for veto in policy.get("semantic_vetoes", []):
            if refs == set(veto["exact_columns"]):
                reasons.append("semantic scope unresolved: " + veto["reason"])
        if reasons:
            decisions.append(_output("blocked_applicability_or_scope", pid, reasons, baseline=base))
            continue
        # B5 typed JSON contains nullable fields; B4 expects optional *absence*.
        original_assertions = item.get("assertions")
        if not isinstance(original_assertions, list):
            decisions.append(_output("rejected_invalid", pid, ["no structured assertions"], baseline=base))
            continue
        clean = [{k: v for k, v in a.items() if v is not None} if isinstance(a, dict) else a
                 for a in original_assertions]
        proposal = {
            "proposal_version": PROPOSAL_VERSION, "id": pid,
            "dataset_id": dataset, "origin": report.get("model_id_requested", "unknown") + "_B5.1_posthoc",
            "assertions": clean, "context_keys": model_context,
        }
        if item.get("when") is not None:
            proposal["when"] = item["when"]
        # Critical: only an EXACT observed rule structure can be mapped by an
        # explicit manual authorization. Do not match on name or domain alone.
        registry = {}
        binding_note = "none; model variables are unresolved by default"
        for grant in catalog["binding_authorizations"]:
            if grant.get("dataset_id") != dataset or grant.get("rule_id") != pid:
                continue
            shape = {key: item.get(key) for key in
                     ("assertions", "when", "context_keys", "passage_ids")}
            if shape != grant["expected_structure"]:
                reasons.append("manual binding refused: rule structure differs from authorized snapshot")
                continue
            # Match documentary *metadata input*, not just the model's output
            # expression. This does not entail that cited passages prove a rule.
            passages_by_id = {p.get("id"): p for p in bundle["passages"] if isinstance(p, dict)}
            expected_evidence = grant.get("expected_evidence_passages", [])
            if not expected_evidence or any(
                any(passages_by_id.get(p["id"], {}).get(k) != p[k]
                    for k in ("column", "description", "source"))
                for p in expected_evidence
            ):
                reasons.append("manual binding refused: evidence passage snapshot changed or is missing")
                continue
            for model_param, registered_name in grant["parameter_map"].items():
                entry = original_registry.get(registered_name)
                if not isinstance(entry, dict):
                    reasons.append(f"curated parameter {registered_name} missing from B4 registry")
                    continue
                if registered_name != f"{dataset}:{registered_name.split(':')[-1]}":
                    reasons.append("curated parameter crosses dataset boundary")
                    continue
                registry[f"{dataset}:{model_param}"] = deepcopy(entry)
            binding_note = grant["authorization"]
            break
        if reasons:
            decisions.append(_output("blocked_unresolved", pid, reasons, baseline=base))
            continue
        result = compile_proposal(proposal, allowed, registry)
        if result.rule is not None:
            try:
                validate_rule(result.rule)
            except (ValueError, TypeError) as exc:
                decisions.append(_output("rejected_invalid", pid, [f"B3 validation: {exc}"], baseline=base))
                continue
        if result.status == "candidate_executable_unverified":
            decisions.append(_output("compiled_unverified_posthoc", pid,
                                    ["B4 structurally compiled; no independently established semantic acceptance",
                                     f"parameter authorization: {binding_note}"],
                                    baseline=base, provenance=result.parameter_provenance,
                                    compiled=result.rule))
        else:
            decisions.append(_output(result.status, pid,
                                     [result.reason, f"parameter authorization: {binding_note}"],
                                     baseline=base, provenance=result.parameter_provenance))
    return {
        "domain": domain, "dataset_id": dataset,
        "model": report.get("model_id_requested"),
        "request_sha256": report.get("request_sha256"),
        "input_bundle_sha256": _stable_hash(bundle),
        "policy_sha256": _stable_hash(catalog),
        "policy_development_stage": catalog["development_stage"],
        "scope": "Local post-hoc evidence/applicability review; not blinded model evaluation",
        "decisions": decisions,
        "warning": "Manual bindings do NOT constitute automatic parameter discovery or independent rule validation."
    }


def load_policy(root: Path, policy_path: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    filepath = policy_path or root / "data/rules/b5_1_review_policy.json"
    policy = json.loads(filepath.read_text(encoding="utf-8-sig"))
    regfile = root / policy["registry_file"]
    base = json.loads(regfile.read_text(encoding="utf-8-sig"))
    return policy, base["registrations"]
