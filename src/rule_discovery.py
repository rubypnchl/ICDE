"""Discover data-derived candidate rules without treating them as verified."""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from src.novelty_pilot import _rule, _split


MIN_SUPPORT = 10
MIN_IDENTITY_RATE = 0.99
COMPLEXITY_PENALTY = 0.01
SEC_API_URL = "https://www.sec.gov/edgar/sec-api-documentation"
UCI_URL = "https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset"


def _number(value: Any) -> Decimal | None:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _rule_id(dataset_id: str, columns: list[str], condition: Any, assertion: Any) -> str:
    content = json.dumps([columns, condition, assertion], sort_keys=True, separators=(",", ":"))
    suffix = hashlib.sha256(content.encode("utf-8")).hexdigest()[:10]
    return f"{_slug(dataset_id)}-{_slug(columns[0])[:36]}-{suffix}"


def _documented_evidence(metadata: dict[str, Any], assertion: dict[str, Any]) -> dict[str, Any] | None:
    for item in metadata.get("documented_constraints", []):
        if (
            item.get("status") == "documented"
            and item.get("assertion") == assertion
            and item.get("source_url")
        ):
            return item
    return None


def _normalized_column(column: str) -> str:
    return re.sub(r"\s+", "", column).casefold()


def _match_sec_evidence(
    rule: dict[str, Any],
    registry: dict[str, Any],
    reporting_context: dict[str, bool],
) -> dict[str, Any]:
    assertion = rule["assertion"]
    if assertion.get("op") != "sum_eq":
        return {"status": "not_found"}
    for entry in registry.get("entries", []):
        documented = entry.get("assertion", {})
        if documented.get("op") != "sum_eq":
            continue
        if (
            _normalized_column(assertion["result_column"])
            != _normalized_column(documented.get("result_column", ""))
            or sorted(map(_normalized_column, assertion.get("term_columns", [])))
            != sorted(map(_normalized_column, documented.get("term_columns", [])))
            or _number(assertion.get("tolerance", 0)) != _number(documented.get("tolerance", 0))
        ):
            continue
        required = entry.get("requirements", [])
        compatibility = {
            requirement: reporting_context.get(_slug(requirement.replace(" ", "_")), False)
            for requirement in required
        }
        source = {
            "id": entry.get("id"),
            "authority": entry.get("authority"),
            "source_url": entry.get("source_url"),
            "evidence_status": entry.get("evidence_status"),
        }
        citation = {
            "description": f"{source['authority']}: {source['id']}",
            "source_url": source["source_url"],
        }
        if citation not in rule["evidence"]:
            rule["evidence"].append(citation)
        return {
            "status": "documented" if all(compatibility.values()) else "context_incompatible",
            "citation": source,
            "requirements": required,
            "context_compatibility": compatibility,
        }
    return {"status": "not_found"}


def _build_rule(
    metadata_path: Path,
    metadata: dict[str, Any],
    columns: list[str],
    condition: dict[str, Any] | None,
    assertion: dict[str, Any],
    source_url: str,
) -> dict[str, Any]:
    rule = _rule(
        metadata_path,
        metadata,
        _rule_id(metadata["dataset"]["id"], columns, condition, assertion),
        columns,
        "conditional_range" if assertion["op"] == "between" else "cross_field",
        condition,
        assertion,
        source_url,
        "Statistical candidate mined from discovery records; no integrity constraint is asserted by this source.",
    )
    rule["provenance"]["metadata_file"] = (Path("data") / "metadata" / metadata_path.name).as_posix()
    return rule


def _candidate_report(
    rule: dict[str, Any],
    parameters: dict[str, Any],
    evidence: dict[str, Any] | None,
    discovery_support: int,
    discovery_total: int,
    complexity: int,
    complexity_penalty: float,
) -> dict[str, Any]:
    rate = parameters.get("discovery_rate")
    score = (rate or 0.0) * (discovery_support / discovery_total if discovery_total else 0.0)
    score -= complexity_penalty * complexity
    return {
        "rule": rule,
        "parameters": parameters,
        "discovery": {
            "support": discovery_support,
            "rows": discovery_total,
            "pass_rate": rate,
            "complexity": complexity,
            "complexity_penalty": complexity_penalty * complexity,
            "score": score,
        },
        "documented_evidence": evidence or {"status": "not_found"},
    }


