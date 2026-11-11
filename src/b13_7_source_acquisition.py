"""B13.7 explicit public-source fetch and local provenance receipts; never stage raw data."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.request
from urllib.parse import urlsplit
import zipfile

STUDY = "b13_7_source_object_acquisition_v1"
EXPECTED = {
    "B13S-HLT-01": ("healthcare", "TRIGLY_I.XPT", "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/TRIGLY_I.XPT", "sas_xpt", "nhanes_2015_2016_cycle"),
    "B13S-HLT-02": ("healthcare", "TCHOL_I.XPT", "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/TCHOL_I.XPT", "sas_xpt", "nhanes_2015_2016_cycle"),
    "B13S-MAN-01": ("manufacturing", "steel_plates_faults.zip", "https://archive.ics.uci.edu/static/public/198/steel%2Bplates%2Bfaults.zip", "zip", "uci_steel_plates_2010_release"),
}
DOC_URLS = {
 "B13S-HLT-01": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/TRIGLY_I.htm",
 "B13S-HLT-02": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/TCHOL_I.htm",
 "B13S-MAN-01": "https://archive.ics.uci.edu/dataset/198/steel%2Bplates%2Bfaults",
}
MAX_BYTES = 64 * 1024 * 1024

class SourceError(ValueError):
    pass

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda: file.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()

def validate_registry(registry: dict) -> list[dict]:
    if not isinstance(registry, dict) or registry.get("study_id") != STUDY:
        raise SourceError("Wrong registry study id")
    if registry.get("scope") != "three_public_source_object_snapshots_only_not_source_eligibility":
        raise SourceError("Acquisition scope changed")
    if registry.get("phase") != "source_acquisition_without_candidate_selection_or_gates":
        raise SourceError("Scientific phase changed")
    if registry.get("data_are_not_bundled") is not True:
        raise SourceError("Data-bundling policy changed")
    items = registry.get("source_ids")
    if not isinstance(items, list) or len(items) != len(EXPECTED):
        raise SourceError("Expected exactly three public source object declarations")
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"source_id", "domain", "object_name", "download_url", "documentation_url", "format", "source_group", "prior_documentation_exposed", "source_specific_eligibility_verified", "reference_truth_available"}:
            raise SourceError("Registry entry fields changed")
        sid = item["source_id"]
        if sid not in EXPECTED or sid in seen:
            raise SourceError("Unexpected or duplicated source ID")
        seen.add(sid)
        if (item["domain"], item["object_name"], item["download_url"], item["format"], item["source_group"]) != EXPECTED[sid]:
            raise SourceError("Source identity or download URL changed")
        if item["documentation_url"] != DOC_URLS[sid]:
            raise SourceError("Documentation URL changed")
        if item["prior_documentation_exposed"] is not True or item["source_specific_eligibility_verified"] is not False or item["reference_truth_available"] is not False:
            raise SourceError("Scientific eligibility controls changed")
    if registry.get("allowed_claims") != ["public_source_file_acquisition_attempted_and_recorded_when_successful"]:
        raise SourceError("Allowed claims changed")
    if set(registry.get("disallowed_claims", [])) != {"independently_verified_file_authenticity", "confirmatory_cohorts_eligible", "validated_semantic_constraint", "matched_gate_effect", "unseen_blinded_discovery", "adjudicated_gold"}:
        raise SourceError("Disallowed claims changed")
    return items

def assert_external_cache(cache_dir: Path, repo_root: Path) -> Path:
    cache = cache_dir.expanduser().resolve()
    root = repo_root.resolve()
    if cache == root or root in cache.parents:
        raise SourceError("Raw source cache must be OUTSIDE the ICDE Git repository")
    if cache == Path(cache.anchor) or not str(cache):
        raise SourceError("Refusing to write to filesystem root")
    return cache

def validate_content(path: Path, fmt: str) -> None:
    if not path.is_file() or path.stat().st_size == 0 or path.stat().st_size > MAX_BYTES:
        raise SourceError("Absent, empty or oversized source file")
    with path.open('rb') as f:
        first = f.read(2048)
    if fmt == "sas_xpt":
        if not first.startswith(b'HEADER RECORD') or b'LIBRARY' not in first:
            raise SourceError("File is not recognisable SAS transport XPT data (may be HTML/error response)")
    elif fmt == "zip":
        if not zipfile.is_zipfile(path):
            raise SourceError("File is not a ZIP archive")
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if not names or any(Path(n).is_absolute() or '..' in Path(n).parts for n in names):
                raise SourceError("Unexpected/unsafe ZIP members")
            if z.testzip() is not None:
                raise SourceError("ZIP CRC validation failed")
    else:
        raise SourceError("Unknown source format")

def verify_existing(item: dict, cache: Path) -> dict:
    target = cache / item["object_name"]
    receipt = cache / (item["source_id"] + ".receipt.json")
    if not target.is_file() or not receipt.is_file():
        raise SourceError("Source file or receipt missing")
    meta = json.loads(receipt.read_text(encoding='utf-8'))
    if set(meta) != {"study_id", "source_id", "object_name", "source_url", "documentation_url", "source_group", "sha256", "size_bytes", "file_type_checked", "review_status", "independent_authenticity_verified", "semantic_eligibility_verified"}:
        raise SourceError("Receipt fields do not match frozen format")
    if (meta["study_id"], meta["source_id"], meta["object_name"], meta["source_url"], meta["documentation_url"], meta["source_group"]) != (STUDY, item["source_id"], item["object_name"], item["download_url"], item["documentation_url"], item["source_group"]):
        raise SourceError("Receipt provenance mismatch")
    if meta["file_type_checked"] is not True or meta["review_status"] != "not_independently_reviewed" or meta["independent_authenticity_verified"] is not False or meta["semantic_eligibility_verified"] is not False:
        raise SourceError("Receipt overstates verification")
    validate_content(target, item["format"])
    if meta["sha256"] != sha256_file(target) or meta["size_bytes"] != target.stat().st_size:
        raise SourceError("Local source file or receipt mutated")
    return meta

def _download_file(item: dict, target: Path, opener=urllib.request.urlopen) -> None:
    url = item["download_url"]
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('wwwn.cdc.gov', 'archive.ics.uci.edu'):
        raise SourceError("Unapproved source URL")
    request = urllib.request.Request(url, headers={'User-Agent':'MetaVerify-B13-SourceAcquisition/1.0 (academic research, manual request)', 'Accept':'application/octet-stream,application/x-sas-xport,application/zip,*/*'})
    bytes_read = 0
    with opener(request, timeout=35) as response, target.open('xb') as output:
        final = urlsplit(response.geturl())
        if final.scheme != 'https' or final.hostname != parsed.hostname:
            raise SourceError("Unexpected redirect; manual verification required")
        while True:
            block = response.read(65536)
            if not block:
                break
            bytes_read += len(block)
            if bytes_read > MAX_BYTES:
                raise SourceError("File exceeded fixed 64-MiB acquisition limit")
            output.write(block)
        output.flush()
        os.fsync(output.fileno())

def acquire(item: dict, cache: Path, *, opener=urllib.request.urlopen) -> dict:
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / item["object_name"]
    receipt_path = cache / (item["source_id"] + ".receipt.json")
    if target.exists() or receipt_path.exists():
        raise SourceError("Existing target or receipt: refusing overwrite; use --verify")
    part = cache / (item["object_name"] + ".part")
    if part.exists():
        raise SourceError("Previous .part exists; inspect before proceeding")
    try:
        _download_file(item, part, opener=opener)
        validate_content(part, item["format"])
        digest = sha256_file(part)
        receipt = {
            "study_id":STUDY, "source_id":item["source_id"], "object_name":item["object_name"],
            "source_url":item["download_url"], "documentation_url":item["documentation_url"],
            "source_group":item["source_group"], "sha256":digest, "size_bytes":part.stat().st_size,
            "file_type_checked":True, "review_status":"not_independently_reviewed",
            "independent_authenticity_verified":False, "semantic_eligibility_verified":False,
        }
        with receipt_path.open('x', encoding='utf-8') as f:
            json.dump(receipt, f, sort_keys=True, indent=2)
            f.write('\n')
        part.rename(target)
        return receipt
    except BaseException:
        if part.exists():
            part.unlink()
        # If receipt was written but rename fails, clean it to keep source/receipt atomic enough.
        if receipt_path.exists() and not target.exists():
            receipt_path.unlink()
        raise
