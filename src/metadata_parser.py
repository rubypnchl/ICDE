"""Normalize metadata from industrial, financial, health, cyber, and public APIs."""

from __future__ import annotations

import argparse
import csv
import hashlib
from html.parser import HTMLParser
import json
import math
import numbers
import random
import re
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "1.0"
MISSING_MARKERS = {"", "na", "n/a", "null", "none", "nan"}


def _field(value: Any = None, status: str = "unknown", source: str | None = None) -> dict[str, Any]:
    return {"value": value, "status": status, "source": source}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_record(path: Path, url: str, root: Path) -> dict[str, Any]:
    return {
        "url": url,
        "file": path.relative_to(root).as_posix(),
        "sha256": _sha256(path),
    }


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _parse_number(value: str) -> int | float | None:
    try:
        number = float(value)
    except ValueError:
        return None
    if number.is_integer():
        return int(number)
    return number


def _infer_type(values: Iterable[str]) -> str:
    observed = [value for value in values if value.strip().lower() not in MISSING_MARKERS]
    if not observed:
        return "unknown"
    parsed = [_parse_number(value) for value in observed]
    if all(value is not None for value in parsed):
        return "integer" if all(isinstance(value, int) for value in parsed) else "number"
    return "string"


def _inferred_type_field(value: str, source: str) -> dict[str, Any]:
    if value == "unknown":
        return _field()
    return _field(value, "inferred", source)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in MISSING_MARKERS
    try:
        return math.isnan(value)
    except TypeError:
        return False


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_table = False
        self.in_cell = False
        self.rows: list[list[str]] = []
        self.row: list[str] = []
        self.cell: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table" and not self.in_table:
            self.in_table = True
        elif self.in_table and tag == "tr":
            self.row = []
        elif self.in_table and tag in {"td", "th"}:
            self.in_cell = True
            self.cell = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.in_table and tag in {"td", "th"} and self.in_cell:
            self.row.append(" ".join("".join(self.cell).split()))
            self.in_cell = False
        elif self.in_table and tag == "tr":
            if self.row:
                self.rows.append(self.row)
        elif tag == "table" and self.in_table:
            self.in_table = False


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.paragraphs: list[str] = []
        self._paragraph: list[str] = []
        self._in_paragraph = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "p":
            self._in_paragraph = True
            self._paragraph = []

    def handle_data(self, data: str) -> None:
        cleaned = " ".join(data.split())
        if cleaned:
            self.text.append(cleaned)
            if self._in_paragraph:
                self._paragraph.append(cleaned)

    def handle_endtag(self, tag: str) -> None:
        if tag == "p" and self._in_paragraph:
            paragraph = " ".join(self._paragraph).strip()
            if paragraph:
                self.paragraphs.append(paragraph)
            self._in_paragraph = False


class _NHANESCodebookParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.variables: dict[str, dict[str, Any]] = {}
        self.current: dict[str, Any] | None = None
        self.capture: str | None = None
        self.parts: list[str] = []
        self.current_label = ""
        self.in_values_table = False
        self.rows: list[list[str]] = []
        self.row: list[str] = []
        self.await_component_description = False
        self.dataset_description: str | None = None

    def _finish_variable(self) -> None:
        if self.current and self.current.get("name"):
            self.variables[self.current["name"]] = self.current

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "h3" and "vartitle" in (attributes.get("class") or "").split():
            self._finish_variable()
            name = attributes.get("id")
            self.current = {"name": name, "description": None, "allowed_values": [], "missing_categories": []}
            self.capture = "heading"
            self.parts = []
        elif tag == "dt" and self.current:
            self.capture = "dt"
            self.parts = []
        elif tag == "dd" and self.current:
            self.capture = "dd"
            self.parts = []
        elif tag == "h2" and attributes.get("id") == "Component_Description":
            self.capture = "component_heading"
        elif tag == "p" and self.await_component_description:
            self.capture = "component_description"
            self.parts = []
        elif tag == "table":
            self.in_values_table = "values" in (attributes.get("class") or "").split()
            if self.in_values_table:
                self.rows = []
        elif self.in_values_table and tag == "tr":
            self.row = []
        elif self.in_values_table and tag in {"th", "td"}:
            self.capture = "cell"
            self.parts = []

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h3" and self.capture == "heading":
            self.capture = None
        elif tag == "h2" and self.capture == "component_heading":
            self.capture = None
            self.await_component_description = True
        elif tag == "p" and self.capture == "component_description":
            self.dataset_description = " ".join("".join(self.parts).split()) or None
            self.capture = None
            self.await_component_description = False
        elif tag == "dt" and self.capture == "dt":
            self.current_label = " ".join("".join(self.parts).split()).rstrip(":")
            self.capture = None
        elif tag == "dd" and self.capture == "dd":
            value = " ".join("".join(self.parts).split())
            if self.current is not None and self.current_label in {"English Text", "SAS Label"}:
                if self.current_label == "English Text" or not self.current.get("description"):
                    self.current["description"] = value or None
            self.capture = None
        elif tag in {"th", "td"} and self.capture == "cell":
            self.row.append(" ".join("".join(self.parts).split()))
            self.capture = None
        elif tag == "tr" and self.in_values_table and self.row:
            self.rows.append(self.row)
        elif tag == "table" and self.in_values_table:
            self.in_values_table = False
            self._finish_values()

    def _finish_values(self) -> None:
        if not self.current or not self.rows:
            return
        headers = [_normalize_name(value) for value in self.rows[0]]
        if "codeorvalue" not in headers or "valuedescription" not in headers:
            return
        code_index = headers.index("codeorvalue")
        description_index = headers.index("valuedescription")
        for row in self.rows[1:]:
            if max(code_index, description_index) >= len(row):
                continue
            code, description = row[code_index].strip(), row[description_index].strip()
            if not code or not description:
                continue
            if description.casefold() == "missing":
                self.current["missing_categories"].append({"code": code, "description": description})
            else:
                self.current["allowed_values"].append({"code": code, "description": description})


def _empty_column(name: str, source_url: str) -> dict[str, Any]:
    return {
        "name": name,
        "type": _field(),
        "description": _field(),
        "unit": _field(),
        "allowed_values": _field(),
        "relationships": _field(),
        "missing_values": _field(),
        "sources": [source_url],
    }


