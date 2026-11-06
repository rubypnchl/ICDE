"""Resolve SEC balance-sheet identities from existing facts and documented evidence."""

from __future__ import annotations

import argparse
import itertools
import json
import re
import time
from pathlib import Path
from typing import Any

from src.rule_discovery import _number, _sec_rows


MIN_DISCOVERY_SUPPORT = 2
REGISTRY_RULE_ID = "SEC-BALANCE-001"


def _label(concept: dict[str, Any]) -> str:
    return str(concept.get("label") or "").casefold()


def _role_candidates(payload: dict[str, Any]) -> tuple[list[str], list[str], list[str], list[str]]:
    facts = payload.get("facts", {}).get("us-gaap", {})
    assets = []
    liabilities = []
    equities = []
    optional = []
    for tag, concept in facts.items():
        label = _label(concept)
        if re.search(r"\bassets\b", label) and not re.search(r"liabilities|income|expense", label):
            if label.strip() in {"assets", "total assets"}:
                assets.append(tag)
        if "liabilit" in label and not re.search(r"and (stockholders|shareholders|equity)", label):
            if label.strip() in {"liabilities", "total liabilities"}:
                liabilities.append(tag)
        if any(term in label for term in ("equity", "stockholders' equity", "shareholders' equity", "partners' capital", "members' equity")):
            if not any(term in label for term in ("equity method", "share-based", "stock option", "investment", "income")):
                equities.append(tag)
        if (
            ("noncontrolling interest" in label or "minority interest" in label
             or "temporary equity" in label or "redeemable equity" in label)
            and not any(term in label for term in ("income", "loss", "earnings"))
        ):
            optional.append(tag)
    return sorted(set(assets)), sorted(set(liabilities)), sorted(set(equities)), sorted(set(optional))


def _registry_match(expression: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any] | None:
    result = f"{expression['assets']} [{expression['unit']}]"
    terms = [f"{tag} [{expression['unit']}]" for tag in [expression["liabilities"], *expression["equity_terms"]]]
    for entry in registry.get("entries", []):
        assertion = entry.get("assertion", {})
        if (
            assertion.get("op") == "sum_eq"
            and assertion.get("result_column") == result
            and sorted(assertion.get("term_columns", [])) == sorted(terms)
            and _number(assertion.get("tolerance", 0)) == 0
        ):
            return {
                "id": entry.get("id"),
                "source_url": entry.get("source_url"),
                "authority": entry.get("authority"),
                "requirements": entry.get("requirements", []),
            }
    return None


def _semantic_score(tags: list[str], concepts: dict[str, Any]) -> int:
    return sum(
        2 if any(marker in _label(concepts[tag]) for marker in
                 ("stockholders' equity", "shareholders' equity", "total equity", "equity attributable"))
        else 1
        for tag in tags
    )


def _naive_expression(
    payload: dict[str, Any],
    discovery_rows: list[dict[str, Any]],
    registry: dict[str, Any],
) -> dict[str, Any] | None:
    assets_tags, liability_tags, equity_tags, _ = _role_candidates(payload)

    assets_tags = [t for t in assets_tags if t == "Assets"]
    liability_tags = [t for t in liability_tags if t == "Liabilities"]
    equity_tags = [t for t in equity_tags if t == "StockholdersEquity"]

    concepts = payload.get("facts", {}).get("us-gaap", {})
    options = []
    for unit in sorted({str(row["unit"]) for row in discovery_rows}):
        for assets, liabilities, equity in itertools.product(assets_tags, liability_tags, equity_tags):
            complete = [
                row for row in discovery_rows
                if str(row["unit"]) == unit
                and all(_number(row.get(tag)) is not None for tag in (assets, liabilities, equity))
            ]
            if len(complete) < MIN_DISCOVERY_SUPPORT:
                continue
            expression = {
                "assets": assets,
                "liabilities": liabilities,
                "equity_terms": [equity],
                "unit": unit,
            }
            options.append(expression)
    if not options:
        return None
    selected = min(options, key=lambda expression: (
        -_semantic_score(expression["equity_terms"], concepts),
        expression["assets"],
        expression["liabilities"],
        expression["equity_terms"][0],
        expression["unit"],
    ))
    citation = _registry_match(selected, registry)
    return {
        "expression": selected,
        "classification": "documented" if citation else "statistically_discovered",
        "evidence": citation,
    }


