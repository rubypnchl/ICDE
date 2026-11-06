"""B4 local-only compiler preview. No LLM/API calls; no raw records sent anywhere."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.rule_bridge import compile_proposal
from src.generic_verifier import validate_rule


def main() -> None:
    demo = json.loads((ROOT / "data/rules/b4_example_proposals.json").read_text(encoding="utf-8"))
    metadata_files = {
        "nhanes-2017-2018-glu-j": "data/metadata/nhanes-glu-j.json",
        "sec-companyfacts": "data/metadata/sec-companyfacts-0000320193.json",
        "cic-ids2017": "data/metadata/cic-ids2017.json",
        "ai4i-2020": "data/metadata/ai4i-2020.json",
    }
    allowed = {}
    for dataset_id, filename in metadata_files.items():
        metadata = json.loads((ROOT / filename).read_text(encoding="utf-8"))
        allowed[dataset_id] = [col["name"] for col in metadata["columns"]]
        if dataset_id == "sec-companyfacts":
            # SEC pilot metadata has 6 lowercase summary concepts; B3 examples
            # operate on case-sensitive US-GAAP tags. Obtain those from the
            # official retained concept file, not inferred aliases.
            sec_path = ROOT / "data/originals/sec/companyfacts/0000320193_apple.json"
            if sec_path.exists():
                payload = json.loads(sec_path.read_text(encoding="utf-8"))
                allowed[dataset_id] = list(payload.get("facts", {}).get("us-gaap", {}))
            else:
                print("SEC raw file absent: finance example will be rejected (safe behaviour).")
    reports = []
    for proposal in demo["examples"]:
        result = compile_proposal(proposal, allowed[proposal["dataset_id"]], demo["registrations"])
        outcome = result.as_dict()
        if result.rule is not None:
            try:
                validate_rule(result.rule)
            except (ValueError, TypeError) as exc:
                raise RuntimeError(f"B3 verifier rejected a compiled B4 rule {proposal['id']}: {exc}") from exc
        reports.append(outcome)
        print(f"{result.proposal_id}: {result.status}; {result.reason}")
    # Explicit legacy outputs are not typed ASTs; NEVER parse their English expressions.
    for domain in ("finance", "healthcare"):
        path = ROOT / f"data/llm_pilot/luna_hypothesis_{domain}.json"
        if path.exists():
            legacy = json.loads(path.read_text(encoding="utf-8"))
            reports.append({"proposal_id": f"luna-{domain}-legacy", "status": "blocked_needs_structured_proposal", "reason": "Luna's prior response is free text, not typed AST; manually authored examples are not model outputs", "candidate_count": len(legacy.get("output", {}).get("rules", [])), "rule": None, "semantic_verified": False})
    target = ROOT / "data/evaluation/b4-compiler-preview.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"scope": "fixture compilation and B3 structural validation only; no independently adjudicated rules", "results": reports}, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {target.relative_to(ROOT)}; model calls: 0")


if __name__ == "__main__":
    main()
