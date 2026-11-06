from src.evaluate_semantic_reliability import _evaluate_synthetic


def test_synthetic_oracles_are_separate_and_cover_four_semantic_cases():
    result = _evaluate_synthetic()
    assert result["case_count"] == 4
    assert result["oracle_labels"]["used_for_discovery_or_prediction"] is False
    methods = result["methods"]
    assert methods["global"]["rule_level"]["scenario_decisions"] == {
        "documented_rule": True,
        "spurious_statistical_pattern": True,
        "incompatible_context": True,
        "documented_data_conflict": True,
    }
    assert methods["context_aware"]["rule_level"]["scenario_decisions"]["incompatible_context"] is False
    assert methods["evidence_gated"]["rule_level"]["scenario_decisions"]["spurious_statistical_pattern"] is None
    assert methods["evidence_gated"]["rule_level"]["scenario_decisions"]["incompatible_context"] is None


def test_rule_and_record_metrics_are_separate_and_selective_coverage_is_reported():
    methods = _evaluate_synthetic()["methods"]
    for metrics in methods.values():
        assert "selective_coverage" in metrics["rule_level"]
        assert "precision" in metrics["rule_level"]
        assert "recall" in metrics["rule_level"]
        assert "abstentions" in metrics["rule_level"]
        assert "tp" in metrics["record_level_detection"]
        assert "f1" in metrics["record_level_detection"]
    assert methods["global"]["rule_level"]["fp"] > 0
    assert methods["evidence_gated"]["rule_level"]["abstentions"] >= 2
    assert methods["context_aware"]["record_level_detection"]["tp"] > methods["global"]["record_level_detection"]["tp"]