def discover_numeric_ranges(
    rows: list[dict[str, Any]],
    metadata: dict[str, Any],
    metadata_path: Path,
    *,
    min_support: int = MIN_SUPPORT,
    complexity_penalty: float = COMPLEXITY_PENALTY,
) -> list[dict[str, Any]]:
    """Mine global and single-categorical-context ranges from discovery rows."""
    column_metadata = {item["name"]: item for item in metadata.get("columns", [])}
    names = list(column_metadata)
    numeric = {
        name: [_number(row.get(name)) for row in rows]
        for name in names
    }
    numeric_types = {"number", "numeric", "integer", "float", "decimal"}
    numeric_names = set()
    for name, values in numeric.items():
        present = [value for value in values if value is not None]
        declared_type = str(column_metadata[name].get("type", {}).get("value", "")).lower()
        declared_documented = column_metadata[name].get("type", {}).get("status") == "documented"
        distinct_ratio = len(set(present)) / max(1, len(present))
        if (
            len(present) >= min_support
            and len(set(present)) > 2
            and declared_type in numeric_types
            and (declared_documented or distinct_ratio < 0.9)
        ):
            numeric_names.add(name)
    categorical_names = []
    for name in names:
        observed = {str(row[name]) for row in rows if row.get(name) not in (None, "")}
        declared_type = str(column_metadata[name].get("type", {}).get("value", "")).lower()
        if name not in numeric_names and declared_type not in numeric_types and 2 <= len(observed) <= 12:
            categorical_names.append(name)

    candidates = []
    for column in sorted(numeric_names):
        valid = [(row, _number(row.get(column))) for row in rows]
        valid = [(row, value) for row, value in valid if value is not None]
        global_values = [value for _, value in valid]
        if len(global_values) < min_support:
            continue
        global_bounds = (min(global_values), max(global_values))
        groups: list[tuple[dict[str, Any] | None, list[Decimal]]] = [(None, global_values)]
        for context in categorical_names:
            grouped: dict[str, list[Decimal]] = defaultdict(list)
            for row, value in valid:
                if row.get(context) not in (None, ""):
                    grouped[str(row[context])].append(value)
            for value, group_values in sorted(grouped.items()):
                if len(group_values) >= min_support and (min(group_values), max(group_values)) != global_bounds:
                    groups.append(({"op": "eq", "column": context, "value": value}, group_values))

        for condition, values in groups:
            lower, upper = min(values), max(values)
            assertion = {
                "op": "between",
                "column": column,
                "lower": float(lower),
                "upper": float(upper),
            }
            columns = [column] if condition is None else [condition["column"], column]
            rule = _build_rule(metadata_path, metadata, columns, condition, assertion, UCI_URL)
            evidence = _documented_evidence(metadata, assertion)
            parameters = {
                "kind": "range",
                "column": column,
                "lower": lower,
                "upper": upper,
                "condition": condition,
                "discovery_rate": 1.0,
            }
            candidates.append(_candidate_report(
                rule, parameters, evidence, len(values), len(rows),
                1 if condition else 0, complexity_penalty,
            ))
    return candidates


def _sec_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str, str, str, str], dict[str, Decimal | None]] = defaultdict(dict)
    for tag, concept in payload.get("facts", {}).get("us-gaap", {}).items():
        for unit, entries in concept.get("units", {}).items():
            for entry in entries:
                if entry.get("form") not in {"10-K", "10-Q"} or entry.get("start"):
                    continue
                end = entry.get("end")
                if not end:
                    continue
                key = (end, entry.get("accn", ""), entry.get("form", ""), entry.get("filed", ""), unit)
                value = _number(entry.get("val"))
                if value is None:
                    continue
                previous = buckets[key].get(tag, value)
                buckets[key][tag] = value if previous == value else None
    rows = []
    for (end, accn, form, filed, unit), values in sorted(buckets.items()):
        row: dict[str, Any] = {"end": end, "accn": accn, "form": form, "filed": filed, "unit": unit}
        row.update({tag: value for tag, value in values.items() if value is not None})
        if len(row) > 5:
            rows.append(row)
    return rows


