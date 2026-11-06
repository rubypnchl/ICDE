"""Review cached B5 JSON under a declared post-hoc policy. NO API calls."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evidence_gate import load_policy, review_report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", nargs="+", choices=("luna", "sol"), default=["luna"])
    ap.add_argument("--domains", nargs="+", choices=("healthcare", "finance", "manufacturing", "cybersecurity"),
                    default=["healthcare", "finance"])
    args = ap.parse_args(argv)
    policy, registry = load_policy(ROOT)
    reports = []
    for model in args.models:
        for domain in args.domains:
            path = ROOT / "data/llm_pilot/structured" / f"{model}_{domain}.json"
            if not path.exists():
                print(f"MISSING (skipped): {path.relative_to(ROOT)}")
                continue
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
            evaluation = review_report(raw, policy, registry)
            reports.append(evaluation)
            for d in evaluation["decisions"]:
                print(f"{model:5} {domain:15} {d['proposal_id']:28} "
                      f"B5={d['b5_original_compilation_status']}  B5.1={d['status']}")
                for reason in d["reasons"]:
                    print("   -", reason)
    if not reports:
        raise SystemExit("No locally cached B5 responses found; no review written.")
    target = ROOT / "data/evaluation/b5_1_evidence_review.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({
        "stage": "B5.1",
        "method": "Post-hoc human-authorized matching and independent-policy applicability gate, no API calls",
        "model_reports": reports,
        "scientific_warning": "Original B5 output files remain unchanged. B5.1 was designed after viewing Luna outputs; do not use B5.1 success rates as unbiased Luna-vs-Sol evidence."
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Saved", target.relative_to(ROOT))
    print("New API calls: 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
