"""Minimal metadata-only rule-proposal feasibility pilot for MetaVerify.

No network calls unless --run is supplied. Python stdlib only.
Outputs are hypotheses, never verified integrity constraints.
"""
from __future__ import annotations

import argparse
import datetime as dt
import getpass
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request
from typing import Any

MODEL_MAP = {"luna": "gpt-6-luna", "sol": "gpt-6-sol"}
REASONING = {"luna": "none", "sol": "low"}
# Conservative nominal (short-input, standard service) rates USD per 1M tokens,
# from 2026-11-06 API price guide; revisit before subsequent experiments.
PRICES = {"luna": (0.10, 0.50), "sol": (2.00, 10.00)}
MAX_OUTPUT_TOKENS = 1000  # includes reasoning tokens
MAX_RULES = 3
API_ENDPOINT = "https://api.openai.com/v1/responses"

# Focus columns are prespecified for a feasibility test, NOT reference rules.
# Selecting related columns favours discovery, so do not claim unbiased recall.
CONFIG = {
    "finance": {
        "metadata": "data/metadata/sec-companyfacts-0000320193.json",
        "raw": "data/originals/sec/companyfacts/0000320193_apple.json",
        "tags": ["Assets", "Liabilities", "StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest", "MinorityInterest", "TemporaryEquityCarryingAmountIncludingPortionAttributableToNoncontrollingInterests"],
    },
    "manufacturing": {
        "metadata": "data/metadata/ai4i-2020.json",
        "columns": ["Type", "Air temperature [K]", "Process temperature [K]", "Torque [Nm]", "Tool wear [min]", "OSF", "Machine failure"],
    },
    "healthcare": {
        "metadata": "data/metadata/nhanes-glu-j.json",
        "columns": ["LBXGLU", "LBDGLUSI", "SEQN", "WTSAF2YR"],
    },
    "cybersecurity": {
        "metadata": "data/metadata/cic-ids2017.json",
        "columns": [" Total Fwd Packets", " Fwd Packet Length Max", " Fwd Packet Length Min", " Fwd Packet Length Mean", " Total Backward Packets", " Bwd Packet Length Max", " Bwd Packet Length Min", " Bwd Packet Length Mean", " Flow Duration"],
    },
}

OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "rules": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "rule_type": {"type": "string", "enum": ["arithmetic", "inequality", "unit_conversion", "conditional", "other"]},
                    "columns": {"type": "array", "items": {"type": "string"}},
                    "expression": {"type": "string"},
                    "applicability": {"type": "string"},
                    "passage_ids": {"type": "array", "items": {"type": "string"}},
                    "uncertainty": {"type": "string"},
                },
                "required": ["rule_type", "columns", "expression", "applicability", "passage_ids", "uncertainty"],
            },
        }
    },
    "required": ["rules"],
}

STRICT_INSTRUCTIONS = (
    "You propose database integrity-constraint CANDIDATES, not proven rules. "
    "Use only supplied column names and numbered source passages. "
    "Propose up to three NONTRIVIAL, testable relationships between at least two columns. "
    "A relationship must be explicitly supported by passage text; column names and common knowledge alone are insufficient. "
    "Do not invent thresholds, formulas, conversion factors, units, or evidence. "
    "Do not equate missing concept with zero. Do not infer that correlations imply constraints. "
    "Only cite passage IDs that contain explicit documentary support. "
    "If none is supported, return an empty rules array. "
    "Expressions are short plain strings, not runnable code; no code generation. "
    "No explanations outside the required JSON."
)

