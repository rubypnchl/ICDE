import copy
from decimal import Decimal

from src.evaluate_detection import (
    _make_benchmark,
    _metrics,
    _record_prediction,
)


def _candidate(evidence="documented"):
    return {
        "rule": {
            "id": "balance",
            "assertion": {
                "op": "sum_eq",
                "result_column": "Assets [USD]",
                "term_columns": ["Liabilities [USD]", "Equity [USD]"],
                "tolerance": 0,
            },
        },
        "parameters": {
            "kind": "sum_eq",
            "result": "Assets",
            "terms": ["Liabilities", "Equity"],
        },
        "documented_evidence": {"status": evidence},
    }


def _record(assets=10, *, mismatch=False):
    base = {"entity": "1", "reporting_date": "2025-12-31",
            "accounting_scope": ("a", "10-K"), "currency": "USD"}
    contexts = {name: copy.deepcopy(base) for name in ("Assets", "Liabilities", "Equity")}
    if mismatch:
        contexts["Equity"]["reporting_date"] = "2024-12-31"
    return {
        "Assets": Decimal(assets),
        "Liabilities": Decimal(4),
        "Equity": Decimal(6),
        "_field_context": contexts,
    }


def test_methods_share_records_and_distinguish_numeric_from_context_errors():
    candidates = [_candidate()]
    records = [_record(), _record(11), _record(mismatch=True)]
    labels = [False, True, True]

    global_metrics = _metrics(
        [_record_prediction(candidates, row, "global") for row in records], labels,
    )
    context_metrics = _metrics(
        [_record_prediction(candidates, row, "context_aware") for row in records], labels,
    )
    gated_metrics = _metrics(
        [_record_prediction(candidates, row, "evidence_gated") for row in records], labels,
    )
    assert global_metrics == {
        "tp": 1, "fp": 0, "fn": 1, "tn": 1, "precision": 1.0,
        "recall": 0.5, "f1": 2 / 3, "fpr": 0.0, "coverage": 1.0, "abstentions": 0,
    }
    assert context_metrics["tp"] == gated_metrics["tp"] == 2
    assert context_metrics["fn"] == gated_metrics["fn"] == 0
    assert records[0]["Assets"] == 10


def test_evidence_gate_abstains_on_undocumented_candidates():
    candidates = [_candidate("not_found")]
    predictions = [
        _record_prediction(candidates, _record(11), method)
        for method in ("global", "context_aware", "evidence_gated")
    ]
    assert predictions == [True, True, None]
    metrics = _metrics([predictions[-1]], [True])
    assert metrics["abstentions"] == 1
    assert metrics["coverage"] == 0
    assert metrics["tp"] == 0
    assert metrics["fn"] == 1
    assert metrics["recall"] == 0


def test_injection_benchmark_mutates_only_record_copies():
    original_rows = [{
        "end": "2025-12-31",
        "accn": "a",
        "form": "10-K",
        "unit": "USD",
        "Assets": Decimal(10),
        "Liabilities": Decimal(4),
        "Equity": Decimal(6),
    }]
    before = copy.deepcopy(original_rows)
    records, labels = _make_benchmark(original_rows, [_candidate()], "1")

    assert original_rows == before
    assert labels == [False, True, True]
    assert records[1]["Assets"] != records[0]["Assets"]
    assert records[2]["_field_context"]["Liabilities"]["reporting_date"] != "2025-12-31"
    assert records[2]["_field_context"]["Equity"]["reporting_date"] == "2025-12-31"