def discover_sec_identities(
    rows: list[dict[str, Any]],
    metadata: dict[str, Any],
    metadata_path: Path,
    *,
    min_support: int = MIN_SUPPORT,
    min_identity_rate: float = MIN_IDENTITY_RATE,
    complexity_penalty: float = COMPLEXITY_PENALTY,
) -> list[dict[str, Any]]:
    """Mine exact, same-unit A=B+C identities over aligned SEC fact rows."""
    match_counts: dict[tuple[str, str, str, str], int] = defaultdict(int)
    for row in rows:
        tags = sorted(
            tag for tag, value in row.items()
            if tag not in {"end", "accn", "form", "filed", "unit"}
            and _number(value) not in (None, Decimal(0))
        )
        values = {tag: _number(row[tag]) for tag in tags}
        lookup: dict[Decimal, list[str]] = defaultdict(list)
        for tag in tags:
            lookup[values[tag]].append(tag)
        seen: set[tuple[str, str, str, str]] = set()
        for left, right in itertools.combinations(tags, 2):
            total = values[left] + values[right]
            for result in lookup.get(total, []):
                if result not in {left, right}:
                    terms = tuple(sorted((left, right)))
                    seen.add((result, terms[0], terms[1], str(row["unit"])))
        for identity in seen:
            match_counts[identity] += 1

    candidates = []
    for (result, left, right, unit), matches in sorted(match_counts.items()):
        support = sum(
            row.get("unit") == unit and all(tag in row for tag in (result, left, right))
            and all(_number(row[tag]) not in (None, Decimal(0)) for tag in (result, left, right))
            for row in rows
        )
        if support < min_support or matches / support < min_identity_rate:
            continue
        unit_columns = [f"{tag} [{unit}]" for tag in (result, left, right)]
        assertion = {
            "op": "sum_eq",
            "result_column": unit_columns[0],
            "term_columns": unit_columns[1:],
            "tolerance": 0,
        }
        rule = _build_rule(metadata_path, metadata, unit_columns, None, assertion, SEC_API_URL)
        evidence = _documented_evidence(metadata, assertion)
        rate = matches / support
        parameters = {
            "kind": "sum_eq",
            "result": result,
            "terms": [left, right],
            "unit": unit,
            "tolerance": Decimal(0),
            "discovery_rate": rate,
        }
        candidates.append(_candidate_report(
            rule, parameters, evidence, support, len(rows), 2, complexity_penalty,
        ))
    return candidates


def _matches_condition(condition: dict[str, Any] | None, row: dict[str, Any]) -> bool:
    if condition is None:
        return True
    if condition["op"] != "eq":
        raise ValueError(f"unsupported condition operator: {condition['op']}")
    return str(row.get(condition["column"])) == str(condition["value"])


def _assertion_holds(candidate: dict[str, Any], row: dict[str, Any]) -> bool | None:
    parameters = candidate["parameters"]
    if parameters["kind"] == "range":
        value = _number(row.get(parameters["column"]))
        return None if value is None else parameters["lower"] <= value <= parameters["upper"]
    values = [_number(row.get(tag)) for tag in [parameters["result"], *parameters["terms"]]]
    if any(value is None or value == 0 for value in values):
        return None
    tolerance = Decimal(str(candidate["rule"]["assertion"].get("tolerance", 0)))
    return abs(values[0] - values[1] - values[2]) <= tolerance


def _decision(evidence_supported: bool, violations: int | None) -> str:
    if not evidence_supported or violations is None:
        return "abstain"
    return "documented_support" if violations == 0 else "documented_conflict"


