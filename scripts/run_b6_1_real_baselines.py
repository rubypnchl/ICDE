"""B6.1: read-only, local development-baseline evaluation of two provisional rules.

Only aggregates are saved. No network, LLM, sample selection, data modification,
held-out or gold-rule claims. Run as a script from the repository root.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.generic_verifier import evaluate_row, validate_rule

PROTOCOL_ID = "b6-frozen-protocol-v1"
SPECS = {
    "manufacturing": {
        "id": "B6-MAN-001",
        "dataset_id": "ai4i-2020",
        "source": "data/originals/ai4i/ai4i2020.csv",
        "source_type": "official_UCI_synthetic_dataset",
        "expected_rows": 10000,
    },
    "cybersecurity": {
        "id": "B6-CYB-001",
        "dataset_id": "cic-ids2017",
        "source": "data/samples/cic_ids2017/flows-50000.csv",
        "source_type": "development_reservoir_sample_not_entire_CICIDS2017",
        "expected_rows": 50000,
    },
}


class EvaluationError(ValueError):
    """Fail closed if provenance, inputs or rule scope differ from the frozen plan."""


def _json(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(result, dict):
        raise EvaluationError(f"Expected JSON object: {path}")
    return result


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _decimal(raw: Any) -> Decimal | None:
    if raw is None or isinstance(raw, bool) or str(raw).strip() == "":
        return None
    try:
        val = Decimal(str(raw).strip())
    except (InvalidOperation, TypeError, ValueError):
        return None
    return val if val.is_finite() else None


def _invalid_measurement(domain: str, row: dict[str, Any]) -> str | None:
    if domain == "manufacturing":
        # Source labels are defined as binary; B3's generic predicate alone
        # would treat some impossible label values as ordinary non-applicability.
        for col in ("TWF", "HDF", "PWF", "OSF", "RNF", "Machine failure"):
            if _decimal(row.get(col)) not in (Decimal(0), Decimal(1)):
                return f"missing_or_nonbinary_label:{col}"
    elif domain == "cybersecurity":
        count = _decimal(row.get(" Total Fwd Packets"))
        if count is None or count < 0 or count != count.to_integral_value():
            return "missing_or_invalid_forward_packet_count"
        # For positive counts, other measurements are evaluated by B3, which
        # abstains on missing / nonfinite numeric values.
    return None


def load_plan(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    cat = _json(root / "data/evaluation/b6_reference_catalogue.json")
    protocol = _json(root / "data/evaluation/b6_protocol_v1.json")
    manifest = _json(root / "data/sources.json")
    if (cat.get("protocol_id") != PROTOCOL_ID
            or protocol.get("protocol_id") != PROTOCOL_ID
            or cat.get("baseline_commit") != protocol.get("baseline_git_commit")
            or protocol.get("frozen_before_future_paid_comparison") is not True):
        raise EvaluationError("B6 catalogue/protocol changed or mismatched; halt for review")
    if not isinstance(manifest.get("datasets"), dict):
        raise EvaluationError("Source manifest missing datasets")
    return cat, protocol, manifest


def prepare(root: Path, domains: list[str]) -> dict[str, dict[str, Any]]:
    """Check all inputs before any result is written or counted."""
    cat, protocol, manifest = load_plan(root)
    found: dict[str, dict[str, Any]] = {}
    for domain in domains:
        cfg = SPECS[domain]
        matching = [e for e in cat.get("entries", []) if e.get("id") == cfg["id"]]
        if len(matching) != 1:
            raise EvaluationError(f"Exactly one reference entry required: {cfg['id']}")
        entry = matching[0]
        if (entry.get("status") != "provisional_source_supported"
                or entry.get("scoring_eligible") is not False
                or entry.get("domain") != domain
                or entry.get("dataset_id") != cfg["dataset_id"]):
            raise EvaluationError(f"Reference status or identity changed: {cfg['id']}")
        rule = entry.get("reference_rule")
        if not isinstance(rule, dict) or rule.get("id") != entry["id"]:
            raise EvaluationError(f"Missing/mismatched rule: {cfg['id']}")
        columns = validate_rule(rule)
        if columns != set(entry.get("columns", [])):
            raise EvaluationError(f"Rule references differ from catalogue: {cfg['id']}")
        rel = cfg["source"]
        src_meta = manifest["datasets"].get(cfg["dataset_id"], {})
        declared = src_meta.get("samples", []) if domain == "cybersecurity" else src_meta.get("files", [])
        if rel not in declared:
            raise EvaluationError(f"Source path is not in manifest for {domain}: {rel}")
        if domain == "cybersecurity":
            sample = src_meta.get("sampling", {})
            if sample.get("seed") != 2017 or sample.get("records_sampled") != cfg["expected_rows"]:
                raise EvaluationError("CIC reservoir sampling provenance has changed")
        path = root / rel
        if not path.is_file():
            raise EvaluationError(f"Required LOCAL CSV not found: {path}. Do not substitute another dataset.")
        if not isinstance(entry.get("evidence"), list) or not entry["evidence"]:
            raise EvaluationError(f"Reference evidence missing: {cfg['id']}")
        found[domain] = {"config": cfg, "entry": entry, "rule": rule, "path": path,
                         "columns": columns}
    return found


def evaluate_csv(domain: str, prepared: dict[str, Any]) -> dict[str, Any]:
    """Stream the full retained CSV without modifying it or storing any rows."""
    cfg = prepared["config"]
    path = prepared["path"]
    rule = prepared["rule"]
    needed = prepared["columns"]
    before = _sha256(path)
    counts: Counter[str] = Counter({name: 0 for name in ("satisfied", "violated", "abstained", "not_applicable")})
    reasons: Counter[str] = Counter()
    header_diagnostics: dict[str, Any] = {}
    started = time.perf_counter()
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        # Some CSV exports contain repeated names for unrelated fields. We
        # cannot use DictReader: duplicate names silently overwrite values.
        # The rule's required fields MUST be present exactly once; other
        # duplicate/empty headers are recorded, never silently discarded.
        reader = csv.reader(fh)
        fields = next(reader, None)
        if not fields:
            raise EvaluationError(f"Missing CSV header: {path}")
        frequencies = Counter(fields)
        missing = sorted(needed - set(fields))
        if missing:
            raise EvaluationError(f"Missing exact CSV columns in {path}: {missing}")
        ambiguous = sorted(name for name in needed if frequencies[name] != 1)
        if ambiguous:
            raise EvaluationError(f"Duplicate required CSV columns in {path}: {ambiguous}")
        positions = {name: fields.index(name) for name in needed}
        header_diagnostics = {
            "field_count": len(fields),
            "nonrequired_duplicate_names": sorted(
                name for name, count in frequencies.items()
                if count > 1 and name not in needed and name != ""
            ),
            "blank_header_positions_1based": [
                position + 1 for position, name in enumerate(fields) if name == ""
            ],
            "required_fields_unique": True,
            "reader": "positional_csv_reader_no_header_overwrite",
        }
        for line_number, values in enumerate(reader, start=2):
            if len(values) != len(fields):
                raise EvaluationError(
                    f"Malformed CSV row at logical line {line_number}: "
                    f"{len(values)} cells versus {len(fields)} headers in {path}"
                )
            # Only keep columns this reference rule uses; preserve exact
            # original column names, including significant leading spaces.
            row = {name: values[position] for name, position in positions.items()}
            failure = _invalid_measurement(domain, row)
            if failure is None:
                outcome = evaluate_row(rule, row)
                status, reason = outcome.status, outcome.reason
            else:
                status, reason = "abstained", failure
            counts[status] += 1
            reasons[f"{status}:{reason}"] += 1
    elapsed = round(time.perf_counter() - started, 6)
    after = _sha256(path)
    if before != after:
        raise EvaluationError(f"Local source file changed during evaluation: {path}")
    total = sum(counts.values())
    if total != cfg["expected_rows"]:
        raise EvaluationError(f"Unexpected source count for {domain}: {total} != {cfg['expected_rows']}")
    eligible = total - counts["not_applicable"]
    evaluated = counts["satisfied"] + counts["violated"]
    return {
        "reference_rule_id": cfg["id"], "domain": domain,
        "dataset_id": cfg["dataset_id"], "source_type": cfg["source_type"],
        "source_file": cfg["source"], "source_sha256": after,
        "source_file_bytes": path.stat().st_size,
        "csv_header_diagnostics": header_diagnostics,
        "record_count": total, "eligible_records": eligible, "evaluated_records": evaluated,
        "counts": dict(counts), "reason_counts": dict(sorted(reasons.items())),
        "coverage_on_eligible": evaluated / eligible if eligible else None,
        "abstention_rate_on_eligible": counts["abstained"] / eligible if eligible else None,
        "violation_fraction_on_evaluated": counts["violated"] / evaluated if evaluated else None,
        "elapsed_seconds_single_run": elapsed,
        "rule_source_status": prepared["entry"]["status"],
        "independently_adjudicated_gold_rule": False,
        "independently_adjudicated_row_defects": False,
        "data_partition": "previously_explored_development_data_not_held_out",
        "interpretation": "Candidate-rule agreement only. Violations are not independently verified errors.",
    }


def run(root: Path, domains: list[str]) -> dict[str, Any]:
    ready = prepare(root, domains)
    results = [evaluate_csv(domain, ready[domain]) for domain in domains]
    return {
        "experiment": "B6.1_local_real_source_development_baseline_v1",
        "runner_revision": "header_compatibility_fix_v2_no_rule_change",
        "protocol_id": PROTOCOL_ID,
        "baseline_git_commit": load_plan(root)[1]["baseline_git_commit"],
        "catalogue_sha256": _sha256(root / "data/evaluation/b6_reference_catalogue.json"),
        "protocol_sha256": _sha256(root / "data/evaluation/b6_protocol_v1.json"),
        "source_manifest_sha256": _sha256(root / "data/sources.json"),
        "runner_sha256": _sha256(Path(__file__)),
        "mode": "development_only_no_independent_holdout_no_gold_scoring",
        "independently_adjudicated_gold_rules": 0,
        "results": results,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--domains", choices=tuple(SPECS), nargs="+", default=list(SPECS))
    ap.add_argument("--check-inputs", action="store_true", help="Preflight sources only (no evaluation)")
    args = ap.parse_args()
    root = args.root.resolve()
    try:
        ready = prepare(root, args.domains)
        for domain, info in ready.items():
            print(f"INPUT OK {domain}: {info['config']['source']}")
        if args.check_inputs:
            print("Only input presence/provenance checked; no dataset evaluated.")
            return 0
        report = run(root, args.domains)
        for item in report["results"]:
            print(f"{item['domain']}: {item['record_count']} rows; {item['counts']}; "
                  f"coverage={item['coverage_on_eligible']} [DEVELOPMENT, NOT GOLD]")
        out = root / "data/evaluation/b6_1_real_baselines.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Saved {out.relative_to(root)}; no network/API calls; no source files modified")
        return 0
    except (EvaluationError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"B6.1 ERROR (no results claimed): {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
