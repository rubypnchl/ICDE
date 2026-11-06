from src.sec_constraint_resolution import (
    _evaluate_expression,
    _expression_candidates,
    _select_semantic_evidence,
    _select_statistical,
)


def _payload():
    return {
        "facts": {
            "us-gaap": {
                "Assets": {"label": "Assets", "units": {"USD": []}},
                "Liabilities": {"label": "Liabilities", "units": {"USD": []}},
                "StockholdersEquity": {
                    "label": "Stockholders' Equity Attributable to Parent",
                    "units": {"USD": []},
                },
                "MinorityInterest": {
                    "label": "Noncontrolling Interest",
                    "units": {"USD": []},
                },
            }
        }
    }


def test_context_resolution_ranks_supported_optional_terms_on_discovery_only():
    rows = [
        {
            "unit": "USD",
            "Assets": 120,
            "Liabilities": 80,
            "StockholdersEquity": 30,
            "MinorityInterest": 10,
        }
        for _ in range(3)
    ]
    candidates = _expression_candidates(_payload(), rows, {"entries": []})
    assert candidates[0]["expression"]["equity_terms"] == [
        "StockholdersEquity", "MinorityInterest",
    ]
    assert candidates[0]["discovery"]["match_rate"] == 1
    assert candidates[0]["classification"] == "statistically_discovered"


def test_missing_or_wrong_unit_facts_abstain_not_pass():
    expression = {
        "assets": "Assets",
        "liabilities": "Liabilities",
        "equity_terms": ["StockholdersEquity", "MinorityInterest"],
        "unit": "USD",
    }
    rows = [
        {"unit": "USD", "Assets": 120, "Liabilities": 80, "StockholdersEquity": 30},
        {"unit": "USD", "Assets": 120, "Liabilities": 80, "StockholdersEquity": 30, "MinorityInterest": 10},
        {"unit": "EUR", "Assets": 120, "Liabilities": 80, "StockholdersEquity": 30, "MinorityInterest": 10},
    ]

    metrics = _evaluate_expression(expression, rows)
    assert metrics["eligible_contexts"] == 2
    assert metrics["evaluated_contexts"] == 1
    assert metrics["abstentions"] == 1
    assert metrics["violations"] == 0
    assert metrics["coverage"] == 0.5


def test_documented_identity_false_alarm_requires_independent_identity_match():
    expression = {
        "assets": "Assets",
        "liabilities": "Liabilities",
        "equity_terms": ["StockholdersEquity", "MinorityInterest"],
        "unit": "USD",
    }
    documented = {
        "assets": "Assets",
        "liabilities": "Liabilities",
        "equity_terms": ["StockholdersEquity"],
        "unit": "USD",
    }
    rows = [{
        "unit": "USD",
        "Assets": 110,
        "Liabilities": 80,
        "StockholdersEquity": 30,
        "MinorityInterest": 10,
    }]

    metrics = _evaluate_expression(
        expression, rows, documented_expression=documented,
    )
    assert metrics["violations"] == 1
    assert metrics["documented_identity_contexts"] == 1
    assert metrics["false_alarms_against_documented_identity"] == 1


def test_ablation_selectors_use_discovery_metrics_and_semantic_evidence_separately():
    statistical = {
        "expression": {"assets": "A", "liabilities": "L", "equity_terms": ["E1"], "unit": "USD"},
        "discovery": {"match_rate": 1.0, "contexts": 4},
        "semantic_score": 1,
        "complexity": 2,
        "evidence": None,
        "classification": "statistically_discovered",
    }
    documented = {
        "expression": {"assets": "A", "liabilities": "L", "equity_terms": ["E2"], "unit": "USD"},
        "discovery": {"match_rate": 0.75, "contexts": 4},
        "semantic_score": 2,
        "complexity": 2,
        "evidence": {"id": "SEC-BALANCE-001"},
        "classification": "documented",
    }

    candidates = [documented, statistical]
    assert _select_statistical(candidates) is statistical
    concepts = {
        "A": {"label": "Assets", "description": "All assets recognized."},
        "L": {"label": "Liabilities", "description": "All liabilities recognized."},
        "E1": {"label": "Stockholders' Equity Attributable to Parent",
               "description": "Equity attributable to the parent."},
        "E2": {"label": "Stockholders' Equity Including Noncontrolling Interest",
               "description": "Equity attributable to both the parent and noncontrolling interests."},
    }
    discovery = [{"A": 10, "L": 4, "E1": 6, "E2": 10, "unit": "USD"}]
    selected = _select_semantic_evidence(candidates, concepts, discovery, 123)
    assert selected is not None
    assert selected["expression"] == documented["expression"]

    heldout = [{"unit": "USD", "A": 10, "L": 4, "E1": 6, "E2": 5}]
    stat_result = _evaluate_expression(statistical["expression"], heldout)
    evidence_result = _evaluate_expression(documented["expression"], heldout)
    assert stat_result["eligible_contexts"] == evidence_result["eligible_contexts"] == len(heldout)
    assert stat_result["violations"] == 0
    assert evidence_result["violations"] == 1


