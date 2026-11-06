"""B6 catalogue and protocol audit. Offline, deterministic, no API or data reads.

Validates references against retained metadata names, checks syntactic B3 DSL,
identifies provisional versus excluded rules, and writes a machine-readable audit.
Does NOT verify document contents, certify source entailment, or run real datasets.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from src.generic_verifier import validate_rule
except ModuleNotFoundError as exc:
    raise SystemExit('Missing src/generic_verifier.py: install B6 into the MetaVerify repository.') from exc

STATUSES = {'provisional_source_supported', 'partially_supported', 'scope_pending', 'excluded'}
SOURCE_URL_PREFIXES = ('https://',)
META = {
    'healthcare': ('nhanes-2017-2018-glu-j', 'data/metadata/nhanes-glu-j.json'),
    'finance': ('sec-companyfacts-320193', 'data/metadata/sec-companyfacts-0000320193.json'),
    'manufacturing': ('ai4i-2020', 'data/metadata/ai4i-2020.json'),
    'cybersecurity': ('cic-ids2017', 'data/metadata/cic-ids2017.json'),
}


def _read(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(obj, dict):
        raise ValueError(f'JSON object expected: {path}')
    return obj


def check_catalogue(root: Path, catalogue: dict[str, Any], protocol: dict[str, Any]) -> dict[str, Any]:
    """Fail closed on malformed catalogue/protocol. Does not access outside sources."""
    if catalogue.get('protocol_id') != protocol.get('protocol_id') or protocol.get('protocol_id') != 'b6-frozen-protocol-v1':
        raise ValueError('catalogue/protocol identifier mismatch')
    if catalogue.get('baseline_commit') != protocol.get('baseline_git_commit'):
        raise ValueError('baseline commit mismatch between catalogue and protocol')
    baseline = protocol.get('baseline_git_commit')
    if not isinstance(baseline, str) or len(baseline) != 40 or any(c not in '0123456789abcdef' for c in baseline):
        raise ValueError('protocol needs a 40-digit immutable baseline SHA')
    if protocol.get('frozen_before_future_paid_comparison') is not True:
        raise ValueError('protocol freeze indicator missing')
    entries = catalogue.get('entries')
    if not isinstance(entries, list) or not entries:
        raise ValueError('catalogue entries must be nonempty list')
    ids: set[str] = set()
    summary = []
    for domain, (dataset_id, filename) in META.items():
        path = root / filename
        if not path.is_file():
            raise ValueError(f'metadata missing for {domain}: {filename}')
        meta = _read(path)
        if meta.get('dataset', {}).get('id') != dataset_id:
            raise ValueError(f'dataset identity changed: {filename}')
    for e in entries:
        if not isinstance(e, dict):
            raise ValueError('catalogue entries must be JSON objects')
        rid, domain, status = e.get('id'), e.get('domain'), e.get('status')
        if not isinstance(rid, str) or not rid or rid in ids:
            raise ValueError(f'duplicate or invalid reference-rule ID: {rid}')
        ids.add(rid)
        if domain not in META or status not in STATUSES:
            raise ValueError(f'{rid}: unknown domain/status')
        dataset_id, metadata_file = META[domain]
        if e.get('dataset_id') != dataset_id:
            raise ValueError(f'{rid}: unexpected dataset identifier')
        if e.get('scoring_eligible') is not False:
            raise ValueError(f'{rid}: do not mark unreviewed rules as final gold')
        fields = e.get('columns')
        if not isinstance(fields, list) or len(fields) < 2 or len(set(fields)) != len(fields) or any(not isinstance(x,str) or not x for x in fields):
            raise ValueError(f'{rid}: at least two unique, exact column names required')
        evid = e.get('evidence')
        if not isinstance(evid, list) or not evid:
            raise ValueError(f'{rid}: source evidence entry required')
        for item in evid:
            if not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item[k].strip() for k in ('url','kind','supports')) or not item['url'].startswith(SOURCE_URL_PREFIXES):
                raise ValueError(f'{rid}: malformed source/evidence URL')
        if not isinstance(e.get('unresolved'), list):
            raise ValueError(f'{rid}: unresolved caveats must be explicit')
        scope = e.get('metadata_scope')
        if scope == 'repository_columns':
            metadata = _read(root / metadata_file)
            names = {col['name'] for col in metadata['columns']}
            unknown = set(fields) - names
            if unknown:
                raise ValueError(f'{rid}: columns absent from metadata (case/space sensitive): {sorted(unknown)}')
        elif scope == 'external_taxonomy_pending' and domain == 'finance':
            if status not in {'scope_pending','excluded'}:
                raise ValueError(f'{rid}: external taxonomy cannot be gold without source check')
        else:
            raise ValueError(f'{rid}: unsupported metadata scope')
        rule = e.get('reference_rule')
        if status == 'excluded' and rule is not None:
            raise ValueError(f'{rid}: excluded rule must never be directly executable')
        if status != 'excluded':
            if not isinstance(rule, dict):
                raise ValueError(f'{rid}: non-excluded candidate needs an inspectable rule DSL')
            referenced = validate_rule(rule)
            if rule.get('id') != rid or rule.get('dataset_id') != dataset_id:
                raise ValueError(f'{rid}: executable rule identity mismatch')
            if set(fields) != referenced:
                raise ValueError(f'{rid}: declared and referenced field sets differ: {set(fields)^referenced}')
            if status == 'provisional_source_supported' and scope != 'repository_columns':
                raise ValueError(f'{rid}: provisional source support needs resolved column scope')
        summary.append({'id':rid,'domain':domain,'status':status,'scoring_eligible':False,'metadata_scope':scope,'source_urls':[v['url'] for v in evid],'dsl_structurally_valid':rule is not None})
    status_counts=dict(sorted(Counter(e['status'] for e in entries).items()))
    if not all(d in {r['domain'] for r in summary} for d in META):
        raise ValueError('all four domains require at least one entry')
    return {
        'protocol_id':protocol['protocol_id'],
        'baseline_commit':baseline,
        'entry_count':len(entries),
        'status_counts':status_counts,
        'final_gold_eligible_count':0,
        'source_url_contents_checked':False,
        'source_entailment_adjudicated':False,
        'real_data_evaluated_by_this_script':False,
        'all_metadata_and_structural_checks_passed':True,
        'entries':summary,
        'next_requirements':['Independent two-reviewer adjudication','Check finance taxonomy and context adapter','Lock precision before independent healthcare test','Execute real held-out/grouped data where available']
    }


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=ROOT)
    ap.add_argument('--write-report',action='store_true',help='Write a deterministic JSON audit under data/evaluation')
    args=ap.parse_args()
    root=args.root.resolve()
    cat_path=root/'data/evaluation/b6_reference_catalogue.json'
    pro_path=root/'data/evaluation/b6_protocol_v1.json'
    catalogue,protocol=_read(cat_path),_read(pro_path)
    result=check_catalogue(root,catalogue,protocol)
    result['catalogue_sha256']=hashlib.sha256(cat_path.read_bytes()).hexdigest()
    result['protocol_sha256']=hashlib.sha256(pro_path.read_bytes()).hexdigest()
    print('B6 catalogue validation: PASS')
    print('Baseline commit:', result['baseline_commit'][:12])
    print('Reference candidates:',result['entry_count'])
    for status,count in result['status_counts'].items():
        print(f'  {status}: {count}')
    print('Final independently adjudicated gold rules:',result['final_gold_eligible_count'])
    print('IMPORTANT: No source-content verification, independent adjudication or real-data testing was performed.')
    if args.write_report:
        out=root/'data/evaluation/b6_catalogue_audit.json'
        out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        print('Saved:',out.relative_to(root))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