def _dataset(
    *,
    dataset_id: str,
    name: str,
    domain: str,
    description: str | None,
    description_source: str | None,
    availability: str,
    columns: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    records_sampled: int | None,
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset": {
            "id": dataset_id,
            "name": name,
            "domain": domain,
            "description": _field(description, "documented" if description else "unknown", description_source),
            "availability": availability,
        },
        "columns": columns,
        "provenance": {
            "sources": sources,
            "records_sampled": records_sampled,
            "limitations": limitations or [],
        },
    }


def _read_csv(path: Path, sample_size: int) -> tuple[list[str], list[dict[str, str]]]:
    if sample_size < 1:
        raise ValueError("sample_size must be positive")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {path}")
        return reader.fieldnames, list(_take(reader, sample_size))


def _take(items: Iterable[Any], count: int) -> Iterable[Any]:
    for index, item in enumerate(items):
        if index >= count:
            break
        yield item


def _create_csv_sample(
    source_files: list[tuple[Path, str]],
    output_path: Path,
    *,
    root: Path,
    sample_size: int,
    seed: int,
) -> dict[str, Any]:
    if sample_size < 1:
        raise ValueError("sample_size must be positive")
    headers: list[str] | None = None
    reservoir: list[tuple[int, int, dict[str, str]]] = []
    rng = random.Random(seed)
    source_rows = [0] * len(source_files)
    source_classes: list[dict[str, dict[str, int]]] = [{} for _ in source_files]
    source_labels: set[str] = set()
    total = 0

    for source_index, (path, _) in enumerate(source_files):
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames:
                raise ValueError(f"CSV has no header: {path}")
            if headers is None:
                headers = reader.fieldnames
                source_labels = {
                    name
                    for name in headers
                    if name.strip().lower() in {"label", "attack_cat"}
                }
            elif reader.fieldnames != headers:
                raise ValueError(f"CSV headers differ between source files: {path}")
            for row in reader:
                source_rows[source_index] += 1
                for label_name in source_labels:
                    label = (row.get(label_name) or "").strip()
                    if label:
                        distribution = source_classes[source_index].setdefault(label_name, {})
                        distribution[label] = distribution.get(label, 0) + 1
                if total < sample_size:
                    reservoir.append((total, source_index, row))
                else:
                    replacement = rng.randrange(total + 1)
                    if replacement < sample_size:
                        reservoir[replacement] = (total, source_index, row)
                total += 1

    if headers is None or total < sample_size:
        raise ValueError(f"sample_size {sample_size} exceeds the {total} available CSV records")

    selected = sorted(reservoir, key=lambda item: item[0])
    sample_classes: dict[str, dict[str, int]] = {}
    source_sample_counts = [0] * len(source_files)
    for _, source_index, row in selected:
        source_sample_counts[source_index] += 1
        for label_name in source_labels:
            label = (row.get(label_name) or "").strip()
            if label:
                distribution = sample_classes.setdefault(label_name, {})
                distribution[label] = distribution.get(label, 0) + 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers, extrasaction="raise")
        writer.writeheader()
        for _, _, row in selected:
            writer.writerow(row)

    source_label_totals: dict[str, dict[str, int]] = {}
    for source_distribution in source_classes:
        for name, counts in source_distribution.items():
            target = source_label_totals.setdefault(name, {})
            for label, count in counts.items():
                target[label] = target.get(label, 0) + count
    return {
        "method": "uniform reservoir sample without replacement across source files",
        "seed": seed,
        "records_sampled": sample_size,
        "records_available": total,
        "source_records": {
            path.relative_to(root).as_posix(): count
            for (path, _), count in zip(source_files, source_rows)
        },
        "source_class_distribution": source_label_totals,
        "sample_class_distribution": sample_classes,
        "source_sample_records": {
            path.relative_to(root).as_posix(): count
            for (path, _), count in zip(source_files, source_sample_counts)
        },
        "sample_file": output_path.relative_to(root).as_posix(),
        "sample_sha256": _sha256(output_path),
    }


def _ai4i_documentation(path: Path, source_url: str) -> dict[str, dict[str, Any]]:
    parser = _TableParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    if not parser.rows:
        return {}
    headers = [_normalize_name(header) for header in parser.rows[0]]
    expected = {"variablename", "type", "description", "units", "missingvalues"}
    if not expected.issubset(set(headers)):
        return {}
    positions = {header: index for index, header in enumerate(headers)}
    documented: dict[str, dict[str, Any]] = {}
    for row in parser.rows[1:]:
        if len(row) < len(headers):
            continue
        name = row[positions["variablename"]]
        if not name:
            continue
        documented[_normalize_name(name)] = {
            "type": row[positions["type"]],
            "description": row[positions["description"]],
            "unit": row[positions["units"]],
            "missing": row[positions["missingvalues"]],
            "source": source_url,
        }
    return documented


def _nhanes_codebook(
    path: Path,
    source_url: str,
) -> tuple[dict[str, dict[str, Any]], str | None]:
    parser = _NHANESCodebookParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    parser._finish_variable()
    variables = {name: {**variable, "source": source_url} for name, variable in parser.variables.items()}
    return variables, parser.dataset_description


def parse_ai4i(
    csv_path: Path,
    documentation_path: Path,
    *,
    root: Path,
    sample_size: int = 1000,
) -> dict[str, Any]:
    data_url = "https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip"
    docs_url = "https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset"
    names, rows = _read_csv(csv_path, sample_size)
    documented = _ai4i_documentation(documentation_path, docs_url)
    columns: list[dict[str, Any]] = []
    for name in names:
        info = documented.get(_normalize_name(re.sub(r"\s*\[[^]]+\]\s*$", "", name)))
        values = [row.get(name, "") or "" for row in rows]
        column = _empty_column(name, data_url)
        column["type"] = _inferred_type_field(_infer_type(values), data_url)
        if info:
            column["sources"].append(info["source"])
            type_text = info["type"].strip().lower()
            type_value = {
                "integer": "integer",
                "categorical": "string",
                "continuous": "number",
                "real": "number",
            }.get(type_text)
            if type_value:
                column["type"] = _field(type_value, "documented", info["source"])
            if info["description"].strip():
                column["description"] = _field(info["description"], "documented", info["source"])
            if info["unit"].strip():
                column["unit"] = _field(info["unit"], "documented", info["source"])
            if info["missing"].strip().lower() in {"yes", "no"}:
                column["missing_values"] = _field(
                    {"present": info["missing"].strip().lower() == "yes"},
                    "documented",
                    info["source"],
                )
        if column["missing_values"]["status"] == "unknown":
            missing_count = sum(value.strip().lower() in MISSING_MARKERS for value in values)
            column["missing_values"] = _field(
                {"count_in_sample": missing_count, "sample_size": len(rows)},
                "inferred",
                data_url,
            )
        columns.append(column)
    return _dataset(
        dataset_id="ai4i-2020",
        name="AI4I 2020 Predictive Maintenance Dataset",
        domain="industrial predictive maintenance",
        description="Synthetic dataset reflecting predictive maintenance data encountered in industry.",
        description_source=docs_url,
        availability="data_and_documentation",
        columns=columns,
        sources=[
            _source_record(csv_path, data_url, root),
            _source_record(documentation_path, docs_url, root),
        ],
        records_sampled=len(rows),
    )


