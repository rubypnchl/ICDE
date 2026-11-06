import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.rule_discovery import (
    _decision,
    _evaluate_candidates,
    _match_sec_evidence,
    discover_numeric_ranges,
    discover_sec_identities,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "data" / "rule.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)
UCI_URL = "https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset"
SEC_URL = "https://www.sec.gov/edgar/sec-api-documentation"


def _metadata(tmp_path: Path, dataset_id: str, url: str) -> tuple[dict, Path]:
    path = tmp_path / "metadata.json"
    path.write_text("{}", encoding="utf-8")
    return {
        "dataset": {"id": dataset_id},
        "columns": [],
        "provenance": {"sources": [{"file": "fixture", "url": url, "sha256": "0" * 64}]},
    }, path


def test_numeric_ranges_generate_minimal_context_and_validate(tmp_path):
    metadata, path = _metadata(tmp_path, "ai4i-fixture", UCI_URL)
    metadata["columns"] = [
        {"name": "group", "type": {"value": "string", "status": "documented"}},
        {"name": "temperature", "type": {"value": "number", "status": "documented"}},
    ]
    rows = [
        {"group": group, "temperature": value}
        for group, values in (("A", [10, 11, 12]), ("B", [100, 101, 102]))
        for value in values
    ]

    candidates = discover_numeric_ranges(
        rows, metadata, path, min_support=2, complexity_penalty=0.1,
    )
    assert len(candidates) == 3
    assert sum(candidate["rule"]["condition"] is None for candidate in candidates) == 1
    assert all(
        len(candidate["rule"]["condition"].get("all", [])) <= 1
        if candidate["rule"]["condition"] else True
        for candidate in candidates
    )
    for candidate in candidates:
        VALIDATOR.validate(candidate["rule"])


def test_sec_identity_is_unit_aligned_and_uses_safe_sum_assertion(tmp_path):
    metadata, path = _metadata(tmp_path, "sec-fixture", SEC_URL)
    rows = [
        {"end": f"202{year}-12-31", "unit": "USD", "Assets": 5, "Liabilities": 2, "Equity": 3}
        for year in range(4)
    ]

    candidates = discover_sec_identities(
        rows, metadata, path, min_support=3, min_identity_rate=1.0,
    )
    identity = next(
        candidate for candidate in candidates
        if candidate["rule"]["assertion"]["result_column"] == "Assets [USD]"
    )
    assert identity["rule"]["assertion"] == {
        "op": "sum_eq",
        "result_column": "Assets [USD]",
        "term_columns": ["Equity [USD]", "Liabilities [USD]"],
        "tolerance": 0,
    }
    VALIDATOR.validate(identity["rule"])
    unsafe = copy.deepcopy(identity["rule"])
    unsafe["assertion"]["op"] = "__import__('os').system"
    assert list(VALIDATOR.iter_errors(unsafe))


def test_documented_violations_become_conflict_not_rejection():
    assert _decision(True, 0) == "documented_support"
    assert _decision(True, 2) == "documented_conflict"
    assert _decision(False, 0) == "abstain"
    assert _decision(True, None) == "abstain"


def test_sec_evidence_matches_terms_order_and_checks_context_and_citation():
    rule = {
        "assertion": {
            "op": "sum_eq",
            "result_column": "Assets [USD]",
            "term_columns": ["StockholdersEquity [USD]", "Liabilities [USD]"],
            "tolerance": 0,
        },
        "evidence": [],
    }
    registry = {
        "entries": [{
            "id": "SEC-BALANCE-001",
            "authority": "SEC",
            "source_url": SEC_URL,
            "evidence_status": "documented_reference",
            "assertion": {
                "op": "sum_eq",
                "result_column": "Assets [USD]",
                "term_columns": ["Liabilities [USD]", "StockholdersEquity [USD]"],
                "tolerance": 0,
            },
            "requirements": [
                "same entity",
                "same reporting date",
                "same accounting scope",
                "same currency",
            ],
        }]
    }
    context = {
        "same-entity": True,
        "same-reporting-date": True,
        "same-accounting-scope": True,
        "same-currency": True,
    }

    match = _match_sec_evidence(rule, registry, context)
    assert match["status"] == "documented"
    assert match["citation"]["source_url"] == SEC_URL
    assert rule["evidence"][0]["source_url"] == SEC_URL

    candidate = {
        "rule": rule,
        "parameters": {
            "kind": "sum_eq",
            "result": "Assets",
            "terms": ["StockholdersEquity", "Liabilities"],
        },
        "documented_evidence": match,
    }
    supported = _evaluate_candidates(
        [candidate],
        [{"Assets": 10, "Liabilities": 4, "StockholdersEquity": 6}],
    )[0]
    assert supported["heldout"]["decision"] == "documented_support"
    assert supported["heldout"]["violations"] == 0

    conflict_candidate = {
        "rule": rule,
        "parameters": {
            "kind": "sum_eq",
            "result": "Assets",
            "terms": ["StockholdersEquity", "Liabilities"],
        },
        "documented_evidence": match,
    }
    conflict = _evaluate_candidates(
        [conflict_candidate],
        [{"Assets": 11, "Liabilities": 4, "StockholdersEquity": 6}],
    )[0]
    assert conflict["heldout"]["decision"] == "documented_conflict"
    assert conflict["heldout"]["violations"] == 1

    incompatible = _match_sec_evidence(
        rule, registry, {**context, "same-accounting-scope": False},
    )
    assert incompatible["status"] == "context_incompatible"
    incompatible_candidate = {
        "rule": rule,
        "parameters": {
            "kind": "sum_eq",
            "result": "Assets",
            "terms": ["StockholdersEquity", "Liabilities"],
        },
        "documented_evidence": incompatible,
    }
    result = _evaluate_candidates(
        [incompatible_candidate],
        [{"Assets": 10, "Liabilities": 4, "StockholdersEquity": 6}],
    )[0]
    assert result["heldout"]["decision"] == "abstain"


def test_undocumented_empirical_candidate_abstains_on_heldout_violations():
    candidate = {
        "parameters": {
            "kind": "range",
            "column": "x",
            "lower": 0,
            "upper": 2,
            "condition": None,
        },
        "documented_evidence": {"status": "not_found"},
        "discovery": {},
        "rule": {},
    }
    evaluated = _evaluate_candidates([candidate], [{"x": 4}])[0]
    assert evaluated["heldout"]["violations"] == 1
    assert evaluated["heldout"]["decision"] == "abstain"
    assert evaluated["baselines"]["context_only"]["descriptive_pass_rate"] is None
