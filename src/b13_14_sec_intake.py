"""B13.14: official SEC submissions object intake for a new *prospective lead*.

A source metadata intake, not source qualification, candidate generation, gate
execution, or independent gold. No private user-agent values are stored.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

STUDY = 'b13_14_disjoint_sec_filing_intake_v1'
OBJ = 'B13_14_SEC_CIK0001058090_submissions.json'
RECEIPT = 'B13_14_SEC_CIK0001058090_intake_receipt_v1.json'
CIK = '0001058090'
FORM = '10-K'
CUTOFF = '2026-11-11'
URL = f'https://data.sec.gov/submissions/CIK{CIK}.json'
MAX_BYTES = 10 * 1024 * 1024
ACCESSION = re.compile(r'^\d{10}-\d{2}-\d{6}$')
DOCUMENT = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,200}$')
EXCLUDED_CIK = re.compile(r'/CIK(\d{10})(?:/|\.json)')
AGENT_EMAIL = re.compile(r'[^\s@]+@[^\s@]+\.[A-Za-z]{2,}')

class IntakeError(ValueError):
    pass

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def canonical(obj: object) -> str:
    return sha(json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8'))

def validate_plan(plan: dict) -> None:
    expected={'study_id':STUDY,'phase':'source_lead_not_a_qualified_candidate',
              'cik':CIK,'form':FORM,'filing_selection_cutoff':CUTOFF,
              'selection_rule':'latest_10_K_filed_on_or_before_cutoff_by_filing_date_then_accession',
              'url':URL, 'prior_exposure_independently_verified':False,
              'financial_context_independently_verified':False,
              'real_candidate_generated':False,'independent_gold_available':False,
              'claim':'official_sec_submission_fingerprint_and_filing_locator_only'}
    if plan != expected:
        raise IntakeError('Intake spec is not frozen B13.14 design')

def excluded_ciks(source_manifest: dict) -> set[str]:
    ds = source_manifest.get('datasets') if isinstance(source_manifest,dict) else None
    if not isinstance(ds, dict) or 'sec-companyfacts' not in ds or 'sec-edgar-xbrl' not in ds:
        raise IntakeError('Original SEC-development-source registry missing')
    out=set()
    for name in ('sec-companyfacts','sec-edgar-xbrl'):
        for url in ds[name].get('source_urls',[]):
            m=EXCLUDED_CIK.search(str(url))
            if m: out.add(m.group(1))
    if len(out)<10:
        raise IntakeError('Prior SEC exclusions incomplete; refuse silent source leakage')
    return out

def validate_source_selection(plan:dict, source_manifest:dict)->set[str]:
    validate_plan(plan)
    excluded=excluded_ciks(source_manifest)
    if plan['cik'] in excluded:
        raise IntakeError('Selected CIK occurs in previously exposed SEC sources')
    return excluded

def _iso(s:object)->date:
    if not isinstance(s,str): raise IntakeError('Malformed SEC filing date')
    try: return date.fromisoformat(s)
    except ValueError as exc: raise IntakeError('Malformed SEC filing date') from exc

def _matches_requested_cik(value: object) -> bool:
    """Check exact filer identity across SEC's padded string and integer formats.

    Submissions API objects use a 10-digit, zero-padded string CIK, while other
    SEC sources may represent the same CIK as an integer. We deliberately
    reject booleans, signed/decimal numbers, whitespace, and other issuers.
    """
    if type(value) is int:
        return value == int(CIK)
    if type(value) is str:
        return value in (CIK, str(int(CIK)))
    return False


def select_filing(submission:dict,plan:dict)->dict:
    if not isinstance(submission,dict) or not _matches_requested_cik(submission.get('cik')):
        raise IntakeError('SEC response has unexpected company CIK')
    filing=submission.get('filings',{}).get('recent') if isinstance(submission.get('filings'),dict) else None
    if not isinstance(filing,dict): raise IntakeError('SEC filings.recent missing')
    fields=('form','filingDate','accessionNumber','reportDate','primaryDocument')
    if any(not isinstance(filing.get(k),list) for k in fields):
        raise IntakeError('SEC recent filing arrays missing')
    n=len(filing['form'])
    if n==0 or any(len(filing[k])!=n for k in fields):
        raise IntakeError('SEC recent filing arrays differ in length or are empty')
    cutoff=_iso(plan['filing_selection_cutoff'])
    eligible=[]
    for i in range(n):
        if filing['form'][i] != plan['form']: continue
        day = _iso(filing['filingDate'][i])
        if day>cutoff:continue
        accession=filing['accessionNumber'][i]
        report=filing['reportDate'][i]
        doc=filing['primaryDocument'][i]
        if not isinstance(accession,str) or not ACCESSION.fullmatch(accession):
            raise IntakeError('Malformed SEC accession')
        if not isinstance(doc,str) or not DOCUMENT.fullmatch(doc) or doc in ('.','..'):
            raise IntakeError('Unsafe or missing SEC primaryDocument')
        rdate=_iso(report)
        if rdate>day:
            raise IntakeError('SEC report period ends after filing date')
        eligible.append((day,accession,{'form':FORM,'filing_date':str(day),'report_date':str(rdate),'accession':accession,'primary_document':doc}))
    if not eligible:raise IntakeError('No eligible 10-K in recent filings at frozen cutoff')
    winner=max(eligible,key=lambda x:(x[0],x[1]))[2]
    if not winner['accession'].startswith(str(int(CIK)).zfill(10)+'-'):
        # Some registrants file with an accession prefix belonging to an agent;
        # do not assert filer/accession equivalence from the prefix.
        winner['accession_prefix_differs_from_filer_CIK']=True
    else: winner['accession_prefix_differs_from_filer_CIK']=False
    accession_folder=winner['accession'].replace('-','')
    winner['filing_landing_url']=(f'https://www.sec.gov/Archives/edgar/data/{int(CIK)}/'
                                  f'{accession_folder}/{winner["primary_document"]}')
    return winner

def assert_external_cache(cache:Path,repo:Path)->Path:
    c=cache.expanduser().resolve();r=repo.resolve()
    if c==r or r in c.parents or c==Path(c.anchor):
        raise IntakeError('SEC raw filing cache must be outside repository')
    return c

def _declared_user_agent(agent:str)->str:
    if not isinstance(agent,str) or len(agent)<12 or not AGENT_EMAIL.search(agent):
        raise IntakeError('Set SEC_USER_AGENT to real organization and contact email (SEC fair access)')
    if any(x in agent.lower() for x in ('example.com','example.org','placeholder','your-email','test.invalid')):
        raise IntakeError('Replace placeholder SEC_USER_AGENT with genuine contact info')
    return agent

def fetch_official(agent:str, *, opener=urlopen)->bytes:
    agent=_declared_user_agent(agent)
    req=Request(URL,headers={'User-Agent':agent,'Accept':'application/json','Accept-Encoding':'identity'})
    with opener(req,timeout=35) as resp:
        final=urlsplit(resp.geturl())
        if final.scheme!='https' or final.hostname!='data.sec.gov' or final.path!=urlsplit(URL).path:
            raise IntakeError('SEC host/path redirect changed; manual review required')
        blob=resp.read(MAX_BYTES+1)
    if not (100<len(blob)<=MAX_BYTES) or not blob.lstrip().startswith(b'{'):
        raise IntakeError('Invalid SEC submissions content size or JSON prefix')
    return blob

def make_receipt(raw:bytes,plan:dict,prior:dict)->dict:
    validate_source_selection(plan,prior)
    if not isinstance(raw,bytes):raise IntakeError('Expected official raw JSON bytes')
    try: obj=json.loads(raw)
    except (ValueError,UnicodeDecodeError) as exc:raise IntakeError('SEC download not valid JSON') from exc
    selected=select_filing(obj,plan)
    return {'study_id':STUDY,'classification':'new_source_lead_not_independent_cohort',
            'source_url':URL,'source_cik':CIK,'company_name_from_api':obj.get('name'),
            'download_object':OBJ,'download_sha256':sha(raw),'download_size_bytes':len(raw),
            'original_source_registry_sha256':canonical(prior),
            'intake_plan_sha256':canonical(plan),
            'selected_filing':selected,
            'development_CIK_exclusion_count':len(excluded_ciks(prior)),
            'not_previously_in_listed_SEC_development_CIKs':True,
            'other_prior_exposure_review_required':True,
            'filing_xbrl_context_verified':False,
            'source_semantic_eligibility_verified':False,
            'real_candidate_count':0,'independent_gold':0,'real_gate_runs':0,
            'rights_or_access_checked_by_human':False,
            'limitations':['SEC submissions metadata, not inspected original filing accounting contexts',
               'Disjointness only against listed SEC development CIKs, not all researchers prior exposure',
               'No constraints, gate decisions, or reviewer labels generated']}

def acquire(cache:Path,repo:Path,plan:dict,prior:dict,agent:str,*,fetcher=fetch_official)->dict:
    cache=assert_external_cache(cache,repo)
    validate_source_selection(plan,prior)
    if (cache/OBJ).exists() or (cache/RECEIPT).exists():
        raise IntakeError('Existing SEC intake files: refusing overwrite; use --verify')
    raw=fetcher(agent)
    receipt=make_receipt(raw,plan,prior)
    cache.mkdir(parents=True,exist_ok=True)
    created=[]
    try:
        with (cache/OBJ).open('xb') as f:f.write(raw)
        created.append(cache/OBJ)
        with (cache/RECEIPT).open('x',encoding='utf-8') as f:
            json.dump(receipt,f,sort_keys=True,indent=2,ensure_ascii=False);f.write('\n')
        created.append(cache/RECEIPT)
    except BaseException:
        for p in created:p.unlink(missing_ok=True)
        raise
    return receipt

def verify(cache:Path,repo:Path,plan:dict,prior:dict)->dict:
    cache=assert_external_cache(cache,repo)
    raw=(cache/OBJ).read_bytes()
    expected=make_receipt(raw,plan,prior)
    receipt=json.loads((cache/RECEIPT).read_text(encoding='utf-8'))
    if expected!=receipt:
        raise IntakeError('SEC filing object or provenance receipt changed')
    return receipt