def parse_sec_xbrl(
    path: Path,
    *,
    root: Path,
    documentation_path: Path | None = None,
) -> dict[str, Any]:
    url = "https://data.sec.gov/api/xbrl/companyconcept/CIK0000320193/us-gaap/Assets.json"
    docs_url = "https://www.sec.gov/edgar/sec-api-documentation"
    payload = json.loads(path.read_text(encoding="utf-8"))
    label = payload.get("label")
    description = payload.get("description")
    columns: list[dict[str, Any]] = []
    observed_values: list[Any] = []
    unit_groups = payload.get("units", {})
    if not isinstance(unit_groups, dict):
        raise ValueError("SEC XBRL JSON field 'units' must be an object")
    if any(not isinstance(values, list) for values in unit_groups.values()):
        raise ValueError("SEC XBRL unit groups must contain arrays")
    rows = [(unit, row) for unit, values in unit_groups.items() for row in values if isinstance(row, dict)]
    for unit in unit_groups:
        observed_values.extend(
            row["val"]
            for row in unit_groups[unit]
            if isinstance(row, dict) and row.get("val") is not None
        )
    if observed_values and all(isinstance(value, int) and not isinstance(value, bool) for value in observed_values):
        type_name = "integer"
    elif observed_values and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in observed_values):
        type_name = "number"
    else:
        type_name = "string" if observed_values else None
    value_column = _empty_column("value", url)
    value_column["type"] = _field(type_name, "inferred" if observed_values else "unknown", url if observed_values else None)
    if description:
        value_column["description"] = _field(description, "documented", url)
    if len(unit_groups) == 1:
        value_column["unit"] = _field(next(iter(unit_groups)), "documented", url)
    missing_value_count = sum(row.get("val") is None for _, row in rows)
    value_column["missing_values"] = _field(
        {"count_in_sample": missing_value_count, "sample_size": len(rows)},
        "inferred",
        url,
    )
    columns.append(value_column)

    known_fields = ("end", "start", "fy", "fp", "form", "filed", "accn", "frame")
    seen_fields = {key for _, row in rows for key in row}
    for field_name in known_fields:
        if field_name not in seen_fields:
            continue
        column = _empty_column(field_name, url)
        values = [row.get(field_name) for _, row in rows]
        observed_values = [value for value in values if value is not None]
        if observed_values and all(isinstance(value, int) and not isinstance(value, bool) for value in observed_values):
            inferred_type = "integer"
        elif observed_values and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in observed_values):
            inferred_type = "number"
        elif observed_values and all(
            isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
            for value in observed_values
        ):
            inferred_type = "date"
        else:
            inferred_type = "string" if observed_values else None
        column["type"] = _field(inferred_type, "inferred" if observed_values else "unknown", url if observed_values else None)
        missing = sum(value is None for value in values)
        column["missing_values"] = _field(
            {"count_in_sample": missing, "sample_size": len(rows)},
            "inferred",
            url,
        )
        columns.append(column)
    dataset = _dataset(
        dataset_id="sec-edgar-xbrl-apple-assets",
        name="SEC EDGAR XBRL Apple Assets concept sample",
        domain="financial reporting",
        description=description,
        description_source=url,
        availability="data_and_api_metadata",
        columns=columns,
        sources=[
            _source_record(path, url, root),
            *(
                [_source_record(documentation_path, docs_url, root)]
                if documentation_path is not None
                else []
            ),
        ],
        records_sampled=len(rows),
    )
    for field_name, value in (
        ("entity", payload.get("entityName")),
        ("taxonomy", payload.get("taxonomy")),
        ("concept", payload.get("tag")),
        ("label", label),
    ):
        dataset["dataset"][field_name] = _field(
            value,
            "documented" if value is not None else "unknown",
            url if value is not None else None,
        )
    if documentation_path is not None:
        parser = _TextParser()
        parser.feed(documentation_path.read_text(encoding="utf-8", errors="replace"))
        documentation = next(
            (paragraph for paragraph in parser.paragraphs if "company-concept API returns" in paragraph),
            None,
        )
        if documentation:
            dataset["api_documentation"] = _field(documentation, "documented", docs_url)
    return dataset


SEC_CONCEPTS = {
    "assets": ("Assets",),
    "liabilities": ("Liabilities",),
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "operating_income": ("OperatingIncomeLoss",),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
}


