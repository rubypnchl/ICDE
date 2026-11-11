"""Design-only offline preflight and candidate-input lock for B13."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.b13_protocol_validation import (  # noqa: E402
    B13Error, STUDY_ID, candidate_hash_records, read_manifest,
    safe_write_lock, sha256_file, validate_candidates, validate_plan,
)


def run(*, lock: bool) -> None:
    plan_path = ROOT / "data/evaluation/b13_plan_v1.json"
    template = ROOT / "data/evaluation/b13_candidate_manifest_template.csv"
    manifest = ROOT / "data/evaluation/b13_candidate_manifest.csv"
    with plan_path.open("r", encoding="utf-8") as stream:
        plan = json.load(stream)
    validate_plan(plan)
    # Check committed template even if a populated manifest exists.
    if read_manifest(template):
        raise B13Error("The blank candidate template must stay blank")
    if lock and not manifest.is_file():
        raise B13Error("No populated b13_candidate_manifest.csv exists; nothing to lock")
    source_path = manifest if manifest.is_file() else template
    rows = read_manifest(source_path)
    stats = validate_candidates(rows, ROOT, plan, lock=lock)
    if not lock:
        print(f"B13 PREFLIGHT PASS: design valid; candidate manifest has {len(rows)} rows; NOT RUN")
        print("No source modified; no gate executed; no independent truth or result produced")
        return
    payload = {
        "study_id": STUDY_ID,
        "classification": "candidate_input_hash_lock_only_no_gate_execution",
        "design_sha256": sha256_file(plan_path),
        "manifest_sha256": sha256_file(source_path),
        "manifest_stats": stats,
        "candidate_hash_records": candidate_hash_records(rows),
        "gate_outputs_present": False,
        "independent_reviewer_decisions_present": False,
        "is_gold_or_confirmatory_result": False,
        "limitations": [
            "Hash verification does not establish official source authenticity",
            "Evidence URLs and locators have not been evaluated for actual entailment",
            "Newness of sources and absence of training leakage are not software-proven",
            "No gate arm execution, human review, or semantic accuracy result",
        ],
    }
    output = ROOT / "data/evaluation/b13_frozen_input_lock_v1.json"
    safe_write_lock(output, payload)
    print("B13 INPUT LOCK WRITTEN:", output)
    print("No gate executed; no independently adjudicated labels or natural-defect claims")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    option = parser.add_mutually_exclusive_group(required=True)
    option.add_argument("--preflight", action="store_true", help="Read-only design and manifest check")
    option.add_argument("--lock", action="store_true", help="Lock fully populated, hash-verified new candidate inputs")
    args = parser.parse_args()
    try:
        run(lock=args.lock)
    except (B13Error, OSError, ValueError, json.JSONDecodeError) as exc:
        print("B13 STOP:", exc, file=sys.stderr)
        raise SystemExit(2)
