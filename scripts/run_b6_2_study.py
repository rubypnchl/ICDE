"""B6.2: offline development-only same-rule baseline and synthetic injection audit.

Reads original AI4I and CIC CSVs without modification. Two reviewers must still
independently examine source meaning; this code cannot create gold labels.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.b6_2_study import (
    REQUIRED, StudyError, analyze_rows, injected_positive, missing_control,
    out_of_scope_control, rows_by_position, score_binary, simple_rule_checker,
    worksheet_rows,
)
from src.generic_verifier import evaluate_row
from scripts.run_b6_1_real_baselines import (
    EvaluationError, _invalid_measurement, _sha256, prepare, load_plan,
)

REPORT_PATH = "data/evaluation/b6_2_development_study.json"
WORKSHEET_PATH = "data/evaluation/b6_2_ai4i_independent_review.csv"
DESIGN_PATH = "data/evaluation/b6_2_design_v1.json"
B61_PATH = "data/evaluation/b6_1_real_baselines.json"


def load_json(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(obj, dict):
        raise StudyError(f"Expected JSON object: {path}")
    return obj


def check_design(root: Path, design: dict, baseline: dict, ready: dict) -> None:
    if design.get("study_id") != "b6_2_development_rule_checker_and_injections_v1":
        raise StudyError("Study design identifier changed")
    if design.get("parent_protocol_id") != baseline.get("protocol_id") or design.get("source_artifact") != B61_PATH:
        raise StudyError("Design is not linked to frozen B6 / B6.1")
    if design.get("baseline_reference_commit") != "1d0bed572f1e37e0f306bb81abe66bb538b9e645":
        raise StudyError("Unexpected B6.1 baseline commit in study design")
    quota=design.get("n_satisfied_source_rows_per_domain")
    if type(quota) is not int or not 1 <= quota <= 1000:
        raise StudyError("Invalid predeclared sample quota")
    seeds=design.get("sample_seed")
    if not isinstance(seeds,dict) or set(seeds)!={"manufacturing","cybersecurity"} or any(type(x) is not int for x in seeds.values()):
        raise StudyError("Invalid predeclared sampling seeds")
    if design.get("reference_rule_ids") != {d:ready[d]["entry"]["id"] for d in ready}:
        raise StudyError("Predeclared reference IDs differ from B6 catalogue")
    if _sha256(root/"data/evaluation/b6_reference_catalogue.json") != baseline.get("catalogue_sha256"):
        raise StudyError("Reference catalogue differs from B6.1 baseline; must version protocol")
    if _sha256(root/"data/evaluation/b6_protocol_v1.json") != baseline.get("protocol_sha256"):
        raise StudyError("Frozen protocol differs from B6.1 baseline")
    if _sha256(root/"data/sources.json") != baseline.get("source_manifest_sha256"):
        raise StudyError("Source manifest differs from B6.1 baseline")
    records=baseline.get("results")
    if (not isinstance(records,list) or len(records)!=2
            or {r.get("domain") for r in records}!={"manufacturing","cybersecurity"}):
        raise StudyError("B6.1 baseline must contain both domains")
    for domain in ready:
        r=next(x for x in records if x["domain"]==domain)
        if (r.get("reference_rule_id")!=ready[domain]["entry"]["id"]
                or r.get("source_file")!=ready[domain]["config"]["source"]
                or not isinstance(r.get("counts"),dict)):
            raise StudyError(f"B6.1 reference identity mismatch for {domain}")
        if _sha256(ready[domain]["path"]) != r.get("source_sha256"):
            raise StudyError(f"{domain} source checksum differs from committed B6.1 report")


def generic_b61_guarded(rule: dict, domain: str, row: dict[str,str]) -> str:
    """Exactly the same guarded B3 execution path used by B6.1."""
    invalid = _invalid_measurement(domain, row)
    if invalid:
        return "abstained"
    return evaluate_row(rule, row).status


def check_controls(domain: str, samples: list[dict[str,str]], rule:dict) -> dict:
    results = {"no_op":0,"injected_violation":0,"out_of_scope":0,"missing_field":0}
    for row in samples:
        base = row.copy()
        altered = injected_positive(domain,row)
        for case, payload, wanted in (
            ("no_op", base, "satisfied"),
            ("injected_violation", altered, "violated"),
            ("out_of_scope", out_of_scope_control(domain,row), "not_applicable"),
            ("missing_field", missing_control(domain,row), "abstained"),
        ):
            simple = simple_rule_checker(domain,payload)
            generic = generic_b61_guarded(rule, domain,payload)
            if simple != wanted or generic != wanted:
                raise StudyError(f"{domain}: sanity probe {case} failed: independent={simple}, generic={generic}, expected={wanted}")
            results[case] += 1
    return results


def run(root:Path, *, quota_override: int | None = None) -> tuple[dict, list[dict]]:
    design=load_json(root/DESIGN_PATH)
    baseline=load_json(root/B61_PATH)
    ready=prepare(root,["manufacturing","cybersecurity"])
    check_design(root,design,baseline,ready)
    if quota_override is not None:
        raise StudyError("Study quota is frozen; no user override allowed")
    studies=[]
    worksheet=[]
    started=time.perf_counter()
    for domain in ("manufacturing","cybersecurity"):
        cfg=ready[domain]
        rule=cfg["rule"]
        base=next(r for r in baseline["results"] if r["domain"]==domain)
        required = set(REQUIRED[domain]) | ({"UDI"} if domain=="manufacturing" else set())
        t0=time.perf_counter()
        result=analyze_rows(domain, rows_by_position(cfg["path"],required),
                            quota=design["n_satisfied_source_rows_per_domain"],
                            seed=design["sample_seed"][domain])
        elapsed=time.perf_counter()-t0
        if (result["counts"] != base["counts"]
                or result["record_count"] != base["record_count"]
                or result["eligible_records"] != base["eligible_records"]):
            raise StudyError(f"{domain}: independently written checker DISAGREES with B6.1; stop and investigate")
        if _sha256(cfg["path"]) != base["source_sha256"]:
            raise StudyError(f"{domain}: source file changed during experiment")
        sampled = result["sampled_clean"]
        controls=check_controls(domain,sampled,rule)
        simple_metrics=score_binary(sampled,domain,simple_rule_checker)
        generic_metrics=score_binary(sampled,domain,lambda d,r:generic_b61_guarded(rule,d,r))
        if simple_metrics["confusion_by_rule_only"] != generic_metrics["confusion_by_rule_only"]:
            raise StudyError(f"{domain}: detector scores diverged on the same injected examples")
        if domain=="manufacturing":
            worksheet=worksheet_rows(result["discrepancies"], base["source_sha256"])
            forward=len([x for x in worksheet if x["case"]=="forward_frozen_rule_violation"])
            if forward != base["counts"]["violated"]:
                raise StudyError("Forward violations differ from B6.1")
        studies.append({
            "domain":domain,"reference_rule_id":rule["id"], "source_sha256":base["source_sha256"],
            "candidate_rule_status":"provisional_source_supported_not_gold",
            "same_rule_simple_checker_counts":result["counts"],
            "agrees_with_B6_1_generic_engine":True,
            "n_orig_satisfying_population":result["satisfied_population"],
            "n_deterministically_selected_originals":len(sampled),
            "selection_seed":design["sample_seed"][domain],
            "source_rows_modified":False,
            "probe_counts_by_expected_status":controls,
            "simple_checker_constructed_case_metrics":simple_metrics,
            "B3_generic_constructed_case_metrics":generic_metrics,
            "elapsed_seconds_single_pass_simple_checker":round(elapsed,6),
            "timing_warning":"Single pass on development data; not an apples-to-apples timed benchmark against saved B6.1 run",
            "independent_source_review_complete":False,
            "claim":"Same frozen-rule execution agrees; injected detection is by construction, not independent anomaly accuracy"
        })
    case_counts={
        "forward_frozen_rule_violation":sum(x["case"]=="forward_frozen_rule_violation" for x in worksheet),
        "reverse_exploratory_only_not_frozen_rule":sum(x["case"]=="reverse_exploratory_only_not_frozen_rule" for x in worksheet),
    }
    rnf_only=sum(x["active_modes"]=="RNF" and x["case"]=="forward_frozen_rule_violation" for x in worksheet)
    report={
        "experiment":design["study_id"],"protocol_id":design["parent_protocol_id"],
        "development_study":True,"real_natural_defect_gold_labels":0,
        "reviewer_count_completed":0,"final_gold_reference_rules":0,
        "design_sha256":_sha256(root/DESIGN_PATH),"B6_1_report_sha256":_sha256(root/B61_PATH),
        "runner_sha256":_sha256(Path(__file__)),
        "source_frozen":True,"no_network_or_paid_model_calls":True,
        "domains":studies,
        "manufacturing_discrepancy_review":{"case_counts":case_counts,"rnf_only_forward":rnf_only,
            "worksheets_generated":len(worksheet),"independent_review_votes_filled":0,
            "interpretation":"Forward errors against provisional rule; reverse cases exploratory only. No confirmed natural defects."},
        "elapsed_seconds_total_single_pass":round(time.perf_counter()-started,6),
        "limitations":["No discovery or semantic-precision comparison: both checkers receive the same frozen reference rule",
                       "Constructed mutations are tautologically linked to the rule and not independent real-world defect labels",
                       "Previously inspected AI4I and CIC samples are development sets", "Independent source adjudication has not occurred"]
    }
    return report, worksheet


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path,default=ROOT)
    ap.add_argument("--check-inputs",action="store_true")
    args=ap.parse_args()
    root=args.root.resolve()
    try:
        design=load_json(root/DESIGN_PATH)
        base=load_json(root/B61_PATH)
        ready=prepare(root,["manufacturing","cybersecurity"])
        check_design(root,design,base,ready)
        if args.check_inputs:
            print("B6.2 preflight PASS: frozen design, catalogue, protocol, source hashes, reference IDs")
            print("No data evaluated or files written")
            return 0
        result, worksheet=run(root)
        # No output before all cross-engine and provenance checks pass.
        csv_path=root/WORKSHEET_PATH
        json_path=root/REPORT_PATH
        csv_path.parent.mkdir(parents=True,exist_ok=True)
        if worksheet:
            with csv_path.open("w",newline="",encoding="utf-8") as f:
                w=csv.DictWriter(f,fieldnames=list(worksheet[0]))
                w.writeheader()
                w.writerows(worksheet)
        json_path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        for domain in result["domains"]:
            print(f"{domain['domain']}: same-rule baseline agreement PASS; "
                  f"{domain['n_deterministically_selected_originals']} clean copies + "
                  f"{domain['n_deterministically_selected_originals']} injected copies; "
                  f"probe statuses checked; no independent gold labels")
        print("Manufacturing worksheet:",result["manufacturing_discrepancy_review"]["case_counts"])
        print(f"Saved {json_path.relative_to(root)} and {csv_path.relative_to(root)}")
        print("No source CSV modified; model/API calls: 0; this is NOT a detection-precision benchmark")
        return 0
    except (StudyError,EvaluationError,ValueError,KeyError,TypeError,OSError,ZeroDivisionError) as exc:
        print(f"B6.2 ERROR (no valid results claimed): {exc}",file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
