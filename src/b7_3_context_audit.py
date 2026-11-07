"""B7.3 retrospective audit of legacy SEC context decisions.

Design: inspect saved outputs, frozen catalogue and Python source; perform
explicit *counterfactual* control probes. No labels, model calls or raw rows.
This is not a comparison with a published discovery algorithm.
"""
from __future__ import annotations

import ast
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


class ContextAuditError(ValueError):
    """Study assumptions invalid; no defensible report can be generated."""


LEGACY_RELATIVE = "data/evaluation/b7_2_existing_dataonly_discovery.json"
CATALOGUE_RELATIVE = "data/evaluation/b6_reference_catalogue.json"
EVIDENCE_RELATIVE = "data/evidence/sec_constraints.json"
SOURCE_RELATIVE = "src/rule_discovery.py"
PLAN_RELATIVE = "data/evaluation/b7_3_plan_v1.json"
SCREEN_RELATIVE = "data/evaluation/b7_2_candidate_screen/summary.json"

REQUIRED = ("same entity", "same reporting date", "same accounting scope", "same currency")
TRI = ("supported", "unknown", "contradicted")
RULE_COLUMNS = ("Assets [USD]", "Liabilities [USD]", "StockholdersEquity [USD]")
TARGET_RULE_ID = "sec-companyfacts-320193-assets-usd-5829762e6f"


def sha_file(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for piece in iter(lambda: f.read(65536), b""):
            h.update(piece)
    return h.hexdigest()


def load_obj(path: Path) -> dict[str, Any]:
    v = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(v, dict):
        raise ContextAuditError(f"Expected JSON object: {path}")
    return v


def assert_legacy_hardcoding(code: str) -> dict[str, str]:
    """AST audit, not a string-match, to find the exact current legacy assignment."""
    tree = ast.parse(code)
    fns = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "run_discovery"]
    if len(fns) != 1:
        raise ContextAuditError("Cannot locate exactly one run_discovery function")
    blocks = []
    for node in ast.walk(fns[0]):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "context" for t in node.targets):
            if isinstance(node.value, ast.Dict):
                blocks.append(node.value)
    if len(blocks) != 1:
        raise ContextAuditError("Unexpected legacy context construction; manual code review required")
    pairs = {}
    for k, v in zip(blocks[0].keys, blocks[0].values):
        if not isinstance(k, ast.Constant) or not isinstance(k.value, str):
            raise ContextAuditError("Unexpected computed context key")
        pairs[k.value] = "hardcoded_true" if isinstance(v, ast.Constant) and v.value is True else "computed_expression"
    if set(pairs) != {"same-entity", "same-reporting-date", "same-accounting-scope", "same-currency"}:
        raise ContextAuditError("Legacy context schema changed")
    if pairs["same-accounting-scope"] != "hardcoded_true":
        raise ContextAuditError("Previously identified hard-coded accounting scope is no longer present")
    if pairs["same-reporting-date"] != "hardcoded_true":
        raise ContextAuditError("Previously identified hard-coded reporting date is no longer present")
    return pairs


