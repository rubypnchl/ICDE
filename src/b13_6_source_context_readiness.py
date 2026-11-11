"""B13.6 read-only screening: questions and linkage, not source or constraint truth."""
from __future__ import annotations
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

STUDY_ID = "b13_6_source_context_readiness_v1"
DOMAINS = ("finance", "healthcare", "cybersecurity", "manufacturing")
REQUIRED_IDS = {"B13S-FIN-01", "B13S-HLT-01", "B13S-HLT-02", "B13S-CYB-01", "B13S-MAN-01"}
REVIEW_FIELDS = ["source_id", "source_group_id", "object_name", "object_sha256",
                 "release_version", "evidence_url", "evidence_locator",
                 "source_eligibility_rationale", "prior_exposure_declaration",
                 "required_context_policy_document", "cluster_independence_rationale",
                 "access_or_licence_note", "reviewer_id", "review_date_utc", "decision"]
CATEGORIES = {"source_identity", "variable_semantics", "context_applicability", "independence", "rights"}

class ReadinessError(ValueError):
    pass

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()

def canonical_sha(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False,allow_nan=False,
        separators=(',',':')).encode('utf-8')).hexdigest()

def load_json(path: Path) -> dict:
    obj=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(obj,dict):raise ReadinessError('Expected JSON object')
    return obj

def validate_blank_template(path: Path) -> None:
    with path.open('r',encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=REVIEW_FIELDS or list(reader):
            raise ReadinessError('Private human review template must be header-only, unchanged')

def _valid_https(url: str) -> bool:
    if not isinstance(url,str):return False
    try:
        p=urlsplit(url)
        return p.scheme=='https' and bool(p.hostname) and not p.username and not p.password and not p.fragment
    except ValueError:return False

def validate_readiness(register: dict, shortlist: dict) -> dict:
    if not isinstance(register,dict) or not isinstance(shortlist,dict):
        raise ReadinessError('Expected objects')
    if register.get('study_id') != STUDY_ID or register.get('parent_study_id') != 'b13_prospective_matched_evidence_gate_v1':
        raise ReadinessError('Wrong study identity')
    if register.get('parent_shortlist_study_id')!='b13_2_source_eligibility_screening_v1':
        raise ReadinessError('Parent shortlist identity changed')
    if register.get('policy_ancestry')!='b13_5_context_declaration_policy_v2_toy_only':
        raise ReadinessError('Policy version/real-data eligibility misrepresented')
    if (register.get('phase'),register.get('status')) != ('documentation_questions_only_not_source_eligibility','preflight_only_source_eligibility_unverified'):
        raise ReadinessError('Unqualified phase or status')
    if shortlist.get('study_id')!='b13_2_source_eligibility_screening_v1' or shortlist.get('status')!='screening_unverified':
        raise ReadinessError('B13.2 is not the expected shortlist')
    parent=shortlist.get('source_shortlist')
    if not isinstance(parent,list) or len(parent)!=5 or any(not isinstance(s,dict) for s in parent):
        raise ReadinessError('B13.2 source list is missing')
    parent_ids={p.get('id') for p in parent}
    if parent_ids!=REQUIRED_IDS or len(parent_ids)!=len(parent):
        raise ReadinessError('B13.2 IDs changed')
    pmap={p['id']:p for p in parent}
    sources=register.get('sources')
    if not isinstance(sources,list) or len(sources)!=5 or any(not isinstance(s,dict) for s in sources):
        raise ReadinessError('Exactly five documented source entries expected')
    ids=[s.get('source_id') for s in sources]
    if len(set(ids))!=5 or set(ids)!=REQUIRED_IDS:
        raise ReadinessError('Source IDs changed or duplicated')
    counts=Counter()
    question_ids=set()
    common_status={
      'cohort_eligibility_confirmed':0,'source_object_downloads':0,
      'real_candidate_gate_runs':0,'gold_rule_count':0,'independent_reviewer_decisions':0}
    for k,v in common_status.items():
        if type(register.get(k)) is not int or register[k]!=v:raise ReadinessError('Forbidden real-result claim: '+k)
    if register.get('real_b4_context_policy_frozen') is not False or register.get('manual_review_required') is not True:
        raise ReadinessError('Context requirements are not frozen or source-qualified')
    if register.get('allowed_claims')!=['source_specific_review_questions_prepared']:
        raise ReadinessError('Unsupported permitted claim')
    if set(register.get('disallowed_claims',[]))!={
        'source_eligibility_verified','documentary_entailment_verified','real_source_context_policy_frozen',
        'independent_gold_labels','prospective_gate_effect','real_candidate_gate_execution'}:
        raise ReadinessError('Safety exclusions changed')
    for s in sources:
        sid=s['source_id'];p=pmap[sid]
        if s.get('domain') not in DOMAINS or s.get('domain')!=p.get('domain') or s.get('official_url')!=p.get('official_url'):
            raise ReadinessError('B13.2 source identity/URL changed: '+sid)
        if not _valid_https(s['official_url']):raise ReadinessError('Invalid official URL')
        counts[s['domain']]+=1
        if not all(isinstance(s.get(k),str) and s[k].strip() for k in ('documentation_note','prospective_cluster_axis_to_verify')):
            raise ReadinessError('Missing source-review details')
        if s.get('documentation_exposure')!='official_documentation_consulted_before_new_candidate_freeze':
            raise ReadinessError('Previously viewed documentation must be disclosed')
        if s.get('source_selection_status')!='not_selected' or s.get('eligibility_status')!='pending_source_specific_human_review':
            raise ReadinessError('No source eligibility established')
        if s.get('required_b4_context_keys_frozen') is not False or s.get('local_source_object_sha256') is not None or type(s.get('new_candidate_count')) is not int or s['new_candidate_count']!=0:
            raise ReadinessError('No source objects, context policy or candidates frozen')
        qs=s.get('questions')
        if not isinstance(qs,list) or len(qs)<3:
            raise ReadinessError('Too few questions for source: '+sid)
        for q in qs:
            if not isinstance(q,dict) or q.get('question_id') in question_ids or not isinstance(q.get('question_id'),str) or not q['question_id'].startswith(sid+'-Q'):
                raise ReadinessError('Duplicate/invalid question ID')
            question_ids.add(q['question_id'])
            if q.get('category') not in CATEGORIES:
                raise ReadinessError('Unrecognised question category')
            if not isinstance(q.get('question'),str) or len(q['question'].strip())<30:
                raise ReadinessError('Incomplete applicability question')
            key=q.get('potential_b4_context_key')
            if key is not None and (not isinstance(key,str) or not key or not key.replace('_','').isalnum()):
                raise ReadinessError('Invalid *proposed* context key')
            if q.get('evidence_url')!=s['official_url'] or not isinstance(q.get('evidence_locator_to_inspect'),str) or not q['evidence_locator_to_inspect'].strip():
                raise ReadinessError('Documentation evidence locator mismatch')
            if q.get('review_state')!='unresolved' or q.get('documentary_entailment_confirmed') is not False:
                raise ReadinessError('No independent documentary entailment completed')
    if dict(counts)!={'finance':1,'healthcare':2,'cybersecurity':1,'manufacturing':1}:
        raise ReadinessError('Domain coverage changed')
    return {'status':'SOURCE QUESTIONS PASS','source_entries':len(sources),'by_domain':dict(counts),
            'questions_pending':len(question_ids),'eligible_confirmatory_cohorts':0,
            'real_context_policies_frozen':0,'real_candidates':0,'gate_runs':0,'gold_rules':0}