# Distinct research treatment: generate plausible, falsifiable hypotheses from
# metadata even if the documentation does not state a complete equation.
# Uncited hypotheses are NOT accepted as verified integrity constraints.
HYPOTHESIS_INSTRUCTIONS = (
    "You are conducting the PROPOSAL stage of a data-quality research experiment. "
    "Suggest up to three plausible, nontrivial, TESTABLE candidate relationships "
    "involving at least two of the exact supplied column names. "
    "Use the provided names, types, units, definitions and domain as clues; "
    "a documentary statement of the full mathematical relationship is NOT required to propose a hypothesis. "
    "A hypothesis is NOT a validated integrity constraint. "
    "Do not fabricate documentation, citations, precise coefficients, thresholds, or units. "
    "If a numerical factor or threshold is missing, represent it using an unknown parameter, "
    "e.g. 'B approximately equals k * A (k unknown)', and state what must be verified. "
    "Use passage_ids only for existing passages with genuine documented definitions; "
    "return passage_ids=[] when no documented passage supports the proposed columns. "
    "A passage about an individual column does NOT prove a proposed equation. "
    "Clearly state such limitations in the uncertainty field. "
    "Do not equate missing values to zero or turn correlations into guaranteed rules. "
    "For inequalities, specify applicability conditions such as nonempty packet populations. "
    "If there is no defensible hypothesis from the supplied information, return an empty rules array. "
    "Expressions must be plain text; do not generate code. No text outside JSON."
)


def instructions_for(mode: str) -> str:
    return STRICT_INSTRUCTIONS if mode == "strict" else HYPOTHESIS_INSTRUCTIONS


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _get_documented(item: dict[str, Any], key: str) -> dict[str, str] | None:
    value = item.get(key)
    if not isinstance(value, dict) or value.get("status") != "documented":
        return None
    if not isinstance(value.get("value"), (str, int, float)):
        return None
    return {"value": str(value["value"])[:420], "source": str(value.get("source") or "")}


def make_bundle(root: Path, domain: str) -> dict[str, Any]:
    cfg = CONFIG[domain]
    metadata_path = root / cfg["metadata"]
    metadata = _read_json(metadata_path)
    passages: list[dict[str, str]] = []
    if domain == "finance" and (root / cfg["raw"]).is_file():
        # SEC concept descriptions are supplied as model input; never raw transaction data.
        payload = _read_json(root / cfg["raw"])
        facts = payload.get("facts", {}).get("us-gaap", {})
        for tag in cfg["tags"]:
            concept = facts.get(tag, {})
            if not concept.get("description"):
                continue
            passages.append({
                "id": f"P{len(passages)+1:02d}", "column": tag,
                "description": str(concept["description"])[:440],
                "unit": "USD (candidate; fact-level units require verification)",
                "type": "number (candidate; fact-level type requires verification)",
                "source": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{str(payload.get('cik', 320193)).zfill(10)}.json",
            })
    else:
        focus = set(cfg.get("columns", []))
        for column in metadata.get("columns", []):
            name = column.get("name", "")
            if name not in focus:
                continue
            desc = _get_documented(column, "description")
            unit = _get_documented(column, "unit")
            # Unspecified description is represented honestly: not an evidence passage.
            passages.append({
                "id": f"P{len(passages)+1:02d}", "column": name,
                "description": (desc or {}).get("value", "NO DOCUMENTED DEFINITION"),
                "unit": (unit or {}).get("value", "unknown"),
                "type": str(column.get("type", {}).get("value") or "unknown"),
                "source": (desc or {}).get("source") or (unit or {}).get("source") or "none",
            })
    return {
        "domain": domain,
        "dataset_id": metadata.get("dataset", {}).get("id", domain),
        "scope_note": "Feasibility pilot with manually chosen relevant columns; source passages can be incomplete; no data values or reference rules supplied.",
        "passages": passages,
    }


def _text_from_response(result: dict[str, Any]) -> str:
    parts = []
    for item in result.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    parts.append(content.get("text", ""))
    if not parts:
        raise RuntimeError(f"No output text (status: {result.get('status')}; incomplete: {result.get('incomplete_details')})")
    return "".join(parts)