def assert_target(legacy: dict[str, Any], catalogue: dict[str, Any], registry: dict[str, Any]):
    datasets = legacy.get("datasets")
    if not isinstance(datasets, dict) or set(datasets) != {"ai4i-2020", "sec-companyfacts-320193"}:
        raise ContextAuditError("Legacy mining datasets changed")
    counts = {}
    matched = []
    for name, info in datasets.items():
        candidates = info.get("candidates")
        if not isinstance(candidates, list) or len(candidates) != info.get("candidate_count"):
            raise ContextAuditError("Legacy candidate counts or records changed")
        ids = [x.get("rule", {}).get("id") for x in candidates]
        if len(set(ids)) != len(ids) or not all(isinstance(k, str) and k for k in ids):
            raise ContextAuditError("Duplicated/malformed candidate IDs")
        statuses = Counter(x.get("heldout", {}).get("decision") for x in candidates)
        if dict(statuses) != {k: v for k, v in info.get("decision_counts", {}).items() if v != 0}:
            raise ContextAuditError("Decision counts no longer agree with saved candidates")
        counts[name] = {"candidates": len(candidates), "legacy_decision_counts": dict(statuses)}
        matched.extend(x for x in candidates if x.get("heldout", {}).get("decision") == "documented_support")
    if len(matched) != 1 or matched[0]["rule"]["id"] != TARGET_RULE_ID:
        raise ContextAuditError("Expected exactly one known legacy supported candidate")
    item = matched[0]
    assertion = item["rule"]["assertion"]
    if (item["rule"].get("dataset_id") != "sec-companyfacts-320193" or
        assertion.get("op") != "sum_eq" or assertion.get("result_column") != RULE_COLUMNS[0] or
        assertion.get("term_columns") != list(RULE_COLUMNS[1:]) or assertion.get("tolerance") != 0):
        raise ContextAuditError("Supported candidate structure not the pinned study target")
    heldout = item.get("heldout", {})
    if heldout.get("applicable_rows") != 41 or heldout.get("violations") != 0:
        raise ContextAuditError("Saved held-out record observation changed")
    ev = item.get("documented_evidence", {})
    if ev.get("status") != "documented" or ev.get("requirements") != list(REQUIRED):
        raise ContextAuditError("Legacy documentary requirements changed")
    if set(ev.get("context_compatibility", {})) != set(REQUIRED) or not all(ev["context_compatibility"].values()):
        raise ContextAuditError("Legacy approved context flags changed")
    refs = registry.get("entries", [])
    matches = [x for x in refs if x.get("id") == "SEC-BALANCE-001"]
    if len(matches) != 1 or matches[0].get("requirements") != list(REQUIRED):
        raise ContextAuditError("SEC registry reference changed")
    ref = matches[0].get("assertion", {})
    if (ref.get("result_column") != assertion.get("result_column") or
            ref.get("term_columns") != assertion.get("term_columns") or
            ref.get("op") != "sum_eq" or ref.get("tolerance") != 0):
        raise ContextAuditError("Registry and legacy rule no longer identical")
    entries = catalogue.get("entries", [])
    excluded = [x for x in entries if x.get("id") == "B6-FIN-002"]
    if len(excluded) != 1 or excluded[0].get("status") != "excluded" or excluded[0].get("scoring_eligible") is not False:
        raise ContextAuditError("Pinned B6-FIN-002 exclusion missing/modified")
    if set(excluded[0].get("columns", [])) != {"Assets", "Liabilities", "StockholdersEquity"}:
        raise ContextAuditError("B6 exclusion does not apply to legacy candidate columns")
    return item, counts, excluded[0]


def context_only_decision(context: dict[str, str]) -> str:
    """Fail closed: true requires explicit *reviewed proof*, not a truthy boolean."""
    if not isinstance(context, dict) or set(context) != set(REQUIRED):
        raise ContextAuditError("Counterfactual context keys are incomplete")
    if any(v not in TRI for v in context.values()):
        raise ContextAuditError("Unknown context state")
    if "contradicted" in context.values():
        return "blocked_context_incompatible"
    if "unknown" in context.values():
        return "abstain_context_unsubstantiated"
    return "candidate_only_unverified"


def frozen_catalogue_decision(context_decision: str, *, excluded: bool) -> str:
    if excluded:
        return "blocked_unqualified_universal_identity"
    return context_decision


def controls() -> list[dict[str, Any]]:
    good = {k: "supported" for k in REQUIRED}
    cases = [{"id": "hypothetical_all_contexts_reviewed", "context": good.copy(),
              "nature": "counterfactual_hypothetical_not_real_data"}]
    for key in REQUIRED:
        for state in ("unknown", "contradicted"):
            ctx = good.copy()
            ctx[key] = state
            cases.append({"id": "counterfactual_" + key.replace(" ", "_") + "_" + state,
                          "context": ctx, "nature": "counterfactual_hypothetical_not_real_data"})
    cases.append({"id": "all_contexts_unknown_real_proof_not_available_in_saved_output",
                  "context": {k: "unknown" for k in REQUIRED},
                  "nature": "conservative_evaluation_of_saved_candidate_evidence"})
    return cases


def validate_plan(plan: dict[str, Any]) -> None:
    if (plan.get("study_id") != "b7_3_saved_sec_context_audit_v1"
            or plan.get("baseline_commit") != "40a7ddb"
            or plan.get("target_rule_id") != TARGET_RULE_ID
            or plan.get("independent_gold_available") is not False
            or plan.get("model_calls_allowed") is not False
            or plan.get("allowed_inputs") != [LEGACY_RELATIVE, CATALOGUE_RELATIVE, EVIDENCE_RELATIVE, SOURCE_RELATIVE, SCREEN_RELATIVE]):
        raise ContextAuditError("Study design changed; do not run with a silently changed plan")


