"""Read-only B13.2 source shortlisting check, never downloads sources."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.b13_2_source_screening import ScreenError, read, validate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true", required=True)
    args = parser.parse_args()
    source = ROOT / "data/evaluation/b13_2_source_screening_v1.json"
    try:
        result = validate(read(source))
    except (ScreenError, ValueError, OSError) as exc:
        print("B13.2 STOP:", exc, file=sys.stderr)
        return 2
    print("B13.2 SOURCE SCREEN PASS: documentation shortlist only")
    print(json.dumps(result, indent=2))
    print("No datasets downloaded; no candidates locked; no gates executed; no gold labels")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
