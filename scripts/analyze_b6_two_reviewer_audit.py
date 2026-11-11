"""Read-only B6 two-reviewer semantic audit from original Excel ZIP archives.

NO adjudicated reference truth, A/B/C outcome, published SOTA comparison,
or natural-error precision/recall is inferred. Raw reviewer workbooks stay outside Git.

python scripts/analyze_b6_two_reviewer_audit.py --reviewer1 <Reviewer_1.zip> \
    --reviewer2 <Reviewer_2.zip> [--output <external-report.json>]

Uses Python 3.10+ standard library only; reads the XLSX container's first sheet.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
N = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
DOMAINS = ('cybersecurity', 'finance', 'healthcare', 'manufacturing')
DECISIONS = {
    'Supported': 'supported',
    'Supported with conditions': 'conditional',
    'Not supported': 'unsupported',
    'Not supported as written': 'unsupported',
    'Needs more evidence': 'unresolved',
}
REVIEW_FIELDS = {'reviewer_id', 'decision', 'evidence_url', 'evidence_locator', 'rationale'}
MAX_XLSX_BYTES = 3_000_000


class ReviewError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise ReviewError(message)


def first_sheet_rows(xlsx_content: bytes) -> list[dict[str, str]]:
    """Minimal, deliberately restricted reader of simple flat .xlsx review sheets."""
    require(len(xlsx_content) <= MAX_XLSX_BYTES, 'Oversized review workbook')
    with ZipFile(io.BytesIO(xlsx_content)) as wb:
        require('xl/worksheets/sheet1.xml' in wb.namelist(), 'First worksheet missing')
        shared = []
        if 'xl/sharedStrings.xml' in wb.namelist():
            strings = ET.fromstring(wb.read('xl/sharedStrings.xml'))
            shared = [''.join(t.text or '' for t in item.iter(N+'t')) for item in strings.findall(N+'si')]
        root = ET.fromstring(wb.read('xl/worksheets/sheet1.xml'))
        result = []
        for row in root.findall('.//'+N+'sheetData/'+N+'row'):
            values = {}
            for cell in row.findall(N+'c'):
                address = cell.get('r', '')
                m = re.fullmatch(r'([A-Z]+)\d+', address)
                require(m is not None, 'Invalid Excel cell address')
                index = 0
                for letter in m.group(1):
                    index = index*26 + (ord(letter)-64)
                index -= 1
                typ = cell.get('t')
                val = cell.find(N+'v')
                if typ == 's':
                    require(val is not None and val.text is not None, 'Missing shared-string index')
                    ix = int(val.text)
                    require(0 <= ix < len(shared), 'Bad shared-string index')
                    text = shared[ix]
                elif typ == 'inlineStr':
                    text = ''.join(t.text or '' for t in cell.findall('.//'+N+'t'))
                else:
                    text = val.text if val is not None and val.text is not None else ''
                if text.strip():
                    values[index] = text
            if values:
                result.append(values)
    require(len(result) >= 2, 'Review sheet needs header and observations')
    heads = [result[0].get(i, '').strip() for i in range(max(result[0])+1)]
    require(len(heads) == len(set(heads)) and all(heads), 'Empty or duplicate review headers')
    rows = [{heads[k]:v for k,v in r.items() if k<len(heads) and v.strip()} for r in result[1:]]
    rows = [r for r in rows if r.get('reference_id')]
    require(rows, 'No review entries in sheet')
    return rows


def read_review_bundle(path: Path, reviewer_number: int) -> dict:
    require(path.is_file(), f'Reviewer {reviewer_number} archive not found')
    result = {}
    with ZipFile(path) as bundle:
        for domain in DOMAINS:
            for kind in ('cases','rules'):
                basename = f'reviewer_{reviewer_number}_{domain}_{kind}'
                matches = [m for m in bundle.namelist()
                           if Path(m).name in (basename+'.xlsx', basename+'.csv.xlsx')]
                require(len(matches) == 1, f'Expected exactly one {basename} workbook')
                zinfo = bundle.getinfo(matches[0])
                require(0 < zinfo.file_size <= MAX_XLSX_BYTES, 'Unexpected workbook size')
                rows = first_sheet_rows(bundle.read(matches[0]))
                for row in rows:
                    require(row.get('reviewer_id') == f'Rev_{reviewer_number}',
                            f'Unexpected reviewer ID in {basename}')
                    require(row.get('reference_id') and row.get('decision'),
                            f'Missing reviewer vote or candidate in {basename}')
                result[(domain,kind)] = rows
    return result


def case_key(domain: str, row: dict) -> tuple:
    if domain == 'finance':
        fields = ('reference_id', 'source_sha256', 'CIK', 'accession', 'reporting_end', 'unit')
    elif domain == 'manufacturing':
        fields = ('reference_id','source_sha256','UDI','case')
    else:
        fields = ('reference_id','source_sha256','source_data_row_1based','row_sha256')
    key = tuple(row.get(x,'') for x in fields)
    require(all(key), f'Incomplete case key for {domain}')
    return key


def unique(rows: list[dict], domain: str, *, kind: str) -> dict:
    keys = [(r['reference_id'],) if kind == 'rules' else case_key(domain, r) for r in rows]
    require(len(keys) == len(set(keys)), f'Duplicate {domain} {kind} identity')
    return dict(zip(keys, rows))


def public_id(domain: str, row: dict) -> dict:
    out = {'reference_id':row['reference_id']}
    if domain == 'finance':
        out.update({k:row.get(k) for k in ('CIK','accession','reporting_end')})
    elif domain == 'manufacturing':
        out['UDI']=row.get('UDI');out['case']=row.get('case')
    else:
        out['source_data_row_1based']=row.get('source_data_row_1based')
    return out


def compare_case_bases(x: dict, y: dict) -> list[str]:
    return sorted(k for k in (set(x)|set(y))-REVIEW_FIELDS if x.get(k,'') != y.get(k,''))


def evaluate_review_bundles(a: dict, b: dict) -> dict:
    rule_rows=[]
    case_domains={}
    mismatches=[]
    unpaired=[]
    counts=Counter()
    for domain in DOMAINS:
        ra=unique(a[(domain,'rules')],domain,kind='rules')
        rb=unique(b[(domain,'rules')],domain,kind='rules')
        require(set(ra)==set(rb),f'Rule candidate set differs in {domain}')
        for key in sorted(ra):
            x,y=ra[key],rb[key]
            require(not compare_case_bases(x,y),f'Rule specification differs in {domain}/{key[0]}')
            require(x['decision'] in DECISIONS and y['decision'] in DECISIONS,
                    f'Unrecognised decision; manual adjudication needed for {key[0]}')
            d1,d2=DECISIONS[x['decision']],DECISIONS[y['decision']]
            rule_rows.append({'reference_id':key[0], 'domain':domain,
                             'reviewer1':d1, 'reviewer2':d2,
                             'exact_category_agreement': d1==d2})
        ca=unique(a[(domain,'cases')],domain,kind='cases')
        cb=unique(b[(domain,'cases')],domain,kind='cases')
        require(set(x['reference_id'] for x in ca.values()).issubset({key[0] for key in ra}),
                'Unknown case rule ID reviewer 1')
        require(set(x['reference_id'] for x in cb.values()).issubset({key[0] for key in rb}),
                'Unknown case rule ID reviewer 2')
        common=set(ca)&set(cb)
        identical=[]
        for key in sorted(common):
            x,y=ca[key],cb[key]
            diffs=compare_case_bases(x,y)
            if diffs:
                mismatches.append({'domain':domain,'case':public_id(domain,x),
                                   'changed_source_fields':diffs})
            else:identical.append((x,y))
        for key in sorted(set(ca)^set(cb)):
            row = ca[key] if key in ca else cb[key]
            unpaired.append({'domain':domain,'reviewer_present':1 if key in ca else 2,
                             'case':public_id(domain,row)})
        counts['reviewer1_cases']+=len(ca)
        counts['reviewer2_cases']+=len(cb)
        counts['matched_case_ids']+=len(common)
        counts['identical_case_inputs']+=len(identical)
        case_domains[domain]={'reviewer1':len(ca),'reviewer2':len(cb),
                              'matched_id':len(common),'identical_source_values':len(identical),
                              'source_value_mismatches':len(common)-len(identical),
                              'only_reviewer1':len(set(ca)-set(cb)),
                              'only_reviewer2':len(set(cb)-set(ca))}
        if domain=='cybersecurity':
            require(all(x['decision']=='No discrepancy (rule satisfied)' and
                        y['decision']=='No discrepancy found. Rule satisfied' for x,y in identical),
                    'Cybersecurity case language changed; inspect manually')
            case_domains[domain]['both_no_observed_discrepancy']=len(identical)
        elif domain=='healthcare':
            require(all(x['decision']=='Unclear' and y['decision']=='Unclear' for x,y in identical),
                    'Healthcare case language changed; inspect manually')
            case_domains[domain]['both_unclear']=len(identical)
        elif domain=='manufacturing':
            forward=[(x,y) for x,y in identical if x.get('case')=='forward_frozen_rule_violation']
            reverse=[(x,y) for x,y in identical if x.get('case')=='reverse_exploratory_only_not_frozen_rule']
            require(len(forward)+len(reverse)==len(identical),'Unexpected manufacturing stratum')
            require(all(x['decision']=='Genuine discrepancy' and y['decision']=='Documented-rule conflict; cause unresolved' for x,y in forward),'Unexpected forward-case judgements')
            require(all(x['decision']=='Unclear' and y['decision']=='Not a violation of the one-way rule' for x,y in reverse),'Unexpected reverse-case judgements')
            case_domains[domain]['both_identify_forward_rule_conflict_but_cause_disputed']=len(forward)
            case_domains[domain]['unclear_vs_not_a_one_way_violation']=len(reverse)
        elif domain=='finance':
            crosswalk = {
               'No numerical discrepancy (scope unverified)': 'arithmetically_consistent_scope_unresolved',
               'Numerical match; filing context not fully verified':'arithmetically_consistent_scope_unresolved',
               'Numerical match; not universal evidence':'arithmetically_consistent_scope_unresolved',
               'Explainable exception':'documented_exception',
               'Explained by noncontrolling interests':'documented_exception',
               'Explained by noncontrolling and redeemable interests':'documented_exception',
               'Worksheet precision difference; SEC filing balances':'worksheet_precision_difference',
            }
            require(all(x['decision'] in crosswalk and y['decision'] in crosswalk for x,y in identical),
                    'Unexpected finance case judgements')
            case_domains[domain]['same_coarse_observation']=sum(crosswalk[x['decision']]==crosswalk[y['decision']] for x,y in identical)
            case_domains[domain]['distinct_coarse_observation']=sum(crosswalk[x['decision']]!=crosswalk[y['decision']] for x,y in identical)
    require(len(rule_rows)==5,'Expected five frozen B6 proposals; review protocol changed')
    return {'study':'metaverify_b6_two_reviewer_document_audit_v1',
        'scope':'previously_inspected_B6_cases_no_adjudicated_gold_no_matched_B13_gate_or_SOTA',
        'rule_reference_count':len(rule_rows),
        'rule_decision_exact_category_agreements':sum(x['exact_category_agreement'] for x in rule_rows),
        'rule_decision_agreement_rate_pct':round(100*sum(x['exact_category_agreement'] for x in rule_rows)/len(rule_rows),2),
        'rules':rule_rows, 'cases':dict(counts),
        'case_strata':case_domains,
        'changed_source_inputs':mismatches,
        'unpaired_cases':unpaired,
        'not_estimable':{'independent_adjudicated_reference_F1':None,
            'A_B_C_semantic_effect':None,'published_sota_performance':None},
        'interpretation':[
            'Two source-provided completed reviewer archives are available; reviewer independence is asserted by provenance but not authenticated by the scoring software.',
            'Rule-level exact category agreement counts literal decisions after a documented minimal wording normalisation; no source-truth adjudication or inferential reliability result is claimed.',
            'Case matching requires identical source attributes and values, not merely shared source IDs.',
            'Manufacturing forward cases agree that the documented implication conflicts with recorded flags; the reviewers differ about whether that proves a natural data defect.',
            'B6 proposals and row reviews are not a matching frozen B13.13 A/B/C policy cohort; no gate-effect or published SOTA comparison is inferred.',
        ]}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reviewer1',type=Path,required=True)
    p.add_argument('--reviewer2',type=Path,required=True)
    p.add_argument('--output',type=Path,help='Optional aggregate JSON file outside the Git repo; must not exist')
    arg=p.parse_args()
    a=read_review_bundle(arg.reviewer1,1)
    b=read_review_bundle(arg.reviewer2,2)
    result=evaluate_review_bundles(a,b)
    result['review_archive_sha256']={
        'reviewer1':hashlib.sha256(arg.reviewer1.read_bytes()).hexdigest(),
        'reviewer2':hashlib.sha256(arg.reviewer2.read_bytes()).hexdigest(),
    }
    payload=json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+'\n'
    if arg.output is not None:
        out=arg.output.expanduser().resolve()
        require(out.parent.exists() and out.parent != ROOT and ROOT not in out.parent.parents,
                'Aggregate output must be outside repository and parent must exist')
        with out.open('x',encoding='utf-8') as f:f.write(payload)
        print('SAVED',out)
    print(payload)


if __name__=='__main__':
    try:main()
    except (ReviewError,ValueError,OSError,KeyError,IndexError,ET.ParseError) as exc:
        print('REVIEW AUDIT STOP:',type(exc).__name__,str(exc),file=sys.stderr)
        raise SystemExit(2)
