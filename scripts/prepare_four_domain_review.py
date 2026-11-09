"""Prepare independently reviewable, ORIGINAL-RECORD MetaVerify worksheets for four domains.

Requires retained local source snapshots; never downloads, invents data, modifies frozen
B6/B7 outputs, fills votes, or certifies semantic gold. Python stdlib + pyreadstat
(already needed for NHANES in the research repository).
"""
from __future__ import annotations
import argparse
import csv
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import random
import sys

SEED = 20271109
OUT = Path('data/evaluation/b6_4_four_domain_review')
MAN_SRC = 'data/evaluation/b6_3_review/reviewer_1_cases.csv'
MAN_SHA = 'dc6630cd9b1f0f853922fad78a1b6436570d3f1ec863f1dd5c4340ac56bc8a8e'
CYB_SRC = 'data/samples/cic_ids2017/flows-50000.csv'
CYB_SHA = '3ee83d5ecbfd50541b0205293a462643309e253e095c41c82cc5c37cf6aef2d5'
HLT_SRC = 'data/originals/nhanes/GLU_J.XPT'
HLT_SHA = '5b38897d0d7bfbc69dd9ca74ffdaf2f6a9bed5a91d4a7bf46e07f1332cc3379e'
VOTE = ['reviewer_id', 'decision', 'evidence_url', 'evidence_locator', 'rationale']
RULE_FIELDS = ['reference_id','domain','dataset_id','reference_status','proposed_constraint',
               'applicability_and_known_limits','source_urls','review_question',*VOTE]
MAN_FIELDS = ['reference_id','source_sha256','UDI','case','active_modes',
              'TWF','HDF','PWF','OSF','RNF','Machine failure',*VOTE]
CYB_FIELDS = ['reference_id','source_file','source_sha256','source_data_row_1based','row_sha256',
              'selection_stratum',' Label',' Total Fwd Packets',' Fwd Packet Length Min',
              ' Fwd Packet Length Mean',' Fwd Packet Length Max','observed_test_status',*VOTE]
HLT_FIELDS = ['reference_id','source_file','source_sha256','source_data_row_1based','row_sha256',
              'selection_stratum','SEQN','LBXGLU','LBDGLUSI','predicted_3_significant_digits',
              'predicted_3_decimal_places','observed_3sig_status','official_precision_note',*VOTE]
FIN_FIELDS = ['reference_id','source_file','source_sha256','CIK','entity_name','reporting_end',
              'accession','form','filed','unit','Assets','Liabilities','StockholdersEquity',
              'LiabilitiesAndStockholdersEquity','arithmetic_difference_USD',
              'observed_arithmetic_status','same_accession_end_unit_form_filed',
              'accounting_scope_evidence_status','source_fact_locator',*VOTE]