def parse_sec_companyfacts(
    path: Path,
    *,
    root: Path,
    documentation_path: Path | None = None,
) -> dict[str, Any]:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/{path.stem.split('_', 1)[0]}.json"
    docs_url = "https://www.sec.gov/edgar/sec-api-documentation"
    payload = json.loads(path.read_text(encoding="utf-8"))
    cik = payload.get("cik")
    entity_name = payload.get("entityName")
    facts = payload.get("facts", {}).get("us-gaap", {})
    if not isinstance(facts, dict):
        raise ValueError(f"SEC Company Facts us-gaap facts must be an object: {path}")

    columns: list[dict[str, Any]] = []
    coverage: dict[str, Any] = {}
    observations = 0
    for concept_name, candidates in SEC_CONCEPTS.items():
        selected_name = next((name for name in candidates if name in facts), None)
        if selected_name is None:
            continue
        concept = facts[selected_name]
        units = concept.get("units", {})
        if not isinstance(units, dict):
            raise ValueError(f"SEC concept units must be an object: {selected_name}")
        values_by_unit: dict[str, list[dict[str, Any]]] = {}
        for unit, entries in units.items():
            if not isinstance(entries, list):
                raise ValueError(f"SEC unit facts must be arrays: {selected_name}/{unit}")
            selected = []
            for entry in entries:
                end = entry.get("end") if isinstance(entry, dict) else None
                if not isinstance(end, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", end):
                    continue
                year = int(end[:4])
                if 2020 <= year <= 2025 and entry.get("val") is not None:
                    selected.append(entry)
            if selected:
                values_by_unit[unit] = selected
        years = sorted(
            {
                int(entry["end"][:4])
                for entries in values_by_unit.values()
                for entry in entries
            }
        )
        if len(years) < 5:
            continue
        fact_values = [
            entry["val"]
            for entries in values_by_unit.values()
            for entry in entries
        ]
        observed_values = [value for value in fact_values if isinstance(value, (int, float))]
        column_type = (
            "integer"
            if observed_values and all(isinstance(value, int) and not isinstance(value, bool) for value in observed_values)
            else "number"
            if observed_values
            else None
        )
        units_list = sorted(values_by_unit)
        column = _empty_column(concept_name, url)
        column["type"] = _field(column_type if observed_values else None, "inferred" if observed_values else "unknown", url if observed_values else None)
        description = concept.get("description")
        if description:
            column["description"] = _field(description, "documented", url)
        if len(units_list) == 1:
            column["unit"] = _field(units_list[0], "documented", url)
        elif units_list:
            column["unit"] = _field(units_list, "documented", url)
        columns.append(column)
        fact_count = sum(len(entries) for entries in values_by_unit.values())
        observations += fact_count
        coverage[concept_name] = {
            "tag": selected_name,
            "years": years,
            "fact_count": fact_count,
            "units": units_list,
        }

    if len(columns) < 2:
        raise ValueError(f"SEC Company Facts has fewer than two concepts with five-year coverage: {path}")
    api_description = None
    if documentation_path is not None:
        documentation_parser = _TextParser()
        documentation_parser.feed(documentation_path.read_text(encoding="utf-8", errors="replace"))
        api_description = next(
            (
                paragraph
                for paragraph in documentation_parser.paragraphs
                if "company concepts data for a company into a single API call" in paragraph
            ),
            None,
        )
    dataset = _dataset(
        dataset_id=f"sec-companyfacts-{cik}",
        name=f"SEC Company Facts: {entity_name}",
        domain="financial reporting",
        description=api_description,
        description_source=docs_url if api_description else None,
        availability="official_companyfacts_2020_2025",
        columns=columns,
        sources=[
            _source_record(path, url, root),
            *(
                [_source_record(documentation_path, docs_url, root)]
                if documentation_path is not None
                else []
            ),
        ],
        records_sampled=observations,
        limitations=[
            "Company Facts is a retained API snapshot. Facts cover 2020-2025 and may include quarterly and annual filings or restatements."
        ],
    )
    dataset["dataset"]["entity"] = _field(entity_name, "documented", url)
    dataset["dataset"]["cik"] = _field(cik, "documented", url)
    dataset["dataset"]["taxonomy"] = _field("us-gaap", "documented", url)
    dataset["dataset"]["coverage"] = coverage
    dataset["dataset"]["year_range"] = {"start": 2020, "end": 2025}
    if api_description:
        dataset["api_documentation"] = _field(api_description, "documented", docs_url)
    return dataset


def parse_nhanes_xpt(
    path: Path,
    *,
    root: Path,
    sample_size: int = 1000,
    documentation_path: Path | None = None,
) -> dict[str, Any]:
    if sample_size < 1:
        raise ValueError("sample_size must be positive")
    base_url = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles"
    url = f"{base_url}/{path.name}"
    docs_url = f"{base_url}/{path.stem}.htm"
    try:
        import pyreadstat
    except ImportError as error:
        raise RuntimeError("NHANES XPT parsing requires pyreadstat; install requirements.txt") from error
    data, metadata = pyreadstat.read_xport(
        str(path),
        row_limit=sample_size,
        output_format="dict",
    )
    row_count = len(next(iter(data.values()))) if data else 0
    if documentation_path:
        documented, dataset_description = _nhanes_codebook(documentation_path, docs_url)
    else:
        documented, dataset_description = {}, None
    columns: list[dict[str, Any]] = []
    for name in metadata.column_names:
        source_label = metadata.column_names_to_labels.get(name) or None
        column = _empty_column(name, url)
        variable_docs = documented.get(name)
        values = data[name]
        observed_values = [value for value in values if not _is_missing(value)]
        if observed_values:
            if all(isinstance(value, numbers.Real) and not isinstance(value, bool) for value in observed_values):
                column_type = "integer" if all(float(value).is_integer() for value in observed_values) else "number"
            else:
                column_type = "string"
            type_source = url
            type_status = "inferred"
        else:
            column_type, type_source, type_status = None, None, "unknown"
        column["type"] = _field(column_type, type_status, type_source)
        description = (variable_docs or {}).get("description") or source_label
        if description:
            description_url = docs_url if (variable_docs or {}).get("description") else url
            column["description"] = _field(description, "documented", description_url)
        if variable_docs and variable_docs["allowed_values"]:
            column["allowed_values"] = _field(variable_docs["allowed_values"], "documented", docs_url)
        value_labels = metadata.variable_value_labels.get(name)
        if value_labels and not (variable_docs and variable_docs["allowed_values"]):
            column["allowed_values"] = _field(value_labels, "documented", url)
        if variable_docs:
            column["sources"].append(docs_url)
        missing_count = sum(_is_missing(value) for value in values)
        missing_value = _field(
            {"count_in_sample": missing_count, "sample_size": row_count},
            "inferred",
            url,
        )
        if variable_docs and variable_docs["missing_categories"]:
            missing_value = _field(
                {
                    "observed_in_sample": missing_value,
                    "documented_categories": _field(
                        variable_docs["missing_categories"],
                        "documented",
                        docs_url,
                    ),
                },
                "inferred",
                url,
            )
        column["missing_values"] = missing_value
        columns.append(column)
    variable = path.stem
    dataset_id = f"nhanes-2017-2018-{variable.lower().replace('_', '-')}"
    return _dataset(
        dataset_id=dataset_id,
        name=f"NHANES 2017-2018 {variable}",
        domain="health and demographics",
        description=dataset_description,
        description_source=docs_url if dataset_description else None,
        availability="data_and_official_codebook" if documentation_path else "data_and_embedded_variable_labels",
        columns=columns,
        sources=[
            _source_record(path, url, root),
            *(
                [_source_record(documentation_path, docs_url, root)]
                if documentation_path is not None
                else []
            ),
        ],
        records_sampled=row_count,
    )


def parse_cic_ids2017(
    documentation_path: Path,
    *,
    root: Path,
    sample_csv: Path | None = None,
    sample_csv_url: str | None = None,
    sample_size: int = 1000,
    source_csv_paths: list[tuple[Path, str]] | None = None,
    sampling_metadata: dict[str, Any] | None = None,
    sample_json: Path | None = None,
    sample_json_url: str | None = None,
    dataset_card_path: Path | None = None,
) -> dict[str, Any]:
    docs_url = "https://www.unb.ca/cic/datasets/ids-2017.html"
    parser = _TextParser()
    parser.feed(documentation_path.read_text(encoding="utf-8", errors="replace"))
    description = next(
        (
            paragraph
            for paragraph in parser.paragraphs
            if "CICIDS2017" in paragraph and "CSV" in paragraph
        ),
        None,
    )
    columns: list[dict[str, Any]] = []
    sources = [_source_record(documentation_path, docs_url, root)]
    records_sampled = None
    source_records_total = None
    availability = "documentation_only"
    limitations = [
        "The sample is from a public Hugging Face mirror of CIC-IDS2017; the official CIC download page requires a contact form."
    ]
    if sample_csv is not None and sample_json is not None:
        raise ValueError("provide at most one CIC sample format")
    if sample_csv is not None:
        if not sample_csv_url:
            raise ValueError("sample_csv_url is required when a CIC CSV sample is provided")
        names, rows = _read_csv(sample_csv, sample_size)
        if source_csv_paths:
            sources.extend(_source_record(path, url, root) for path, url in source_csv_paths)
            source_records_total = (
                sampling_metadata.get("records_available")
                if sampling_metadata
                else None
            )
        else:
            sources.append(_source_record(sample_csv, sample_csv_url, root))
        records_sampled = len(rows)
        availability = "data_and_documentation"
        limitations = [
            "The original CIC download page requires a contact form; the retained flow records are from the pinned public Hugging Face mirror."
        ]
        if dataset_card_path is not None:
            dataset_card_url = (
                "https://huggingface.co/datasets/c01dsnap/CIC-IDS2017/"
                "resolve/4e9edfa727f800b6f595bc2ee7420527156562b2/README.md"
            )
            sources.append(_source_record(dataset_card_path, dataset_card_url, root))
            license_path = dataset_card_path.parent / "LICENSE"
            if license_path.is_file():
                license_url = (
                    "https://huggingface.co/datasets/c01dsnap/CIC-IDS2017/"
                    "resolve/4e9edfa727f800b6f595bc2ee7420527156562b2/LICENSE"
                )
                sources.append(_source_record(license_path, license_url, root))
        for name in names:
            values = [row.get(name, "") or "" for row in rows]
            column = _empty_column(name, sample_csv_url)
            if source_csv_paths:
                column["sources"].extend(url for _, url in source_csv_paths)
            column["type"] = _inferred_type_field(_infer_type(values), sample_csv_url)
            missing_count = sum(value.strip().lower() in MISSING_MARKERS for value in values)
            column["missing_values"] = _field(
                {"count_in_sample": missing_count, "sample_size": len(rows)},
                "inferred",
                sample_csv_url,
            )
            columns.append(column)
        label_name = next((name for name in names if name.strip().lower() == "label"), None)
        class_coverage: dict[str, int] = {}
        if label_name:
            for row in rows:
                label = row.get(label_name, "")
                if label:
                    class_coverage[label] = class_coverage.get(label, 0) + 1
    if sample_json is not None:
        if not sample_json_url:
            raise ValueError("sample_json_url is required when a CIC JSON sample is provided")
        payload = json.loads(sample_json.read_text(encoding="utf-8"))
        features, rows = payload.get("features"), payload.get("rows")
        if not isinstance(features, list) or not isinstance(rows, list):
            raise ValueError("CIC row sample must contain feature and row arrays")
        if any(not isinstance(feature, dict) for feature in features):
            raise ValueError("CIC sample features must be objects")
        sources.append(_source_record(sample_json, sample_json_url, root))
        if dataset_card_path is not None:
            dataset_card_url = (
                "https://huggingface.co/datasets/c01dsnap/CIC-IDS2017/"
                "resolve/4e9edfa727f800b6f595bc2ee7420527156562b2/README.md"
            )
            sources.append(_source_record(dataset_card_path, dataset_card_url, root))
            license_path = dataset_card_path.parent / "LICENSE"
            if license_path.is_file():
                license_url = (
                    "https://huggingface.co/datasets/c01dsnap/CIC-IDS2017/"
                    "resolve/4e9edfa727f800b6f595bc2ee7420527156562b2/LICENSE"
                )
                sources.append(_source_record(license_path, license_url, root))
        records_sampled = len(rows)
        source_records_total = payload.get("num_rows_total")
        availability = "data_and_documentation"
        for feature in features:
            name, feature_type = feature.get("name"), feature.get("type")
            dtype = feature_type.get("dtype") if isinstance(feature_type, dict) else None
            if not isinstance(name, str) or not isinstance(dtype, str):
                raise ValueError("CIC sample features require string names and dtypes")
            column_type = {
                "int8": "integer",
                "int16": "integer",
                "int32": "integer",
                "int64": "integer",
                "float32": "number",
                "float64": "number",
                "string": "string",
            }.get(dtype, dtype)
            column = _empty_column(name, sample_json_url)
            column["type"] = _field(column_type, "documented", sample_json_url)
            column["sources"].append(docs_url)
            values = []
            for record in rows:
                if not isinstance(record, dict) or not isinstance(record.get("row"), dict):
                    raise ValueError("CIC sample rows must contain row objects")
                values.append(record["row"].get(name))
            column["missing_values"] = _field(
                {
                    "count_in_sample": sum(_is_missing(value) for value in values),
                    "sample_size": len(rows),
                },
                "inferred",
                sample_json_url,
            )
            columns.append(column)
        if isinstance(payload.get("num_rows_total"), int):
            limitations.append(
                f"The pinned mirrored split contains {payload['num_rows_total']} rows; this output samples {len(rows)}."
            )
    result = _dataset(
        dataset_id="cic-ids2017",
        name="CIC-IDS2017",
        domain="network intrusion detection",
        description=description,
        description_source=docs_url,
        availability=availability,
        columns=columns,
        sources=sources,
        records_sampled=records_sampled,
        limitations=limitations,
    )
    if isinstance(source_records_total, int):
        result["provenance"]["source_records_total"] = source_records_total
    if sample_csv is not None:
        result["dataset"]["class_coverage"] = class_coverage
        if sampling_metadata:
            result["provenance"]["sampling"] = sampling_metadata
            result["dataset"]["licensing_note"] = (
                "The pinned mirror labels its license as 'other' and its README requests citation but grants no explicit reuse license; verify rights before redistribution."
            )
    return result


def parse_ton_iot_unavailable(path: Path, *, root: Path) -> dict[str, Any]:
    url = "https://research.unsw.edu.au/projects/toniot-datasets"
    parser = _TextParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    description = next(
        (paragraph for paragraph in parser.paragraphs if "TON_IoT datasets" in paragraph),
        None,
    )
    result = _dataset(
        dataset_id="ton-iot",
        name="ToN_IoT",
        domain="IoT and industrial IoT cybersecurity",
        description=description,
        description_source=url if description else None,
        availability="blocked_authentication",
        columns=[],
        sources=[_source_record(path, url, root)],
        records_sampled=None,
        limitations=[
            "The official UNSW SharePoint folder was retried without credentials and returned HTTP 403; authentication was not bypassed. Verified UNSW-NB15 train/test files are recorded separately."
        ],
    )
    result["dataset"]["data_access_url"] = _field(
        "https://unsw-my.sharepoint.com/:f:/g/personal/z5025758_ad_unsw_edu_au/EvBTaetotpdGnW7rJQ8fCvYBh8063CNeY9W33MpRsarJaQ",
        "documented",
        url,
    )
    return result


def parse_unsw_nb15(
    sample_path: Path,
    *,
    root: Path,
    source_files: list[tuple[Path, str]],
    sampling_metadata: dict[str, Any],
) -> dict[str, Any]:
    official_url = "https://research.unsw.edu.au/projects/unsw-nb15-dataset"
    mirror_docs_url = (
        "https://huggingface.co/datasets/Mireu-Lab/UNSW-NB15/"
        "resolve/3eb02c4a0a29866b7abcb5ef77c45cf4fcc8f6b0/README.md"
    )
    repository_url = "https://huggingface.co/datasets/Mireu-Lab/UNSW-NB15"
    names, rows = _read_csv(sample_path, sampling_metadata["records_sampled"])
    columns: list[dict[str, Any]] = []
    sample_url = repository_url
    for name in names:
        values = [row.get(name, "") or "" for row in rows]
        column = _empty_column(name, sample_url)
        column["sources"].extend(url for _, url in source_files)
        column["type"] = _inferred_type_field(_infer_type(values), sample_url)
        column["missing_values"] = _field(
            {
                "count_in_sample": sum(_is_missing(value) for value in values),
                "sample_size": len(rows),
            },
            "inferred",
            sample_url,
        )
        columns.append(column)

    parser = _TextParser()
    official_path = next(path for path, url in source_files if url == official_url)
    parser.feed(official_path.read_text(encoding="utf-8", errors="replace"))
    description = next(
        (text for text in parser.paragraphs if "UNSW-NB15" in text and "records" in text),
        None,
    )
    result = _dataset(
        dataset_id="unsw-nb15",
        name="UNSW-NB15",
        domain="network intrusion detection",
        description=description,
        description_source=official_url if description else None,
        availability="verified_public_mirror_train_test",
        columns=columns,
        sources=[
            _source_record(path, url, root)
            for path, url in source_files
        ],
        records_sampled=len(rows),
        limitations=[
            "The official UNSW SharePoint download returned HTTP 403 without credentials; no authentication was bypassed.",
            "The pinned mirror identifies its files as train.csv and test.csv, but observed row counts are 82,332 and 175,341 respectively, opposite the official page's declared training/test counts. Original mirror filenames are retained; split identity is not silently relabeled.",
            "The mirror README declares GPL-3.0; no standalone license file was present in the pinned repository revision.",
        ],
    )
    result["provenance"]["source_records_total"] = sampling_metadata["records_available"]
    result["provenance"]["sampling"] = sampling_metadata
    result["dataset"]["class_coverage"] = sampling_metadata["sample_class_distribution"]
    result["dataset"]["licensing_note"] = (
        "Pinned mirror README declares GPL-3.0; original UNSW dataset attribution and citation are preserved."
    )
    result["dataset"]["source_file_records"] = sampling_metadata["source_records"]
    result["dataset"]["mirror_source"] = repository_url
    return result


def parse_world_bank_wdi(root: Path) -> dict[str, Any]:
    original_dir = root / "data" / "originals" / "worldbank"
    codes = ("NY.GDP.PCAP.CD", "SP.POP.TOTL")
    countries = {"USA", "CAN", "GBR", "DEU", "FRA", "JPN", "CHN", "IND", "BRA", "ZAF"}
    columns: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    row_count = 0
    coverage: dict[str, Any] = {}
    for code in codes:
        token = code.replace(".", "_")
        data_path = original_dir / f"{token}.json"
        indicator_path = original_dir / f"indicator-{token}.json"
        data_url = f"https://api.worldbank.org/v2/country/all/indicator/{code}?date=2020%3A2024&format=json&per_page=2000"
        indicator_url = f"https://api.worldbank.org/v2/indicator/{code}?format=json"
        data_payload = json.loads(data_path.read_text(encoding="utf-8"))
        indicator_payload = json.loads(indicator_path.read_text(encoding="utf-8"))
        if not isinstance(data_payload, list) or len(data_payload) != 2 or not isinstance(data_payload[1], list):
            raise ValueError(f"Invalid World Bank indicator response: {data_path}")
        if not isinstance(indicator_payload, list) or len(indicator_payload) != 2 or not indicator_payload[1]:
            raise ValueError(f"Invalid World Bank indicator metadata response: {indicator_path}")
        records = [
            row
            for row in data_payload[1]
            if row.get("countryiso3code") in countries and 2020 <= int(row["date"]) <= 2024
        ]
        if len(data_payload[1]) != data_payload[0].get("total"):
            raise ValueError(f"World Bank response is paginated; refusing partial data: {data_path}")
        metadata = indicator_payload[1][0]
        column = _empty_column(code, data_url)
        column["type"] = _inferred_type_field(
            _infer_type([str(row["value"]) for row in records if row.get("value") is not None]),
            data_url,
        )
        description = metadata.get("sourceNote") or metadata.get("name")
        if description:
            column["description"] = _field(description, "documented", indicator_url)
        unit = metadata.get("unit")
        if unit:
            column["unit"] = _field(unit, "documented", indicator_url)
        column["missing_values"] = _field(
            {
                "count_in_sample": sum(row.get("value") is None for row in records),
                "sample_size": len(records),
            },
            "inferred",
            data_url,
        )
        columns.append(column)
        row_count += len(records)
        coverage[code] = {
            "indicator_name": metadata.get("name"),
            "countries": sorted({row["countryiso3code"] for row in records}),
            "years": sorted({int(row["date"]) for row in records}),
            "observations": len(records),
        }
        sources.extend(
            [
                _source_record(data_path, data_url, root),
                _source_record(indicator_path, indicator_url, root),
            ]
        )
    result = _dataset(
        dataset_id="world-bank-wdi-2020-2024",
        name="World Bank World Development Indicators sample",
        domain="economics and development",
        description=None,
        description_source=None,
        availability="official_api_sample",
        columns=columns,
        sources=sources,
        records_sampled=row_count,
        limitations=[
            "Indicator API responses cover all economies; metadata coverage is restricted to the ten selected ISO-3 countries."
        ],
    )
    result["dataset"]["coverage"] = coverage
    return result


def parse_nist_nvd(root: Path) -> dict[str, Any]:
    original_dir = root / "data" / "originals" / "nist_nvd"
    documentation_path = root / "data" / "originals" / "nist_nvd" / "api-vulnerabilities.html"
    base_url = (
        "https://services.nvd.nist.gov/rest/json/cves/2.0?"
        "pubStartDate=2025-01-01T00%3A00%3A00.000&pubEndDate=2025-01-31T23%3A59%3A59.999"
        "&resultsPerPage=2000"
    )
    docs_url = "https://nvd.nist.gov/developers/vulnerabilities"
    data_url = base_url
    pages = []
    sources = []
    expected_total = None
    expected_start = 0
    for page_number in (1, 2):
        data_path = original_dir / f"cves-2025-01-page-{page_number}.json"
        data_url = f"{base_url}&startIndex={expected_start}"
        payload = json.loads(data_path.read_text(encoding="utf-8"))
        vulnerabilities = payload.get("vulnerabilities")
        if not isinstance(vulnerabilities, list):
            raise ValueError("NVD response must contain a vulnerabilities array")
        if payload.get("startIndex") != expected_start:
            raise ValueError(f"NVD page has unexpected startIndex: {data_path}")
        if expected_total is None:
            expected_total = payload.get("totalResults")
        elif payload.get("totalResults") != expected_total:
            raise ValueError("NVD paginated responses disagree on totalResults")
        pages.append(vulnerabilities)
        sources.append(_source_record(data_path, data_url, root))
        expected_start += len(vulnerabilities)
    if not isinstance(expected_total, int) or expected_start > expected_total:
        raise ValueError("NVD pagination metadata is invalid")
    vulnerabilities = [item for page in pages for item in page]
    cve_ids = [
        item.get("cve", {}).get("id")
        for item in vulnerabilities
        if isinstance(item, dict) and isinstance(item.get("cve"), dict)
    ]
    if len(cve_ids) != len(vulnerabilities) or len(cve_ids) != len(set(cve_ids)):
        raise ValueError("NVD pages contain invalid or duplicate CVE identifiers")
    observations: dict[str, list[Any]] = {
        "cve_id": [],
        "published": [],
        "last_modified": [],
        "status": [],
        "description": [],
        "cvss_base_score": [],
    }
    for item in vulnerabilities:
        if not isinstance(item, dict) or not isinstance(item.get("cve"), dict):
            raise ValueError("NVD vulnerability entries must contain a CVE object")
        cve = item["cve"]
        descriptions = cve.get("descriptions") or []
        if not isinstance(descriptions, list):
            raise ValueError("NVD CVE descriptions must be an array")
        english = next(
            (
                entry.get("value")
                for entry in descriptions
                if isinstance(entry, dict) and entry.get("lang") == "en"
            ),
            None,
        )
        metrics = cve.get("metrics") or {}
        if not isinstance(metrics, dict):
            raise ValueError("NVD CVE metrics must be an object")
        score = next(
            (
                metric.get("cvssData", {}).get("baseScore")
                for metric_name in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2")
                for metric in (metrics.get(metric_name) or [])
                if isinstance(metric, dict) and isinstance(metric.get("cvssData"), dict)
            ),
            None,
        )
        observations["cve_id"].append(cve.get("id"))
        observations["published"].append(cve.get("published"))
        observations["last_modified"].append(cve.get("lastModified"))
        observations["status"].append(cve.get("vulnStatus"))
        observations["description"].append(english)
        observations["cvss_base_score"].append(score)
    columns: list[dict[str, Any]] = []
    for name, values in observations.items():
        column = _empty_column(name, docs_url)
        observed_values = [value for value in values if value is not None]
        if not observed_values:
            column_type, type_status, type_source = None, "unknown", None
        elif name in {"published", "last_modified"} and all(
            isinstance(value, str) and re.match(r"\d{4}-\d{2}-\d{2}T", value)
            for value in observed_values
        ):
            column_type, type_status, type_source = "datetime", "inferred", data_url
        elif all(isinstance(value, bool) for value in observed_values):
            column_type, type_status, type_source = "boolean", "inferred", data_url
        elif all(isinstance(value, int) and not isinstance(value, bool) for value in observed_values):
            column_type, type_status, type_source = "integer", "inferred", data_url
        elif all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in observed_values):
            column_type, type_status, type_source = "number", "inferred", data_url
        elif all(isinstance(value, str) for value in observed_values):
            column_type, type_status, type_source = "string", "inferred", data_url
        else:
            column_type, type_status, type_source = None, "unknown", None
        column["type"] = _field(column_type, type_status, type_source)
        column["missing_values"] = _field(
            {"count_in_sample": sum(value is None for value in values), "sample_size": len(vulnerabilities)},
            "inferred",
            data_url,
        )
        columns.append(column)
    result = _dataset(
        dataset_id="nist-nvd-cves-2025-01",
        name="NIST NVD CVE API paginated sample",
        domain="vulnerability metadata",
        description="NVD CVE records published during January 2025; the first two 2,000-record API pages.",
        description_source=docs_url,
        availability="official_api_paginated_sample",
        columns=columns,
        sources=[
            *sources,
            _source_record(documentation_path, docs_url, root),
        ],
        records_sampled=len(vulnerabilities),
        limitations=[
            f"The API reports {expected_total} records for January 2025; the first {len(vulnerabilities)} are retained."
        ],
    )
    result["provenance"]["source_records_total"] = expected_total
    result["provenance"]["sampling"] = {
        "method": "official NVD CVE API pagination in startIndex order",
        "results_per_page": 2000,
        "pages": len(pages),
        "start_indices": [0, 2000],
        "records_sampled": len(vulnerabilities),
    }
    status_counts: dict[str, int] = {}
    for status in observations["status"]:
        if status:
            status_counts[status] = status_counts.get(status, 0) + 1
    result["dataset"]["class_coverage"] = {"vulnStatus": status_counts}
    result["dataset"]["query_window"] = {"published_start": "2025-01-01", "published_end": "2025-01-31"}
    return result


