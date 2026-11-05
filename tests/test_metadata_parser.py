import copy
import hashlib
import json
from pathlib import Path

import pytest

from src.metadata_parser import (
    _ai4i_documentation,
    _create_csv_sample,
    _infer_type,
    _nhanes_codebook,
    _empty_column,
    _field,
    _inferred_type_field,
    _read_csv,
    build_metadata,
    parse_cic_ids2017,
    parse_nhanes_xpt,
    parse_sec_xbrl,
    validate_metadata,
)


@pytest.fixture(scope="session")
def available_metadata():
    return build_metadata(Path(__file__).resolve().parents[1], sample_size=1000)


def test_type_inference_does_not_confuse_integer_and_number():
    assert _infer_type(["1", "2", "3"]) == "integer"
    assert _infer_type(["1.5", "2"]) == "number"
    assert _infer_type(["one", "2"]) == "string"
    assert _infer_type(["", "NA"]) == "unknown"


def test_csv_rejects_empty_headers_and_nonpositive_samples(tmp_path: Path):
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="no header"):
        _read_csv(path, 10)
    with pytest.raises(ValueError, match="sample_size"):
        _read_csv(path, 0)


def test_csv_reservoir_sample_is_reproducible_and_tracks_class_counts(tmp_path: Path):
    source = tmp_path / "source.csv"
    source.write_text(
        "flow,label\n1,BENIGN\n2,ATTACK\n3,BENIGN\n4,ATTACK\n",
        encoding="utf-8",
    )
    source_url = "https://example.test/source.csv"
    first = _create_csv_sample(
        [(source, source_url)],
        tmp_path / "samples" / "first.csv",
        root=tmp_path,
        sample_size=3,
        seed=42,
    )
    second = _create_csv_sample(
        [(source, source_url)],
        tmp_path / "samples" / "second.csv",
        root=tmp_path,
        sample_size=3,
        seed=42,
    )
    assert first["sample_sha256"] == second["sample_sha256"]
    assert first["records_available"] == 4
    assert first["sample_class_distribution"] == {"label": {"ATTACK": 2, "BENIGN": 1}}
    with pytest.raises(ValueError, match="exceeds"):
        _create_csv_sample(
            [(source, source_url)],
            tmp_path / "samples" / "too-large.csv",
            root=tmp_path,
            sample_size=5,
            seed=42,
        )


def test_common_schema_field_tracks_origin_and_unknowns():
    assert _field("K", "documented", "https://example.test/data-dictionary") == {
        "value": "K",
        "status": "documented",
        "source": "https://example.test/data-dictionary",
    }
    assert _empty_column("unknown_field", "https://example.test/data")["description"] == {
        "value": None,
        "status": "unknown",
        "source": None,
    }
    assert _inferred_type_field("unknown", "https://example.test/data") == _field()


def test_ai4i_documentation_reads_provided_table(tmp_path: Path):
    page = tmp_path / "uci.html"
    page.write_text(
        "<table><tr><th>Variable Name</th><th>Type</th><th>Description</th>"
        "<th>Units</th><th>Missing Values</th></tr>"
        "<tr><td>Speed</td><td>Integer</td><td>Rotation rate</td>"
        "<td>rpm</td><td>no</td></tr></table>",
        encoding="utf-8",
    )
    result = _ai4i_documentation(page, "https://example.test/docs")
    assert result["speed"] == {
        "type": "Integer",
        "description": "Rotation rate",
        "unit": "rpm",
        "missing": "no",
        "source": "https://example.test/docs",
    }


def test_sec_parser_preserves_documented_and_inferred_fields(tmp_path: Path):
    path = tmp_path / "sec.json"
    path.write_text(
        json.dumps(
            {
                "cik": 1,
                "entityName": "Example Corp",
                "taxonomy": "us-gaap",
                "tag": "Assets",
                "label": "Assets",
                "description": "Reported assets.",
                "units": {"USD": [{"end": "2024-12-31", "val": 100, "form": "10-K"}]},
            }
        ),
        encoding="utf-8",
    )
    result = parse_sec_xbrl(path, root=tmp_path)
    assert result["dataset"]["description"]["status"] == "documented"
    value = next(column for column in result["columns"] if column["name"] == "value")
    assert value["description"]["value"] == "Reported assets."
    assert value["type"]["status"] == "inferred"
    assert value["unit"]["value"] == "USD"
    assert all(column["allowed_values"]["value"] is None for column in result["columns"])


