"""Synthetic semantic-reliability benchmark plus an unlabelled SEC positive control."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from src.evaluate_detection import (
    METHODS,
    _metrics,
    _predict,
    _rule_violation,
)
from src.rule_discovery import (
    _match_sec_evidence,
    _sec_rows,
    _split,
    discover_sec_identities,
)


THRESHOLD = 0.9
SEC_EVIDENCE_ID = "SEC-BALANCE-001"


def _synthetic_candidate(
    rule_id: str,
    result: str,
    terms: list[str],
    *,
    evidence: str,
) -> dict[str, Any]:
    return {
        "rule": {
            "id": rule_id,
            "verification_status": "candidate",
            "assertion": {
                "op": "sum_eq",
                "result_column": f"{result} [USD]",
                "term_columns": [f"{term} [USD]" for term in terms],
                "tolerance": 0,
            },
        },
        "parameters": {
            "kind": "sum_eq",
            "result": result,
            "terms": terms,
        },
        "documented_evidence": {
            "status": evidence,
            "citation": {"id": "SYNTHETIC" if evidence == "documented" else None},
        },
    }


def _synthetic_record(
    values: dict[str, int],
    tags: list[str],
    *,
    context_mismatch: bool = False,
) -> dict[str, Any]:
    shared = {
        "entity": "synthetic-entity",
        "reporting_date": "2025-12-31",
        "accounting_scope": ("synthetic-accession", "10-K"),
        "currency": "USD",
    }
    contexts = {tag: copy.deepcopy(shared) for tag in tags}
    if context_mismatch:
        contexts[tags[-1]]["reporting_date"] = "2024-12-31"
    return {**values, "_field_context": contexts}


def _synthetic_cases() -> tuple[list[dict[str, Any]], list[bool], list[dict[str, Any]], list[bool]]:
    cases = [
        {
            "candidate": _synthetic_candidate("documented-rule", "A", ["B", "C"], evidence="documented"),
            "discovery": [_synthetic_record({"A": 10, "B": 4, "C": 6}, ["A", "B", "C"])],
            "heldout": [
                _synthetic_record({"A": 10, "B": 4, "C": 6}, ["A", "B", "C"]),
                _synthetic_record({"A": 11, "B": 4, "C": 6}, ["A", "B", "C"]),
            ],
            "oracle_rule_valid": True,
            "record_labels": [False, True],
            "scenario": "documented_rule",
        },
        {
            "candidate": _synthetic_candidate("spurious-pattern", "D", ["E", "F"], evidence="not_found"),
            "discovery": [_synthetic_record({"D": 9, "E": 4, "F": 5}, ["D", "E", "F"])],
            "heldout": [_synthetic_record({"D": 9, "E": 4, "F": 5}, ["D", "E", "F"])],
            "oracle_rule_valid": False,
            "record_labels": [False],
            "scenario": "spurious_statistical_pattern",
        },
        {
            "candidate": _synthetic_candidate("incompatible-context", "G", ["H", "I"], evidence="documented"),
            "discovery": [
                _synthetic_record({"G": 10, "H": 4, "I": 6}, ["G", "H", "I"], context_mismatch=True)
            ],
            "heldout": [
                _synthetic_record({"G": 10, "H": 4, "I": 6}, ["G", "H", "I"], context_mismatch=True),
                _synthetic_record({"G": 10, "H": 4, "I": 6}, ["G", "H", "I"]),
            ],
            "oracle_rule_valid": False,
            "record_labels": [True, False],
            "scenario": "incompatible_context",
        },
        {
            "candidate": _synthetic_candidate("documented-data-conflict", "J", ["K", "L"], evidence="documented"),
            "discovery": [_synthetic_record({"J": 10, "K": 4, "L": 6}, ["J", "K", "L"])],
            "heldout": [
                _synthetic_record({"J": 10, "K": 4, "L": 6}, ["J", "K", "L"]),
                _synthetic_record({"J": 12, "K": 4, "L": 6}, ["J", "K", "L"]),
            ],
            "oracle_rule_valid": True,
            "record_labels": [False, True],
            "scenario": "documented_data_conflict",
        },
    ]
    rule_labels = [case["oracle_rule_valid"] for case in cases]
    record_cases = [
        {"candidate": case["candidate"], "record": record}
        for case in cases
        for record in case["heldout"]
    ]
    record_labels = [label for case in cases for label in case["record_labels"]]
    return cases, rule_labels, record_cases, record_labels


def _rule_prediction(case: dict[str, Any], method: str) -> bool | None:
    candidate = case["candidate"]
    discovery = case["discovery"]
    outcomes = [_rule_violation(candidate, row) for row in discovery]
    observed = [outcome for outcome in outcomes if outcome is not None]
    fit = 1 - sum(observed) / len(observed) if observed else 0
    context_compatible = not any(
        _context_mismatch_for(candidate, row) for row in discovery
    )
    if method == "global":
        return fit >= THRESHOLD
    if method == "context_aware":
        return fit >= THRESHOLD and context_compatible
    if method == "evidence_gated":
        if candidate["documented_evidence"]["status"] != "documented" or not context_compatible:
            return None
        return True
    raise ValueError(f"unknown method: {method}")


def _context_mismatch_for(candidate: dict[str, Any], record: dict[str, Any]) -> bool:
    params = candidate["parameters"]
    tags = [params["result"], *params["terms"]]
    contexts = [record.get("_field_context", {}).get(tag) for tag in tags]
    if any(context is None for context in contexts):
        return True
    keys = ("entity", "reporting_date", "accounting_scope", "currency")
    return any(len({repr(context.get(key)) for context in contexts}) > 1 for key in keys)


def _evaluate_synthetic() -> dict[str, Any]:
    cases, rule_labels, record_cases, record_labels = _synthetic_cases()
    methods = {}
    for method in METHODS:
        rule_predictions = [_rule_prediction(case, method) for case in cases]
        record_predictions = [
            _predict(pair["candidate"], pair["record"], method)
            for pair in record_cases
        ]
        rule_metrics = _metrics(rule_predictions, rule_labels)
        methods[method] = {
            "rule_level": {
                **rule_metrics,
                "selective_coverage": rule_metrics["coverage"],
                "selective_precision": (
                    sum(prediction is True and label for prediction, label in zip(rule_predictions, rule_labels))
                    / sum(prediction is True for prediction in rule_predictions)
                    if any(prediction is True for prediction in rule_predictions) else None
                ),
                "scenario_decisions": {
                    case["scenario"]: prediction
                    for case, prediction in zip(cases, rule_predictions)
                },
            },
            "record_level_detection": _metrics(record_predictions, record_labels),
        }
    return {
        "label": "synthetic only; oracle labels are separate from discovery inputs and detector inputs",
        "case_count": len(cases),
        "record_count": len(record_cases),
        "oracle_labels": {
            "rule_correctness": [case["oracle_rule_valid"] for case in cases],
            "record_error": record_labels,
            "used_for_discovery_or_prediction": False,
        },
        "methods": methods,
    }


def _real_sec_control(root: Path) -> dict[str, Any]:
    source_path = root / "data" / "originals" / "sec" / "companyfacts" / "0000320193_apple.json"
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    metadata_path = root / "data" / "metadata" / "sec-companyfacts-0000320193.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    discovery, heldout = _split(_sec_rows(payload), group_by="end")
    candidates = discover_sec_identities(discovery, metadata, metadata_path)
    registry = json.loads((root / "data" / "evidence" / "sec_constraints.json").read_text(encoding="utf-8"))
    for candidate in candidates:
        assertion = candidate["rule"]["assertion"]
        columns = [assertion["result_column"], *assertion["term_columns"]]
        units = [column.rsplit("[", 1)[-1].rstrip("]") for column in columns if "[" in column]
        candidate["documented_evidence"] = _match_sec_evidence(
            candidate["rule"],
            registry,
            {
                "same-entity": bool(payload.get("cik") or payload.get("entityName")),
                "same-reporting-date": True,
                "same-accounting-scope": True,
                "same-currency": len(units) == len(columns) and len(set(units)) == 1,
            },
        )
    positive = next(
        (candidate for candidate in candidates
         if candidate["documented_evidence"].get("citation", {}).get("id") == SEC_EVIDENCE_ID),
        None,
    )
    if positive is None:
        raise RuntimeError(f"Real SEC positive control {SEC_EVIDENCE_ID} was not discovered")
    tags = [positive["parameters"]["result"], *positive["parameters"]["terms"]]
    applicable = [row for row in heldout if all(tag in row for tag in tags)]
    violations = sum(_rule_violation(positive, row) is True for row in applicable)
    return {
        "status": "real SEC evidence-backed positive control; not synthetic",
        "candidate_id": positive["rule"]["id"],
        "evidence_id": SEC_EVIDENCE_ID,
        "evidence_url": positive["documented_evidence"]["citation"]["source_url"],
        "discovery_rows": len(discovery),
        "heldout_reporting_dates": len(heldout),
        "applicable_heldout_facts": len(applicable),
        "heldout_violations": violations,
        "rule_correctness_label": "N/A; source citation is not ground truth",
        "record_error_labels": "N/A; observed violations are not independently adjudicated errors",
        "verification_status": positive["rule"]["verification_status"],
    }


def run_benchmark(root: Path) -> dict[str, Any]:
    root = root.resolve()
    return {
        "benchmark": "MetaVerify Module 2E semantic reliability",
        "synthetic": _evaluate_synthetic(),
        "real_data_positive_control": _real_sec_control(root),
        "interpretation": "Synthetic metrics use explicit benchmark oracles. Real SEC evidence and held-out fit are reported separately and do not establish semantic correctness.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("data/semantic-reliability.json"))
    args = parser.parse_args()
    report = run_benchmark(args.root)
    output = args.root / args.output if not args.output.is_absolute() else args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