def validate_proposals(proposal: dict[str, Any], bundle: dict[str, Any], *, mode: str = "strict") -> list[dict[str, Any]]:
    """Reject fabricated column references and passage references; NOT truth verification."""
    allowed_columns = {p["column"] for p in bundle["passages"]}
    allowed_passages = {p["id"] for p in bundle["passages"] if p["description"] != "NO DOCUMENTED DEFINITION"}
    decisions = []
    for rule in proposal.get("rules", [])[:MAX_RULES]:
        columns = rule.get("columns", [])
        cited = rule.get("passage_ids", [])
        valid = (
            isinstance(columns, list) and len(set(columns)) >= 2
            and all(c in allowed_columns for c in columns)
            and isinstance(cited, list)
            and (bool(cited) or mode == "hypothesis")
            and all(p in allowed_passages for p in cited)
        )
        decisions.append({
            **rule,
            "syntax_and_reference_check": "pass" if valid else "fail",
            "verification_status": (
                ("hypothesis_unverified" if mode == "hypothesis" else "candidate_unverified")
                if valid else "rejected_invalid_reference"
            ),
            "has_documented_definition_passage": bool(cited),
            "note": (
                "Syntax and reference existence only; uncited hypotheses are allowed in hypothesis mode. "
                "Citing an attribute definition does NOT establish that it supports the proposed relationship. "
                "Semantic entailment, applicability, and data accuracy are NOT checked."
            ),
        })
    return decisions


def _build_request(model_choice: str, bundle: dict[str, Any], *, mode: str = "strict") -> dict[str, Any]:
    payload = {
        "model": MODEL_MAP[model_choice],
        "reasoning": {"effort": REASONING[model_choice]},
        "store": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "instructions": instructions_for(mode),
        "input": json.dumps(bundle, ensure_ascii=False, separators=(",", ":")),
        "text": {"format": {"type": "json_schema", "name": "metaverify_rule_proposals", "strict": True, "schema": OUTPUT_SCHEMA}},
    }
    return payload


def _estimated_request_max_usd(model_choice: str, request: dict[str, Any]) -> float:
    # Rough upper estimate for this short, Latin-script metadata pilot only.
    # Not a guaranteed spending cap. Use provider-side usage controls as well.
    in_text = request["instructions"] + request["input"] + json.dumps(request["text"]["format"]["schema"])
    estimated_input_tokens = math.ceil(len(in_text.encode("utf-8")) / 2)
    input_price, output_price = PRICES[model_choice]
    return (estimated_input_tokens * input_price + MAX_OUTPUT_TOKENS * output_price) / 1_000_000


