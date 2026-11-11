"""B13.2 source-shortlist schema validation. No data/network access or gate execution."""
from __future__ import annotations
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

STUDY = "b13_2_source_eligibility_screening_v1"
DOMAINS = {"finance", "healthcare", "cybersecurity", "manufacturing"}
HOSTS = {
    "finance": {"www.sec.gov", "sec.gov", "data.sec.gov"},
    "healthcare": {"wwwn.cdc.gov"},
    "cybersecurity": {"www.unb.ca", "unb.ca"},
    "manufacturing": {"archive.ics.uci.edu", "www.archive.ics.uci.edu"},
}
FIELDS = {"id", "domain", "title", "official_url", "group_selection", "relationship_to_previous_work", "eligibility_status", "rights_or_access_note", "limitations"}

class ScreenError(ValueError):
    pass


def validate(payload: dict) -> dict:
    if not isinstance(payload, dict) or payload.get("study_id") != STUDY:
        raise ScreenError("Unrecognised study")
    if payload.get("phase") != "source_shortlist_only_not_a_candidate_cohort" or payload.get("status") != "screening_unverified":
        raise ScreenError("Cannot represent this list as a frozen or verified cohort")
    if payload.get("parent_protocol") != "b13_prospective_matched_evidence_gate_v1":
        raise ScreenError("Unrecognised B13 parent protocol")
    for key in ("gate_policies_frozen", "candidate_set_frozen", "data_downloaded_by_package", "evaluation_performed", "source_independence_confirmed"):
        if payload.get(key) is not False:
            raise ScreenError(f"Prohibited completed-status assertion: {key}")
    if payload.get("allowed_claims") != ["official_source_shortlist_prepared"]:
        raise ScreenError("Allowed-claim state was changed")
    required_denials = {"source_independence_verified", "gold_constraint_count", "prospective_gate_result", "new_natural_defects", "rule_discovery_accuracy"}
    denials = payload.get("disallowed_claims")
    if not isinstance(denials, list) or not required_denials.issubset(set(denials)):
        raise ScreenError("Critical scientific disclaimers missing")
    items = payload.get("source_shortlist")
    if not isinstance(items, list) or len(items) < 4:
        raise ScreenError("Expected a four-domain source shortlist")
    counts = Counter()
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != FIELDS:
            raise ScreenError("Source entry has missing/unknown columns")
        if any(not isinstance(value, str) or not value.strip() for value in item.values()):
            raise ScreenError("Blank source attribute")
        sid = item["id"]
        if not re.fullmatch(r"B13S-[A-Z]{3}-\d{2}", sid) or sid in seen:
            raise ScreenError("Invalid or duplicate source ID")
        seen.add(sid)
        domain = item["domain"]
        if domain not in DOMAINS:
            raise ScreenError("Unknown domain")
        parsed = urlparse(item["official_url"])
        if parsed.scheme != "https" or parsed.hostname not in HOSTS[domain] or parsed.username or parsed.password:
            raise ScreenError("Not an approved primary source URL")
        if item["eligibility_status"] != "pending_manual_verification":
            raise ScreenError("Eligibility cannot be verified by this offline script")
        counts[domain] += 1
    if set(counts) != DOMAINS:
        raise ScreenError("Missing one or more domains")
    return {"status": "SCREENING PASS", "source_entries": len(items), "by_domain": dict(sorted(counts.items())),
            "eligible_confirmatory_cohorts": 0, "candidates_frozen": 0, "gate_runs": 0, "adjudicated_gold": 0}


def read(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)