def run(root: Path, *, preflight: bool = False) -> dict[str, Any]:
    root = root.resolve()
    plan = load_obj(root / PLAN_RELATIVE)
    validate_plan(plan)
    paths = {p: root / p for p in plan["allowed_inputs"]}
    for rel, path in paths.items():
        if not path.is_file():
            raise ContextAuditError(f"Required frozen study input missing: {rel}")
    legacy = load_obj(paths[LEGACY_RELATIVE])
    cat = load_obj(paths[CATALOGUE_RELATIVE])
    reg = load_obj(paths[EVIDENCE_RELATIVE])
    screen = load_obj(paths[SCREEN_RELATIVE])
    if screen.get("study_id") != "b7_2_four_domain_pair_screen_v1" or screen.get("scope") != "retrospective_previously_inspected_metadata_not_unseen":
        raise ContextAuditError("B7.2 screening lineage changed")
    source = paths[SOURCE_RELATIVE].read_text(encoding="utf-8-sig")
    assignments = assert_legacy_hardcoding(source)
    target, prior_counts, exclusion = assert_target(legacy, cat, reg)
    if preflight:
        return {"status": "PREFLIGHT_PASS", "candidate_id": target["rule"]["id"],
                "historical_rows": target["heldout"]["applicable_rows"],
                "source_hardcoding_detected": assignments}
    cases = []
    for case in controls():
        context_result = context_only_decision(case["context"])
        cases.append({**case,
                      "recorded_legacy_saved_decision": target["heldout"]["decision"],
                      "fail_closed_context_only": context_result,
                      "fail_closed_with_frozen_catalogue": frozen_catalogue_decision(context_result, excluded=True),
                      "accuracy_label": None})
    return {
        "study_id": plan["study_id"], "type": "retrospective_audit_plus_constructed_control_probes",
        "baseline_commit": plan["baseline_commit"],
        "plan_sha256": sha_file(root / PLAN_RELATIVE),
        "input_sha256": {rel: sha_file(p) for rel, p in paths.items()},
        "legacy_candidate_summary": prior_counts,
        "legacy_supported_rule": {
            "rule_id": target["rule"]["id"],
            "assertion": target["rule"]["assertion"],
            "stored_context_compatibility": target["documented_evidence"]["context_compatibility"],
            "recorded_heldout_rows": 41, "recorded_violations": 0,
            "recorded_decision": "documented_support",
            "source_reference_id": "SEC-BALANCE-001",
            "does_not_establish_true_context": True,
        },
        "static_source_audit": {
            "context_assignments": assignments,
            "finding": "Legacy registry check hard-codes reporting-date and accounting-scope flags to True. Earlier SEC grouping uses reporting end dates, but this flag is not a separate proof; matching accounting scope is not established."
        },
        "frozen_catalogue_crosscheck": {
            "reference_id": exclusion["id"],
            "reference_status": exclusion["status"],
            "reason": exclusion.get("exclusion_reason"),
            "scope": "Universal parent-only-equity identity excluded; no claim that each observed numeric equality is false.",
        },
        "conservative_saved_candidate_decisions": {
            "without_new_context_proof": "abstain_context_unsubstantiated",
            "with_frozen_B6_universal_exclusion": "blocked_unqualified_universal_identity",
            "is_independently_verified": False,
        },
        "constructed_control_cases": cases,
        "constructed_control_summary": {
            "count": len(cases),
            "context_only_counts": dict(Counter(x["fail_closed_context_only"] for x in cases)),
            "catalogue_aware_counts": dict(Counter(x["fail_closed_with_frozen_catalogue"] for x in cases)),
            "is_real_data_accuracy_experiment": False,
        },
        "scientific_limits": [
            "The comparison is retrospective; B6.3 independent adjudication remains empty.",
            "The B6 catalogue exclusion was already known; this is not new external ground truth.",
            "41/41 exact arithmetic matches do not demonstrate semantically valid reporting scope or independent gold precision.",
            "Controlled scenario counts reflect our constructed cases and policy definitions, not measured natural error rates.",
            "No new original-data access, published discovery baseline, prospective LLM outputs or independently established label.",
            "The strict audit is a diagnostic policy simulation, not a deployment-ready refactoring of the legacy miner.",
        ],
        "independently_adjudicated_gold_rules": 0,
        "precision": None, "recall": None, "natural_defect_confirmations": 0,
    }