def _evaluate_candidates(candidates: list[dict[str, Any]], heldout: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for candidate in candidates:
        evidence = candidate["documented_evidence"]
        supported = evidence.get("status") == "documented"
        outcomes = [
            outcome
            for row in heldout
            if _matches_condition(candidate["parameters"].get("condition"), row)
            and (outcome := _assertion_holds(candidate, row)) is not None
        ]
        violations = sum(not outcome for outcome in outcomes) if outcomes else None
        candidate["heldout"] = {
            "applicable_rows": len(outcomes),
            "violations": violations,
            "decision": _decision(supported, violations),
        }
        baselines = {}
        for name in ("global", "conditional", "context_only"):
            selected_rows = [
                row for row in heldout
                if name == "global" or _matches_condition(candidate["parameters"].get("condition"), row)
            ]
            if name == "context_only":
                checked = []
            else:
                checked = [
                    result for row in selected_rows
                    if (result := _assertion_holds(candidate, row)) is not None
                ]
            baseline_violations = sum(not result for result in checked) if checked else None
            baselines[name] = {
                "applicable_rows": len(checked) if name != "context_only" else len(selected_rows),
                "violations": baseline_violations,
                "descriptive_pass_rate": (
                    (len(checked) - baseline_violations) / len(checked)
                    if checked and baseline_violations is not None else None
                ),
            }
        candidate["baselines"] = baselines
        candidate.pop("parameters")
    return candidates


def _dataset_result(
    dataset_id: str,
    candidates: list[dict[str, Any]],
    discovery_rows: int,
    heldout: list[dict[str, Any]],
    split_description: str,
) -> dict[str, Any]:
    _evaluate_candidates(candidates, heldout)
    comparison = {}
    for baseline in ("global", "conditional", "context_only"):
        items = [candidate["baselines"][baseline] for candidate in candidates]
        checked = sum(item["applicable_rows"] for item in items)
        violations = sum(item["violations"] or 0 for item in items)
        comparison[baseline] = {
            "candidate_count": len(candidates),
            "applicable_rows": checked,
            "violations": violations if baseline != "context_only" else None,
            "descriptive_pass_rate": (checked - violations) / checked if checked and baseline != "context_only" else None,
            "error_metrics": {"precision": "N/A", "false_positive_rate": "N/A"},
        }
    return {
        "dataset_id": dataset_id,
        "split": split_description,
        "discovery_rows": discovery_rows,
        "heldout_rows": len(heldout),
        "candidate_count": len(candidates),
        "decision_counts": {
            decision: sum(item["heldout"]["decision"] == decision for item in candidates)
            for decision in ("documented_support", "documented_conflict", "abstain")
        },
        "error_metrics": {
            "precision": "N/A",
            "false_positive_rate": "N/A",
            "reason": "No independent rule-level labels are present in Module 1 metadata.",
        },
        "baseline_comparison": comparison,
        "candidates": candidates,
    }


def run_discovery(
    root: Path,
    *,
    min_support: int = MIN_SUPPORT,
    complexity_penalty: float = COMPLEXITY_PENALTY,
) -> dict[str, Any]:
    """Run reproducible discovery on the locally retained AI4I and SEC datasets."""
    root = root.resolve()
    ai_metadata_path = root / "data" / "metadata" / "ai4i-2020.json"
    ai_metadata = json.loads(ai_metadata_path.read_text(encoding="utf-8"))
    ai_path = root / "data" / "originals" / "ai4i" / "ai4i2020.csv"
    with ai_path.open(encoding="utf-8-sig", newline="") as stream:
        ai_rows = list(csv.DictReader(stream))
    ai_discovery, ai_heldout = _split(ai_rows)
    ai_candidates = discover_numeric_ranges(
        ai_discovery, ai_metadata, ai_metadata_path,
        min_support=min_support, complexity_penalty=complexity_penalty,
    )

    sec_metadata_path = root / "data" / "metadata" / "sec-companyfacts-0000320193.json"
    sec_metadata = json.loads(sec_metadata_path.read_text(encoding="utf-8"))
    sec_path = root / "data" / "originals" / "sec" / "companyfacts" / "0000320193_apple.json"
    sec_payload = json.loads(sec_path.read_text(encoding="utf-8"))
    sec_rows = _sec_rows(sec_payload)
    sec_discovery, sec_heldout = _split(sec_rows, group_by="end")
    sec_candidates = discover_sec_identities(
        sec_discovery, sec_metadata, sec_metadata_path,
        min_support=min_support, complexity_penalty=complexity_penalty,
    )
    evidence_path = root / "data" / "evidence" / "sec_constraints.json"
    evidence_registry = json.loads(evidence_path.read_text(encoding="utf-8"))
    for candidate in sec_candidates:
        columns = [
            candidate["rule"]["assertion"]["result_column"],
            *candidate["rule"]["assertion"]["term_columns"],
        ]
        currency_units = [
            match.group(1)
            for column in columns
            if (match := re.search(r"\[([^\]]+)\]$", column))
        ]
        context = {
            "same-entity": bool(sec_payload.get("cik") or sec_payload.get("entityName")),
            "same-reporting-date": True,
            "same-accounting-scope": True,
            "same-currency": len(currency_units) == len(columns) and len(set(currency_units)) == 1,
        }
        candidate["documented_evidence"] = _match_sec_evidence(
            candidate["rule"], evidence_registry, context,
        )
    return {
        "module": "MetaVerify Module 2B",
        "method": {
            "seed": 2401,
            "split": "deterministic 70/30; SEC grouped by reporting end date",
            "minimum_support": min_support,
            "minimum_SEC_identity_rate": MIN_IDENTITY_RATE,
            "complexity_penalty_per_context_or_relation": complexity_penalty,
            "numeric_contexts": "single categorical equality predicates; redundant global-equivalent contexts omitted",
            "SEC_alignment": "same end, accession, form, filing date, and unit; instant facts only",
            "decisions": "independent documentation plus compatible reporting context and held-out checks: documented_support, documented_conflict, or abstain; empirical fit alone is not semantic proof",
        },
        "datasets": {
            ai_metadata["dataset"]["id"]: _dataset_result(
                ai_metadata["dataset"]["id"], ai_candidates, len(ai_discovery), ai_heldout,
                "seeded 70/30 random rows",
            ),
            sec_metadata["dataset"]["id"]: _dataset_result(
                sec_metadata["dataset"]["id"], sec_candidates, len(sec_discovery), sec_heldout,
                "seeded 70/30 reporting-end-date groups",
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("data/rule-discovery.json"))
    parser.add_argument("--min-support", type=int, default=MIN_SUPPORT)
    parser.add_argument("--complexity-penalty", type=float, default=COMPLEXITY_PENALTY)
    args = parser.parse_args()
    if args.min_support < 1 or args.complexity_penalty < 0:
        parser.error("--min-support must be positive and --complexity-penalty nonnegative")
    result = run_discovery(
        args.root, min_support=args.min_support, complexity_penalty=args.complexity_penalty,
    )
    output = args.root / args.output if not args.output.is_absolute() else args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    counts = [f"{name}={item['candidate_count']}" for name, item in result["datasets"].items()]
    print(f"{output}: " + ", ".join(counts))


if __name__ == "__main__":
    main()
