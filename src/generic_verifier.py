"""MetaVerify B3: small, safe, domain-neutral row constraint interpreter.

This checks supplied hypotheses. It does NOT discover rules, establish documentary
support, adjudicate real-world data errors, or execute free-text LLM expressions.
No eval/exec or model API calls; standard library only.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = "metaverify-exec-v0.1"
COMPARATORS = {"eq", "ne", "lt", "lte", "gt", "gte"}
STATUSES = ("satisfied", "violated", "not_applicable", "abstained")


class MissingOrInvalid(Exception):
    """A required record field is missing, nonnumeric, or non-finite."""


@dataclass(frozen=True)
class Outcome:
    status: str
    reason: str


def _decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise MissingOrInvalid("missing or boolean numeric value")
    try:
        number = Decimal(str(value).strip())
    except (ValueError, InvalidOperation, TypeError):
        raise MissingOrInvalid("non-numeric value") from None
    if not number.is_finite():
        raise MissingOrInvalid("non-finite numeric value")
    return number


def _expression_refs(expr: Any, *, depth: int = 0) -> set[str]:
    if depth > 6 or not isinstance(expr, dict):
        raise ValueError("invalid or overly nested numeric expression")
    if set(expr) == {"column"} and isinstance(expr["column"], str) and expr["column"]:
        return {expr["column"]}
    if set(expr) == {"constant"}:
        try:
            _decimal(expr["constant"])
        except MissingOrInvalid as exc:
            raise ValueError(f"invalid numeric constant: {exc}") from exc
        return set()
    if len(expr) != 1:
        raise ValueError("expression must contain exactly one supported operator")
    op, args = next(iter(expr.items()))
    if op not in {"add", "multiply", "subtract"} or not isinstance(args, list):
        raise ValueError(f"unsupported expression operator: {op}")
    if len(args) < 2 or (op == "subtract" and len(args) != 2):
        raise ValueError(f"invalid number of operands for {op}")
    refs: set[str] = set()
    for arg in args:
        refs.update(_expression_refs(arg, depth=depth + 1))
    return refs


def _predicate_refs(pred: Any) -> set[str]:
    if not isinstance(pred, dict):
        raise ValueError("condition must be an object")
    if set(pred) in ({"all"}, {"any"}):
        group = next(iter(pred.values()))
        if not isinstance(group, list) or not group:
            raise ValueError("condition group must be nonempty")
        refs: set[str] = set()
        for item in group:
            refs.update(_predicate_refs(item))
        return refs
    if set(pred) != {"column", "op", "value"}:
        raise ValueError("condition must have column, op and value")
    if (not isinstance(pred["column"], str) or not pred["column"]
        or not isinstance(pred["op"], str) or pred["op"] not in COMPARATORS):
        raise ValueError("unsupported conditional predicate")
    if pred["op"] in {"lt", "lte", "gt", "gte"}:
        try:
            _decimal(pred["value"])
        except MissingOrInvalid as exc:
            raise ValueError(f"invalid condition numeric value: {exc}") from exc
    return {pred["column"]}


def validate_rule(rule: Mapping[str, Any]) -> set[str]:
    """Validate a small typed DSL. Returns the set of referenced columns."""
    if not isinstance(rule, dict) or rule.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported rule schema version")
    if not isinstance(rule.get("id"), str) or not rule["id"]:
        raise ValueError("nonempty rule id required")
    if not isinstance(rule.get("dataset_id"), str) or not rule["dataset_id"]:
        raise ValueError("nonempty dataset_id required")
    assertions = rule.get("assertions")
    if not isinstance(assertions, list) or not assertions:
        raise ValueError("nonempty assertions list required")
    refs: set[str] = set()
    for check in assertions:
        if not isinstance(check, dict):
            raise ValueError("assertion must be an object")
        if (not {"left", "op", "right"}.issubset(check)
            or not isinstance(check["op"], str) or check["op"] not in COMPARATORS):
            raise ValueError("assertion needs left, op, right with supported operator")
        if set(check) - {"left", "op", "right", "round_right", "abs_tolerance"}:
            raise ValueError("unsupported assertion fields")
        refs.update(_expression_refs(check["left"]))
        refs.update(_expression_refs(check["right"]))
        if "round_right" in check:
            rnd = check["round_right"]
            if (not isinstance(rnd, dict) or set(rnd) != {"mode", "digits"}
                or rnd["mode"] not in {"significant_figures", "decimal_places"}
                or type(rnd["digits"]) is not int or not 1 <= rnd["digits"] <= 12):
                raise ValueError("invalid rounding configuration")
        if "abs_tolerance" in check:
            if check["op"] not in {"eq", "ne"}:
                raise ValueError("tolerance applies only to eq/ne")
            try:
                if _decimal(check["abs_tolerance"]) < 0:
                    raise ValueError("negative tolerance")
            except MissingOrInvalid as exc:
                raise ValueError("invalid tolerance") from exc
    if rule.get("when") is not None:
        refs.update(_predicate_refs(rule["when"]))
    keys = rule.get("context_keys", [])
    if not isinstance(keys, list) or any(not isinstance(k, str) or not k for k in keys):
        raise ValueError("context_keys must be a list of nonempty names")
    if len(set(keys)) != len(keys):
        raise ValueError("context_keys must be unique")
    return refs


def _evaluate_expression(expr: dict[str, Any], record: Mapping[str, Any]) -> Decimal:
    if "column" in expr:
        name = expr["column"]
        if name not in record:
            raise MissingOrInvalid(f"missing field: {name}")
        return _decimal(record[name])
    if "constant" in expr:
        return _decimal(expr["constant"])
    op, args = next(iter(expr.items()))
    nums = [_evaluate_expression(a, record) for a in args]
    if op == "add":
        return sum(nums, Decimal(0))
    if op == "multiply":
        product = Decimal(1)
        for n in nums:
            product *= n
        return product
    if op == "subtract":
        return nums[0] - nums[1]
    raise ValueError("unsupported expression")


def _compare(left: Decimal, op: str, right: Decimal, tolerance: Decimal = Decimal(0)) -> bool:
    if op == "eq":
        return abs(left - right) <= tolerance
    if op == "ne":
        return abs(left - right) > tolerance
    if op == "lt":
        return left < right
    if op == "lte":
        return left <= right
    if op == "gt":
        return left > right
    if op == "gte":
        return left >= right
    raise ValueError("unsupported comparison")


def _round_right(value: Decimal, specification: Mapping[str, Any]) -> Decimal:
    digits = specification["digits"]
    if value == 0:
        return value
    if specification["mode"] == "decimal_places":
        step = Decimal("1").scaleb(-digits)
    else:
        step = Decimal("1").scaleb(value.adjusted() - digits + 1)
    return value.quantize(step, rounding=ROUND_HALF_UP)


def _predicate_value(pred: dict[str, Any], record: Mapping[str, Any]) -> bool:
    if "all" in pred or "any" in pred:
        is_all = "all" in pred
        items = pred["all"] if is_all else pred["any"]
        unknown = False
        for part in items:
            try:
                value = _predicate_value(part, record)
            except MissingOrInvalid:
                unknown = True
                continue
            if is_all and not value:
                return False
            if not is_all and value:
                return True
        if unknown:
            raise MissingOrInvalid("incomplete condition group")
        return is_all
    column = pred["column"]
    if column not in record or record[column] is None:
        raise MissingOrInvalid(f"missing condition field: {column}")
    if pred["op"] in {"eq", "ne"}:
        # Equality can be categorical or numeric; preserve categories as strings.
        x, y = record[column], pred["value"]
        try:
            equal = _decimal(x) == _decimal(y)
        except MissingOrInvalid:
            equal = str(x) == str(y)
        return equal if pred["op"] == "eq" else not equal
    return _compare(_decimal(record[column]), pred["op"], _decimal(pred["value"]))


def _check_context(rule: Mapping[str, Any], record: Mapping[str, Any], refs: set[str]) -> None:
    keys = rule.get("context_keys", [])
    if not keys:
        return
    field_ctx = record.get("_field_context")
    if not isinstance(field_ctx, dict):
        raise MissingOrInvalid("required per-field reporting context absent")
    # Compare the context of fields actually used in the assertions/conditions.
    for key in keys:
        values = []
        for col in refs:
            context = field_ctx.get(col)
            if not isinstance(context, dict) or key not in context or context[key] is None:
                raise MissingOrInvalid(f"missing context {key} for {col}")
            values.append(context[key])
        if values and any(value != values[0] for value in values[1:]):
            raise MissingOrInvalid(f"incompatible {key} across fields")


def evaluate_row(rule: dict[str, Any], record: Mapping[str, Any], *, _validated_refs: set[str] | None = None) -> Outcome:
    refs = validate_rule(rule) if _validated_refs is None else _validated_refs
    try:
        if rule.get("when") is not None and not _predicate_value(rule["when"], record):
            return Outcome("not_applicable", "condition is false")
        _check_context(rule, record, refs)
        for check in rule["assertions"]:
            left = _evaluate_expression(check["left"], record)
            right = _evaluate_expression(check["right"], record)
            if "round_right" in check:
                right = _round_right(right, check["round_right"])
            tol = _decimal(check.get("abs_tolerance", "0"))
            if not _compare(left, check["op"], right, tol):
                return Outcome("violated", "one or more expressions disagree")
        return Outcome("satisfied", "all executable expressions hold")
    except (MissingOrInvalid, InvalidOperation, OverflowError) as exc:
        return Outcome("abstained", str(exc))


def evaluate_rows(rule: dict[str, Any], records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    refs = validate_rule(rule)
    counts = {s: 0 for s in STATUSES}
    for record in records:
        counts[evaluate_row(rule, record, _validated_refs=refs).status] += 1
    total = sum(counts.values())
    eligible = total - counts["not_applicable"]
    evaluated = counts["satisfied"] + counts["violated"]
    return {
        "rule_id": rule["id"],
        "dataset_id": rule["dataset_id"],
        "record_count": total,
        "eligible_records": eligible,
        "evaluated_records": evaluated,
        "counts": counts,
        "coverage_on_eligible": evaluated / eligible if eligible else None,
        "interpretation": "Violations are expression mismatches, NOT independently adjudicated data errors.",
    }
