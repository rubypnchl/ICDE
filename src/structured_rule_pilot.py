"""B5: optional low-cost LLM typed-proposal experiment, never evidence acceptance.

No API request unless --run. No source records are sent: compact metadata only.
Reads B4 with a *blank* parameter registry, deliberately blocking invented values.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

from src.llm_rule_pilot import (CONFIG, MODEL_MAP, PRICES, REASONING,
    _call_openai, _text_from_response, _usage_cost, make_bundle)
from src.rule_bridge import compile_proposal, PROPOSAL_VERSION
from src.generic_verifier import validate_rule

PROMPT = (
    "You propose TESTABLE cross-column data integrity HYPOTHESES from metadata, "
    "not verified rules. Propose at most TWO per input. Output typed AST objects, "
    "never free-text formulas or executable Python. Only use exact input column names "
    "(preserve spaces and case). Allowed numeric expression nodes are column, parameter, "
    "add, multiply and subtract. Every numeric factor or threshold MUST be an UNRESOLVED "
    "named parameter (e.g., k1, t1); never use constant nodes or invent values. "
    "A rule must reference at least two distinct input columns. "
    "For a conditional comparison, use a simple when predicate; categorical values "
    "can be strings, numeric thresholds require parameter references. "
    "If a precision rule is plausible, represent round_right as a named parameter; "
    "do not guess precision. Set absent round_right and abs_tolerance to null. "
    "If a constraint needs other context, include only context keys genuinely supported "
    "by provided metadata; otherwise use []. Do not assert that metadata documents "
    "an equation merely because it defines its fields. "
    "Cite only IDs of passages with actual definitions, not NO DOCUMENTED DEFINITION. "
    "Return an empty rules list if none is plausible. State uncertainty briefly. "
    "No explanation outside JSON."
)


def _obj(**props: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": props,
            "required": list(props), "additionalProperties": False}


def _ref(node: str) -> dict[str, Any]:
    return {"$ref": f"#/$defs/{node}"}


def response_schema() -> dict[str, Any]:
    expr = {"anyOf": [
        _obj(column={"type": "string"}),
        _obj(parameter={"type": "string"}),
        _obj(add={"type": "array", "items": _ref("expression")}),
        _obj(multiply={"type": "array", "items": _ref("expression")}),
        _obj(subtract={"type": "array", "items": _ref("expression")}),
    ]}
    param = _obj(parameter={"type": "string"})
    condition = _obj(column={"type": "string"},
                     op={"type": "string", "enum": ["eq", "ne", "gt", "gte", "lt", "lte"]},
                     value={"anyOf": [{"type": "string"}, _ref("parameter")]})
    assertion = _obj(left=_ref("expression"),
                     op={"type": "string", "enum": ["eq", "ne", "gt", "gte", "lt", "lte"]},
                     right=_ref("expression"),
                     round_right={"anyOf": [{"type": "null"}, _ref("parameter")]},
                     abs_tolerance={"anyOf": [{"type": "null"}, _ref("parameter")]})
    rule = _obj(id={"type": "string"},
                assertions={"type": "array", "items": assertion},
                when={"anyOf": [{"type": "null"}, condition]},
                context_keys={"type": "array", "items": {"type": "string"}},
                passage_ids={"type": "array", "items": {"type": "string"}},
                uncertainty={"type": "string"})
    return {**_obj(rules={"type": "array", "items": rule}),
            "$defs": {"expression": expr, "parameter": param}}


def build_request(model: str, bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": MODEL_MAP[model],
        "reasoning": {"effort": REASONING[model]},
        "store": False,
        "max_output_tokens": 1400 if model == "luna" else 2200,
        "instructions": PROMPT,
        "input": json.dumps(bundle, ensure_ascii=False, separators=(",", ":")),
        "text": {"format": {"type": "json_schema", "name": "metaverify_typed_proposals",
                            "strict": True, "schema": response_schema()}},
    }


def request_hash(request: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def estimate_cost(model: str, request: dict[str, Any]) -> float:
    # Soft guard estimate, not a provider-side cap. Assumes <=2 UTF8 bytes/token
    # for short metadata and includes output-token ceiling and full schema text.
    in_size = len((request["instructions"] + request["input"] +
                   json.dumps(request["text"]["format"]["schema"])).encode("utf-8"))
    input_price, output_price = PRICES[model]
    return ((in_size + 1) // 2 * input_price +
            request["max_output_tokens"] * output_price) / 1_000_000


def inspect_response(payload: Any, bundle: dict[str, Any], model: str) -> list[dict[str, Any]]:
    """Syntax/reference screening, B4 compilation, B3 validation. NO data check."""
    if not isinstance(payload, dict) or not isinstance(payload.get("rules"), list):
        raise ValueError("model output requires a rules array")
    if len(payload["rules"]) > 2:
        raise ValueError("model proposed more than two rules")
    allowed_columns = [p["column"] for p in bundle["passages"]]
    real_passages = {p["id"] for p in bundle["passages"]
                     if p["description"] != "NO DOCUMENTED DEFINITION"}
    records = []
    for i, item in enumerate(payload["rules"]):
        if not isinstance(item, dict):
            records.append({"status": "rejected_invalid", "reason": "nonobject model proposal"})
            continue
        pid = item.get("id", f"rule-{i}")
        citations = item.get("passage_ids")
        if not isinstance(citations, list) or any(p not in real_passages for p in citations):
            records.append({"id": pid, "status": "rejected_invalid",
                            "reason": "invalid or undocumented passage reference"})
            continue
        ast = {"proposal_version": PROPOSAL_VERSION, "id": item.get("id"),
               "dataset_id": bundle["dataset_id"],
               "origin": f"model_{MODEL_MAP[model]}_b5",
               "assertions": [], "context_keys": item.get("context_keys", [])}
        for chk in item.get("assertions", []) if isinstance(item.get("assertions"), list) else []:
            if isinstance(chk, dict):
                # Structured output requires nullable fields; B4 requires absence
                # when not specified. Do NOT inject numeric values.
                ast["assertions"].append({k: v for k, v in chk.items() if v is not None})
            else:
                ast["assertions"].append(chk)
        if item.get("when") is not None:
            ast["when"] = item["when"]
        compiled = compile_proposal(ast, allowed_columns, {})  # No curator values supplied
        as_dict = compiled.as_dict()
        if compiled.rule is not None:
            validate_rule(compiled.rule)
        records.append({"id": pid, "source_passage_ids": citations,
                        "uncertainty": item.get("uncertainty"),
                        "compilation": as_dict})
    return records


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--model", choices=("luna", "sol"), default="luna")
    ap.add_argument("--domains", choices=tuple(CONFIG), nargs="+", default=["healthcare", "finance"])
    ap.add_argument("--run", action="store_true", help="Opt in to paid API calls")
    ap.add_argument("--max-estimated-usd", type=float, default=0.10,
                    help="Local soft request estimate, NOT a billing cap")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    outdir = root / "data" / "llm_pilot" / "structured"
    outdir.mkdir(parents=True, exist_ok=True)
    bundles = {name: make_bundle(root, name) for name in args.domains}
    requests = {name: build_request(args.model, bundle) for name, bundle in bundles.items()}
    estimate = sum(estimate_cost(args.model, req) for req in requests.values())
    input_file = outdir / "inputs.json"
    # Note: same exact input for Sol and Luna. Don't change after first model run.
    if input_file.exists():
        prior = json.loads(input_file.read_text(encoding="utf-8"))
        for name in bundles:
            if name in prior and prior[name] != bundles[name]:
                raise SystemExit("INPUT CHANGED versus saved benchmark; stop to inspect before any new calls")
        prior.update(bundles)
        bundles = prior
    input_file.write_text(json.dumps(bundles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"B5 | model={MODEL_MAP[args.model]} | domains={', '.join(args.domains)}")
    print(f"Estimated upper token cost (not guaranteed): ${estimate:.5f}")
    for name in args.domains:
        p = bundles[name]["passages"]
        print(f"  {name}: {len(p)} fields; {sum(x['description'] != 'NO DOCUMENTED DEFINITION' for x in p)} documented definitions")
    if not args.run:
        print("DRY RUN: no API requests; inspect", input_file)
        return 0
    if not 0 <= args.max_estimated_usd or estimate > args.max_estimated_usd:
        raise SystemExit("Soft cost estimate exceeds --max-estimated-usd; no API requests sent")
    all_cached = all((outdir / f"{args.model}_{name}.json").exists() for name in args.domains)
    api_key = "" if all_cached else (os.environ.get("OPENAI_API_KEY") or getpass.getpass("OpenAI API key (hidden): ").strip())
    if not all_cached and not api_key:
        raise SystemExit("Missing API key")
    cost_so_far = 0.0
    for name in args.domains:
        path = outdir / f"{args.model}_{name}.json"
        request = requests[name]
        rh = request_hash(request)
        if path.exists():
            cached = json.loads(path.read_text(encoding="utf-8"))
            if cached.get("request_sha256") != rh:
                raise SystemExit(f"STALE CACHE: {path}; no overwrite or paid retry")
            print("CACHED:", path)
            continue
        if cost_so_far + estimate_cost(args.model, request) > args.max_estimated_usd:
            print("Stopped before next call would exceed local soft budget")
            break
        print("CALLING:", MODEL_MAP[args.model], name, flush=True)
        response = _call_openai(request, api_key)
        usage = response.get("usage") or {}
        cost = _usage_cost(usage, args.model)
        cost_so_far += cost
        error = None
        raw = None
        proposals = []
        try:
            raw = json.loads(_text_from_response(response))
            proposals = inspect_response(raw, bundles[name], args.model)
        except (ValueError, TypeError, KeyError, RuntimeError) as exc:
            error = f"{type(exc).__name__}: {exc}"
        report = {"dataset_id": bundles[name]["dataset_id"], "domain": name,
                  "model_id_requested": MODEL_MAP[args.model], "prompt_mode": "structured_hypothesis",
                  "request_sha256": rh, "input_bundle": bundles[name],
                  "response_status": response.get("status"), "output": raw,
                  "compile_results": proposals, "error": error,
                  "usage": usage, "estimated_cost_usd": round(cost, 7),
                  "scientific_warning": "No generated rule is semantically verified or independently benchmarked"}
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        statuses = [r.get("compilation", {}).get("status", r.get("status")) for r in proposals]
        print(f"  saved {path}; statuses={statuses}; estimated cost=${cost:.6f}; error={error}")
    print(f"Estimated cost of new calls this run: ${cost_so_far:.6f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
