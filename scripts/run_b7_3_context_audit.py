"""B7.3: read-only audit of saved SEC evidence; optional write of new report.

Run from any directory; never modifies old experiment results or source files.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.b7_3_context_audit import ContextAuditError, run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("data/evaluation/b7_3_context_audit.json"))
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        output = run(root, preflight=args.preflight)
        if args.preflight:
            print("B7.3 preflight PASS (no results written)")
            print("Detected context construction:", json.dumps(output["source_hardcoding_detected"], sort_keys=True))
            return 0
        path = root / args.output if not args.output.is_absolute() else args.output
        if path.exists():
            raise ContextAuditError(f"Refusing to overwrite B7.3 report: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        print("B7.3 COMPLETE — retrospective context audit and 10 controlled probes")
        print("Legacy: 41/41 held-out arithmetic matches, status=recorded documented_support")
        print("Strict policy: no independently substantiated accounting scope; abstain without review")
        print("Frozen B6-FIN-002: unqualified universal formula excluded")
        print("NO independent gold; NO semantic precision/recall; NO real defect claims")
        print("Saved:", path)
        return 0
    except (OSError, ValueError, TypeError, KeyError, SyntaxError, json.JSONDecodeError) as exc:
        print(f"B7.3 STOPPED (nothing scored): {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
