"""Run MetaVerify generic v0.1 verifier on fixtures or local NHANES glucose facts.

Run from repository root:
    python scripts/run_generic_verifier.py --demo
    python scripts/run_generic_verifier.py --healthcare
No model calls, no Codex, no data download. No raw records saved.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.generic_verifier import evaluate_row, evaluate_rows

RULES_PATH = Path("data/rules/generic_examples.json")


def _rules():
    payload = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    return {item["id"]: item for item in payload["rules"]}


def demo() -> None:
    rules = _rules()
    samples = {
        "health-glucose-3sig": [
            {"LBXGLU": 100, "LBDGLUSI": 5.55},
            {"LBXGLU": 100, "LBDGLUSI": 5.5},
            {"LBXGLU": None, "LBDGLUSI": 5.55},
        ],
        "finance-balance-sheet-candidate": [
            {"Assets": 100, "Liabilities": 60, "StockholdersEquity": 40,
             "_field_context": {c: {"entity": "A", "reporting_date": "2025-12-31", "accounting_scope": "consolidated", "currency": "USD"} for c in ("Assets", "Liabilities", "StockholdersEquity")}},
        ],
        "cyber-packet-length-order-candidate": [
            {" Total Fwd Packets": 3, " Fwd Packet Length Min": 10, " Fwd Packet Length Mean": 20, " Fwd Packet Length Max": 30},
            {" Total Fwd Packets": 0, " Fwd Packet Length Min": 0, " Fwd Packet Length Mean": 0, " Fwd Packet Length Max": 0},
        ],
        "manufacturing-nonnegative-torque-conditional-demo": [
            {"Type": "L", "Torque [Nm]": 15}, {"Type": "M", "Torque [Nm]": -2},
        ],
    }
    print(json.dumps({key: evaluate_rows(rule, samples[key]) for key, rule in rules.items()}, indent=2))
    print("Demo uses synthetic fixture records ONLY; not a four-domain real-data experiment.")


def healthcare() -> None:
    try:
        import pyreadstat
    except ImportError:
        raise SystemExit("Install pyreadstat from existing requirements.txt") from None
    file = Path("data/originals/nhanes/GLU_J.XPT")
    if not file.exists():
        raise SystemExit(f"Local dataset file missing: {file}")
    data, _ = pyreadstat.read_xport(str(file), usecols=["LBXGLU", "LBDGLUSI"], output_format="dict")
    rows = ({"LBXGLU": mg, "LBDGLUSI": si} for mg, si in zip(data["LBXGLU"], data["LBDGLUSI"]))
    result = evaluate_rows(_rules()["health-glucose-3sig"], rows)
    source_sha256 = hashlib.sha256(file.read_bytes()).hexdigest()
    prior = Path("data/evaluation/nhanes-glucose-precision.json")
    if prior.exists():
        reference = json.loads(prior.read_text(encoding="utf-8"))
        if reference.get("source_sha256") != source_sha256:
            raise SystemExit("The XPT snapshot hash differs from the earlier precision study; report separately")
        result["comparison_with_prior_study"] = {
            "same_source_hash": True,
            "matched_count_agrees": result["counts"]["satisfied"] == reference.get("rounding_matches", {}).get("3_significant_figures"),
            "evaluable_count_agrees": result["evaluated_records"] == reference.get("records_evaluable"),
        }
    result["source_sha256"] = source_sha256
    result["scientific_limitation"] = ("3-significant-figure precision was selected using the same dataset; "
        "reproducing agreement on this snapshot is NOT an independent held-out validation.")
    target = Path("data/evaluation/generic-nhanes-glucose.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print("Saved:", target)


def main():
    parser = argparse.ArgumentParser()
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--demo", action="store_true")
    selector.add_argument("--healthcare", action="store_true")
    args = parser.parse_args()
    demo() if args.demo else healthcare()


if __name__ == "__main__":
    main()