CASE_FIELDS = {'manufacturing':MAN_FIELDS,'cybersecurity':CYB_FIELDS,'healthcare':HLT_FIELDS,'finance':FIN_FIELDS}
SOURCES = {
 'manufacturing':['https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset'],
 'cybersecurity':['https://github.com/ahlashkari/CICFlowMeter/blob/master/ReadMe.txt','https://github.com/ahlashkari/CICFlowMeter/blob/master/src/main/java/cic/cs/unb/ca/jnetpcap/BasicFlow.java'],
 'healthcare':['https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/GLU_J.htm'],
 'finance':['https://xbrl.us/data-rule/dqc_0015-le-V2pr/','https://www.sec.gov/search-filings/edgar-application-programming-interfaces']
}
RULES = [
 dict(reference_id='B6-MAN-001',domain='manufacturing',dataset_id='ai4i-2020',reference_status='provisional_source_supported',
      proposed_constraint='If TWF OR HDF OR PWF OR OSF OR RNF equals 1, Machine failure must equal 1 (ONE-WAY only).',
      applicability_and_known_limits='Same AI4I 2020 record; RNF discrepancy in official synthetic data unresolved. The 9 reverse-direction cases do not violate this one-way implication.',
      review_question='Does original AI4I generation description and exact released CSV justify the one-way implication including RNF? Explain discrepancies and version.'),
 dict(reference_id='B6-CYB-001',domain='cybersecurity',dataset_id='cic-ids2017',reference_status='provisional_source_supported',
      proposed_constraint='If Total Fwd Packets > 0, Fwd Packet Length Min <= Mean <= Max (same flow).',
      applicability_and_known_limits='Must use same forward-direction population, positive packet count, finite values, identical generating version and exact leading-space headers.',
      review_question='Do CICFlowMeter definition AND retained CIC-IDS2017 generator version support the implication as encoded?'),
 dict(reference_id='B6-HLT-001',domain='healthcare',dataset_id='nhanes-2017-2018-glu-j',reference_status='partially_supported',
      proposed_constraint='LBDGLUSI = round_to_3_significant_figures(LBXGLU * 0.05551) [CURRENT UNVALIDATED PRECISION].',
      applicability_and_known_limits='Same participant and both glucose values present. CDC documents factor 0.05551 and says rounded to 3 decimals; 3 significant figures was fitted to same snapshot. Do not treat as established gold.',
      review_question='Does CDC source justify factor, direction AND exact executable 3-significant-figure rounding? If not, what precision is actually justified?'),
 dict(reference_id='B6-FIN-001',domain='finance',dataset_id='sec-companyfacts-320193',reference_status='scope_pending',
      proposed_constraint='Assets = LiabilitiesAndStockholdersEquity (same US-GAAP instant reporting context).',
      applicability_and_known_limits='Require same entity, accession, reporting end, currency and accounting scope; Companyfacts alone may not establish consolidation/dimensions and right-hand concept may be missing.',
      review_question='Does official taxonomy support this exact concept-level identity in the selected filing contexts, including unit, accession, end, scope and restatement?'),
 dict(reference_id='B6-FIN-002',domain='finance',dataset_id='sec-companyfacts-320193',reference_status='excluded_unqualified_candidate_review',
      proposed_constraint='Assets = Liabilities + StockholdersEquity (parent-only equity; unsafe as universal identity).',
      applicability_and_known_limits='Frozen B6 excludes unrestricted formula; may require noncontrolling/redeemable equity adjustments. Historical 41/41 empirical matches do not establish semantic truth.',
      review_question='Is this equation valid AS WRITTEN for all aligned contexts? Identify cases needing equity components, exceptions and filing/source evidence.'),
]
for rule in RULES:
 rule['source_urls'] = ' | '.join(SOURCES[rule['domain']])


def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(2**20),b''):h.update(block)
    return h.hexdigest()


def verify(path:Path, expected:str):
    if not path.exists():raise FileNotFoundError('Required local source missing: '+str(path))
    actual=sha(path)
    if actual.lower()!=expected.lower():raise ValueError(f'SHA256 mismatch for {path}: expected {expected}, observed {actual}; NO rows used')
    return actual


