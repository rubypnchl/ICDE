"""Evaluate SEC error detection on deterministic, controlled held-out injections."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from src.rule_discovery import (
    _match_sec_evidence,
    _number,
    _sec_rows,
    _split,
    discover_sec_identities,
)


METHODS = ("global", "context_aware", "evidence_gated")
CONTEXT_KEYS = ("entity", "reporting_date", "accounting_scope", "currency")


def _prepare_candidate(
    candidate: dict[str, Any],
    registry: dict[str, Any],
    source: dict[str, Any],
) -> None:
    assertion = candidate["rule"]["assertion"]
    columns = [assertion["result_column"], *assertion["term_columns"]]
    units = [column.rsplit("[", 1)[-1].rstrip("]") for column in columns if "[" in column]
    context = {
        "same-entity": bool(source.get("cik") or source.get("entityName")),
        "same-reporting-date": True,
        "same-accounting-scope": True,
        "same-currency": len(units) == len(columns) and len(set(units)) == 1,
    }
    candidate["documented_evidence"] = _match_sec_evidence(
        candidate["rule"], registry, context,
    )


def _record_context(row: dict[str, Any], entity: str) -> dict[str, Any]:
    return {
        "entity": entity,
        "reporting_date": row["end"],
        "accounting_scope": (row["accn"], row["form"]),
        "currency": row["unit"],
    }


def _make_benchmark(
    heldout: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    entity: str,
) -> tuple[list[dict[str, Any]], list[bool]]:
    records: list[dict[str, Any]] = []
    labels: list[bool] = []
    for index, row in enumerate(heldout):
        record = copy.deepcopy(row)
        context = _record_context(row, entity)
        record["_field_context"] = {
            tag: copy.deepcopy(context)
            for candidate in candidates
            for tag in [candidate["parameters"]["result"], *candidate["parameters"]["terms"]]
            if tag in row
        }
        record["_record_id"] = f"heldout-{index}"
        records.append(record)
        labels.append(False)

    evidence_candidate = next(
        (
            candidate for candidate in candidates
            if candidate["documented_evidence"].get("status") == "documented"
        ),
        None,
    )
    if evidence_candidate is None:
        raise RuntimeError("SEC evidence registry did not match a discovered held-out candidate")

    params = evidence_candidate["parameters"]
    base = next(
        (
            row for row in records
            if all(tag in row and _number(row[tag]) is not None
                   for tag in [params["result"], *params["terms"]])
        ),
        None,
    )
    if base is None:
        raise RuntimeError("No held-out SEC row supports the documented candidate")

    numeric_error = copy.deepcopy(base)
    expected = _number(numeric_error[params["terms"][0]]) + _number(numeric_error[params["terms"][1]])
    numeric_error[params["result"]] = expected + abs(expected) + 1
    numeric_error["_record_id"] = "injected-numeric-error"
    records.append(numeric_error)
    labels.append(True)

    context_error = copy.deepcopy(base)
    altered_tag = params["terms"][0]
    context_error["_field_context"][altered_tag]["reporting_date"] = (
        "mismatched:" + context_error["_field_context"][altered_tag]["reporting_date"]
    )
    context_error["_record_id"] = "injected-context-mismatch"
    records.append(context_error)
    labels.append(True)
    return records, labels


def _context_mismatch(candidate: dict[str, Any], record: dict[str, Any]) -> bool:
    params = candidate["parameters"]
    tags = [params["result"], *params["terms"]]
    contexts = [
        record.get("_field_context", {}).get(tag)
        for tag in tags
    ]
    if any(context is None for context in contexts):
        return True
    return any(
        len({repr(context.get(key)) for context in contexts}) > 1
        for key in CONTEXT_KEYS
    )


def _rule_violation(candidate: dict[str, Any], record: dict[str, Any]) -> bool | None:
    params = candidate["parameters"]
    values = [_number(record.get(tag)) for tag in [params["result"], *params["terms"]]]
    if any(value is None for value in values):
        return None
    tolerance = _number(candidate["rule"]["assertion"].get("tolerance", 0)) or 0
    return abs(values[0] - values[1] - values[2]) > tolerance


def _predict(candidate: dict[str, Any], record: dict[str, Any], method: str) -> bool | None:
    if method not in METHODS:
        raise ValueError(f"unknown detection method: {method}")
    if method == "evidence_gated" and candidate["documented_evidence"].get("status") != "documented":
        return None
    violation = _rule_violation(candidate, record)
    if violation is None:
        return None
    mismatch = _context_mismatch(candidate, record)
    if method != "global" and mismatch:
        return True
    return violation


def _record_prediction(candidates: list[dict[str, Any]], record: dict[str, Any], method: str) -> bool | None:
    outcomes = [_predict(candidate, record, method) for candidate in candidates]
    applicable = [outcome for outcome in outcomes if outcome is not None]
    if not applicable:
        return None
    return any(applicable)


def _metrics(predictions: list[bool | None], labels: list[bool]) -> dict[str, Any]:
    # Abstention means no alert for confusion counts; abstentions are also reported separately.
    tp = sum(prediction is True and label for prediction, label in zip(predictions, labels))
    fp = sum(prediction is True and not label for prediction, label in zip(predictions, labels))
    fn = sum(prediction is not True and label for prediction, label in zip(predictions, labels))
    tn = sum(prediction is not True and not label for prediction, label in zip(predictions, labels))
    abstentions = sum(prediction is None for prediction in predictions)
    decided = len(predictions) - abstentions
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
    fpr = fp / (fp + tn) if fp + tn else None
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fpr": fpr,
        "coverage": decided / len(predictions) if predictions else 0.0,
        "abstentions": abstentions,
    }


def run_evaluation(root: Path) -> dict[str, Any]:
    root = root.resolve()
    sec_path = root / "data" / "originals" / "sec" / "companyfacts" / "0000320193_apple.json"
    payload = json.loads(sec_path.read_text(encoding="utf-8"))
    metadata_path = root / "data" / "metadata" / "sec-companyfacts-0000320193.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    rows = _sec_rows(payload)
    discovery, heldout = _split(rows, group_by="end")
    candidates = discover_sec_identities(discovery, metadata, metadata_path)
    registry_path = root / "data" / "evidence" / "sec_constraints.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    for candidate in candidates:
        _prepare_candidate(candidate, registry, payload)

    records, labels = _make_benchmark(
        heldout, candidates, str(payload.get("cik", payload.get("entityName", "unknown"))),
    )
    metrics = {
        method: _metrics(
            [_record_prediction(candidates, record, method) for record in records],
            labels,
        )
        for method in METHODS
    }
    return {
        "evaluation": "controlled SEC held-out injection benchmark",
        "split": "deterministic 70/30 reporting-end-date groups; candidates mined from discovery only",
        "record_count": len(records),
        "candidate_count": len(candidates),
        "candidate_assessment": {
            "evidence_matched": sum(c["documented_evidence"].get("status") == "documented" for c in candidates),
            "undocumented_or_incompatible": sum(c["documented_evidence"].get("status") != "documented" for c in candidates),
            "unverified_candidates": sum(c["rule"]["verification_status"] == "candidate" for c in candidates),
            "semantic_correctness": "not established; evidence matching is not candidate ground truth",
        },
        "metric_semantics": "abstentions count as no alert in confusion metrics and are separately reported; coverage counts non-abstained records",
        "record_labels": {
            "definition": "only injected numeric/context mutations are positive; held-out originals are untouched controls, not externally adjudicated SEC errors",
            "positive_injections": ["numeric_error", "context_mismatch"],
            "labels_used_for_prediction": False,
        },
        "methods": metrics,
        "record_ids": [record["_record_id"] for record in records],
        "candidate_ids": [candidate["rule"]["id"] for candidate in candidates],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("data/detection-evaluation.json"))
    args = parser.parse_args()
    result = run_evaluation(args.root)
    output = args.root / args.output if not args.output.is_absolute() else args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
