"""One-step, no-network SEC 10-K -> frozen B13.13 candidate -> matched A/B/C pilot.

Uses B13.14/15 verified source bytes; one pre-inspected human-curated accounting
hypothesis; no discovery claim, human gold, or treatment-effect estimate.
"""
from __future__ import annotations

import json
from pathlib import Path
from collections import Counter

from src.b13_13_matched_pilot import (
    STUDY, PHASE, PilotError, freeze, run_matched, sha256_file, exclusive_json
)
from src.b13_14_sec_intake import assert_external_cache
from src.b13_15_sec_filing_context_audit import (
    verify as verify_b1315, InlineAuditParser, RAW, AUDIT, PAIR, EXPECTED_DATE,
    EXPECTED_URL, CIK,
)

EXPECTED_ORIGINAL_SHA256 = '5d69c4eeb95ed560ed1300d993c94a9dd2017398566abe509bc2d186cf4b2cbc'
FILES = ('candidate_packet.json', 'frozen_input_lock.json', 'blinded_review_packet.json',
         'matched_A_B_C.json', 'MANUSCRIPT_SEC_PILOT.md')


def audited_pair(data: bytes, aggregate: dict) -> tuple[str,str]:
    """Identify exactly one unambiguous target pair; do not extract monetary values."""
    parser = InlineAuditParser()
    parser.feed(data.decode('utf-8', errors='replace'))
    parser.close()
    parser.finish()
    if parser.repeated_context_ids or parser.duplicate_unit_names:
        raise PilotError('Ambiguous XBRL contexts, units, or missing references')
    possible = []
    by_key = Counter()
    for f in parser.facts:
        context = parser.contexts.get(f['context'])
        unit = parser.units.get(f['unit'])
        if not context or not unit or f['concept'] not in PAIR or f['nil']:
            continue
        cik = context['entity_identifier'].strip().lstrip('0') or '0'
        usd = not unit['complex'] and unit['measure'].strip().lower() in ('iso4217:usd','usd')
        if (cik == str(int(CIK)) and context['instant'].strip() == EXPECTED_DATE
                and not context['dimensional_markup'] and usd):
            by_key[(f['context'],f['unit'],f['concept'])] += 1
    keys = {(ctx,u) for ctx,u,_ in by_key}
    for ctx,u in sorted(keys):
        if by_key[(ctx,u,PAIR[0])] == by_key[(ctx,u,PAIR[1])] == 1:
            possible.append((ctx,u))
    if (len(possible) != 1 or aggregate.get('same_context_same_unit_target_pair_instances') != 1
            or aggregate.get('target_pair_ambiguous_duplicate_instances') != 0
            or aggregate.get('structural_opportunity_count') != 1
            or aggregate.get('numeric_ix_fact_count') != len(parser.facts)):
        raise PilotError('Source does not contain the expected single unambiguous accounting opportunity')
    return possible[0]


def make_packet(cache: Path, root: Path, *, aggregate: dict, context_id: str, unit_id: str) -> dict:
    source = (cache / RAW).resolve()
    raw_sha = sha256_file(source)
    if raw_sha != EXPECTED_ORIGINAL_SHA256 or aggregate['source_filing_sha256'] != raw_sha:
        raise PilotError('Original SEC source changed from the previously verified filing')
    cid = 'CMG_2025_BALANCE_SHEET_TOTAL_DEV_PILOT'
    keys = ['cik', 'report_date', 'context_ref', 'unit_ref']
    actual_context = dict(zip(keys, [CIK, EXPECTED_DATE, context_id, unit_id]))
    proposal = {
        'proposal_version':'metaverify-proposal-v0.1',
        'id':cid,
        'dataset_id':'sec_cmg_2025_10k_inline_xbrl',
        'origin':'human_curated_preinspected_balance_sheet_hypothesis_not_new_discovery',
        'assertions':[{'left':{'column':'Assets'},'op':'eq',
                       'right':{'column':'LiabilitiesAndStockholdersEquity'}}],
        'context_keys':keys,
    }
    candidate = {
        'candidate_id':cid,
        'domain':'finance',
        'source_group':'sec_cik_0001058090_2025_10k',
        'source_file':str(source),
        'source_sha256':raw_sha,
        'source_evidence_url':EXPECTED_URL,
        'source_evidence_locator':'2025-12-31 consolidated balance-sheet inline-XBRL target concepts (scope not independently adjudicated)',
        'prior_exposure':'previously_inspected',
        'proposal':proposal,
        'allowed_columns':['Assets','LiabilitiesAndStockholdersEquity'],
        'parameter_registry':{},
        'source_context_policy':{
            'required_context_keys':keys,
            'required_when':None,
            'context_review':'unknown',
            'applicability_review':'unknown',
            'source_eligibility_review':'unknown',
            'reviewer_id':'NO_INDEPENDENT_SOURCE_REVIEW_YET',
            'basis_url':EXPECTED_URL,
            'basis_locator':'matching dimensionless instant and USD context; no independent semantic review',
        },
        'policy_evidence':{
            'metadata':'supported',   # solely the B13.15 co-location observation
            'documentary':{'status':'unknown','verified':False,'evidence_url':'','evidence_locator':''},
            'context_evidence':{k:'unknown' for k in keys},
            'curator_id':'AUTOMATED_B13_15_STRUCTURAL_CURATOR',
        },
        'field_context_by_column':{
            'Assets':dict(actual_context),
            'LiabilitiesAndStockholdersEquity':dict(actual_context),
        },
    }
    return {'study_id':STUDY,'phase':PHASE,'candidates':[candidate]}


