"""B13.15: audit SEC original inline-XBRL structure, not semantic eligibility or gold.

Reject source/receipt changes, keep downloaded raw source OUTSIDE Git, and emit
only aggregate structural counts plus narrow candidate *opportunities*.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from src.b13_14_sec_intake import (CIK, RECEIPT as PARENT_RECEIPT, OBJ as PARENT_OBJ,
    assert_external_cache, canonical, sha, verify as verify_b1314, _declared_user_agent)

STUDY = 'b13_15_original_filing_inline_context_audit_v1'
RAW = 'B13_15_CMG_2025_10K_original_inline.html'
RECEIPT = 'B13_15_CMG_2025_10K_filing_receipt_v1.json'
AUDIT = 'B13_15_CMG_2025_10K_context_audit_v1.json'
OPPORTUNITIES = 'B13_15_CMG_2025_10K_structural_opportunities_v1.csv'
EXPECTED_ACCESSION = '0001058090-26-000009'
EXPECTED_DATE = '2025-12-31'
EXPECTED_URL = 'https://www.sec.gov/Archives/edgar/data/1058090/000105809026000009/cmg-20251231.htm'
MAX_BYTES = 45 * 1024 * 1024
MAX_CONTEXTS = 60000
MAX_FACTS = 1200000
HEADERS = ['opportunity_id','source_group','source_filing_accession','report_date',
           'concept_left','concept_right','matching_dimensionless_instant_contexts',
           'matching_usable_units','duplicate_or_missing_context_flag',
           'assessment','independent_documentary_review','independent_gold']
PAIR = ('us-gaap:Assets','us-gaap:LiabilitiesAndStockholdersEquity')

class FilingAuditError(ValueError): pass


def official_source(parent: dict) -> str:
    f = parent.get('selected_filing')
    if (parent.get('source_cik') != CIK or not isinstance(f,dict) or
        f.get('accession') != EXPECTED_ACCESSION or f.get('form') != '10-K' or
        f.get('report_date') != EXPECTED_DATE or f.get('filing_date') != '2026-02-04' or
        f.get('primary_document') != 'cmg-20251231.htm' or
        f.get('filing_landing_url') != EXPECTED_URL or
        parent.get('source_semantic_eligibility_verified') is not False or
        parent.get('independent_gold') != 0 or parent.get('real_gate_runs') != 0):
        raise FilingAuditError('B13.14 receipt changed or incorrectly claims eligibility')
    return f['filing_landing_url']


def check_filing_url(url:str) -> None:
    u=urlsplit(url)
    if (u.scheme != 'https' or u.hostname != 'www.sec.gov' or u.path != urlsplit(EXPECTED_URL).path
        or u.username or u.password or u.port or u.query or u.fragment):
        raise FilingAuditError('Original SEC filing URL/path does not match frozen accession')


def fetch_html(url: str, agent: str, *, opener=urlopen) -> bytes:
    check_filing_url(url)
    useragent=_declared_user_agent(agent)
    req=Request(url,headers={'User-Agent':useragent,'Accept':'text/html','Accept-Encoding':'identity'})
    with opener(req,timeout=55) as response:
        actual=response.geturl()
        check_filing_url(actual)
        kind=response.headers.get('Content-Type','').lower()
        if kind and not any(x in kind for x in ('text/html','application/xhtml+xml','application/octet-stream')):
            raise FilingAuditError('SEC returned an unexpected content type')
        data=response.read(MAX_BYTES+1)
    if not 1000 <= len(data) <= MAX_BYTES or not data.lstrip().startswith((b'<',b'<!')):
        raise FilingAuditError('SEC did not return a plausible filing HTML object')
    return data


def _local(tag: str) -> str:
    return tag.rsplit(':',1)[-1].lower()


class InlineAuditParser(HTMLParser):
    """Conservative HTMLParser scan. Captures no monetary amounts or full filing text."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.contexts={}
        self.current=None
        self.unit=None
        self.units={}
        self.capture=None
        self.capture_depth=0
        self.facts=[]
        self.tag_stack=[]
        self.repeated_context_ids=0
        self.duplicate_unit_names=0
        self.nonfraction_missing_ref=0
        self.namespaces=set()

    def handle_starttag(self, tag, attrs):
        self._start(tag, dict(attrs))

    def handle_startendtag(self, tag, attrs):
        self._start(tag, dict(attrs))
        self.handle_endtag(tag)

    def _start(self,tag,attr):
        local=_local(tag)
        if self.current is not None:
            self.capture_depth+=1
            if local in ('segment','scenario','explicitmember','typedmember'):
                self.current['dimensional_markup']=True
            if local in ('identifier','instant','startdate','enddate'):
                self.capture=local
        if local=='unit' and (tag.startswith('xbrli:') or tag=='unit'):
            uid=attr.get('id')
            if not uid or len(uid)>200 or self.unit is not None:
                raise FilingAuditError('Malformed XBRL unit ID')
            self.unit={'id':uid,'measure':'','complex':False}
        elif self.unit is not None:
            if local=='measure':self.capture='unit_measure'
            elif local in ('divide','unitnumerator','unitdenominator'):
                self.unit['complex']=True
        if local=='context' and (tag.startswith('xbrli:') or tag=='context'):
            if self.current is not None:
                raise FilingAuditError('Nested XBRL contexts')
            cid=attr.get('id')
            if not isinstance(cid,str) or not cid.strip() or len(cid)>200:
                raise FilingAuditError('Malformed context ID')
            if cid in self.contexts:
                self.repeated_context_ids+=1
            self.current={'id':cid,'entity_identifier':'','instant':'','startdate':'','enddate':'',
                          'dimensional_markup':False}
            self.capture_depth=0
            self.capture=None
        if tag in ('ix:nonfraction','ix:nonfraction'):
            if len(self.facts)>=MAX_FACTS: raise FilingAuditError('Excessive number of inline numeric facts')
            self.facts.append({'concept':attr.get('name',''),
                'context':attr.get('contextref',''), 'unit':attr.get('unitref',''),
                'nil':attr.get('xsi:nil')=='true',
                'has_format':bool(attr.get('format'))})
            if not attr.get('contextref') or not attr.get('unitref'):
                self.nonfraction_missing_ref+=1

    def handle_data(self,data):
        if self.capture=='unit_measure' and self.unit is not None:
            self.unit['measure']+=data[:150]
        elif self.current is not None and self.capture:
            if len(data)>150: data=data[:150]
            self.current['entity_identifier' if self.capture=='identifier' else self.capture]+=data

    def handle_endtag(self,tag):
        local=_local(tag)
        if local=='unit' and self.unit is not None:
            uid=self.unit['id']
            if uid in self.units:self.duplicate_unit_names+=1
            else:self.units[uid]=self.unit
            self.unit=None
            self.capture=None
            return
        if local=='measure' and self.capture=='unit_measure':
            self.capture=None
        if self.current is None:return
        if local=='context' and (tag.startswith('xbrli:') or tag=='context'):
            cid=self.current['id']
            if cid not in self.contexts:
                self.contexts[cid]=self.current
                if len(self.contexts)>MAX_CONTEXTS: raise FilingAuditError('Excessive XBRL contexts')
            self.current=None
            self.capture=None
            self.capture_depth=0
            return
        if local==self.capture: self.capture=None
        if self.capture_depth: self.capture_depth-=1

    def finish(self):
        if self.current is not None: raise FilingAuditError('Unclosed XBRL context')
        if self.unit is not None: raise FilingAuditError('Unclosed XBRL unit')
        if not self.contexts or not self.facts:
            raise FilingAuditError('Original filing does not expose both XBRL contexts and inline numeric facts')