def read_csv(path:Path):
    with path.open('r',newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames or len(reader.fieldnames)!=len(set(reader.fieldnames)):
            raise ValueError(f'Invalid or duplicate CSV headers: {path}')
        return list(reader)


def load_man(root:Path):
    """Copy the same 27 exact source rows already frozen in B6.3, no decisions."""
    src=root/MAN_SRC
    if not src.exists():raise FileNotFoundError(f'B6.3 original reviewer file missing: {src}')
    data=read_csv(src)
    if len(data)!=27:raise ValueError('Expected exactly 27 B6.3 manufacturing cases')
    seen=[]
    for row in data:
        if row['reference_id']!='B6-MAN-001' or row['source_sha256']!=MAN_SHA:
            raise ValueError('B6.3 manufacturing row source mismatch')
        if any(row.get(v,'').strip() for v in VOTE):
            raise ValueError('B6.3 reviewer file already contains decisions; use original blank source not private opinions')
        seen.append(int(row['UDI']))
    if len(set(seen))!=27:raise ValueError('Duplicate AI4I UDI in B6.3')
    if sum(x['case']=='forward_frozen_rule_violation' for x in data)!=18 or sum(x['case']=='reverse_exploratory_only_not_frozen_rule' for x in data)!=9:
        raise ValueError('B6.3 source categories differ from frozen 18+9')
    # Reconcile every frozen case with the exact original UCI CSV, not just its worksheet hash string.
    original=root/'data/originals/ai4i/ai4i2020.csv'
    verify(original,MAN_SHA)
    observed={}
    target_ids={str(x) for x in seen}
    with original.open(encoding='utf-8-sig',newline='') as f:
        rr=csv.DictReader(f)
        required=['UDI','TWF','HDF','PWF','OSF','RNF','Machine failure']
        if not rr.fieldnames or any(rr.fieldnames.count(k)!=1 for k in required):
            raise ValueError('Original AI4I CSV lacks unique required columns')
        n=0
        for raw in rr:
            n+=1
            if raw['UDI'] in target_ids:
                if raw['UDI'] in observed:raise ValueError('Duplicate original AI4I UDI')
                observed[raw['UDI']]=raw
    if n!=10000 or len(observed)!=27:
        raise ValueError('AI4I original row count or frozen 27-case match is incomplete')
    for row in data:
        raw=observed[row['UDI']]
        if any(str(row[k])!=str(raw[k]) for k in required[1:]):
            raise ValueError('B6.3 case value differs from original source at UDI '+row['UDI'])
    return [{k:row.get(k,'') for k in MAN_FIELDS} for row in data]


def numeric(v):
    try:
        x=Decimal(str(v).strip())
        return x if x.is_finite() else None
    except (InvalidOperation,ValueError,TypeError):return None


def load_cyb(root:Path):
    src=root/CYB_SRC
    verify(src,CYB_SHA)
    with src.open('r',encoding='utf-8-sig',newline='') as f:
        rr=csv.reader(f)
        head=next(rr)
        # CIC mirror has duplicate unrelated columns; select by UNIQUE positions.
        required=[' Label',' Total Fwd Packets',' Fwd Packet Length Min',
                  ' Fwd Packet Length Mean',' Fwd Packet Length Max']
        for k in required:
            if head.count(k)!=1:raise ValueError(f'CIC required header not unique: {k!r} ({head.count(k)})')
        pos={k:head.index(k) for k in required}
        groups=defaultdict(list)
        for line,raw in enumerate(rr,start=2):
            if len(raw)!=len(head):raise ValueError(f'CIC row {line}: CSV width mismatch')
            label=raw[pos[' Label']]
            values=[raw[pos[k]] for k in required[1:]]
            count,mn,mean,mx=map(numeric,values)
            if None in (count,mn,mean,mx):status='abstained_missing_or_nonfinite'
            elif count<=0:status='not_applicable_no_forward_packets'
            elif mn<=mean<=mx:status='satisfied_provisional_expression'
            else:status='violated_provisional_expression'
            r={
             'reference_id':'B6-CYB-001','source_file':CYB_SRC,'source_sha256':CYB_SHA,
             'source_data_row_1based':line-1,
             'row_sha256':hashlib.sha256(json.dumps(raw,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),
             'selection_stratum':label, 'observed_test_status':status}
            r.update({k:raw[pos[k]] for k in required})
            groups[label].append(r)
    if sum(map(len,groups.values()))!=50000:raise ValueError('CIC source does not contain 50,000 sampled data rows')
    rng=random.Random(SEED+1)
    keys=sorted(groups)
    if not keys:raise ValueError('No CIC label groups')
    for group in groups.values():rng.shuffle(group)
    selected=[]
    while len(selected)<20:
        added=False
        for key in keys:
            if groups[key] and len(selected)<20:
                selected.append(groups[key].pop());added=True
        if not added:break
    if len(selected)!=20:raise ValueError('Insufficient CIC original records for 20-case selection')
    return [{k:row.get(k,'') for k in CYB_FIELDS} for row in selected]


def sig_round(value:Decimal,digits=3):
    if value==0:return value
    return value.quantize(Decimal('1').scaleb(value.adjusted()-digits+1), rounding=ROUND_HALF_UP)


def cellstr(value):
    if value is None:return ''
    try:
        if isinstance(value,float) and not math.isfinite(value):return ''
        if isinstance(value,float) and value.is_integer():return str(int(value))
    except TypeError:pass
    return str(value)


def load_hlt(root:Path):
    src=root/HLT_SRC
    verify(src,HLT_SHA)
    try:import pyreadstat
    except ImportError as e:raise RuntimeError('Install pyreadstat (already used by repo NHANES scripts): python -m pip install pyreadstat') from e
    data,_=pyreadstat.read_xport(str(src),usecols=['SEQN','LBXGLU','LBDGLUSI'],output_format='dict')
    n=len(data['SEQN'])
    if n!=3036:raise ValueError(f'GLU_J row count changed: expected 3036, got {n}')
    complete=[];missing=[]
    for i in range(n):
        seq=cellstr(data['SEQN'][i]); mg=cellstr(data['LBXGLU'][i]); si=cellstr(data['LBDGLUSI'][i])
        a,b=numeric(mg),numeric(si)
        predsig=sig_round(a*Decimal('0.05551')) if a is not None else None
        preddec=(a*Decimal('0.05551')).quantize(Decimal('0.001'),rounding=ROUND_HALF_UP) if a is not None else None
        status='abstained_missing' if a is None or b is None else ('satisfied_posthoc_3sig_expression' if predsig==b else 'violated_posthoc_3sig_expression')
        r={'reference_id':'B6-HLT-001','source_file':HLT_SRC,'source_sha256':HLT_SHA,
           'source_data_row_1based':i+1,
           'row_sha256':hashlib.sha256(json.dumps([seq,mg,si],ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),
           'SEQN':seq,'LBXGLU':mg,'LBDGLUSI':si,
           'predicted_3_significant_digits':str(predsig) if predsig is not None else '',
           'predicted_3_decimal_places':str(preddec) if preddec is not None else '',
           'observed_3sig_status':status,
           'official_precision_note':'CDC says 3 decimals; posthoc prototype uses 3 significant figures (not adjudicated)' }
        if a is None or b is None:missing.append(r)
        else:complete.append((a,r))
    # Preserve 4 equally sized empirical glucose strata plus missingness controls.
    complete.sort(key=lambda x:(x[0],x[1]['SEQN']))
    quartiles=[complete[i*len(complete)//4:(i+1)*len(complete)//4] for i in range(4)]
    rng=random.Random(SEED+2);selected=[]
    for j,quartile in enumerate(quartiles):
        pool=[x[1] for x in quartile];rng.shuffle(pool)
        for r in pool[:4]:r['selection_stratum']=f'glucose_quartile_{j+1}';selected.append(r)
    rng.shuffle(missing)
    for r in missing[:4]:r['selection_stratum']='missingness_control';selected.append(r)
    if len(selected)!=20:raise ValueError('GLU_J has insufficient original rows for chosen 16+4 strata')
    return [{k:row.get(k,'') for k in HLT_FIELDS} for row in selected]


def raw_sec_facts(payload,tag):
    concept=payload.get('facts',{}).get('us-gaap',{}).get(tag,{})
    facts=concept.get('units',{}).get('USD',[])
    for f in facts:
        if f.get('start') or f.get('form') not in ('10-K','10-Q'):continue
        if not all(f.get(k) for k in ('end','accn','form','filed')):continue
        v=numeric(f.get('val'))
        if v is None:continue
        yield f,v


def load_fin(root:Path):
    originals=root/'data/originals/sec/companyfacts'
    if not originals.exists():raise FileNotFoundError(f'Local SEC companyfacts folder not found: {originals}')
    candidates={'B6-FIN-001':[],'B6-FIN-002':[]}
    included=[];missing=[]
    for secfile in sorted(originals.glob('*.json')):
        # Each source must be bound to retained company metadata and exact hash.
        cif=secfile.name.split('_')[0]
        meta_path=root/f'data/metadata/sec-companyfacts-{cif}.json'
        if not meta_path.exists():
            raise ValueError(f'Unregistered SEC source snapshot: {secfile.name}')
        meta=json.loads(meta_path.read_text(encoding='utf-8-sig'))
        source_list=[x for x in meta['provenance']['sources'] if x.get('file')==secfile.relative_to(root).as_posix()]
        if len(source_list)!=1:raise ValueError(f'No unambiguous metadata hash for {secfile}')
        actual=verify(secfile,source_list[0]['sha256'])
        payload=json.loads(secfile.read_text(encoding='utf-8-sig'))
        entity=payload.get('entityName','')
        cik=str(payload.get('cik',cif)).zfill(10)
        contexts=defaultdict(lambda:defaultdict(set))
        for tag in ('Assets','Liabilities','StockholdersEquity','LiabilitiesAndStockholdersEquity'):
            for fact,v in raw_sec_facts(payload,tag):
                key=(fact['end'],fact['accn'],fact['form'],fact['filed'],'USD')
                contexts[key][tag].add(v)
        for (end,accn,form,filed,unit), facts in contexts.items():
            # Duplicate/conflicting same-tag facts do not silently overwrite each other.
            if any(len(v)>1 for v in facts.values()):continue
            vals={k:next(iter(v)) for k,v in facts.items()}
            for ref,tags in [('B6-FIN-001',('Assets','LiabilitiesAndStockholdersEquity')),
                             ('B6-FIN-002',('Assets','Liabilities','StockholdersEquity'))]:
                if not all(x in vals for x in tags):continue
                difference=(vals['Assets']-vals['LiabilitiesAndStockholdersEquity']) if ref=='B6-FIN-001' else (vals['Assets']-vals['Liabilities']-vals['StockholdersEquity'])
                row={'reference_id':ref,'source_file':secfile.relative_to(root).as_posix(),'source_sha256':actual,
                     'CIK':cik,'entity_name':entity,'reporting_end':end,'accession':accn,
                     'form':form,'filed':filed,'unit':'USD',
                     'arithmetic_difference_USD':str(difference),
                     'observed_arithmetic_status':'equal_numbers_unverified_scope' if difference==0 else 'unequal_numbers_unverified_scope',
                     'same_accession_end_unit_form_filed':'true_by_exact_join_not_accounting_scope',
                     'accounting_scope_evidence_status':'UNKNOWN_companyfacts_omits_dimension_scope',
                     'source_fact_locator':'us-gaap/'+' + '.join(tags)+'; units/USD; end='+end+'; accn='+accn}
                for col in ('Assets','Liabilities','StockholdersEquity','LiabilitiesAndStockholdersEquity'):
                    row[col]=str(vals[col]) if col in vals else ''
                candidates[ref].append(row)
        included.append({'file':secfile.relative_to(root).as_posix(),'sha256':actual,'cik':cik})
    if not included:raise ValueError('No locally retained SEC companyfacts JSON files found')
    result=[];counts={}
    for ref in ('B6-FIN-001','B6-FIN-002'):
        pool=candidates[ref]
        # Deterministic, exact-context selection; diversify across companies without rewarding fit.
        pool.sort(key=lambda x:hashlib.sha256((str(SEED)+':'+ref+':'+x['CIK']+':'+x['accession']+':'+x['reporting_end']).encode()).hexdigest())
        distinct={};extra=[]
        for r in pool:
            if r['CIK'] not in distinct:distinct[r['CIK']]=r
            else:extra.append(r)
        primary=list(distinct.values())
        primary.sort(key=lambda x:x['CIK'])
        chosen=(primary + extra)[:10]
        counts[ref]={'available_contexts':len(pool),'selected':len(chosen),'requested':10}
        result.extend(chosen)
    # A shortfall is reported in the manifest; original examples are never invented.
    return [{k:row.get(k,'') for k in FIN_FIELDS} for row in result],included,counts


def write_csv(path:Path,fields:list[str],rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator='\n')
        w.writeheader()
        for row in rows:
            prepared={k:row.get(k,'') for k in fields}
            for k in VOTE:prepared[k]=''
            w.writerow(prepared)


def prepare(root:Path,target:Path):
    if target.exists():raise FileExistsError(f'Refusing to overwrite existing worksheet package: {target}')
    # NO writes until all four source validations and record selection succeed.
    man=load_man(root)
    cyb=load_cyb(root)
    hlt=load_hlt(root)
    fin,fin_sources,fin_counts=load_fin(root)
    cases={'manufacturing':man,'cybersecurity':cyb,'healthcare':hlt,'finance':fin}
    target.mkdir(parents=True,exist_ok=False)
    for reviewer in (1,2):
        for domain,rows in cases.items():
            selected_rules=[r for r in RULES if r['domain']==domain]
            write_csv(target/f'reviewer_{reviewer}_{domain}_rules.csv',RULE_FIELDS,selected_rules)
            write_csv(target/f'reviewer_{reviewer}_{domain}_cases.csv',CASE_FIELDS[domain],rows)
    manifest={
      'protocol':'B6.4-four-domain-independent-review-v1',
      'classification':'prepared_blank_human_reviews_not_gold_not_adjudication',
      'original_repository_source':'https://github.com/rubypnchl/ICDE',
      'source_fingerprints':{'ai4i':MAN_SHA,'cic_50000':CYB_SHA,'nhanes_glu_j':HLT_SHA,'sec_sources':fin_sources},
      'selection':{'seed':SEED,'manufacturing':'all 27 previously frozen B6.3 cases (18 forward, 9 reverse exploratory)',
          'cybersecurity':'20 deterministically stratified by original flow label; no rows invented',
          'healthcare':'16 glucose values (four from each quartile) plus four missingness controls',
          'finance':'up to 10 contexts per reference formula; exact join on issuer, accession, end, form, filed, USD; diversify CIK; no assumed accounting scope'},
      'finance_rule_counts':fin_counts,
      'counts':{d:{'rules':len([r for r in RULES if r['domain']==d]),'cases':len(rows)} for d,rows in cases.items()},
      'review_status':'all_decisions_blank','independent_gold_count':0,
      'warning':'A record matched against a candidate does not mean clean/defective; exact SEC filing accounting scope is UNKNOWN; healthcare rounding not independently settled; cybersecurity zero natural violations in B6.1.',
    }
    (target/'review_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (target/'README.txt').write_text(
      'INDEPENDENT HUMAN REVIEW PACK — B6.4\\n'.replace('\\n','\n') +
      'Give each reviewer only their reviewer_N_*.csv files, plus official source links.\n'
      'Both reviewer decision columns remain blank. Reviewer IDs must be different people.\n'
      'Rule decisions: supports_as_written | supports_with_conditions | not_supported | needs_more_evidence.\n'
      'Case decisions (new B6.4 worksheet protocol): consistent_with_rule | supported_discrepancy | explainable_exception | ambiguous | source_version_mismatch | not_applicable | insufficient_record_evidence.\n'
      'For satisfying/non-violating sampled rows use consistent_with_rule only if source and context justify it; otherwise insufficient_record_evidence. Do NOT claim all sampled rows are defects.\n'
      'Use actual source URL, locator and rationale for each review. Keep completed personal reviews PRIVATE.\n'
      'No automatic gold labels, no reviewer agreement claimed, no source files modified.\n'
      'FINANCE: Companyfacts JSON may not encode dimension/consolidation scope, so record-level context verification is limited.\n'
      'HEALTH: CDC states 3 decimals, but prototype uses empirically selected 3 significant figures; independent precision not established.\n',encoding='utf-8')
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--output',type=Path,default=OUT)
    p.add_argument('--dry-run',action='store_true',help='Verify availability and original hashes; do not write worksheets')
    args=p.parse_args()
    root=args.root.resolve()
    target=args.output if args.output.is_absolute() else root/args.output
    try:
        if args.dry_run:
            print('Manufacturing frozen form:',(root/MAN_SRC).exists())
            print('Cybersecurity sample:',(root/CYB_SRC).exists())
            print('Healthcare XPT:',(root/HLT_SRC).exists())
            print('SEC source folder:',(root/'data/originals/sec/companyfacts').exists())
            # Use full checks to fail on incompatible input, without creating any files.
            m=load_man(root);c=load_cyb(root);h=load_hlt(root);f,fs,fc=load_fin(root)
            print('PREFLIGHT PASS:',len(m),'manufacturing,',len(c),'cybersecurity,',len(h),'healthcare,',len(f),'finance cases')
            print('Finance:',json.dumps(fc))
            return 0
        report=prepare(root,target)
        print('FOUR-DOMAIN REVIEW PACK READY:',target)
        for d,summary in report['counts'].items():print(f"{d}: {summary['rules']} rule(s), {summary['cases']} original-source case(s), two INDEPENDENT blank reviewer copies")
        print('All decisions BLANK; no adjudicated gold or natural defects inferred')
        return 0
    except (ValueError,FileNotFoundError,FileExistsError,RuntimeError,KeyError,OSError) as e:
        print('STOPPED (NO ORIGINAL VALUES INVENTED):',e,file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
