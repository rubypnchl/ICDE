import copy
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RULE_SCHEMA = json.loads((ROOT / "data" / "rule.schema.json").read_text(encoding="utf-8"))
RULE_FILES = sorted((ROOT / "data" / "rules").glob("*.json"))


def test_candidate_rule_examples_validate_and_are_unverified():
    from jsonschema import Draft202012Validator, FormatChecker

    validator = Draft202012Validator(RULE_SCHEMA, format_checker=FormatChecker())
    assert len(RULE_FILES) == 4
    examples = [json.loads(path.read_text(encoding="utf-8")) for path in RULE_FILES]
    assert {rule["dataset_id"].split("-")[0] for rule in examples} == {
        "ai4i",
        "nhanes",
        "unsw",
        "sec",
    }
    for rule in examples:
        validator.validate(rule)
        assert rule["verification_status"] == "candidate"
        assert rule["provenance"]["metadata_file"].startswith("data/metadata/")


def test_rule_schema_rejects_executable_operators_and_verified_status():
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(RULE_SCHEMA)
    example = json.loads(RULE_FILES[0].read_text(encoding="utf-8"))
    unsafe = copy.deepcopy(example)
    unsafe["condition"]["op"] = "__import__('os').system"
    assert list(validator.iter_errors(unsafe))
    verified = copy.deepcopy(example)
    verified["verification_status"] = "verified"
    assert list(validator.iter_errors(verified))
