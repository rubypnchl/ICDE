"""Offline B5 summary; no API calls, no ground-truth accuracy claims."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data/llm_pilot/structured"
DOMAINS = ("finance", "manufacturing", "healthcare", "cybersecurity")
MODELS = ("luna", "sol")


def status_of(row):
    return row.get("compilation", {}).get("status", row.get("status", "unknown"))


def main():
    reports = []
    for domain in DOMAINS:
        present = {}
        for model in MODELS:
            path = DIR / f"{model}_{domain}.json"
            if not path.exists():
                continue
            item = json.loads(path.read_text(encoding="utf-8"))
            present[model] = item
            counts = {k: sum(status_of(p) == k for p in item.get("compile_results", []))
                      for k in ("candidate_executable_unverified", "blocked_unresolved", "rejected_invalid")}
            reports.append({"domain": domain, "model": model,
                            "model_proposals": len((item.get("output") or {}).get("rules", [])),
                            "compilation_counts": counts,
                            "error": item.get("error"),
                            "usage": item.get("usage"),
                            "estimated_cost_usd": item.get("estimated_cost_usd")})
            print(f"{domain:15} {model:5} proposals={reports[-1]['model_proposals']} "
                  f"compiled={counts['candidate_executable_unverified']} "
                  f"blocked={counts['blocked_unresolved']} rejected={counts['rejected_invalid']} "
                  f"error={item.get('error')}")
        if len(present) == 2 and present['luna'].get('input_bundle') != present['sol'].get('input_bundle'):
            raise SystemExit(f"FAIRNESS FAILURE: {domain} input bundles differ between models")
    output = ROOT / "data/evaluation/b5-structured-pilot-summary.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "method": "LLM typed-proposal feasibility pilot; no independently adjudicated rule correctness",
        "records": reports,
        "warning": "Compilable does NOT mean a valid or evidence-supported integrity constraint. Manual focused columns may bias proposal yield."
    }, indent=2) + "\n", encoding="utf-8")
    print("Saved", output.relative_to(ROOT))


if __name__ == "__main__":
    main()
