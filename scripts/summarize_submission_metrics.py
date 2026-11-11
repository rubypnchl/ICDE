"""Read-only, source-report-grounded numerical and policy metrics for MetaVerify.

This is NOT an independent gold-standard evaluation, published SOTA comparison,
or proof of improved constraint discovery. Does not load or export raw NHANES rows.

python scripts/summarize_submission_metrics.py \
    --source-cache '<external NHANES cache>' \
    --sec-controls '<external SEC controls.json>' \
    --output '<external cache>/Submission_Metrics_Overview_v1.json'
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.summarize_sec_ablation import summarize as summarize_sec

PAIR_IDS = {"TRIGLY_TR_UNIT", "TRIGLY_LDL_UNIT", "TCHOL_TC_UNIT"}
METHODS = {"documented_cdc_factor", "train_median_ratio", "train_least_squares"}
TOLERANCES = {"0.0005", "0.005"}
SHIFTS_BASELINE = {"-0.01", "-0.005", "-0.001", "0.001", "0.005", "0.01"}
SHIFTS_PERTURB = {"0.001", "0.005", "0.01"}


class MetricsError(ValueError):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise MetricsError(reason)


def whole(value, label: str) -> int:
    require(type(value) is int and value >= 0, f"Invalid count: {label}")
    return value


def rate(n: int, d: int) -> float:
    require(d > 0 and 0 <= n <= d, "Invalid rate numerator/denominator")
    return round(100.0 * n / d, 4)


def keyed(rows: list, key: str, expected: set, title: str) -> dict:
    require(isinstance(rows, list) and len(rows) == len(expected), f"Wrong {title} row count")
    require(all(isinstance(x, dict) and isinstance(x.get(key), str) for x in rows), f"Bad {title} row")
    out = {x[key]: x for x in rows}
    require(len(out) == len(rows) and set(out) == expected, f"Wrong/duplicate {title} identifiers")
    return out


def calculate(b11: dict, b12: dict, perturb: dict, baseline: dict, controls: dict) -> dict:
    """Validate cross-report conservation and derive descriptive metrics only."""
    require(b11.get("study_id") == "b13_11_real_xpt_matched_compiler_diagnostic_v1", "Unexpected B13.11")
    require(b11.get("gold_rules") == 0 and b11.get("independent_documentary_reviews") == 0
            and b11.get("source_clusters") == 1 and b11.get("pair_candidates_hand_curated") == 3
            and b11.get("exact_equality_mismatch_counts_are_data_errors") is False,
            "B13.11 scientific scope changed")
    require(b12.get("study_id") == "b13_12_fixed_grid_precision_sensitivity_v1"
            and b12.get("gold_rules") == 0 and b12.get("thresholds_independently_justified") is False,
            "B13.12 scientific scope changed")
    require(perturb.get("study_id") == "metaverify_submission_day_controlled_precision_perturbation_v1"
            and perturb.get("source_clusters") == 1 and perturb.get("independent_semantic_gold") == 0
            and perturb.get("candidate_admission_accuracy_measured") is False,
            "Perturbation scientific scope changed")
    require(baseline.get("study_id") == "metaverify_matched_numeric_coefficient_baselines_v1"
            and baseline.get("source_group_count") == 1 and baseline.get("independent_semantic_gold") == 0
            and baseline.get("real_sota_guardrail_run") is False
            and baseline.get("real_sota_autotest_run") is False,
            "Matched-baseline scientific scope changed")

    rows11 = keyed(b11.get("pair_outcomes"), "pair_id", PAIR_IDS, "B13.11")
    rows12 = keyed(b12.get("pairs"), "pair_id", PAIR_IDS, "B13.12")
    counts = Counter()
    tolerance = {t: Counter() for t in ("0.0005", "0.005")}
    per_pair = {}
    for pid in sorted(PAIR_IDS):
        r = rows11[pid]
        c = r.get("b3_counts", {})
        require(isinstance(c, dict) and set(c) == {"satisfied", "violated", "abstained", "not_applicable"},
                f"B13.11 status schema changed for {pid}")
        for name, value in c.items():
            counts[name] += whole(value, f"{pid}.{name}")
        total = whole(r.get("record_count"), f"{pid}.record_count")
        evaluated = whole(r.get("evaluated_records"), f"{pid}.evaluated_records")
        require(sum(c.values()) == total and c["satisfied"] + c["violated"] == evaluated
                and c["not_applicable"] == 0, f"B13.11 record conservation failed for {pid}")
        g = rows12[pid]
        require(g.get("paired_nonmissing") == evaluated and g.get("previous_exact_counts") == c,
                f"B13.12 parent mismatch for {pid}")
        grid = keyed(g.get("grid"), "tolerance_mmol_l", {"0.0005", "0.005", "0.01", "0.05", "0.1"},
                     f"B13.12 grid {pid}")
        for t in tolerance:
            cell = grid[t]
            m = whole(cell.get("satisfied"), f"{pid}.{t}.satisfied")
            v = whole(cell.get("mismatched"), f"{pid}.{t}.mismatched")
            a = whole(cell.get("abstained"), f"{pid}.{t}.abstained")
            require(m + v == evaluated and a == c["abstained"], f"B13.12 conservation failed: {pid}/{t}")
            tolerance[t]["satisfied"] += m
            tolerance[t]["mismatched"] += v
        per_pair[pid] = {"source_rows": total, "evaluated": evaluated, "abstained": c["abstained"],
                         "strict_satisfied": c["satisfied"], "strict_mismatched": c["violated"],
                         "within_0_0005": grid["0.0005"]["satisfied"],
                         "within_0_005": grid["0.005"]["satisfied"]}
    candidate_checks = sum(x["source_rows"] for x in per_pair.values())
    evaluated_total = sum(x["evaluated"] for x in per_pair.values())
    require(candidate_checks == evaluated_total + counts["abstained"], "NHANES total conservation failed")

    pert_rows = perturb.get("cells")
    require(isinstance(pert_rows, list) and len(pert_rows) == 18, "Wrong perturbation grid size")
    pert_seen = set()
    controlled = Counter()
    for row in pert_rows:
        pid, tol, shift = row.get("pair_id"), row.get("tolerance_mmol_l"), row.get("added_to_recorded_right_mmol_l")
        ident = (pid, tol, shift)
        require(pid in PAIR_IDS and tol in TOLERANCES and shift in SHIFTS_PERTURB
                and ident not in pert_seen, "Unexpected/duplicate perturbation cell")
        pert_seen.add(ident)
        original, shifted = row.get("unchanged"), row.get("shifted")
        require(isinstance(original, dict) and isinstance(shifted, dict), "Missing paired perturbation counts")
        base = next(x for x in rows12[pid]["grid"] if x["tolerance_mmol_l"] == tol)
        require(original.get("satisfied") == base["satisfied"] and original.get("violated") == base["mismatched"]
                and original.get("abstained") == base["abstained"], "Perturbation's original counts differ from B13.12")
        flagged = whole(row.get("satisfied_to_violated"), "perturbation newly flagged")
        resolved = whole(row.get("violated_to_satisfied"), "perturbation resolved")
        require(flagged <= original["satisfied"] and resolved <= original["violated"]
                and shifted.get("violated") == original["violated"] + flagged - resolved
                and shifted.get("satisfied") == original["satisfied"] - flagged + resolved
                and shifted.get("abstained") == original["abstained"], "Perturbation conservation failed")
        if (tol, shift) == ("0.005", "0.01"):
            controlled["checked"] += whole(row.get("paired_nonmissing"), "perturbation test count")
            controlled["flagged_after_shift"] += shifted["violated"]
            controlled["newly_flagged"] += flagged
            controlled["previously_satisfied"] += original["satisfied"]
    require(len(pert_seen) == 18, "Incomplete perturbation combinations")

    base_pairs = keyed(baseline.get("pairs"), "pair_id", PAIR_IDS, "baseline pairs")
    base_rows = baseline.get("cells")
    require(isinstance(base_rows, list) and len(base_rows) == 108, "Wrong matched-baseline grid size")
    base_seen = set()
    method_totals = {method: Counter() for method in sorted(METHODS)}
    for row in base_rows:
        pid, method = row.get("pair_id"), row.get("method")
        tol, shift = row.get("tolerance_mmol_l"), row.get("synthetic_shift_mmol_l")
        ident = (pid, method, tol, shift)
        require(pid in PAIR_IDS and method in METHODS and tol in TOLERANCES
                and shift in SHIFTS_BASELINE and ident not in base_seen,
                "Unexpected/duplicate matched-baseline cell")
        base_seen.add(ident)
        n = whole(row.get("test_nonmissing"), "baseline complete test records")
        abst = whole(row.get("test_abstained"), "baseline abstained records")
        satisfied = whole(row.get("unmodified_satisfied"), "baseline originally satisfied")
        mismatch = whole(row.get("unmodified_violated"), "baseline originally violated")
        modified = whole(row.get("modified_violated"), "baseline modified violated")
        flagged = whole(row.get("newly_flagged"), "baseline newly flagged")
        resolved = whole(row.get("violated_to_satisfied"), "baseline previously violated now satisfied")
        require(n == satisfied + mismatch and n + abst == base_pairs[pid]["test_rows"]
                and n == base_pairs[pid]["test_nonmissing"] and modified == mismatch + flagged - resolved
                and flagged <= satisfied and resolved <= mismatch,
                "Matched-baseline paired count conservation failed")
        if (tol, shift) == ("0.005", "0.01"):
            totals = method_totals[method]
            totals["test_checks"] += n
            totals["originally_satisfied"] += satisfied
            totals["originally_flagged"] += mismatch
            totals["modified_flagged"] += modified
            totals["newly_flagged"] += flagged
    require(len(base_seen) == 108, "Incomplete baseline combinations")

    sec = summarize_sec(controls)
    sec_n = sec["controlled_scenario_count"]
    sec_rates = {arm: {state: {"count": v, "rate_pct": rate(v, sec_n)}
                       for state, v in sec["arm_counts"][arm].items()} for arm in "ABC"}
    method_summary = {}
    for method, item in method_totals.items():
        method_summary[method] = dict(item)
        method_summary[method]["shifted_flagged_rate_pct"] = rate(item["modified_flagged"], item["test_checks"])
        method_summary[method]["new_flags_among_initially_satisfied_pct"] = rate(item["newly_flagged"], item["originally_satisfied"])

    return {
        "study": "metaverify_submission_metrics_synthesis_v1",
        "scope": "descriptive_existing_runs_not_independent_gold_or_SOTA",
        "nhanes": {
            "survey_cycle_clusters": 1, "hand_curated_relationships": 3,
            "pair_record_checks_total": candidate_checks, "evaluated_checks": evaluated_total,
            "evaluation_coverage_pct": rate(evaluated_total, candidate_checks),
            "abstained_checks": counts["abstained"],
            "abstention_rate_pct": rate(counts["abstained"], candidate_checks),
            "strict_equality_mismatches": counts["violated"],
            "strict_equality_satisfied": counts["satisfied"],
            "strict_mismatch_rate_among_evaluated_pct": rate(counts["violated"], evaluated_total),
            "exploratory_tolerance": {t: {"within_tolerance": counts["satisfied"],
                "within_tolerance_rate_among_evaluated_pct": rate(counts["satisfied"], evaluated_total)}
                for t, counts in tolerance.items()},
            "per_relationship": per_pair,
        },
        "controlled_perturbation": {
            "tolerance_mmol_l": "0.005", "positive_shift_mmol_l": "0.01",
            **dict(controlled), "shifted_flagged_rate_pct": rate(controlled["flagged_after_shift"], controlled["checked"]),
            "newly_flagged_among_originally_satisfied_pct": rate(controlled["newly_flagged"], controlled["previously_satisfied"]),
        },
        "matched_numeric_coefficient_baselines": {
            "tolerance_mmol_l": "0.005", "positive_shift_mmol_l": "0.01",
            "methods": method_summary, "benchmark_type": "same_B4_B3_engine_with_alternate_coefficient_values_not_published_SOTA",
        },
        "sec_controlled_policy": {
            "independent_candidates": 1, "repeated_scenarios": sec_n,
            "simulated_evidence_scenarios": sec["simulated_evidence_scenarios"],
            "arm_decision_rates": sec_rates,
            "A_to_B": sec["A_to_B"], "B_to_C": sec["B_to_C"],
            "C_by_classification": sec["C_by_classification"],
        },
        "effectiveness_not_estimable": {
            "admission_precision": None, "invalid_admission_rate": None,
            "independent_discovery_precision": None, "independent_discovery_recall": None,
            "natural_error_detection_precision": None, "natural_error_detection_recall": None,
            "F1": None, "p95_runtime_seconds": None, "published_sota_improvement": None,
            "reason": "No independently adjudicated candidate/error reference set, matched published SOTA run or instrumented runtime report",
        },
        "limitations": [
            "All NHANES relationships are previously inspected and from one survey cycle; pair-record checks are not independent participants.",
            "Exploratory numeric tolerances are not certified clinical/source rounding rules; strict mismatches are not natural defects.",
            "Controlled shifts target the tested predicate; they do not establish recall on naturally occurring errors.",
            "SEC policy configurations repeat one candidate; simulated evidence flags are not reviewer decisions.",
            "Matched numerical baselines change coefficients but reuse B4/B3; no published SOTA system was run.",
            "No semantic accuracy, admission benefit, false-positive reduction, independent gold, uncertainty or inferential claims.",
        ],
    }


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    require(isinstance(data, dict), f"Expected report object in {path.name}")
    return data


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-cache", type=Path, required=True, help="Existing external NHANES evaluation report directory")
    p.add_argument("--sec-controls", type=Path, required=True, help="Existing controls.json; no source records")
    p.add_argument("--output", type=Path, help="Optional external JSON output, exclusively created; never overwritten")
    args = p.parse_args()
    cache = args.source_cache.resolve()
    require(cache.is_dir() and cache != ROOT and ROOT not in cache.parents,
            "NHANES source cache must be an existing external directory")
    inputs = [cache / name for name in (
        "B13_11_retrospective_matched_replay_v1.json",
        "B13_12_fixed_grid_sensitivity_v1.json",
        "Submission_Day_Precision_Perturbation_v1.json",
        "Submission_Day_Matched_Numeric_Baselines_v1.json",
    )]
    controls = args.sec_controls.resolve()
    require(controls.is_file(), "SEC controls.json is missing")
    report = calculate(*(load_json(path) for path in inputs), load_json(controls))
    payload = json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.output:
        output = args.output.resolve()
        require(output.parent.is_dir() and output.parent != ROOT and ROOT not in output.parent.parents,
                "Metrics output must remain outside the Git repository")
        with output.open("x", encoding="utf-8") as target:
            target.write(payload)
        print("SAVED:", output)
    print(payload, end="")


if __name__ == "__main__":
    try:
        main()
    except (MetricsError, ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        print("METRICS STOP:", type(exc).__name__, str(exc), file=sys.stderr)
        raise SystemExit(2)
