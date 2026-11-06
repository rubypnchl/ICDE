"""B6.3 offline, additive, two-reviewer case and source adjudication workflow.

Creates independent BLANK review sheets and audits submitted human answers.
It never assigns gold reference status or natural defect truth. No model/network calls.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY = Path("data/evaluation/b6_3_review_policy_v1.json")
BASE_CASES = Path("data/evaluation/b6_2_ai4i_independent_review.csv")
B61 = Path("data/evaluation/b6_1_real_baselines.json")
B62 = Path("data/evaluation/b6_2_development_study.json")
CAT = Path("data/evaluation/b6_reference_catalogue.json")
PRO = Path("data/evaluation/b6_protocol_v1.json")
OUT = Path("data/evaluation/b6_3_review")
CASE_IDENTITY = ["reference_id", "source_sha256", "UDI", "case", "active_modes",
                 "TWF", "HDF", "PWF", "OSF", "RNF", "Machine failure"]
RULE_IDENTITY = ["reference_id", "domain", "reference_status", "source_urls",
                 "review_question"]
VOTE = ["reviewer_id", "decision", "evidence_url", "evidence_locator", "rationale"]
CASE_TYPES = ("forward_frozen_rule_violation", "reverse_exploratory_only_not_frozen_rule")
EXPECTED_MAN_SHA = "dc6630cd9b1f0f853922fad78a1b6436570d3f1ec863f1dd5c4340ac56bc8a8e"
EXPECTED_CYB_SHA = "3ee83d5ecbfd50541b0205293a462643309e253e095c41c82cc5c37cf6aef2d5"


class ReviewError(ValueError):
    pass


def filehash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def obj(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ReviewError(f"Missing input: {path}")
    result = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(result, dict):
        raise ReviewError(f"Expected JSON object: {path}")
    return result


def read_csv(path: Path, expected: list[str] | None = None) -> list[dict[str, str]]:
    if not path.is_file():
        raise ReviewError(f"Missing CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header or len(header) != len(set(header)):
            raise ReviewError(f"Missing/duplicate CSV headers: {path}")
        if expected is not None and header != expected:
            raise ReviewError(f"Unexpected CSV header/order in {path}")
        records = []
        for n, values in enumerate(reader, 2):
            if len(values) != len(header):
                raise ReviewError(f"Malformed CSV record {path}:{n}")
            records.append(dict(zip(header, values)))
        return records


def write_csv(path: Path, names: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=names, lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def original_case_rows(root: Path, policy: dict[str, Any]) -> list[dict[str, str]]:
    # The original B6.2 review sheet must have blank human-review fields.
    path = root / BASE_CASES
    rows = read_csv(path)
    if len(rows) != policy["required_case_count"]:
        raise ReviewError("Frozen discrepancy worksheet count changed")
    if set(CASE_IDENTITY) - set(rows[0]):
        raise ReviewError("Missing required original case fields")
    udis: set[str] = set()
    counts = Counter()
    expected_uid = sorted([int(r["UDI"]) for r in rows])
    if expected_uid != [int(r["UDI"]) for r in rows]:
        raise ReviewError("Original B6.2 rows reordered")
    for r in rows:
        if r["reference_id"] != "B6-MAN-001" or r["source_sha256"] != EXPECTED_MAN_SHA:
            raise ReviewError("Original case reference/source mismatch")
        uid = r["UDI"]
        if not uid.isdecimal() or uid in udis:
            raise ReviewError("Missing, nonnumeric or duplicate UDI")
        udis.add(uid)
        if any(r.get(k, "") for k in r if k not in CASE_IDENTITY and k != "notes"):
            raise ReviewError("Original B6.2 worksheet has human reviews filled; do not use as frozen blank input")
        flags = [r.get(m) for m in ("TWF", "HDF", "PWF", "OSF", "RNF", "Machine failure")]
        if any(v not in ("0", "1") for v in flags):
            raise ReviewError("Nonbinary/missing source flag in frozen worksheet")
        active = "|".join(m for m in ("TWF", "HDF", "PWF", "OSF", "RNF") if r[m] == "1")
        if active != r["active_modes"]:
            raise ReviewError("Source active-mode pattern mismatch")
        case = r["case"]
        if case == CASE_TYPES[0] and not (active == "RNF" and r["Machine failure"] == "0"):
            raise ReviewError("Unexpected forward-case semantics")
        if case == CASE_TYPES[1] and not (active == "" and r["Machine failure"] == "1"):
            raise ReviewError("Unexpected exploratory reverse-case semantics")
        if case not in CASE_TYPES:
            raise ReviewError("Unknown discrepancy case type")
        counts[case] += 1
    if dict(counts) != policy["expected_case_breakdown"]:
        raise ReviewError("Frozen case breakdown changed")
    return [{k: r[k] for k in CASE_IDENTITY} for r in rows]


def load(root: Path) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]], dict[str, str]]:
    policy = obj(root / POLICY)
    cat, pro = obj(root / CAT), obj(root / PRO)
    b61, b62 = obj(root / B61), obj(root / B62)
    if (policy.get("parent_protocol_id") != pro.get("protocol_id")
        or cat.get("protocol_id") != pro.get("protocol_id")
        or pro.get("protocol_id") != "b6-frozen-protocol-v1"):
        raise ReviewError("Frozen catalogue/protocol identity mismatch")
    if (policy.get("starting_commit") != "954f9f6d7a475391999f172c06bc93525fe98448"
        or b62.get("reviewer_count_completed") != 0
        or b62.get("final_gold_reference_rules") != 0
        or b62.get("real_natural_defect_gold_labels") != 0):
        raise ReviewError("Unrecognised B6.2 review baseline")
    if (b62.get("B6_1_report_sha256") != filehash(root / B61)
        or b61.get("catalogue_sha256") != filehash(root / CAT)
        or b61.get("protocol_sha256") != filehash(root / PRO)):
        raise ReviewError("Frozen B6.1/B6.2 report or reference file hashes changed")
    by_domain = {x["domain"]: x for x in b61.get("results", [])}
    source_hashes = {"manufacturing": EXPECTED_MAN_SHA, "cybersecurity": EXPECTED_CYB_SHA}
    for d, src in source_hashes.items():
        if (by_domain.get(d, {}).get("source_sha256") != src
            or next((x.get("source_sha256") for x in b62.get("domains", []) if x.get("domain") == d), None) != src):
            raise ReviewError(f"Source hash mismatch in frozen reports: {d}")
    if b62.get("manufacturing_discrepancy_review", {}).get("worksheets_generated") != 27:
        raise ReviewError("B6.2 discrepancy count changed")
    cases = original_case_rows(root, policy)
    ref_entries = {x["id"]: x for x in cat["entries"]}
    rule_items = []
    questions = {
        "B6-MAN-001": "Do original AI4I documentation and exact CSV version entail this one-way five-flag implication? Explain RNF five-count/source discrepancy and scope.",
        "B6-CYB-001": "Do CICFlowMeter feature definitions and retained mirror version support min<=mean<=max for positive forward packet count? Check exact CSV header mapping."
    }
    for rid in policy["source_rule_ids"]:
        e = ref_entries.get(rid)
        if not e or e["status"] != "provisional_source_supported" or e["scoring_eligible"] is not False:
            raise ReviewError(f"Missing or ineligible provisional reference rule: {rid}")
        urls = [x["url"] for x in e["evidence"]]
        if urls != policy["reference_sources"][rid]:
            raise ReviewError(f"Review source URLs no longer match catalogue: {rid}")
        rule_items.append({"reference_id": rid, "domain": e["domain"], "reference_status": e["status"],
                           "source_urls": " | ".join(urls), "review_question": questions[rid]})
    fingerprints = {p.as_posix(): filehash(root / p) for p in (POLICY, BASE_CASES, CAT, PRO, B61, B62)}
    return policy, cases, rule_items, fingerprints


def template_rows(items: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{**item, **{k: "" for k in VOTE}} for item in items]


def prepare(root: Path) -> dict[str, Any]:
    policy, cases, rules, hashes = load(root)
    out = root / OUT
    paths = [out / f"reviewer_{i}_{part}.csv" for i in (1, 2) for part in ("cases", "rules")]
    paths += [out / "review_manifest.json", out / "review_audit.json"]
    if any(p.exists() for p in paths):
        raise ReviewError("B6.3 output already exists. Refusing to overwrite reviewer work; run --audit instead")
    for i in (1, 2):
        write_csv(out / f"reviewer_{i}_cases.csv", CASE_IDENTITY + VOTE, template_rows(cases))
        write_csv(out / f"reviewer_{i}_rules.csv", RULE_IDENTITY + VOTE, template_rows(rules))
    manifest = {"study_id": policy["study_id"], "phase": "blank_reviewer_templates_not_reviewed",
                "baseline_sha256": hashes, "case_rows": len(cases), "rule_rows": len(rules),
                "two_independent_reviews_completed": False, "independent_gold_rule_count": 0,
                "note": "Human reviewers must complete separate sheets independently; do not treat templates as evidence."}
    (out / "review_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"case_rows": len(cases), "rule_rows": len(rules), "output": str(out)}


def _check_vote(row: dict[str, str], allowed: set[str]) -> bool:
    # Completely blank is missing; partially filled rows MUST fail closed.
    values = [row[k].strip() for k in VOTE]
    if not any(values):
        return False
    if not all(values):
        raise ReviewError("Partially filled human decision: require reviewer ID, decision, source URL, locator and rationale")
    if row["decision"] not in allowed:
        raise ReviewError("Unsupported human decision")
    if not row["evidence_url"].startswith("https://") or len(row["rationale"].strip()) < 10:
        raise ReviewError("Missing verifiable evidence URL or substantive rationale")
    return True


def audit_part(root: Path, policy: dict[str, Any], part: str, originals: list[dict[str, str]]) -> dict[str, Any]:
    keys = CASE_IDENTITY if part == "cases" else RULE_IDENTITY
    allowed = set(policy["case_decisions"] if part == "cases" else policy["rule_decisions"])
    responses = []
    for num in (1, 2):
        rows = read_csv(root / OUT / f"reviewer_{num}_{part}.csv", keys + VOTE)
        if len(rows) != len(originals):
            raise ReviewError(f"Reviewer {num} altered {part} row count")
        completed = 0
        reviewer_ids = set()
        for original, row in zip(originals, rows):
            if any(row[k] != original[k] for k in keys):
                raise ReviewError(f"Reviewer {num} altered fixed {part} record identity")
            if _check_vote(row, allowed):
                completed += 1
                reviewer_ids.add(row["reviewer_id"].strip())
        if len(reviewer_ids) > 1:
            raise ReviewError("One reviewer file contains multiple reviewer identities")
        responses.append({"rows": rows, "completed": completed, "reviewer_ids": reviewer_ids})
    ids1, ids2 = responses[0]["reviewer_ids"], responses[1]["reviewer_ids"]
    if ids1 and ids2 and ids1 == ids2:
        raise ReviewError("Reviewer 1 and 2 must have different IDs; software cannot establish human independence")
    both = equal = conflict = 0
    for r1, r2 in zip(responses[0]["rows"], responses[1]["rows"]):
        if r1["decision"].strip() and r2["decision"].strip():
            both += 1
            equal += int(r1["decision"] == r2["decision"])
            conflict += int(r1["decision"] != r2["decision"])
    return {"items_total": len(originals), "reviewer_1_completed": responses[0]["completed"],
            "reviewer_2_completed": responses[1]["completed"], "both_completed": both,
            "agreed": equal, "disagreed": conflict, "not_jointly_reviewed": len(originals) - both,
            "raw_agreement_among_jointly_reviewed": equal / both if both else None,
            "human_independence_verified_by_software": False}


def audit(root: Path) -> dict[str, Any]:
    policy, cases, rules, fingerprints = load(root)
    manifest = obj(root / OUT / "review_manifest.json")
    if manifest.get("baseline_sha256") != fingerprints or manifest.get("study_id") != policy["study_id"]:
        raise ReviewError("Source, design, or original worksheet changed since review preparation")
    case_stats = audit_part(root, policy, "cases", cases)
    rule_stats = audit_part(root, policy, "rules", rules)
    summary = {"study_id": policy["study_id"], "status": "review_in_progress",
               "manufacturing_discrepancies": {"forward": 18, "reverse_exploratory": 9},
               "cases": case_stats, "source_rules": rule_stats,
               "independently_adjudicated_gold_rules": 0, "confirmed_natural_defects": 0,
               "eligible_for_final_gold_scoring": False,
               "human_independence_not_established_by_script": True,
               "adjudicator_decisions_entered": False,
               "warning": "Agreement between human votes alone is not independent evidence of true labels; unresolved source semantics and adjudicator review required."}
    output = root / OUT / "review_audit.json"
    output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--check-inputs", action="store_true")
    choice.add_argument("--prepare", action="store_true")
    choice.add_argument("--audit", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        if args.check_inputs:
            _, cases, rules, _ = load(args.root)
            print(f"B6.3 preflight PASS: {len(cases)} frozen discrepancy cases, {len(rules)} provisional source rules; human votes: zero in source")
            print("No inputs modified; no dataset reads, network or API calls")
        elif args.prepare:
            result = prepare(args.root)
            print(f"B6.3 templates created: {result['case_rows']} cases x 2 reviewers; {result['rule_rows']} rules x 2 reviewers")
            print("Human decisions intentionally BLANK; gold reference rules: 0")
        else:
            result = audit(args.root)
            print(f"B6.3 audit: cases jointly reviewed {result['cases']['both_completed']}/27; "
                  f"source rules jointly reviewed {result['source_rules']['both_completed']}/2; "
                  "independently adjudicated gold rules: 0")
            print("Any later human votes require independent provenance review; no gold status assigned")
        return 0
    except (ReviewError, OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"B6.3 ERROR (no adjudication claimed): {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
