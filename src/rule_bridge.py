"""B4: Safe, domain-neutral bridge from structured *hypotheses* to B3 rules.

Inputs are typed JSON objects, not natural language or executable Python.
This module cannot establish semantic truth, validate a source's contents,
calibrate precision independently, or certify observed data errors.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

PROPOSAL_VERSION = "metaverify-proposal-v0.1"
EXEC_VERSION = "metaverify-exec-v0.1"
COMPARATORS = {"eq", "ne", "lt", "lte", "gt", "gte"}
ALLOWED_PROVENANCE = {"documented_reference", "empirical_same_dataset", "fixture_only"}


class InvalidProposal(ValueError):
    """Malformed or unsafe proposal: never pass it to the verifier."""


class UnresolvedParameter(Exception):
    """Required parameter missing from the explicitly supplied registry."""

    def __init__(self, name: str, reason: str):
        self.name, self.reason = name, reason
        super().__init__(reason)


def _finite_string(value: Any) -> str:
    if isinstance(value, bool) or value is None or not isinstance(value, (str, int, float)):
        raise InvalidProposal("numeric parameter must be a finite numeric scalar")
    try:
        parsed = Decimal(str(value))
    except (ValueError, InvalidOperation):
        raise InvalidProposal("invalid numeric parameter") from None
    if not parsed.is_finite():
        raise InvalidProposal("NaN and Infinity are disallowed")
    return str(parsed)


def _registry_entry(name: str, dataset_id: str, kind: str, registry: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(name, str) or not name or len(name) > 80:
        raise InvalidProposal("invalid parameter name")
    record = registry.get(f"{dataset_id}:{name}")
    if record is None:
        raise UnresolvedParameter(name, f"no independent parameter registration for {name}")
    if not isinstance(record, dict) or record.get("kind") != kind:
        raise InvalidProposal(f"registry kind mismatch for {name}")
    if record.get("origin") not in ALLOWED_PROVENANCE:
        raise UnresolvedParameter(name, f"unreviewed parameter provenance for {name}")
    if not isinstance(record.get("rationale"), str) or not record["rationale"].strip():
        raise UnresolvedParameter(name, f"missing provenance rationale for {name}")
    if record["origin"] == "documented_reference" and not str(record.get("source_url", "")).startswith("https://"):
        raise UnresolvedParameter(name, f"missing documentary source URL for {name}")
    # A registry entry is a human/curator assertion; checking these fields does NOT
    # verify the URL contents or guarantee an independent evidence review.
    return record


def _numeric_param(name: str, dataset_id: str, registry: Mapping[str, Any], used: dict[str, Any]) -> str:
    entry = _registry_entry(name, dataset_id, "number", registry)
    value = _finite_string(entry.get("value"))
    used[name] = {"origin": entry["origin"], "source_url": entry.get("source_url"), "rationale": entry["rationale"]}
    return value


def _expr(ast: Any, allowed: set[str], dataset_id: str, registry: Mapping[str, Any], used: dict[str, Any], refs: set[str], depth: int = 0) -> dict[str, Any]:
    if depth > 6 or not isinstance(ast, dict) or len(ast) != 1:
        raise InvalidProposal("invalid or overly nested expression")
    op, value = next(iter(ast.items()))
    if op == "column":
        if not isinstance(value, str) or value not in allowed:
            raise InvalidProposal(f"unknown column: {value}")
        refs.add(value)
        return {"column": value}
    if op == "parameter":
        return {"constant": _numeric_param(value, dataset_id, registry, used)}
    if op == "constant":
        raise InvalidProposal("model-supplied numeric constants are forbidden; use a named parameter")
    if op not in {"add", "multiply", "subtract"}:
        raise InvalidProposal(f"unsupported arithmetic operator: {op}")
    if not isinstance(value, list) or not 2 <= len(value) <= 8 or (op == "subtract" and len(value) != 2):
        raise InvalidProposal("invalid operand count")
    return {op: [_expr(p, allowed, dataset_id, registry, used, refs, depth + 1) for p in value]}


def _predicate(ast: Any, allowed: set[str], dataset_id: str, registry: Mapping[str, Any], used: dict[str, Any], refs: set[str], depth: int = 0) -> dict[str, Any]:
    if depth > 5 or not isinstance(ast, dict):
        raise InvalidProposal("malformed or deeply nested applicability condition")
    if set(ast) in ({"all"}, {"any"}):
        key = next(iter(ast))
        args = ast[key]
        if not isinstance(args, list) or not 1 <= len(args) <= 8:
            raise InvalidProposal("invalid condition group")
        return {key: [_predicate(x, allowed, dataset_id, registry, used, refs, depth + 1) for x in args]}
    if set(ast) != {"column", "op", "value"} or ast["op"] not in COMPARATORS:
        raise InvalidProposal("unsupported applicability predicate")
    col = ast["column"]
    if not isinstance(col, str) or col not in allowed:
        raise InvalidProposal(f"unknown conditional column: {col}")
    refs.add(col)
    raw = ast["value"]
    if isinstance(raw, dict) and set(raw) == {"parameter"}:
        value = _numeric_param(raw["parameter"], dataset_id, registry, used)
    elif isinstance(raw, str) and raw and ast["op"] in {"eq", "ne"}:
        # Explicit nonnumeric categorical labels are allowed. Numeric-looking
        # values must come from the independent registry, including zero.
        try:
            _finite_string(raw)
        except InvalidProposal:
            value = raw
        else:
            raise InvalidProposal("numeric condition literals require registered parameters")
    else:
        raise InvalidProposal("condition values must be categorical strings or registered numeric parameters")
    return {"column": col, "op": ast["op"], "value": value}


def _rounding(ast: Any, dataset_id: str, registry: Mapping[str, Any], used: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(ast, dict) or set(ast) != {"parameter"}:
        raise InvalidProposal("rounding must be a named registered parameter")
    name = ast["parameter"]
    entry = _registry_entry(name, dataset_id, "rounding", registry)
    spec = entry.get("value")
    if not isinstance(spec, dict) or set(spec) != {"mode", "digits"}:
        raise InvalidProposal("invalid registered rounding specification")
    if spec["mode"] not in {"significant_figures", "decimal_places"} or type(spec["digits"]) is not int or not 1 <= spec["digits"] <= 12:
        raise InvalidProposal("invalid registered rounding mode or precision")
    used[name] = {"origin": entry["origin"], "source_url": entry.get("source_url"), "rationale": entry["rationale"]}
    return dict(spec)


@dataclass
class Compilation:
    status: str
    proposal_id: str
    reason: str
    rule: dict[str, Any] | None
    parameter_provenance: dict[str, Any]
    # It is crucial that compiled status never implies semantic correctness.

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "proposal_id": self.proposal_id, "reason": self.reason,
                "rule": self.rule, "parameter_provenance": self.parameter_provenance,
                "semantic_verified": False, "data_errors_adjudicated": False}


def compile_proposal(proposal: Mapping[str, Any], allowed_columns: list[str], registry: Mapping[str, Any] | None = None) -> Compilation:
    """Return an unverified B3 rule, a blocked hypothesis, or a rejected one."""
    pid = str(proposal.get("id", "<missing-id>")) if isinstance(proposal, dict) else "<invalid>"
    used: dict[str, Any] = {}
    try:
        if not isinstance(proposal, dict):
            raise InvalidProposal("proposal must be an object")
        allowed_keys = {"proposal_version", "id", "dataset_id", "assertions", "when", "context_keys", "origin"}
        if set(proposal) - allowed_keys:
            raise InvalidProposal("unexpected proposal keys")
        if proposal.get("proposal_version") != PROPOSAL_VERSION:
            raise InvalidProposal("unsupported proposal version (free-text proposals cannot be compiled)")
        if not isinstance(proposal.get("id"), str) or not proposal["id"]:
            raise InvalidProposal("missing rule ID")
        ds = proposal.get("dataset_id")
        if not isinstance(ds, str) or not ds:
            raise InvalidProposal("missing dataset ID")
        if not isinstance(proposal.get("origin"), str) or not proposal["origin"]:
            raise InvalidProposal("proposal origin is required for audit")
        if (not isinstance(allowed_columns, list) or not allowed_columns or
                any(not isinstance(c, str) or not c for c in allowed_columns)):
            raise InvalidProposal("allowed_columns must come from an explicit metadata scope")
        allowed = set(allowed_columns)
        if not isinstance(proposal.get("assertions"), list) or not 1 <= len(proposal["assertions"]) <= 8:
            raise InvalidProposal("1–8 assertions are required")
        context = proposal.get("context_keys", [])
        if not isinstance(context, list) or any(not isinstance(k, str) or not k for k in context) or len(set(context)) != len(context):
            raise InvalidProposal("invalid context keys")
        refs: set[str] = set()
        checks = []
        for item in proposal["assertions"]:
            if not isinstance(item, dict) or not {"left", "op", "right"}.issubset(item) or set(item) - {"left", "op", "right", "round_right", "abs_tolerance"}:
                raise InvalidProposal("malformed assertion")
            if item["op"] not in COMPARATORS:
                raise InvalidProposal("unsupported assertion comparator")
            check = {
                "left": _expr(item["left"], allowed, ds, registry or {}, used, refs),
                "op": item["op"],
                "right": _expr(item["right"], allowed, ds, registry or {}, used, refs),
            }
            if "round_right" in item:
                check["round_right"] = _rounding(item["round_right"], ds, registry or {}, used)
            if "abs_tolerance" in item:
                if item["op"] not in {"eq", "ne"}:
                    raise InvalidProposal("tolerance only allowed for equality")
                spec = item["abs_tolerance"]
                if not isinstance(spec, dict) or set(spec) != {"parameter"}:
                    raise InvalidProposal("tolerance requires registered parameter")
                tolerance = _numeric_param(spec["parameter"], ds, registry or {}, used)
                if Decimal(tolerance) < 0:
                    raise InvalidProposal("negative tolerance")
                check["abs_tolerance"] = tolerance
            checks.append(check)
        when = None
        if proposal.get("when") is not None:
            when = _predicate(proposal["when"], allowed, ds, registry or {}, used, refs)
        if len(refs) < 2:
            raise InvalidProposal("feasibility pilot requires relationships involving at least two columns")
        executable = {"schema_version": EXEC_VERSION, "id": proposal["id"], "dataset_id": ds,
                      "assertions": checks, "context_keys": context,
                      "evidence_status": "candidate_unverified", "proposal_origin": proposal["origin"]}
        if when is not None:
            executable["when"] = when
        return Compilation("candidate_executable_unverified", pid, "syntax and parameters resolved; NO semantic acceptance", executable, used)
    except UnresolvedParameter as exc:
        return Compilation("blocked_unresolved", pid, exc.reason, None, used)
    except (InvalidProposal, KeyError, TypeError) as exc:
        return Compilation("rejected_invalid", pid, str(exc), None, used)