def test_sec_empty_or_missing_metadata_stays_unknown(tmp_path: Path):
    path = tmp_path / "sec.json"
    path.write_text(json.dumps({"units": {}}), encoding="utf-8")
    result = parse_sec_xbrl(path, root=tmp_path)
    value = result["columns"][0]
    assert value["description"]["status"] == "unknown"
    assert value["unit"]["status"] == "unknown"
    assert value["type"]["status"] == "unknown"
    assert value["type"]["value"] is None
    assert value["missing_values"]["value"]["sample_size"] == 0

    path.write_text(json.dumps({"units": {"USD": {}}}), encoding="utf-8")
    with pytest.raises(ValueError, match="unit groups"):
        parse_sec_xbrl(path, root=tmp_path)


def test_nhanes_codebook_extracts_official_descriptions_and_codes(tmp_path: Path):
    codebook = tmp_path / "DEMO_J.htm"
    codebook.write_text(
        '<h2 id="Component_Description">Component Description</h2>'
        "<p>The demographics file documents the survey component.</p>"
        '<h3 class="vartitle" id="RIAGENDR">RIAGENDR - Gender</h3>'
        "<dl><dt>English Text:</dt><dd>Gender of the participant.</dd></dl>"
        '<table class="values"><thead><tr><th>Code or Value</th>'
        "<th>Value Description</th><th>Count</th></tr></thead><tbody>"
        "<tr><td>1</td><td>Male</td><td>5000</td></tr>"
        "<tr><td>2</td><td>Female</td><td>5000</td></tr>"
        "<tr><td>.</td><td>Missing</td><td>0</td></tr>"
        "</tbody></table>",
        encoding="utf-8",
    )
    variables, description = _nhanes_codebook(codebook, "https://example.test/DEMO_J.htm")
    assert description == "The demographics file documents the survey component."
    assert variables["RIAGENDR"]["description"] == "Gender of the participant."
    assert variables["RIAGENDR"]["allowed_values"] == [
        {"code": "1", "description": "Male"},
        {"code": "2", "description": "Female"},
    ]


def test_nhanes_rejects_nonpositive_sample_before_reading(tmp_path: Path):
    with pytest.raises(ValueError, match="sample_size"):
        parse_nhanes_xpt(tmp_path / "missing.XPT", root=tmp_path, sample_size=0)


def test_cic_documentation_only_has_no_invented_columns(tmp_path: Path):
    docs = tmp_path / "cic.html"
    docs.write_text(
        "<p>CICIDS2017 includes labelled network flows distributed as CSV files.</p>",
        encoding="utf-8",
    )
    result = parse_cic_ids2017(docs, root=tmp_path)
    assert result["dataset"]["description"]["status"] == "documented"
    assert result["columns"] == []
    assert result["dataset"]["availability"] == "documentation_only"
    assert result["provenance"]["limitations"]


def test_cic_optional_csv_headers_are_inferred(tmp_path: Path):
    docs = tmp_path / "cic.html"
    docs.write_text("<p>CICIDS2017 labeled flow CSV dataset.</p>", encoding="utf-8")
    data = tmp_path / "flow.csv"
    data.write_text("Port,Label\n443,BENIGN\n80,ATTACK\n", encoding="utf-8")
    result = parse_cic_ids2017(
        docs,
        root=tmp_path,
        sample_csv=data,
        sample_csv_url="https://example.test/flow.csv",
    )
    assert [column["name"] for column in result["columns"]] == ["Port", "Label"]
    assert result["columns"][0]["type"]["value"] == "integer"
    assert result["columns"][1]["type"]["value"] == "string"


