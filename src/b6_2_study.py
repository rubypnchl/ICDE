"""B6.2 independent rule checker and controlled, deliberately limited perturbations.

IMPORTANT: This is NOT an independent rule-discovery baseline; it is a
hand-coded execution baseline for the *same frozen reference rule*. A synthetic
mutation's detection is a tautological rule-consistency test, not defect truth.
No network calls, APIs, LLMs, pandas, writes to source CSVs or data repair.
"""
from __future__ import annotations

from collections import Counter
import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
import random
from typing import Any, Iterable

MODES = ("TWF", "HDF", "PWF", "OSF", "RNF")
REQUIRED = {
    "manufacturing": (*MODES, "Machine failure"),
    "cybersecurity": (" Total Fwd Packets", " Fwd Packet Length Min", " Fwd Packet Length Mean", " Fwd Packet Length Max"),
}
STATUSES = ("satisfied", "violated", "abstained", "not_applicable")

class StudyError(ValueError):
    """Failure of a research invariant; no valid result should be published."""


def dec(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool) or str(value).strip() == "":
        return None
    try:
        number = Decimal(str(value).strip())
    except (TypeError, ValueError, InvalidOperation):
        return None
    return number if number.is_finite() else None


def simple_rule_checker(domain: str, record: dict[str, str]) -> str:
    """Independent hard-coded rule checker; does not use B3's interpreter."""
    if domain == "manufacturing":
        vals = [dec(record.get(field)) for field in REQUIRED[domain]]
        if any(v not in (Decimal(0), Decimal(1)) for v in vals):
            return "abstained"
        if not any(v == 1 for v in vals[:5]):
            return "not_applicable"
        return "satisfied" if vals[5] == 1 else "violated"
    if domain == "cybersecurity":
        count = dec(record.get(" Total Fwd Packets"))
        if count is None or count < 0 or count != count.to_integral_value():
            return "abstained"
        if count == 0:
            return "not_applicable"
        mn, mean, mx = [dec(record.get(field)) for field in REQUIRED[domain][1:]]
        if any(x is None for x in (mn, mean, mx)):
            return "abstained"
        return "satisfied" if mn <= mean <= mx else "violated"
    raise StudyError(f"Unknown domain: {domain}")


def rows_by_position(path: Path, required: Iterable[str]):
    """Read only needed fields, refusing ambiguity and malformed CSV records."""
    required = set(required)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        head = next(reader, None)
        if not head:
            raise StudyError(f"Missing header: {path}")
        freq = Counter(head)
        missing = sorted(required - set(head))
        if missing:
            raise StudyError(f"Missing required headers: {missing}")
        duplicate = sorted(c for c in required if freq[c] != 1)
        if duplicate:
            raise StudyError(f"Duplicate required headers: {duplicate}")
        positions = {c: head.index(c) for c in required}
        for line, values in enumerate(reader, start=2):
            if len(values) != len(head):
                raise StudyError(f"Malformed row {line}: {len(values)} cells vs {len(head)} columns")
            yield {name: values[i] for name, i in positions.items()}


def reservoir_keep(samples: list[dict[str, str]], candidate: dict[str, str], seen: int, quota: int, rng: random.Random) -> None:
    """Uniform reservoir sampling among matching rows in a fixed input order."""
    if len(samples) < quota:
        samples.append(candidate.copy())
    else:
        position = rng.randrange(seen)
        if position < quota:
            samples[position] = candidate.copy()