def scan_html(data: bytes, parent: dict, filing_receipt_hash: str) -> tuple[dict,list[dict]]:
    official_source(parent)
    if not isinstance(data,bytes) or len(data)==0:
        raise FilingAuditError('Missing filing HTML')
    text=data.decode('utf-8',errors='replace')
    parser=InlineAuditParser()
    parser.feed(text)
    parser.close()
    parser.finish()
    contexts=parser.contexts
    right_cik=str(int(CIK))
    eligible={}
    for id_,c in contexts.items():
        entity=c['entity_identifier'].strip().lstrip('0') or '0'
        # Instant reporting period only; dimensional scopes excluded conservatively.
        if entity==right_cik and c['instant'].strip()==EXPECTED_DATE and not c['dimensional_markup']:
            eligible[id_]=c
    count=Counter(f['concept'] for f in parser.facts)
    refs=defaultdict(Counter)
    missing_context=0
    for f in parser.facts:
        if f['context'] not in contexts:
            missing_context+=1
        unit=parser.units.get(f['unit'])
        valid_usd_unit=(unit is not None and not unit['complex'] and
                        unit['measure'].strip().lower() in ('iso4217:usd','usd'))
        if f['context'] in eligible and f['concept'] in PAIR and valid_usd_unit and not f['nil']:
            refs[f['context']][(f['concept'],f['unit'])]+=1
    matches=[]
    ambiguous=0
    for context_id, facts in refs.items():
        units=sorted({u for concept,u in facts if concept==PAIR[0]} &
                     {u for concept,u in facts if concept==PAIR[1]})
        for unit in units:
            duplicate = facts[(PAIR[0],unit)]!=1 or facts[(PAIR[1],unit)]!=1
            if duplicate: ambiguous+=1
            matches.append({'context_id':context_id,'unit':unit,'duplicate':duplicate})
    matches.sort(key=lambda x:(x['context_id'],x['unit']))
    opportunities=[]
    if matches:
        opportunities.append({
          'opportunity_id':'CMG_2025_ASSETS_BALANCE_SHEET_TOTAL',
          'source_group':'sec_cik_0001058090_2025_10k',
          'source_filing_accession':EXPECTED_ACCESSION,'report_date':EXPECTED_DATE,
          'concept_left':PAIR[0],'concept_right':PAIR[1],
          'matching_dimensionless_instant_contexts':len({x['context_id'] for x in matches}),
          'matching_usable_units':len({x['unit'] for x in matches}),
          'duplicate_or_missing_context_flag':bool(ambiguous or missing_context or parser.repeated_context_ids or parser.duplicate_unit_names),
          'assessment':'structural_co_location_only_not_a_compiled_candidate',
          'independent_documentary_review':'not_performed','independent_gold':'not_available'})
    report={'study_id':STUDY,'phase':'source_structure_only_not_candidate_adjudication',
      'source_group':'sec_cik_0001058090_2025_10k',
      'source_cik':CIK,'accession':EXPECTED_ACCESSION,'report_date':EXPECTED_DATE,
      'original_filing_url':EXPECTED_URL,'source_filing_sha256':sha(data),
      'b13_14_receipt_sha256':filing_receipt_hash,
      'xbrl_context_count':len(contexts),'duplicate_context_id_count':parser.repeated_context_ids,
      'xbrl_unit_count':len(parser.units),'duplicate_unit_id_count':parser.duplicate_unit_names,
      'numeric_ix_fact_count':len(parser.facts),
      'numeric_facts_with_unresolved_context':missing_context,
      'numeric_facts_missing_context_or_unit_ref':parser.nonfraction_missing_ref,
      'dimensionless_expected_entity_instant_contexts':len(eligible),
      'target_concept_mention_counts':{k:count[k] for k in PAIR},
      'same_context_same_unit_target_pair_instances':len(matches),
      'target_pair_ambiguous_duplicate_instances':ambiguous,
      'structural_opportunity_count':len(opportunities),
      'source_authenticated_by_software':False,
      'xbrl_fact_values_transformed_or_validated':False,
      'consolidation_scope_independently_qualified':False,
      'dimensions_and_custom_extensions_fully_interpreted':False,
      'independent_documentary_review_completed':False,
      'independent_gold_rules':0,'candidate_packet_created':False,
      'real_gate_executions':0,
      'limitations':['Original filing source is fingerprinted; SEC source identity is not independently attested',
        'HTMLParser is a structural audit; no transformation-registry sign/scale/precision processing',
        'Same contextRef and unitRef and entity/instant do not prove accounting semantics or consolidated reporting',
        'The preselected accounting relationship is not novel LLM discovery',
        'Potential duplicated facts or contexts must be resolved before candidate generation']}
    return report,opportunities