def build_metadata(root: Path, *, sample_size: int = 1000) -> dict[str, dict[str, Any]]:
    originals = root / "data" / "originals"
    cic_revision = "4e9edfa727f800b6f595bc2ee7420527156562b2"
    cic_csvs = [
        (
            originals / "cic_ids2017" / name,
            f"https://huggingface.co/datasets/c01dsnap/CIC-IDS2017/resolve/{cic_revision}/{name}",
        )
        for name in (
            "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv",
            "Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv",
        )
    ]
    cic_sample = root / "data" / "samples" / "cic_ids2017" / "flows-50000.csv"
    cic_sampling = _create_csv_sample(
        cic_csvs,
        cic_sample,
        root=root,
        sample_size=50_000,
        seed=2017,
    )
    unsw_revision = "3eb02c4a0a29866b7abcb5ef77c45cf4fcc8f6b0"
    unsw_train = originals / "unsw_nb15" / "train.csv"
    unsw_test = originals / "unsw_nb15" / "test.csv"
    unsw_csvs = [
        (
            unsw_train,
            f"https://huggingface.co/datasets/Mireu-Lab/UNSW-NB15/resolve/{unsw_revision}/train.csv",
        ),
        (
            unsw_test,
            f"https://huggingface.co/datasets/Mireu-Lab/UNSW-NB15/resolve/{unsw_revision}/test.csv",
        ),
    ]
    unsw_sample = root / "data" / "samples" / "unsw_nb15" / "flows-100000.csv"
    unsw_sampling = _create_csv_sample(
        unsw_csvs,
        unsw_sample,
        root=root,
        sample_size=100_000,
        seed=2015,
    )
    unsw_sources = [
        *unsw_csvs,
        (
            originals / "unsw_nb15" / "README.md",
            f"https://huggingface.co/datasets/Mireu-Lab/UNSW-NB15/resolve/{unsw_revision}/README.md",
        ),
        (
            originals / "unsw_nb15" / "official-project-page.html",
            "https://research.unsw.edu.au/projects/unsw-nb15-dataset",
        ),
    ]
    output = {
        "ai4i-2020": parse_ai4i(
            originals / "ai4i" / "ai4i2020.csv",
            originals / "ai4i" / "uci-dataset-page.html",
            root=root,
            sample_size=10_000,
        ),
        "sec-edgar-xbrl": parse_sec_xbrl(
            originals / "sec" / "apple_assets.json",
            root=root,
            documentation_path=originals / "sec" / "api-documentation.html",
        ),
        "nhanes-2017-2018": parse_nhanes_xpt(
            originals / "nhanes" / "DEMO_J.XPT",
            root=root,
            sample_size=sample_size,
            documentation_path=originals / "nhanes" / "DEMO_J.htm",
        ),
        "nhanes-cbc-j": parse_nhanes_xpt(
            originals / "nhanes" / "CBC_J.XPT",
            root=root,
            sample_size=sample_size,
            documentation_path=originals / "nhanes" / "CBC_J.htm",
        ),
        "nhanes-hdl-j": parse_nhanes_xpt(
            originals / "nhanes" / "HDL_J.XPT",
            root=root,
            sample_size=sample_size,
            documentation_path=originals / "nhanes" / "HDL_J.htm",
        ),
        "nhanes-glu-j": parse_nhanes_xpt(
            originals / "nhanes" / "GLU_J.XPT",
            root=root,
            sample_size=sample_size,
            documentation_path=originals / "nhanes" / "GLU_J.htm",
        ),
        "ton-iot": parse_ton_iot_unavailable(
            originals / "toniot" / "official-project-page.html",
            root=root,
        ),
        "unsw-nb15": parse_unsw_nb15(
            unsw_sample,
            root=root,
            source_files=unsw_sources,
            sampling_metadata=unsw_sampling,
        ),
        "world-bank-wdi": parse_world_bank_wdi(root),
        "nist-nvd": parse_nist_nvd(root),
        "cic-ids2017": parse_cic_ids2017(
            originals / "cic_ids2017" / "ids-2017.html",
            root=root,
            sample_csv=cic_sample,
            sample_csv_url=(
                f"https://huggingface.co/datasets/c01dsnap/CIC-IDS2017/tree/{cic_revision}"
            ),
            sample_size=50_000,
            source_csv_paths=cic_csvs,
            sampling_metadata=cic_sampling,
            dataset_card_path=originals / "cic_ids2017" / "dataset-card.md",
        ),
    }
    for path in sorted((originals / "sec" / "companyfacts").glob("*.json")):
        cik = path.stem.split("_", 1)[0]
        output[f"sec-companyfacts-{cik}"] = parse_sec_companyfacts(
            path,
            root=root,
            documentation_path=originals / "sec" / "api-documentation.html",
        )
    return output


def validate_metadata(metadata: dict[str, Any], schema_path: Path) -> None:
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError as error:
        raise RuntimeError("JSON metadata validation requires jsonschema; install requirements.txt") from error
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(metadata),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise ValueError(f"metadata schema validation failed at {location}: {error.message}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--sample-size", type=int, default=1000)
    args = parser.parse_args()
    if args.sample_size < 1:
        parser.error("--sample-size must be positive")
    output_dir = args.output_dir or args.root / "data" / "metadata"
    output_dir.mkdir(parents=True, exist_ok=True)
    schema_path = args.root / "data" / "metadata.schema.json"
    for dataset_id, metadata in build_metadata(args.root, sample_size=args.sample_size).items():
        validate_metadata(metadata, schema_path)
        output_path = output_dir / f"{dataset_id}.json"
        output_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