def analyze_rows(domain: str, rows: Iterable[dict[str,str]], *, quota: int, seed: int):
    if type(quota) is not int or quota < 1 or type(seed) is not int:
        raise StudyError("Invalid predeclared selection configuration")
    rng = random.Random(seed)
    counts = Counter({status: 0 for status in STATUSES})
    sampled: list[dict[str,str]] = []
    nonapp: list[dict[str,str]] = []
    seen_clean, seen_nonapp = 0, 0
    anomalies: list[dict[str,str]] = []
    udis: set[str] = set()
    reverses = 0
    rnf_only = 0
    for row in rows:
        counts[simple_rule_checker(domain, row)] += 1
        status = simple_rule_checker(domain, row)
        if status == "satisfied":
            seen_clean += 1
            reservoir_keep(sampled, row, seen_clean, quota, rng)
        if status == "not_applicable":
            seen_nonapp += 1
            reservoir_keep(nonapp, row, seen_nonapp, min(8,quota), rng)
        if domain == "manufacturing":
            uid = row.get("UDI")
            if not uid or not uid.isdigit() or uid in udis:
                raise StudyError(f"Missing, nonnumeric or duplicate UDI: {uid}")
            udis.add(uid)
            vals = [dec(row.get(c)) for c in REQUIRED[domain]]
            if any(v not in (Decimal(0),Decimal(1)) for v in vals):
                continue
            modes_active = tuple(mode for mode in MODES if dec(row[mode]) == 1)
            case = None
            if modes_active and dec(row["Machine failure"]) == 0:
                case = "forward_frozen_rule_violation"
                if modes_active == ("RNF",):
                    rnf_only += 1
            elif not modes_active and dec(row["Machine failure"]) == 1:
                case = "reverse_exploratory_only_not_frozen_rule"
                reverses += 1
            if case:
                anomalies.append({"UDI":uid, "case":case,
                                  "active_modes":"|".join(modes_active),
                                  **{k:row[k] for k in REQUIRED["manufacturing"]}})
    if seen_clean < quota:
        raise StudyError(f"Too few satisfied {domain} rows for predeclared quota: {seen_clean} < {quota}")
    return {"counts":dict(counts),"record_count":sum(counts.values()),"eligible_records":sum(counts.values())-counts["not_applicable"],
            "sampled_clean":sampled,"sampled_nonapp":nonapp,"discrepancies":anomalies,
            "forward_rnf_only":rnf_only,"reverse_exploratory":reverses,
            "satisfied_population":seen_clean}


def injected_positive(domain: str, record: dict[str,str]) -> dict[str,str]:
    """Exact deterministic mutation; input MUST satisfy the frozen rule."""
    if simple_rule_checker(domain, record) != "satisfied":
        raise StudyError("Positive injection requires an originally satisfying eligible record")
    changed = record.copy()
    if domain == "manufacturing":
        changed["Machine failure"] = "0"
    elif domain == "cybersecurity":
        mx = dec(record[" Fwd Packet Length Max"])
        assert mx is not None
        changed[" Fwd Packet Length Mean"] = str(mx + Decimal(1))
    else:
        raise StudyError("Unknown domain")
    if simple_rule_checker(domain, changed) != "violated":
        raise StudyError("Mutation did not actually violate the rule")
    return changed


def out_of_scope_control(domain: str, record: dict[str,str]) -> dict[str,str]:
    changed = record.copy()
    if domain == "manufacturing":
        for name in MODES:
            changed[name] = "0"
    elif domain == "cybersecurity":
        changed[" Total Fwd Packets"] = "0"
    else:
        raise StudyError("Unknown domain")
    return changed


def missing_control(domain: str, record: dict[str,str]) -> dict[str,str]:
    changed = record.copy()
    changed["TWF" if domain == "manufacturing" else " Total Fwd Packets"] = ""
    return changed


def score_binary(originals: list[dict[str,str]], domain: str, detector) -> dict[str,Any]:
    """Sanity check on BY-RULE selected clean and injected copies. Not natural defect precision."""
    cm = Counter({k:0 for k in ("TP","FP","TN","FN","unresolved")})
    for orig in originals:
        for label, row in ((0, orig), (1, injected_positive(domain,orig))):
            verdict = detector(domain,row)
            if verdict not in STATUSES:
                raise StudyError("Detector produced an invalid status")
            if verdict in ("not_applicable", "abstained"):
                cm["unresolved"] += 1
            elif label == 1:
                cm["TP" if verdict == "violated" else "FN"] += 1
            else:
                cm["FP" if verdict == "violated" else "TN"] += 1
    tp,fp,tn,fn = (cm[k] for k in ("TP","FP","TN","FN"))
    return {"confusion_by_rule_only":dict(cm),
            "precision_on_constructed_cases":tp/(tp+fp) if tp+fp else None,
            "recall_on_constructed_cases":tp/(tp+fn) if tp+fn else None,
            "note":"Expected sanity-check results from mutations designed to break the same rule. Not independent natural-defect precision or generalisation."}


def worksheet_rows(discrepancies: list[dict[str,str]], source_sha256: str) -> list[dict[str,str]]:
    return [{"reference_id":"B6-MAN-001", "source_sha256":source_sha256, **d,
             "reviewer_1_id":"", "reviewer_1_decision":"", "reviewer_1_evidence":"",
             "reviewer_2_id":"", "reviewer_2_decision":"", "reviewer_2_evidence":"",
             "adjudicator":"", "adjudicated_decision":"", "notes":""}
            for d in sorted(discrepancies,key=lambda x:int(x["UDI"]))]