def serialize_opportunities(rows:list[dict])->str:
    out=io.StringIO(newline='')
    writer=csv.DictWriter(out,fieldnames=HEADERS,lineterminator='\n')
    writer.writeheader()
    for r in rows:
        writer.writerow({h:('true' if r[h] else 'false') if isinstance(r[h],bool) else r[h] for h in HEADERS})
    return out.getvalue()


def _b14_receipt(cache:Path,root:Path,plan:dict,development_manifest:dict)->tuple[dict,str]:
    # Guarantees downloaded submission bytes still equal the original B13.14 receipt.
    receipt=verify_b1314(cache,root,plan,development_manifest)
    path=cache/PARENT_RECEIPT
    return receipt,sha(path.read_bytes())


def acquire(cache:Path,root:Path,plan:dict,development_manifest:dict, agent:str, *,fetcher=fetch_html)->dict:
    cache=assert_external_cache(cache,root)
    parent,parent_receipt_hash=_b14_receipt(cache,root,plan,development_manifest)
    url=official_source(parent)
    if any((cache/name).exists() for name in (RAW,RECEIPT,AUDIT,OPPORTUNITIES)):
        raise FilingAuditError('B13.15 output exists; use --verify, do not overwrite')
    raw=fetcher(url,agent)
    # Prohibit recording HTML that has no scan-able numeric contexts.
    report,_=scan_html(raw,parent,parent_receipt_hash)
    receipt={'study_id':STUDY,'phase':'downloaded_original_filing_not_source_qualified',
        'parent_b13_14_receipt_sha256':parent_receipt_hash,
        'official_filing_url':url,'accession':EXPECTED_ACCESSION,
        'raw_file_name':RAW,'raw_sha256':sha(raw),'raw_bytes':len(raw),
        'source_semantic_eligibility_verified':False,'independent_gold':0,
        'numeric_xbrl_facts_observed':report['numeric_ix_fact_count']}
    created=[]
    try:
        with (cache/RAW).open('xb') as file:file.write(raw)
        created.append(cache/RAW)
        with (cache/RECEIPT).open('x',encoding='utf-8') as file:
            json.dump(receipt,file,sort_keys=True,indent=2,ensure_ascii=False);file.write('\n')
        created.append(cache/RECEIPT)
    except BaseException:
        for p in created:p.unlink(missing_ok=True)
        raise
    return receipt