def test_cic_pinned_json_sample_uses_real_feature_types(tmp_path: Path):
    docs = tmp_path / "cic.html"
    docs.write_text("<p>CICIDS2017 labelled flow dataset.</p>", encoding="utf-8")
    sample = tmp_path / "rows.json"
    sample.write_text(
        json.dumps(
            {
                "features": [
                    {"name": " Destination Port", "type": {"dtype": "int64"}},
                    {"name": " Label", "type": {"dtype": "string"}},
                ],
                "rows": [
                    {"row": {" Destination Port": 443, " Label": "BENIGN"}},
                    {"row": {" Destination Port": None, " Label": "ATTACK"}},
                ],
                "num_rows_total": 10,
            }
        ),
        encoding="utf-8",
    )
    result = parse_cic_ids2017(
        docs,
        root=tmp_path,
        sample_json=sample,
        sample_json_url="https://example.test/rows?revision=abc",
    )
    assert result["provenance"]["records_sampled"] == 2
    assert result["columns"][0]["type"]["value"] == "integer"
    assert result["columns"][0]["type"]["status"] == "documented"
    assert result["columns"][0]["missing_values"]["value"]["count_in_sample"] == 1
    assert result["columns"][1]["allowed_values"]["status"] == "unknown"
    assert "samples 2" in result["provenance"]["limitations"][-1]


def test_cic_requires_provenance_url_for_sample(tmp_path: Path):
    docs = tmp_path / "cic.html"
    docs.write_text("<p>CICIDS2017 labelled flows.</p>", encoding="utf-8")
    sample = tmp_path / "flow.csv"
    sample.write_text("Port\n443\n", encoding="utf-8")
    with pytest.raises(ValueError, match="sample_csv_url"):
        parse_cic_ids2017(docs, root=tmp_path, sample_csv=sample)


def test_available_datasets_follow_common_schema(available_metadata):
    root = Path(__file__).resolve().parents[1]
    outputs = available_metadata
    assert {
        "ai4i-2020",
        "sec-edgar-xbrl",
        "nhanes-2017-2018",
        "nhanes-cbc-j",
        "nhanes-hdl-j",
        "nhanes-glu-j",
        "ton-iot",
        "unsw-nb15",
        "world-bank-wdi",
        "nist-nvd",
        "cic-ids2017",
    } <= outputs.keys()
    for output_name, metadata in outputs.items():
        assert metadata["schema_version"] == "1.0"
        assert {"dataset", "columns", "provenance"} <= metadata.keys()
        assert {"id", "name", "domain", "description", "availability"} <= metadata["dataset"].keys()
        assert {"sources", "records_sampled", "limitations"} <= metadata["provenance"].keys()
        sample_path = root / "data" / "metadata" / f"{output_name}.json"
        assert json.loads(sample_path.read_text(encoding="utf-8")) == metadata
        for column in metadata["columns"]:
            assert {
                "name",
                "type",
                "description",
                "unit",
                "allowed_values",
                "relationships",
                "missing_values",
                "sources",
            } <= column.keys()
            for key in ("type", "description", "unit", "allowed_values", "relationships", "missing_values"):
                assert column[key]["status"] in {"documented", "inferred", "unknown"}
                assert "value" in column[key] and "source" in column[key]
        for source in metadata["provenance"]["sources"]:
            source_path = root / source["file"]
            assert source_path.is_file()
            assert hashlib.sha256(source_path.read_bytes()).hexdigest() == source["sha256"]
        validate_metadata(metadata, root / "data" / "metadata.schema.json")
    assert outputs["sec-edgar-xbrl"]["api_documentation"]["status"] == "documented"


def test_sec_companyfacts_covers_ten_companies_multiple_concepts_and_years(available_metadata):
    outputs = available_metadata
    companyfacts = {
        key: value for key, value in outputs.items() if key.startswith("sec-companyfacts-")
    }
    assert len(companyfacts) == 10
    for metadata in companyfacts.values():
        assert len(metadata["columns"]) >= 2
        assert metadata["dataset"]["year_range"] == {"start": 2020, "end": 2025}
        assert all(
            len(concept["years"]) >= 5
            for concept in metadata["dataset"]["coverage"].values()
        )