def _select_statistical(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    return max(candidates, key=lambda item: (
        item["discovery"]["match_rate"],
        -item["complexity"],
        item["discovery"]["contexts"],
        item["expression"]["assets"],
        *item["expression"]["equity_terms"],
    ))


def _taxonomy_component_role(tag: str, concepts: dict[str, Any]) -> str | None:
    concept = concepts.get(tag, {})
    label = _label(concept)
    definition = str(concept.get("description") or "").casefold()
    text = f"{label} {definition}"
    if "temporary equity" in label or "redeemable noncontrolling interest" in label:
        return "temporary_equity"
    if re.search(r"attributable to both (?:the )?parent and noncontrolling interests", text):
        return "parent_and_nci_equity"
    if (
        "attributable to noncontrolling interest" in label
        or "attributable to noncontrolling interest" in definition
        or "not attributable to the parent" in definition
    ):
        return "nci_equity"
    if "attributable to the parent" in text:
        return "parent_equity"
    if label.strip() in {"assets", "total assets"} and "all assets" in definition:
        return "assets"
    if label.strip() in {"liabilities", "total liabilities"} and "all liabilities" in definition:
        return "liabilities"
    return None


def _semantic_component_evidence(
    expression: dict[str, Any],
    concepts: dict[str, Any],
    discovery_rows: list[dict[str, Any]],
    cik: Any,
) -> dict[str, Any] | None:
    if (
        _taxonomy_component_role(expression["assets"], concepts) != "assets"
        or _taxonomy_component_role(expression["liabilities"], concepts) != "liabilities"
    ):
        return None

    term_roles = {
        tag: _taxonomy_component_role(tag, concepts)
        for tag in expression["equity_terms"]
    }
    if any(role not in {"parent_equity", "nci_equity", "parent_and_nci_equity", "temporary_equity"}
           for role in term_roles.values()):
        return None

    primary = [tag for tag, role in term_roles.items() if role != "temporary_equity"]
    temporary = [tag for tag, role in term_roles.items() if role == "temporary_equity"]
    primary_roles = [term_roles[tag] for tag in primary]
    covers_parent_nci = (
        primary_roles.count("parent_and_nci_equity") == 1 and len(primary_roles) == 1
    ) or (
        primary_roles.count("parent_equity") == 1
        and primary_roles.count("nci_equity") == 1
        and len(primary_roles) == 2
    )
    if not covers_parent_nci:
        return None

    potential_temporary = [
        tag for tag in concepts
        if _taxonomy_component_role(tag, concepts) == "temporary_equity"
        and any(_number(row.get(tag)) not in (None, 0) for row in discovery_rows)
    ]
    if len(potential_temporary) > 1:
        return None
    if set(potential_temporary) != set(temporary):
        return None

    padded_cik = str(cik or "").zfill(10)
    source_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{padded_cik}.json"
    components = [expression["assets"], expression["liabilities"], *expression["equity_terms"]]
    evidence = []
    for tag in components:
        definition = concepts[tag].get("description")
        if not definition:
            return None
        evidence.append({
            "taxonomy": "us-gaap",
            "concept": tag,
            "role": _taxonomy_component_role(tag, concepts),
            "definition": definition,
            "source_url": source_url,
            "source_field": f"facts.us-gaap.{tag}.description",
        })
    return {
        "basis": "pre-evaluation embedded US-GAAP taxonomy component definitions",
        "components": evidence,
    }


def _select_semantic_evidence(
    candidates: list[dict[str, Any]],
    concepts: dict[str, Any],
    discovery_rows: list[dict[str, Any]],
    cik: Any = None,
) -> dict[str, Any] | None:
    compatible = []
    for candidate in candidates:
        evidence = _semantic_component_evidence(
            candidate["expression"], concepts, discovery_rows, cik,
        )
        if evidence is not None:
            compatible.append((candidate, evidence))
    if not compatible:
        return None
    best_complexity = min(candidate["complexity"] for candidate, _ in compatible)
    best = [
        (candidate, evidence)
        for candidate, evidence in compatible
        if candidate["complexity"] == best_complexity
    ]
    expressions = {
        json.dumps(candidate["expression"], sort_keys=True)
        for candidate, _ in best
    }
    if len(expressions) != 1:
        return None
    candidate, evidence = best[0]
    return {**candidate, "semantic_evidence": evidence}


def _expression_candidates(
    payload: dict[str, Any],
    discovery_rows: list[dict[str, Any]],
    registry: dict[str, Any],
    *,
    min_support: int = MIN_DISCOVERY_SUPPORT,
) -> list[dict[str, Any]]:
    assets_tags, liability_tags, equity_tags, optional_tags = _role_candidates(payload)
    concepts = payload.get("facts", {}).get("us-gaap", {})
    candidates = []
    for unit in sorted({str(row["unit"]) for row in discovery_rows}):
        unit_rows = [row for row in discovery_rows if str(row["unit"]) == unit]
        for assets, liabilities, equity in itertools.product(assets_tags, liability_tags, equity_tags):
            if len({assets, liabilities, equity}) != 3:
                continue
            equity_role = _taxonomy_component_role(equity, concepts)
            extras = [
                tag for tag in optional_tags
                if tag not in {assets, liabilities, equity}
                and not (
                    equity_role == "parent_and_nci_equity"
                    and _taxonomy_component_role(tag, concepts) == "nci_equity"
                )
            ]
            extra_options = [()]
            extra_options += [(tag,) for tag in extras]
            extra_options += list(itertools.combinations(extras, 2))
            for extras in extra_options:
                terms = [liabilities, equity, *extras]
                if len(set(terms)) != len(terms):
                    continue
                complete = [
                    row for row in unit_rows
                    if all(_number(row.get(tag)) is not None for tag in [assets, *terms])
                ]
                if len(complete) < min_support:
                    continue
                matches = sum(
                    _number(row[assets]) == sum((_number(row[tag]) for tag in terms), start=0)
                    for row in complete
                )
                semantic = _semantic_score([equity, *extras], concepts)
                expression = {
                    "assets": assets,
                    "liabilities": liabilities,
                    "equity_terms": [equity, *extras],
                    "unit": unit,
                }
                citation = _registry_match(expression, registry)
                candidates.append({
                    "expression": expression,
                    "classification": "documented" if citation else "statistically_discovered",
                    "evidence": citation,
                    "discovery": {
                        "contexts": len(complete),
                        "matches": matches,
                        "match_rate": matches / len(complete),
                    },
                    "semantic_score": semantic,
                    "complexity": len(terms),
                })
    candidates.sort(key=lambda item: (
        item["discovery"]["match_rate"],
        item["evidence"] is not None,
        item["semantic_score"],
        -item["complexity"],
        item["discovery"]["contexts"],
        item["expression"]["assets"],
        *item["expression"]["equity_terms"],
    ), reverse=True)
    for rank, candidate in enumerate(candidates, 1):
        candidate["rank"] = rank
    return candidates


def _identity_holds(expression: dict[str, Any], row: dict[str, Any]) -> bool | None:
    tags = [expression["assets"], expression["liabilities"], *expression["equity_terms"]]
    values = [_number(row.get(tag)) for tag in tags]
    if any(value is None for value in values):
        return None
    return values[0] == sum(values[1:], start=0)


def _evaluate_expression(
    expression: dict[str, Any],
    rows: list[dict[str, Any]],
    documented_expression: dict[str, Any] | None = None,
) -> dict[str, Any]:
    eligible = [row for row in rows if str(row.get("unit")) == expression["unit"]]
    results = [_identity_holds(expression, row) for row in eligible]
    evaluated = [result for result in results if result is not None]
    abstentions = len(results) - len(evaluated)
    false_alarms = 0
    documented_contexts = 0
    if documented_expression is not None:
        for row, result in zip(eligible, results):
            independent = (
                _identity_holds(documented_expression, row)
                if str(row.get("unit")) == documented_expression["unit"] else None
            )
            if independent is True:
                documented_contexts += 1
                false_alarms += result is False
    return {
        "eligible_contexts": len(eligible),
        "evaluated_contexts": len(evaluated),
        "violations": sum(result is False for result in evaluated),
        "abstentions": abstentions,
        "coverage": len(evaluated) / len(eligible) if eligible else 0.0,
        "false_alarms_against_documented_identity": false_alarms,
        "documented_identity_contexts": documented_contexts,
    }


def _abstention_evaluation(row_count: int) -> dict[str, Any]:
    return {
        "eligible_contexts": row_count,
        "evaluated_contexts": 0,
        "violations": 0,
        "abstentions": row_count,
        "coverage": 0.0,
        "false_alarms_against_documented_identity": 0,
        "documented_identity_contexts": 0,
    }


def _entity_result(path: Path, payload: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    rows = _sec_rows(payload)
    discovery = [row for row in rows if "2020" <= str(row["end"])[:4] <= "2023"]
    heldout = [row for row in rows if "2024" <= str(row["end"])[:4] <= "2025"]

    naive_started = time.perf_counter()
    naive = _naive_expression(payload, discovery, registry)
    naive_selection_runtime = time.perf_counter() - naive_started
    doc_entry = next(
        (entry for entry in registry.get("entries", []) if entry.get("id") == REGISTRY_RULE_ID),
        None,
    )
    documented_expression = None
    if doc_entry:
        assertion = doc_entry["assertion"]
        documented_expression = {
            "assets": assertion["result_column"].rsplit(" [", 1)[0],
            "liabilities": next(
                (term.rsplit(" [", 1)[0] for term in assertion["term_columns"]
                 if "liabilit" in term.casefold()), ""),
            "equity_terms": [
                term.rsplit(" [", 1)[0] for term in assertion["term_columns"]
                if "liabilit" not in term.casefold()
            ],
            "unit": assertion["result_column"].rsplit(" [", 1)[-1].rstrip("]"),
        }
    statistical_started = time.perf_counter()
    candidates = _expression_candidates(payload, discovery, registry)
    statistical = _select_statistical(candidates)
    statistical_selection_runtime = time.perf_counter() - statistical_started
    semantic_started = time.perf_counter()
    concepts = payload.get("facts", {}).get("us-gaap", {})
    semantic = _select_semantic_evidence(
        candidates, concepts, discovery, payload.get("cik"),
    )
    semantic_selection_runtime = time.perf_counter() - semantic_started
    selected = {
        "naive": naive,
        "statistical_only": statistical,
        "semantic_evidence": semantic,
    }
    naive_eval_started = time.perf_counter()
    naive_evaluation = (
        _evaluate_expression(naive["expression"], heldout, documented_expression=documented_expression)
        if naive else _abstention_evaluation(len(heldout))
    )
    naive_evaluation_runtime = time.perf_counter() - naive_eval_started
    comparisons = {}
    timings = {}
    for method, candidate in selected.items():
        selection_runtime = {
            "naive": naive_selection_runtime,
            "statistical_only": statistical_selection_runtime,
            "semantic_evidence": statistical_selection_runtime + semantic_selection_runtime,
        }[method]
        evaluation_started = time.perf_counter()
        evaluation = (
            _evaluate_expression(
                candidate["expression"], heldout,
                documented_expression=documented_expression,
            )
            if candidate else _abstention_evaluation(len(heldout))
        )
        evaluation_runtime = time.perf_counter() - evaluation_started
        if method == "naive":
            evaluation_runtime = naive_evaluation_runtime
            evaluation = naive_evaluation
        comparisons[method] = {
            **evaluation,
            "selection_runtime_seconds": selection_runtime,
            "evaluation_runtime_seconds": evaluation_runtime,
            "total_runtime_seconds": selection_runtime + evaluation_runtime,
            "selected_formula": candidate["expression"] if candidate else None,
            "classification": (
                "taxonomy_component_evidence"
                if method == "semantic_evidence" and candidate
                else candidate["classification"] if candidate else "abstain_no_candidate"
            ),
            "evidence": (
                candidate.get("semantic_evidence") if method == "semantic_evidence" and candidate
                else candidate["evidence"] if candidate else None
            ),
        }
        timings[method] = selection_runtime + evaluation_runtime
    return {
        "source_file": path.as_posix(),
        "entity": payload.get("cik"),
        "status": "ok" if candidates else "abstain_no_candidate",
        "discovery_contexts_2020_2023": len(discovery),
        "evaluation_contexts_2024_2025": len(heldout),
        "shared_heldout_context_count": len(heldout),
        "candidate_count": len(candidates),
        "ranked_candidates": candidates[:10],
        "ablation_methods": {
            "naive": "minimum semantically labeled one-equity expression; no empirical-fit ranking",
            "statistical_only": "highest 2020-2023 match rate, then minimum complexity; evidence ignored",
            "semantic_evidence": "pre-evaluation US-GAAP component definitions require complete parent/NCI and disclosed temporary-equity composition; generic identity evidence is ignored; abstains on incomplete or ambiguous components",
        },
        "evaluation_2024_2025": comparisons,
        "runtime_seconds": timings,
    }


def run_resolution(root: Path) -> dict[str, Any]:
    root = root.resolve()
    registry_path = root / "data" / "evidence" / "sec_constraints.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    source_dir = root / "data" / "originals" / "sec" / "companyfacts"
    reports = [
        _entity_result(path.relative_to(root), json.loads(path.read_text(encoding="utf-8")), registry)
        for path in sorted(source_dir.glob("*.json"))
    ]
    return {
        "module": "SEC automatic accounting-constraint resolution",
        "method": {
            "discovery_period": "2020-2023",
            "evaluation_period": "2024-2025",
            "context_key": ["entity", "accession", "reporting date", "form", "unit"],
            "missing_or_ambiguous": "abstain; excluded from passes",
            "ranking": "component-level taxonomy semantic compatibility and minimum expression complexity; only 2020-2023 discovery contexts are used",
            "status_labels": "only exact evidence-registry matches are documented; all other formulas are statistical candidates",
            "violation_semantics": "observed equation mismatches, not adjudicated data errors; statistical candidates remain unverified",
        },
        "entities": reports,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("data/sec-constraint-resolution.json"))
    args = parser.parse_args()
    report = run_resolution(args.root)
    output = args.root / args.output if not args.output.is_absolute() else args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
