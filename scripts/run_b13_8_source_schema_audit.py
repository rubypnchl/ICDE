"""Offline read-only B13.8 inspection of the three exact B13.7 source objects."""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.b13_8_source_schema_audit import (
    AuditError, audit_all, exclusive_save, validate_plan,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    options = parser.add_mutually_exclusive_group(required=True)
    options.add_argument("--preflight", action="store_true")
    options.add_argument("--inspect", action="store_true")
    parser.add_argument("--cache-dir", type=Path, default=Path.home() / "Downloads" / "ICDE-B13-Source-Cache")
    args = parser.parse_args()
    plan = json.loads((ROOT / "data/evaluation/b13_8_schema_audit_plan_v1.json").read_text(encoding="utf-8"))
    registry = json.loads((ROOT / "data/evaluation/b13_7_source_objects_v1.json").read_text(encoding="utf-8"))
    validate_plan(plan, registry)
    if args.preflight:
        print("B13.8 PREFLIGHT PASS: exact 3 previously acquired source objects pinned; NO source read")
        print("Healthcare: 2 XPT files in ONE survey cycle; manufacturing: 1 ZIP")
        print("No rows emitted, no candidate generation, no gates or gold; source eligibility remains 0")
        return
    from src.b13_7_source_acquisition import assert_external_cache
    cache = assert_external_cache(args.cache_dir, ROOT)
    report = audit_all(cache, ROOT, plan, registry)
    dest = cache / "B13_8_source_schema_audit_v1.json"
    exclusive_save(dest, report, cache, ROOT)
    print("B13.8 EXPLORATORY SOURCE SCHEMA AUDIT COMPLETE")
    print(json.dumps({
        "NHANES_TRIGLY_rows": report["healthcare"][0]["row_count"],
        "NHANES_TCHOL_rows": report["healthcare"][1]["row_count"],
        "NHANES_shared_identifiers_count": report["nhanes_cycle_join_inventory"]["intersection_SEQN_count"],
        "UCI_fault_rows": report["manufacturing"]["row_count"],
        "UCI_columns": report["manufacturing"]["total_column_count"],
        "UCI_label_positive_count_per_row": report["manufacturing"]["label_positive_count_per_row"],
        "real_candidates": 0, "gold_rules": 0, "gate_runs": 0,
    }, indent=2))
    print("Aggregate JSON written OUTSIDE Git:", dest)
    print("No original file modified; no raw records or SEQN values written")


if __name__ == "__main__":
    try:
        main()
    except (AuditError, OSError, ValueError, TypeError, ImportError, zipfile.BadZipFile) as exc:
        print("B13.8 STOP:", type(exc).__name__ + ":", exc, file=sys.stderr)
        sys.exit(2)