def test_ai4i_processes_all_records_and_nhanes_has_three_lab_files(available_metadata):
    outputs = available_metadata
    assert outputs["ai4i-2020"]["provenance"]["records_sampled"] == 10_000
    assert {
        "nhanes-cbc-j",
        "nhanes-hdl-j",
        "nhanes-glu-j",
    } <= outputs.keys()
    for key in ("nhanes-cbc-j", "nhanes-hdl-j", "nhanes-glu-j"):
        assert outputs[key]["provenance"]["records_sampled"] == 1000
        assert outputs[key]["dataset"]["availability"] == "data_and_official_codebook"
        assert outputs[key]["columns"]
    gender = next(
        column for column in outputs["nhanes-2017-2018"]["columns"] if column["name"] == "RIAGENDR"
    )
    documented_missing = gender["missing_values"]["value"]["documented_categories"]
    assert documented_missing["status"] == "documented"
    assert documented_missing["value"] == [{"code": ".", "description": "Missing"}]


def test_supplementary_sources_and_ton_iot_access_limitation(available_metadata):
    outputs = available_metadata
    wdi = outputs["world-bank-wdi"]
    assert len(wdi["columns"]) == 2
    assert all(len(item["countries"]) == 10 for item in wdi["dataset"]["coverage"].values())
    assert all(item["years"] == [2020, 2021, 2022, 2023, 2024] for item in wdi["dataset"]["coverage"].values())
    nvd = outputs["nist-nvd"]
    assert nvd["provenance"]["records_sampled"] == 4000
    assert nvd["provenance"]["source_records_total"] == 4415
    assert nvd["provenance"]["sampling"]["start_indices"] == [0, 2000]
    assert sum(nvd["dataset"]["class_coverage"]["vulnStatus"].values()) == 4000
    score = next(column for column in nvd["columns"] if column["name"] == "cvss_base_score")
    assert score["missing_values"]["value"]["sample_size"] == 4000
    ton = outputs["ton-iot"]
    assert ton["dataset"]["availability"] == "blocked_authentication"
    assert ton["columns"] == []
    assert ton["provenance"]["records_sampled"] is None
    unsw = outputs["unsw-nb15"]
    assert unsw["provenance"]["records_sampled"] == 100_000
    assert unsw["provenance"]["source_records_total"] == 257_673
    assert len(unsw["columns"]) == 45
    assert len(unsw["dataset"]["class_coverage"]["attack_cat"]) == 10
    assert set(unsw["dataset"]["class_coverage"]["label"]) == {"0", "1"}
    assert "opposite" in " ".join(unsw["provenance"]["limitations"])
    attack_category = next(column for column in unsw["columns"] if column["name"] == "attack_cat")
    binary_label = next(column for column in unsw["columns"] if column["name"] == "label")
    assert attack_category["type"]["value"] == "string"
    assert binary_label["type"]["value"] == "integer"
    assert all(column["missing_values"]["value"]["sample_size"] == 100_000 for column in unsw["columns"])


def test_cic_ids2017_sample_remains_a_regression_fixture(available_metadata):
    cic = available_metadata["cic-ids2017"]
    assert len(cic["columns"]) == 79
    assert cic["provenance"]["records_sampled"] == 50_000
    assert cic["columns"][-1]["name"].strip() == "Label"
    assert cic["provenance"]["source_records_total"] == 512_212
    assert set(cic["dataset"]["class_coverage"]) == {"BENIGN", "DDoS", "PortScan"}
    assert sum(cic["dataset"]["class_coverage"].values()) == 50_000
    assert cic["provenance"]["sampling"]["seed"] == 2017
    assert next(column for column in cic["columns"] if column["name"].strip() == "Destination Port")["type"]["value"] == "integer"
    assert next(column for column in cic["columns"] if column["name"].strip() == "Label")["type"]["value"] == "string"
    assert next(column for column in cic["columns"] if column["name"].strip() == "Flow Bytes/s")["missing_values"]["value"]["count_in_sample"] == 1
    sample_path = Path(__file__).resolve().parents[1] / cic["provenance"]["sampling"]["sample_file"]
    assert sample_path.is_file()
    assert hashlib.sha256(sample_path.read_bytes()).hexdigest() == cic["provenance"]["sampling"]["sample_sha256"]


def test_schema_rejects_invented_values_for_unknown_fields(available_metadata):
    root = Path(__file__).resolve().parents[1]
    metadata = copy.deepcopy(available_metadata["cic-ids2017"])
    metadata["columns"][0]["unit"] = {"value": "invented", "status": "unknown", "source": None}
    with pytest.raises(ValueError, match="schema validation failed"):
        validate_metadata(metadata, root / "data" / "metadata.schema.json")
