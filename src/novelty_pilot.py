"""Small discovery/held-out comparison of candidate constraint selectors."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import time
from pathlib import Path
from typing import Any


THRESHOLD = 0.99
SEED = 2401


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _split(rows: list[dict[str, Any]], *, group_by: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rng = random.Random(SEED)
    if group_by is None:
        shuffled = rows.copy()
        rng.shuffle(shuffled)
        cut = int(len(shuffled) * 0.7)
        return shuffled[:cut], shuffled[cut:]
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row[group_by]), []).append(row)
    keys = sorted(groups)
    rng.shuffle(keys)
    cut = max(1, int(len(keys) * 0.7))
    discovery_keys = set(keys[:cut])
    discovery = [row for key, group in groups.items() if key in discovery_keys for row in group]
    heldout = [row for key, group in groups.items() if key not in discovery_keys for row in group]
    return discovery, heldout


def _rule(
    metadata_path: Path,
    metadata: dict[str, Any],
    rule_id: str,
    columns: list[str],
    rule_type: str,
    condition: dict[str, Any] | None,
    assertion: dict[str, Any],
    evidence_url: str,
    evidence_text: str,
) -> dict[str, Any]:
    source = next(
        (item for item in metadata["provenance"]["sources"] if item["url"] == evidence_url),
        metadata["provenance"]["sources"][0],
    )
    return {
        "schema_version": "1.0",
        "id": rule_id,
        "dataset_id": metadata["dataset"]["id"],
        "columns": columns,
        "rule_type": rule_type,
        "condition": condition,
        "assertion": assertion,
        "evidence": [{"description": evidence_text, "source_url": evidence_url}],
        "provenance": {
            "metadata_file": metadata_path.as_posix(),
            "metadata_sha256": _sha256(metadata_path),
            "source_files": [source],
        },
        "confidence": 0.25 if "statistical" in evidence_text.lower() else 0.55,
        "verification_status": "candidate",
    }


def _candidate(
    rule: dict[str, Any],
    scope: str,
    evidence_supported: bool,
    evaluator: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return {
        "rule": rule,
        "scope": scope,
        "evidence_supported": evidence_supported,
        "evaluator": evaluator,
        "parameters": parameters,
    }


def _rule_valid(candidate: dict[str, Any], row: dict[str, Any]) -> bool | None:
    params = candidate["parameters"]
    evaluator = candidate["evaluator"]
    if evaluator == "range":
        if params.get("group") and row[params["group"]] != params["group_value"]:
            return None
        value = float(row[params["column"]])
        return params["lower"] <= value <= params["upper"]
    if evaluator == "failure_implication":
        if not any(int(row[name]) == 1 for name in params["flags"]):
            return None
        return int(row[params["target"]]) == 1
    if evaluator == "nonnegative":
        return float(row[params["column"]]) >= 0
    if evaluator == "assets_cover_liabilities":
        if params.get("form") and row["form"] != params["form"]:
            return None
        return float(row["assets"]) >= float(row["liabilities"])
    raise ValueError(f"unknown evaluator: {evaluator}")


def _score_candidate(candidate: dict[str, Any], rows: list[dict[str, Any]]) -> float | None:
    outcomes = [_rule_valid(candidate, row) for row in rows]
    applicable = [outcome for outcome in outcomes if outcome is not None]
    if not applicable:
        return None
    return sum(applicable) / len(applicable)


def _decision(
    outcome: bool | None,
    *,
    selected: bool,
    evidence_supported: bool,
    strategy: str,
) -> str:
    if not selected or outcome is None or (strategy == "evidence_gated" and not evidence_supported):
        return "abstain"
    return "accept" if outcome else "reject"


def _ai4i_candidates(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    metadata_path = root / "data" / "metadata" / "ai4i-2020.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    data_path = root / "data" / "originals" / "ai4i" / "ai4i2020.csv"
    with data_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    discovery, heldout = _split(rows)
    values = [float(row["Air temperature [K]"]) for row in discovery]
    candidates = []

    def add_range(scope: str, group: str | None, group_value: str | None, subset: list[dict[str, Any]]) -> None:
        lower = min(float(row["Air temperature [K]"]) for row in subset)
        upper = max(float(row["Air temperature [K]"]) for row in subset)
        rule_id = "ai4i-air-temperature-global" if group is None else f"ai4i-air-temperature-type-{group_value}"
        condition = None if group is None else {"op": "eq", "column": group, "value": group_value}
        rule = _rule(
            metadata_path,
            metadata,
            rule_id,
            ["Air temperature [K]"] if group is None else [group, "Air temperature [K]"],
            "conditional_range" if group else "conditional_range",
            condition,
            {"op": "between", "column": "Air temperature [K]", "lower": lower, "upper": upper},
            "https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset",
            "Statistical bounds learned from discovery rows; UCI documents a generated distribution, not hard integrity limits.",
        )
        candidates.append(
            _candidate(rule, scope, False, "range", {
                "column": "Air temperature [K]", "lower": lower, "upper": upper,
                "group": group, "group_value": group_value,
            })
        )

    add_range("global", None, None, discovery)
    for kind in sorted({row["Type"] for row in discovery}):
        subset = [row for row in discovery if row["Type"] == kind]
        add_range("conditional", "Type", kind, subset)

    for flag in ("TWF", "HDF", "PWF", "OSF", "RNF"):
        rule = _rule(
            metadata_path,
            metadata,
            f"ai4i-{flag.lower()}-implies-machine-failure",
            [flag, "Machine failure"],
            "cross_field",
            {"op": "eq", "column": flag, "value": 1},
            {"op": "eq", "column": "Machine failure", "value": 1},
            "https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset",
            f"UCI documentation states that a true {flag} failure mode sets Machine failure to 1.",
        )
        candidates.append(
            _candidate(rule, "evidence", True, "failure_implication", {"flags": [flag], "target": "Machine failure"})
        )
    return candidates, discovery, heldout


def _sec_candidates(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    metadata_path = root / "data" / "metadata" / "sec-companyfacts-0000320193.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    source_path = root / "data" / "originals" / "sec" / "companyfacts" / "0000320193_apple.json"
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    facts = payload["facts"]["us-gaap"]
    facts_by_tag: dict[str, dict[str, dict[str, Any]]] = {}
    for column, tag in (("assets", "Assets"), ("liabilities", "Liabilities")):
        by_key = {}
        for unit, entries in facts[tag]["units"].items():
            for entry in entries:
                if not 2020 <= int(entry.get("end", "0")[:4]) <= 2025:
                    continue
                key = (entry.get("end"), entry.get("accn"), entry.get("form"), unit)
                by_key[key] = entry["val"]
        facts_by_tag[column] = by_key
    rows = [
        {"end": key[0], "accn": key[1], "form": key[2], "assets": assets, "liabilities": facts_by_tag["liabilities"][key]}
        for key, assets in facts_by_tag["assets"].items()
        if key in facts_by_tag["liabilities"] and key[2] in {"10-K", "10-Q"}
    ]
    discovery, heldout = _split(rows, group_by="end")
    candidates = []
    sec_url = "https://www.sec.gov/edgar/sec-api-documentation"
    evidence_text = "Statistical regularity in SEC facts; SEC API documentation describes concepts and reporting fields, not this integrity constraint."
    for column in ("assets", "liabilities"):
        rule = _rule(
            metadata_path, metadata, f"sec-{column}-nonnegative", [column], "conditional_range", None,
            {"op": "gte", "column": column, "value": 0}, sec_url, evidence_text,
        )
        candidates.append(_candidate(rule, "global", False, "nonnegative", {"column": column}))
    for form in sorted({row["form"] for row in discovery}):
        rule = _rule(
            metadata_path, metadata, f"sec-assets-cover-liabilities-{form}", ["form", "assets", "liabilities"],
            "cross_field", {"op": "eq", "column": "form", "value": form},
            {"op": "gte", "left_column": "assets", "right_column": "liabilities"},
            sec_url, evidence_text,
        )
        candidates.append(_candidate(rule, "conditional", False, "assets_cover_liabilities", {"form": form}))
    return candidates, discovery, heldout


def _evaluate(
    candidates: list[dict[str, Any]],
    discovery: list[dict[str, Any]],
    heldout: list[dict[str, Any]],
    schema_path: Path,
) -> dict[str, Any]:
    from jsonschema import Draft202012Validator, FormatChecker

    validator = Draft202012Validator(
        json.loads(schema_path.read_text(encoding="utf-8")),
        format_checker=FormatChecker(),
    )
    for candidate in candidates:
        validator.validate(candidate["rule"])
        candidate["discovery_pass_rate"] = _score_candidate(candidate, discovery)
    results = {}
    for strategy in ("global", "conditional", "evidence_gated"):
        started = time.perf_counter()
        if strategy == "evidence_gated":
            selected = [item for item in candidates if item["evidence_supported"]]
        else:
            scope = "global" if strategy == "global" else "conditional"
            selected = [
                item for item in candidates
                if item["scope"] == scope
                and item["discovery_pass_rate"] is not None
                and item["discovery_pass_rate"] >= THRESHOLD
            ]
        unsupported = sum(not item["evidence_supported"] for item in candidates)
        decisions = {"accept": 0, "reject": 0, "abstain": 0}
        heldout_rates = {}
        rule_decisions = {}
        for candidate in candidates:
            is_selected = candidate in selected
            outcomes = [
                outcome
                for row in heldout
                if (outcome := _rule_valid(candidate, row)) is not None
            ]
            pass_rate = sum(outcomes) / len(outcomes) if outcomes else None
            heldout_rates[candidate["rule"]["id"]] = pass_rate
            decision = _decision(
                all(outcomes) if outcomes else None,
                selected=is_selected,
                evidence_supported=candidate["evidence_supported"],
                strategy=strategy,
            )
            decisions[decision] += 1
            rule_decisions[candidate["rule"]["id"]] = {
                "selected": is_selected,
                "independently_documented": candidate["evidence_supported"],
                "heldout_applicable_rows": len(outcomes),
                "heldout_violations": sum(not outcome for outcome in outcomes),
                "decision": decision,
            }
        runtime = time.perf_counter() - started
        results[strategy] = {
            "selected_rules": [item["rule"]["id"] for item in selected],
            "rule_precision": decisions["accept"] / len(selected) if selected else None,
            "false_positive_rate": (
                sum(not item["evidence_supported"] for item in selected) / unsupported
                if unsupported else 0.0
            ),
            "coverage": len(selected) / len(candidates) if candidates else 0.0,
            "decisions": decisions,
            "heldout_rule_pass_rates": heldout_rates,
            "rule_decisions": rule_decisions,
            "runtime_seconds": runtime,
        }
    return results


def run_pilot(root: Path) -> dict[str, Any]:
    schema_path = root / "data" / "rule.schema.json"
    datasets = {}
    for dataset_id, builder in (("ai4i-2020", _ai4i_candidates), ("sec-companyfacts-0000320193", _sec_candidates)):
        candidates, discovery, heldout = builder(root)
        datasets[dataset_id] = {
            "split": {
                "method": "seeded 70/30 random rows (AI4I); seeded 70/30 reporting-end-date groups (SEC)",
                "seed": SEED,
                "discovery_rows": len(discovery),
                "heldout_rows": len(heldout),
            },
            "candidate_count": len(candidates),
            "selection_threshold": THRESHOLD,
            "metrics": _evaluate(candidates, discovery, heldout, schema_path),
        }
    return {
        "pilot": "MetaVerify Module 2A novelty pilot",
        "warning": "Empirical regularities are unverified candidates, not integrity rules. Only independently documented assertions are evidence-gated.",
        "metric_definitions": {
            "rule_precision": "selected rules with independent documentation support and zero held-out violations / selected rules; null when none selected",
            "false_positive_rate": "selected unsupported candidates / all unsupported candidates (conservative proxy, not a measured error rate)",
            "coverage": "selected candidate rules / all candidate rules",
            "decisions": "per-rule pilot decisions; unsupported statistical candidates always abstain, regardless of held-out pass rate",
        },
        "decision_semantics": {
            "accept": "independently documented candidate with zero observed held-out violations; remains unverified",
            "reject": "independently documented candidate with at least one held-out violation; indicates a rule/data conflict, not a finding of bad data",
            "abstain": "unsupported, unselected, or not evaluable candidate",
        },
        "datasets": datasets,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("data/novelty-pilot.json"))
    args = parser.parse_args()
    result = run_pilot(args.root)
    output = args.root / args.output if not args.output.is_absolute() else args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