def test_exxon_style_parent_equity_requires_component_level_nci():
    concepts = {
        "Assets": {"label": "Assets", "description": "Sum of all assets recognized."},
        "Liabilities": {"label": "Liabilities", "description": "Sum of all liabilities recognized."},
        "StockholdersEquity": {
            "label": "Stockholders' Equity Attributable to Parent",
            "description": "Equity attributable to the parent; excludes noncontrolling interests.",
        },
        "MinorityInterest": {
            "label": "Stockholders' Equity Attributable to Noncontrolling Interest",
            "description": "Equity attributable to noncontrolling interest, not attributable to the parent.",
        },
    }
    incomplete = {
        "expression": {
            "assets": "Assets", "liabilities": "Liabilities",
            "equity_terms": ["StockholdersEquity"], "unit": "USD",
        },
        "complexity": 2, "evidence": {"id": "generic-balance-identity"},
        "discovery": {"match_rate": 1.0, "contexts": 3},
    }
    complete = {
        "expression": {
            "assets": "Assets", "liabilities": "Liabilities",
            "equity_terms": ["StockholdersEquity", "MinorityInterest"], "unit": "USD",
        },
        "complexity": 3, "evidence": None,
        "discovery": {"match_rate": 0.8, "contexts": 3},
    }
    discovery = [
        {"unit": "USD", "Assets": 120, "Liabilities": 80, "StockholdersEquity": 30, "MinorityInterest": 10},
        {"unit": "USD", "Assets": 120, "Liabilities": 80, "StockholdersEquity": 30, "MinorityInterest": 10},
    ]

    selected = _select_semantic_evidence([incomplete, complete], concepts, discovery, 34088)
    assert selected is not None
    assert selected["expression"] == complete["expression"]
    assert selected["semantic_evidence"]["components"][-1]["role"] == "nci_equity"
    assert incomplete not in [selected]


def test_tesla_style_inclusive_equity_requires_disclosed_temporary_equity():
    concepts = {
        "Assets": {"label": "Assets", "description": "Sum of all assets recognized."},
        "Liabilities": {"label": "Liabilities", "description": "Sum of all liabilities recognized."},
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": {
            "label": "Stockholders' Equity Including Noncontrolling Interest",
            "description": "Attributable to both parent and noncontrolling interests; excludes temporary equity.",
        },
        "TemporaryEquityCarryingAmountIncludingPortionAttributableToNoncontrollingInterests": {
            "label": "Temporary Equity, Including Noncontrolling Interests",
            "description": "Temporary equity attributable to parent and noncontrolling interests, not included in permanent equity.",
        },
    }
    incomplete = {
        "expression": {
            "assets": "Assets", "liabilities": "Liabilities",
            "equity_terms": ["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
            "unit": "USD",
        },
        "complexity": 2, "evidence": {"id": "generic-balance-identity"},
        "discovery": {"match_rate": 1.0, "contexts": 3},
    }
    complete = {
        "expression": {
            "assets": "Assets", "liabilities": "Liabilities",
            "equity_terms": [
                "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
                "TemporaryEquityCarryingAmountIncludingPortionAttributableToNoncontrollingInterests",
            ],
            "unit": "USD",
        },
        "complexity": 3, "evidence": None,
        "discovery": {"match_rate": 0.8, "contexts": 3},
    }
    discovery = [
        {
            "unit": "USD", "Assets": 120, "Liabilities": 80,
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": 35,
            "TemporaryEquityCarryingAmountIncludingPortionAttributableToNoncontrollingInterests": 5,
        }
        for _ in range(2)
    ]

    selected = _select_semantic_evidence([incomplete, complete], concepts, discovery, 1318605)
    assert selected is not None
    assert selected["expression"] == complete["expression"]
    assert selected["semantic_evidence"]["components"][-1]["role"] == "temporary_equity"
    assert _select_semantic_evidence([incomplete], concepts, discovery, 1318605) is None
