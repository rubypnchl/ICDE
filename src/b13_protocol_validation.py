"""B13 design and candidate-source snapshot validation (no gate execution)."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

STUDY_ID = "b13_prospective_matched_evidence_gate_v1"
DOMAINS = ("finance", "healthcare", "cybersecurity", "manufacturing")
ARMS = (
    ("A", "compiler_only"),
    ("B", "compiler_plus_metadata"),
    ("C", "compiler_plus_metadata_plus_document_and_context"),
)
COLUMNS = (
    "candidate_id", "domain", "source_group", "source_path", "source_sha256",
    "opportunity_id", "proposal_method", "proposal_path", "proposal_sha256",
    "context_path", "context_sha256", "registry_path", "registry_sha256",
    "source_evidence_url", "source_evidence_locator",
)
SHA = re.compile(r"^[0-9a-f]{64}$")
IDENT = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")


class B13Error(ValueError):
    """A fail-closed protocol, input or provenance check failed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_plan(plan: dict) -> None:
    if plan.get("study_id") != STUDY_ID:
        raise B13Error("Unexpected study_id")
    if plan.get("protocol_state") != "design_draft_not_run":
        raise B13Error("This package is design-only and cannot report as run")
    if plan.get("study_type") != "matched_candidate_admission_policy_comparison":
        raise B13Error("Incorrect study type")
    if plan.get("domains") != list(DOMAINS):
        raise B13Error("The four frozen domains are not as expected")
    quota = plan.get("target_unique_candidates_per_domain")
    if type(quota) is not int or not 1 <= quota <= 1000:
        raise B13Error("Invalid per-domain target")
    if plan.get("target_is_statistical_power_calculation") is not False:
        raise B13Error("Do not misstate the engineering target as a power study")
    arms = plan.get("arms")
    if not isinstance(arms, list) or len(arms) != 3:
        raise B13Error("All three arms required")
    for entry, expected in zip(arms, ARMS):
        if (entry.get("id"), entry.get("name")) != expected:
            raise B13Error("Policy arm order/name changed")
        if entry.get("same_candidates") is not True or entry.get("shared_parameter_registry") is not True:
            raise B13Error("Arms must share candidates and bindings")
    if plan.get("allowed_claims_now") != ["protocol_design_only"]:
        raise B13Error("Only design-only claims are supported")
    if any(plan.get(flag) is not value for flag, value in (
        ("no_git_push", True), ("no_network_calls", True),
        ("no_source_modifications", True))):
        raise B13Error("Safety safeguards changed")


def read_manifest(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(COLUMNS):
            raise B13Error("Candidate manifest schema differs from versioned template")
        rows = list(reader)
    for index, row in enumerate(rows, start=2):
        if None in row or any(v is None for v in row.values()):
            raise B13Error(f"Malformed or overlong row at line {index}")
    return rows


def _validate_file(path_str: str, expected_hash: str, field: str, base: Path) -> None:
    if not SHA.fullmatch(expected_hash):
        raise B13Error(f"Invalid SHA-256 for {field}")
    if not path_str or "\x00" in path_str:
        raise B13Error(f"Missing or invalid file path for {field}")
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = base / path
    if not path.is_file():
        raise B13Error(f"Missing source/proposal/context/registry file for {field}")
    if sha256_file(path).lower() != expected_hash:
        raise B13Error(f"SHA-256 mismatch for {field}")


def validate_candidates(rows: list[dict], base: Path, plan: dict, *, lock: bool) -> dict:
    if lock and not rows:
        raise B13Error("Cannot lock an empty candidate manifest")
    seen: set[str] = set()
    counts = Counter()
    for i, row in enumerate(rows, 2):
        cid = row["candidate_id"].strip()
        if not IDENT.fullmatch(cid) or cid in seen:
            raise B13Error(f"Invalid or duplicated candidate_id at line {i}")
        seen.add(cid)
        if row["domain"] not in DOMAINS:
            raise B13Error(f"Unknown domain at line {i}")
        for field in ("source_group", "opportunity_id", "proposal_method"):
            if not row[field].strip():
                raise B13Error(f"Missing {field} at line {i}")
        parsed = urlparse(row["source_evidence_url"])
        if parsed.scheme != "https" or not parsed.netloc or not row["source_evidence_locator"].strip():
            raise B13Error(f"Missing HTTPS documentary source/locator at line {i}")
        for stem in ("source", "proposal", "context", "registry"):
            _validate_file(row[f"{stem}_path"], row[f"{stem}_sha256"], f"{cid}:{stem}", base)
        counts[row["domain"]] += 1
    if lock:
        quota = plan["target_unique_candidates_per_domain"]
        missing = {domain: quota - counts[domain] for domain in DOMAINS if counts[domain] < quota}
        if missing:
            raise B13Error(f"Not enough new source-qualified candidates to lock; deficits={missing}")
    return {"candidates_total": len(rows), "by_domain": {d: counts[d] for d in DOMAINS},
            "evidence_content_verified": False, "novel_source_status_verified": False,
            "independently_adjudicated_gold_rules": 0}


def candidate_hash_records(rows: list[dict]) -> list[dict]:
    """Lock candidate identifiers and hashes only; never publish private local paths."""
    return [
        {"candidate_id": row["candidate_id"], "domain": row["domain"],
         "source_group": row["source_group"], "source_sha256": row["source_sha256"],
         "proposal_sha256": row["proposal_sha256"], "context_sha256": row["context_sha256"],
         "registry_sha256": row["registry_sha256"]}
        for row in rows
    ]


def safe_write_lock(output: Path, payload: dict) -> None:
    # Exclusive create prevents accidental result overwrite.
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
