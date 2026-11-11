"""B13.8 source schema/aggregate inspection. Read-only, no rule discovery/gates.

Only exact pinned B13.7 receipt-verified files may be inspected. Clinical rows and
SEQN identifiers never leave process memory; no archive extraction is performed.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import zipfile

from src.b13_7_source_acquisition import (
    validate_registry as validate_b137_registry, verify_existing,
    sha256_file, assert_external_cache,
)

STUDY = "b13_8_read_only_source_schema_audit_v1"
PARENT_SHA = "dbf0da0baa39ca9d3e1722e8adc0e3b2f0c5d06047887ecddc062bc8bb62650d"
PINNED = {
    "B13S-HLT-01": ("TRIGLY_I.XPT", "dd5a24f7b3bff19f899db38b766445bc4217b6ec6d1bd1accf7065a037e8a59d", 154800, "nhanes_2015_2016_cycle"),
    "B13S-HLT-02": ("TCHOL_I.XPT", "e7f51cf7c002db01d023278922d89d72318c679967e72ff259ba532b2d72e54d", 193760, "nhanes_2015_2016_cycle"),
    "B13S-MAN-01": ("steel_plates_faults.zip", "cb8eb9859198b63f053e443513036b401746fa517ef58bd17c846c6741c93919", 100890, "uci_steel_plates_2010_release"),
}
EXPECTED_LABS = {
    "B13S-HLT-01": ("SEQN", "LBXTR", "LBDTRSI", "LBDLDL", "LBDLDLSI"),
    "B13S-HLT-02": ("SEQN", "LBXTC"),
}
FAULT_LABELS = ("Pastry", "Z_Scratch", "K_Scatch", "Stains", "Dirtiness", "Bumps", "Other_Faults")
MAX_MEMBER_BYTES = 2_000_000
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,79}$")

class AuditError(ValueError):
    """Source, schema, integrity or privacy invariant failed."""


def canonical_sha(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                                    allow_nan=False).encode("utf-8")).hexdigest()


def validate_plan(plan: dict, source_registry: dict) -> None:
    validate_b137_registry(source_registry)
    if canonical_sha(source_registry) != PARENT_SHA:
        raise AuditError("B13.7 source registry changed from frozen snapshot")
    if not isinstance(plan, dict) or plan.get("study_id") != STUDY:
        raise AuditError("Wrong B13.8 study identifier")
    if plan.get("parent_source_registry_study_id") != "b13_7_source_object_acquisition_v1":
        raise AuditError("Wrong parent source study")
    if plan.get("parent_source_registry_canonical_sha256") != PARENT_SHA:
        raise AuditError("Parent source registry hash mismatch")
    if plan.get("phase") != "exploratory_schema_feasibility_not_confirmatory":
        raise AuditError("Unexpected evaluation phase")
    if plan.get("source_reading_policy") != "read_only_local_verified_cache_in_memory":
        raise AuditError("Source reading policy changed")
    if plan.get("output_policy") != "aggregate_json_outside_git_repo_exclusive_write_no_rows_or_identifiers":
        raise AuditError("Unsafe output policy")
    if plan.get("methods") != ["xpt_schema_column_missingness_and_join_id_counts", "zip_membership_original_table_shape_and_label_counts"]:
        raise AuditError("Methods changed")
    if plan.get("external_documents_previously_seen") is not True:
        raise AuditError("Previous documentation exposure must be disclosed")
    for key in ("source_eligibility_confirmed", "reference_semantic_truth_confirmed", "prospective_rule_discovery_or_gate_allowed"):
        if plan.get(key) is not False:
            raise AuditError("Cannot mark source eligible, gold or run gate")
    if plan.get("allowed_claims") != ["aggregate_exploratory_schema_characterization_if_local_run_succeeds"]:
        raise AuditError("Allowed claims changed")
    if set(plan.get("disallowed_claims", [])) != {"confirmatory_untouched_cohort", "independently_verified_source_authenticity", "derivation_precision_gold", "natural_data_error", "rule_discovery_accuracy", "real_gate_evaluation", "independent_adjudication"}:
        raise AuditError("Disallowed claims changed")
    items = plan.get("objects")
    if not isinstance(items, list) or len(items) != 3:
        raise AuditError("Exactly three pinned local objects required")
    ids = [x.get("source_id") for x in items if isinstance(x, dict)]
    if set(ids) != set(PINNED) or len(set(ids)) != 3:
        raise AuditError("Source list missing or duplicated")
    for item in items:
        sid = item["source_id"]
        if tuple(item.get(k) for k in ("object_name", "sha256", "size_bytes", "source_group")) != PINNED[sid]:
            raise AuditError("Source size, fingerprint or group changed: " + sid)
        if sid in EXPECTED_LABS:
            if item.get("minimum_expected_columns") != list(EXPECTED_LABS[sid]):
                raise AuditError("Expected NHANES variables changed")
            if set(item) != {"source_id", "object_name", "sha256", "size_bytes", "source_group", "minimum_expected_columns"}:
                raise AuditError("Unexpected healthcare schema fields")
        else:
            if item.get("expected_archive_members") != ["Faults.NNA", "Faults27x7_var"]:
                raise AuditError("Archive membership changed")
            if set(item) != {"source_id", "object_name", "sha256", "size_bytes", "source_group", "expected_archive_members"}:
                raise AuditError("Unexpected archive schema fields")


def _is_null(value: object) -> bool:
    if value is None:
        return True
    try:
        return bool(math.isnan(float(value)))
    except (ValueError, TypeError, OverflowError):
        return False


def _ids(series: object) -> tuple[set[int], int, int]:
    """Collect SEQNs in process RAM; never return/serialize the IDs externally."""
    result: set[int] = set()
    absent = 0
    duplicates = 0
    for value in series:
        if _is_null(value):
            absent += 1
            continue
        try:
            x = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise AuditError("Non-numeric SEQN") from exc
        if not math.isfinite(x) or x < 0 or not x.is_integer():
            raise AuditError("Invalid NHANES SEQN")
        v = int(x)
        if v in result:
            duplicates += 1
        result.add(v)
    return result, absent, duplicates


def summarize_xpt_frame(frame: object, sid: str) -> tuple[dict, set[int]]:
    """Frame is a pandas DataFrame from read_xport; no raw rows in summary."""
    if sid not in EXPECTED_LABS:
        raise AuditError("Unexpected healthcare source")
    columns = list(frame.columns)
    if any(not isinstance(c, str) or not IDENTIFIER.fullmatch(c) for c in columns) or len(columns) != len(set(columns)):
        raise AuditError("Unsafe, duplicate or malformed XPT variable names")
    if any(c not in columns for c in EXPECTED_LABS[sid]):
        raise AuditError("Missing documented XPT variable")
    n = len(frame)
    if n == 0:
        raise AuditError("XPT file contains no rows")
    # Only completeness and published column names/types, never individual values.
    summaries = []
    for col in columns:
        ser = frame[col]
        missing = int(ser.isna().sum())
        if not 0 <= missing <= n:
            raise AuditError("Invalid missingness count")
        summaries.append({"name": col, "dtype": str(ser.dtype), "present": n - missing, "missing": missing})
    seqn_set, null_seqn, duplicate_seqn = _ids(frame["SEQN"])
    return {"source_id": sid, "row_count": n, "column_count": len(columns),
            "columns": summaries, "seqn_missing": null_seqn,
            "seqn_duplicate_nonmissing": duplicate_seqn,
            "seqn_unique_nonmissing": len(seqn_set),
            "source_claim": "observed_schema_not_semantic_validation"}, seqn_set


def read_xpt_aggregates(path: Path, sid: str) -> tuple[dict, set[int]]:
    try:
        import pyreadstat
    except ImportError as exc:
        raise AuditError("pyreadstat is required; install existing repo requirements.txt in your $py environment") from exc
    # Release is small (<200 KB), and B13.7 receipts are reverified first.
    frame, metadata = pyreadstat.read_xport(str(path))
    out, seqns = summarize_xpt_frame(frame, sid)
    actual_cols = list(getattr(metadata, "column_names", []))
    if actual_cols and actual_cols != [x["name"] for x in out["columns"]]:
        raise AuditError("XPT metadata and dataframe column order differ")
    return out, seqns


def _safe_zip_info(info: zipfile.ZipInfo) -> str:
    name = info.filename
    parts = PurePosixPath(name).parts
    if (not name or name.startswith("/") or "\\" in name or ".." in parts or ":" in name
            or info.flag_bits & 1 or info.file_size > MAX_MEMBER_BYTES):
        raise AuditError("Unsafe/encrypted or oversized archive member")
    return name


def audit_faults_zip(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:
            raise AuditError("Archive CRC mismatch")
        infos = [i for i in z.infolist() if not i.is_dir()]
        names = [_safe_zip_info(i) for i in infos]
        if len(names) != 2 or len(set(names)) != 2 or {PurePosixPath(n).name for n in names} != {"Faults.NNA", "Faults27x7_var"}:
            raise AuditError("Unexpected UCI Steel Plates ZIP members")
        indexed = {PurePosixPath(i.filename).name: i for i in infos}
        var_data = z.read(indexed["Faults27x7_var"])
        variables = var_data.decode("utf-8-sig", errors="strict").split()
        if len(variables) != 34 or any(not IDENTIFIER.fullmatch(x) for x in variables) or len(set(variables)) != 34:
            raise AuditError("Unexpected 34-variable schema in UCI variable file")
        if set(variables[27:]) != set(FAULT_LABELS):
            raise AuditError("Seven UCI fault labels not mapped to last seven columns")
        nrows = 0
        label_counts = Counter()
        label_sum_hist = Counter()
        with z.open(indexed["Faults.NNA"]) as raw:
            for line in io.TextIOWrapper(raw, encoding="ascii", errors="strict", newline=""):
                if not line.strip():
                    continue
                fields = line.split()
                if len(fields) != 34:
                    raise AuditError("UCI row has unexpected number of columns")
                try:
                    numbers = [Decimal(v) for v in fields]
                except InvalidOperation as exc:
                    raise AuditError("Nonnumeric UCI field") from exc
                if not all(v.is_finite() for v in numbers):
                    raise AuditError("Nonfinite UCI field")
                labels = numbers[27:]
                if any(v not in (Decimal(0), Decimal(1)) for v in labels):
                    raise AuditError("UCI fault indicator not binary")
                for j, val in enumerate(labels):
                    if val == 1:
                        label_counts[variables[27 + j]] += 1
                label_sum_hist[str(sum(labels))] += 1
                nrows += 1
                if nrows > 20_000:
                    raise AuditError("Unexpectedly large UCI table")
        if nrows == 0:
            raise AuditError("Empty UCI table")
        member_hashes = []
        for name in sorted(names):
            data = z.read(name)
            if len(data) > MAX_MEMBER_BYTES:
                raise AuditError("ZIP member size limit exceeded")
            member_hashes.append({"member_name": PurePosixPath(name).name,
                                  "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return {"source_id": "B13S-MAN-01", "row_count": nrows, "feature_column_count": 27,
            "label_column_count": 7, "total_column_count": 34,
            "variable_names": variables, "fault_label_positive_counts": {label: label_counts[label] for label in FAULT_LABELS},
            "label_positive_count_per_row": {k: label_sum_hist[k] for k in ("0", "1", "2", "3", "4", "5", "6", "7")},
            "members": member_hashes, "source_claim": "observed_binary_fault_columns_not_semantically_adjudicated"}


def audit_all(cache: Path, repo_root: Path, plan: dict, source_registry: dict) -> dict:
    validate_plan(plan, source_registry)
    cache = assert_external_cache(cache, repo_root)
    items = {x["source_id"]: x for x in validate_b137_registry(source_registry)}
    src = {x["source_id"]: x for x in plan["objects"]}
    receipts = []
    for sid, fixed in PINNED.items():
        meta = verify_existing(items[sid], cache)
        if (meta["object_name"], meta["sha256"], meta["size_bytes"], meta["source_group"]) != fixed:
            raise AuditError("Local receipt differs from source fingerprints previously observed: " + sid)
        receipts.append({"source_id": sid, "source_group": meta["source_group"],
                         "sha256": meta["sha256"], "size_bytes": meta["size_bytes"]})
    h1, ids1 = read_xpt_aggregates(cache / src["B13S-HLT-01"]["object_name"], "B13S-HLT-01")
    h2, ids2 = read_xpt_aggregates(cache / src["B13S-HLT-02"]["object_name"], "B13S-HLT-02")
    man = audit_faults_zip(cache / src["B13S-MAN-01"]["object_name"])
    # Hash again to reject in-place source changes during inspection.
    for sid, fixed in PINNED.items():
        path = cache / fixed[0]
        if sha256_file(path) != fixed[1]:
            raise AuditError("Source changed while inspecting: " + sid)
    return {"study_id": STUDY, "classification": "exploratory_source_schema_characterization_only",
            "source_registry_canonical_sha256": PARENT_SHA,
            "b13_8_plan_canonical_sha256": canonical_sha(plan),
            "source_file_receipts": receipts,
            "healthcare": [h1, h2],
            "nhanes_cycle_join_inventory": {
                "shared_survey_cycle": "2015-2016",
                "TRIGLY_unique_SEQN_count": len(ids1),
                "TCHOL_unique_SEQN_count": len(ids2),
                "intersection_SEQN_count": len(ids1 & ids2),
                "TRIGLY_only_count": len(ids1 - ids2),
                "TCHOL_only_count": len(ids2 - ids1),
                "raw_identifiers_emitted": False,
                "cross_file_join_performed": False,
            },
            "manufacturing": man,
            "real_candidates_generated": 0, "real_gate_executions": 0,
            "source_semantic_eligibility_verified": False, "independently_adjudicated_gold_rules": 0,
            "independent_source_authenticity_verified": False,
            "limitations": [
                "Exploratory previously documented source groups, not untouched confirmatory discovery",
                "Local B13.7 receipt checks are not third-party signed source authenticity",
                "Survey participants share the same NHANES cycle; counts are not independent rule replicates",
                "UCI fault one-hot frequency is an observed representation, not adjudicated defect truth",
                "No clinical derived-variable equality, precision or threshold was scored",
                "Raw rows, SEQN identifiers, proposal hypotheses, and private reviewer texts not emitted",
            ]}


def exclusive_save(output: Path, payload: dict, cache: Path, repo_root: Path) -> None:
    cache = assert_external_cache(cache, repo_root)
    output = output.expanduser().resolve()
    if output.parent != cache:
        raise AuditError("Aggregate output must stay immediately inside external cache")
    if output.name != "B13_8_source_schema_audit_v1.json":
        raise AuditError("Unapproved report filename")
    with output.open("x", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        f.write("\n")