def _call_openai(request: dict[str, Any], api_key: str) -> dict[str, Any]:
    data = json.dumps(request, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(API_ENDPOINT, data=data, method="POST", headers={
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=100) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")[:750]
        raise RuntimeError(f"API HTTP {exc.code}: {message}") from None


def _usage_cost(usage: dict[str, Any], model_choice: str) -> float:
    in_t, out_t = PRICES[model_choice]
    # Conservative: don't discount cached input; no tools used here.
    return (usage.get("input_tokens", 0) * in_t + usage.get("output_tokens", 0) * out_t) / 1_000_000


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path("."), help="MetaVerify repository root")
    ap.add_argument("--model", choices=tuple(MODEL_MAP), default="luna")
    ap.add_argument("--run", action="store_true", help="Actually call the API; otherwise dry-run only")
    ap.add_argument("--mode", choices=("strict", "hypothesis"), default="strict",
                    help="Keep strict baseline separate from metadata-based hypothesis discovery")
    ap.add_argument("--domains", nargs="+", choices=tuple(CONFIG), default=list(CONFIG),
                    help="Run only selected domains to minimise API calls")
    ap.add_argument("--max-estimated-usd", type=float, default=0.08,
                    help="Soft per-run USD limit, NOT a billing cap")
    args = ap.parse_args()
    root = args.root.resolve()
    output_dir = root / "data" / "llm_pilot"
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle_map = {domain: make_bundle(root, domain) for domain in args.domains}
    requests = {domain: _build_request(args.model, b, mode=args.mode) for domain, b in bundle_map.items()}
    estimated_total = sum(_estimated_request_max_usd(args.model, v) for v in requests.values())
    input_file = output_dir / ("input_bundles.json" if args.mode == "strict" else "input_bundles_hypothesis.json")
    input_file.write_text(json.dumps(bundle_map, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Model: {MODEL_MAP[args.model]} | mode={args.mode} | domains={len(bundle_map)}")
    print(f"Approximate upper cost per batch under nominal short-context rates: ${estimated_total:.4f} (not guaranteed)")
    print("Inputs saved:", input_file)
    for domain, bundle in bundle_map.items():
        count = sum(p["description"] != "NO DOCUMENTED DEFINITION" for p in bundle["passages"])
        print(f"  {domain}: {len(bundle['passages'])} columns; {count} documented descriptions")
    if not args.run:
        print("DRY RUN: no API request made. Inspect input_bundles.json first.")
        return 0
    if estimated_total > args.max_estimated_usd:
        raise SystemExit("Estimated cost exceeds soft limit; no API requests sent.")
    api_key = os.environ.get("OPENAI_API_KEY") or getpass.getpass("OpenAI API key (hidden, not saved): ").strip()
    if not api_key:
        raise SystemExit("No API key supplied.")
    total_cost = 0.0
    for domain, bundle in bundle_map.items():
        request = requests[domain]
        path = output_dir / (f"{args.model}_{domain}.json" if args.mode == "strict" else f"{args.model}_hypothesis_{domain}.json")
        if path.exists():
            prior = _read_json(path)
            current_hash = hashlib.sha256((request["instructions"] + request["input"]).encode()).hexdigest()
            if prior.get("prompt_sha256") != current_hash:
                print("STALE CACHE: inputs changed for", domain, "— not re-calling automatically.")
                print("  Inspect old report and deliberately rename it before rerunning:", path)
                continue
            print("Cached (skipped):", path)
            continue
        projected = _estimated_request_max_usd(args.model, request)
        if total_cost + projected > args.max_estimated_usd:
            print("Stopped before budget estimate exceeded; no further calls.")
            break
        print(f"Calling {MODEL_MAP[args.model]} for {domain} ...", flush=True)
        response = _call_openai(request, api_key)
        usage = response.get("usage") or {}
        total_cost += _usage_cost(usage, args.model)
        try:
            proposed = json.loads(_text_from_response(response))
            decisions = validate_proposals(proposed, bundle, mode=args.mode)
            error = None
        except (json.JSONDecodeError, RuntimeError, KeyError, TypeError, AttributeError) as exc:
            proposed, decisions, error = None, [], f"{type(exc).__name__}: {exc}"
        report = {
            "domain": domain,
            "proposal_mode": args.mode,
            "model": response.get("model", MODEL_MAP[args.model]),
            "model_id_requested": MODEL_MAP[args.model],
            "reasoning_effort": REASONING[args.model],
            "prompt_sha256": hashlib.sha256((request["instructions"] + request["input"]).encode()).hexdigest(),
            "input_bundle": bundle,
            "api_response_id": response.get("id"),
            "response_status": response.get("status"),
            "output": proposed,
            "proposals_with_reference_checks": decisions,
            "error": error,
            "usage": usage,
            "estimated_cost_usd": round(_usage_cost(usage, args.model), 7),
            "research_warning": "NOT VERIFIED: no independent semantic adjudication or held-out evaluation has been performed. Hypotheses must not be reported as accepted rules.",
        }
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  saved {path} | candidates={len(decisions)} | estimated token cost=${report['estimated_cost_usd']:.5f}")
    print(f"Actual observed batch estimated token charges: ${total_cost:.5f} (provider billing may differ)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