def verified_raw(cache:Path,root:Path,plan:dict,development_manifest:dict)->tuple[bytes,dict,str]:
    cache=assert_external_cache(cache,root)
    parent,parent_sha=_b14_receipt(cache,root,plan,development_manifest)
    data=(cache/RAW).read_bytes()
    receipt=json.loads((cache/RECEIPT).read_text(encoding='utf-8'))
    expected={'study_id':STUDY,'phase':'downloaded_original_filing_not_source_qualified',
        'parent_b13_14_receipt_sha256':parent_sha,
        'official_filing_url':official_source(parent),'accession':EXPECTED_ACCESSION,
        'raw_file_name':RAW,'raw_sha256':sha(data),'raw_bytes':len(data),
        'source_semantic_eligibility_verified':False,'independent_gold':0}
    for k,v in expected.items():
        if receipt.get(k)!=v:raise FilingAuditError('Original filing receipt or bytes changed: '+k)
    report,_=scan_html(data,parent,parent_sha)
    if receipt.get('numeric_xbrl_facts_observed')!=report['numeric_ix_fact_count']:
        raise FilingAuditError('Inline XBRL fact count differs from acquisition receipt')
    return data,parent,parent_sha


def audit(cache:Path,root:Path,plan:dict,development_manifest:dict)->tuple[dict,list[dict]]:
    cache=assert_external_cache(cache,root)
    raw,parent,parent_sha=verified_raw(cache,root,plan,development_manifest)
    report,opportunities=scan_html(raw,parent,parent_sha)
    if (cache/AUDIT).exists() or (cache/OPPORTUNITIES).exists():
        raise FilingAuditError('Source audit outputs already exist; use --verify')
    created=[]
    try:
        with (cache/AUDIT).open('x',encoding='utf-8') as f:
            json.dump(report,f,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False);f.write('\n')
        created.append(cache/AUDIT)
        with (cache/OPPORTUNITIES).open('x',encoding='utf-8',newline='') as f:
            f.write(serialize_opportunities(opportunities))
        created.append(cache/OPPORTUNITIES)
    except BaseException:
        for p in created:p.unlink(missing_ok=True)
        raise
    return report,opportunities


def verify(cache:Path,root:Path,plan:dict,development_manifest:dict)->dict:
    cache=assert_external_cache(cache,root)
    raw,parent,parent_sha=verified_raw(cache,root,plan,development_manifest)
    report,opportunities=scan_html(raw,parent,parent_sha)
    if (cache/AUDIT).exists() != (cache/OPPORTUNITIES).exists():
        raise FilingAuditError('Incomplete B13.15 audit outputs')
    if (cache/AUDIT).exists():
        if json.loads((cache/AUDIT).read_text(encoding='utf-8')) != report:
            raise FilingAuditError('B13.15 aggregate audit changed')
        if (cache/OPPORTUNITIES).read_text(encoding='utf-8') != serialize_opportunities(opportunities):
            raise FilingAuditError('B13.15 opportunity register changed')
    return report
