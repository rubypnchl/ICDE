from src.novelty_pilot import _decision, _rule_valid


def _candidate(evidence: bool):
    return {
        "rule": {"id": "test-rule"},
        "scope": "global",
        "evidence_supported": evidence,
        "evaluator": "nonnegative",
        "parameters": {"column": "value"},
        "discovery_pass_rate": 1.0,
    }


def test_candidate_decisions_distinguish_accept_reject_and_abstain():
    candidate = _candidate(True)
    assert _rule_valid(candidate, {"value": 2}) is True
    assert _rule_valid(candidate, {"value": -1}) is False
    assert _decision(True, selected=True, evidence_supported=True, strategy="evidence_gated") == "accept"
    assert _decision(False, selected=True, evidence_supported=True, strategy="evidence_gated") == "reject"
    assert _decision(False, selected=True, evidence_supported=False, strategy="evidence_gated") == "abstain"
    assert _decision(True, selected=False, evidence_supported=True, strategy="global") == "abstain"


def test_evidence_gate_abstains_on_unsupported_candidate():
    candidate = _candidate(False)
    assert _rule_valid(candidate, {"value": -1}) is False
    assert candidate["evidence_supported"] is False