def render_summary(report: dict, lock: dict, aggregate: dict) -> str:
    row=report['outcomes'][0]
    return f'''# MetaVerify SEC 10-K — deadline-day engineering diagnostic

- Source: Chipotle Mexican Grill 2025 10-K, accession `0001058090-26-000009`, filed 2026-02-04.
- Original SEC HTML SHA-256: `{EXPECTED_ORIGINAL_SHA256}`.
- Structural audit: {aggregate['xbrl_context_count']} contexts; {aggregate['numeric_ix_fact_count']} numeric inline facts; 1 matched context/unit opportunity.
- B4 compilation status: `{row['b4_status']}`; B3 schema validation through the B13.13 adapter.
- Same pre-inspected human-curated candidate, identical compilation used in arms A/B/C.
- Decisions: A **{row['A']}**, B **{row['B']}**, C **{row['C']}**.
- C reason: `{row['reasons']['C']}`.
- Frozen candidate hash: `{lock['input_canonical_sha256']}`.

**Limitations:** Single already screened issuer/filing and one previously inspected accounting relationship; B13.15 checked only co-location of numeric facts, not actual monetary values. No B3 row-value verification, independent accountant/source reviews, gold labels, uncertainty intervals, or evidence-gate benefit estimate. Arm B uses mechanically observed metadata; Arm C must abstain until independently justified documentary/context evidence is supplied. This is an engineering integration demonstration, **not** an independently evaluated constraint-discovery result. Keep the existing B13.7–B13.12 results as the manuscript's completed retrospective experiments.
'''


def run(cache_dir: Path, repo_root: Path) -> tuple[dict, list[Path]]:
    cache=assert_external_cache(cache_dir,repo_root)
    plan=json.loads((repo_root/'data/evaluation/b13_14_sec_intake_plan_v1.json').read_text(encoding='utf-8'))
    development=json.loads((repo_root/'data/sources.json').read_text(encoding='utf-8'))
    aggregate=verify_b1315(cache,repo_root,plan,development)
    data=(cache/RAW).read_bytes()
    context_id,unit_id=audited_pair(data,aggregate)
    packet=make_packet(cache,repo_root,aggregate=aggregate,context_id=context_id,unit_id=unit_id)
    lock,blind=freeze(packet,repo_root)
    report=run_matched(packet,lock,repo_root)
    if (report['candidate_count'] != 1 or report['compiler_invocations'] != 1
            or report['arm_counts'] != {'A':{'admit':1,'abstain':0,'block':0},
                                       'B':{'admit':1,'abstain':0,'block':0},
                                       'C':{'admit':0,'abstain':1,'block':0}}):
        raise PilotError('Unexpected matched gate decisions; fail closed')
    out=cache/'CMG_Deadline_Pilot'
    targets=[out/n for n in FILES]
    if any(path.exists() for path in targets):
        raise PilotError('Output already exists; refusing overwrite (check existing CMG_Deadline_Pilot folder)')
    out.mkdir(parents=True,exist_ok=True)
    created=[]
    try:
        for path, content in zip(targets, [packet,lock,blind,report,render_summary(report,lock,aggregate)]):
            if isinstance(content,dict):
                exclusive_json(path,content)
            else:
                with path.open('x',encoding='utf-8') as stream: stream.write(content)
            created.append(path)
    except BaseException:
        for file in created: file.unlink(missing_ok=True)
        raise
    return report,targets
