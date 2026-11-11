"""B13.13: gated *pilot*, never an independently confirmed B13 effect study.

Locks source/proposal/evidence snapshots, compiles each typed hypothesis exactly once,
exposes no arm decisions in blinded reviewer packets, and scores only supplied human
review records. Software cannot authenticate independent reviewers or documents.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.rule_bridge import compile_proposal
from src.generic_verifier import validate_rule
from src.b13_4_b4_adapter import normalize_b4_compilation, AdapterError
from src.b13_7_source_acquisition import assert_external_cache, sha256_file

STUDY = 'b13_13_real_input_matched_arm_pilot_v1'
PHASE = 'pilot_not_confirmatory_no_unverified_gold'
DOMAINS = {'finance', 'healthcare', 'cybersecurity', 'manufacturing'}
SIGNALS = {'supported', 'unknown', 'contradicted'}
DECISIONS = {'admit', 'abstain', 'block'}
VOTES = {'supports_as_written', 'supports_with_conditions', 'not_supported', 'needs_more_evidence'}
REVIEW_HEADERS = ['candidate_id','reviewer_id','decision','evidence_url','evidence_locator','rationale']
SENSITIVE = {'gold','gold_label','reference_label','adjudicated','reviewer_votes','arm_decisions','outcome','final_label'}

class PilotError(ValueError):
    """Violation of frozen input, role separation, or policy contract."""


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                                     allow_nan=False).encode('utf-8')).hexdigest()


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(value, dict):
        raise PilotError('JSON root must be an object')
    return value


def https_url(url: Any) -> bool:
    if not isinstance(url, str):
        return False
    p = urlparse(url)
    return p.scheme == 'https' and bool(p.hostname) and not p.username and not p.password


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 250


def _signal(s: Any) -> bool:
    return isinstance(s, str) and s in SIGNALS


def _rationale(s: Any) -> bool:
    return isinstance(s, str) and bool(s.strip()) and len(s) <= 4000


def _single_candidate(c: dict, root: Path) -> None:
    expected = {'candidate_id','domain','source_group','source_file','source_sha256',
                'source_evidence_url','source_evidence_locator','prior_exposure',
                'proposal','allowed_columns','parameter_registry','source_context_policy',
                'policy_evidence','field_context_by_column'}
    if not isinstance(c, dict) or set(c) != expected or set(c) & SENSITIVE:
        raise PilotError('Unexpected candidate fields; reviewer truth and outcomes are forbidden')
    if not _nonempty(c['candidate_id']) or c['domain'] not in DOMAINS or not _nonempty(c['source_group']):
        raise PilotError('Invalid candidate identifier/domain/source group')
    if not c['candidate_id'].isascii() or any(z not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-' for z in c['candidate_id']):
        raise PilotError('Unsafe candidate identifier')
    if c['prior_exposure'] not in {'new_disjoint_human_attested','previously_inspected','unknown'}:
        raise PilotError('Prior exposure must be explicitly disclosed')
    if not https_url(c['source_evidence_url']) or not _nonempty(c['source_evidence_locator']):
        raise PilotError('Source requires HTTPS documentation URL and locator')
    if not isinstance(c['source_file'], str) or not c['source_file'].strip():
        raise PilotError('Source file path must be a nonempty string')
    source = Path(c['source_file']).expanduser().resolve()
    root = root.resolve()
    if root == source or root in source.parents:
        raise PilotError('Source data must not be stored in the Git repository')
    if (not source.is_file() or not isinstance(c['source_sha256'], str) or
            len(c['source_sha256']) != 64 or not all(h in '0123456789abcdef' for h in c['source_sha256'])):
        raise PilotError('Source path or SHA-256 missing')
    if sha256_file(source) != c['source_sha256']:
        raise PilotError('Source bytes changed or provided source fingerprint is wrong')
    proposal = c['proposal']
    if not isinstance(proposal, dict) or proposal.get('id') != c['candidate_id'] or not _nonempty(proposal.get('dataset_id')):
        raise PilotError('Typed proposal identity differs from candidate')
    if set(proposal) & SENSITIVE:
        raise PilotError('Reference truth cannot be attached to proposal')
    allowed = c['allowed_columns']
    if (not isinstance(allowed, list) or len(allowed) < 2 or len(set(allowed)) != len(allowed)
            or not all(_nonempty(x) for x in allowed)):
        raise PilotError('Missing source-scoped allowed columns')
    if not isinstance(c['parameter_registry'], dict):
        raise PilotError('Parameter registry must be a typed dictionary')
    policy = c['source_context_policy']
    if (not isinstance(policy, dict) or set(policy) != {'required_context_keys', 'required_when',
           'context_review', 'applicability_review', 'source_eligibility_review', 'reviewer_id', 'basis_url', 'basis_locator'}):
        raise PilotError('Source policy lacks independent predeclaration fields')
    keys = policy['required_context_keys']
    if not isinstance(keys, list) or any(not _nonempty(k) for k in keys) or len(keys) != len(set(keys)):
        raise PilotError('Invalid source-required context list')
    if policy['required_when'] is not None and not isinstance(policy['required_when'], dict):
        raise PilotError('Required applicability predicate must be null or typed AST')
    if not all(_signal(policy[k]) for k in ('context_review','applicability_review','source_eligibility_review')):
        raise PilotError('Missing explicit source-context review states')
    if not _nonempty(policy['reviewer_id']) or not https_url(policy['basis_url']) or not _nonempty(policy['basis_locator']):
        raise PilotError('Source-review identity/basis missing')
    evidence = c['policy_evidence']
    if not isinstance(evidence, dict) or set(evidence) != {'metadata','documentary','context_evidence','curator_id'}:
        raise PilotError('Policy evidence schema changed')
    if not _signal(evidence['metadata']) or not _nonempty(evidence['curator_id']):
        raise PilotError('Invalid metadata signal or curator')
    doc = evidence['documentary']
    if not isinstance(doc, dict) or set(doc) != {'status','verified','evidence_url','evidence_locator'}:
        raise PilotError('Malformed documentary signal')
    if not _signal(doc['status']) or type(doc['verified']) is not bool:
        raise PilotError('Invalid documentary state')
    if doc['verified'] and doc['status'] != 'supported':
        raise PilotError('Only supported documentary evidence can be marked verified')
    if doc['status'] == 'supported' and (not https_url(doc['evidence_url']) or not _nonempty(doc['evidence_locator'])):
        raise PilotError('Supported documentary claim needs source URL and locator')
    ctx = evidence['context_evidence']
    if not isinstance(ctx, dict) or set(ctx) - set(keys) or any(not _signal(v) for v in ctx.values()):
        raise PilotError('Context evidence must use only predeclared keys')
    fields = c['field_context_by_column']
    if not isinstance(fields, dict) or set(fields) - set(allowed) or any(not isinstance(v, dict) for v in fields.values()):
        raise PilotError('Per-field contexts do not match source-scoped column names')
    for col, val in fields.items():
        if set(val) - set(keys) or any(x is None or isinstance(x, (dict, list)) for x in val.values()):
            raise PilotError('Malformed per-field context metadata')


def validate_packet(packet: dict, repo_root: Path) -> list[dict]:
    if not isinstance(packet, dict) or set(packet) != {'study_id','phase','candidates'}:
        raise PilotError('Unexpected packet structure')
    if packet['study_id'] != STUDY or packet['phase'] != PHASE:
        raise PilotError('B13.13 always remains a non-confirmatory pilot')
    rows = packet['candidates']
    if not isinstance(rows, list) or not rows or len(rows) > 100:
        raise PilotError('At least one and at most 100 genuinely sourced candidates required')
    seen = set()
    for c in rows:
        _single_candidate(c, repo_root)
        if c['candidate_id'] in seen:
            raise PilotError('Duplicate candidate identifier')
        seen.add(c['candidate_id'])
    return rows


def blinded_review_packet(packet: dict) -> dict:
    """Never reveal metadata/documentary gate signals, source-curator IDs or arm outcomes."""
    entries = []
    for c in packet['candidates']:
        proposal = dict(c['proposal'])
        proposal.pop('origin', None)  # generation method identity is blinded
        entries.append({'candidate_id': c['candidate_id'], 'domain': c['domain'],
           'source_group':c['source_group'], 'source_evidence_url':c['source_evidence_url'],
           'source_evidence_locator':c['source_evidence_locator'],
           'proposal_without_model_origin':proposal,
           'proposed_registered_parameter_values_without_curator_provenance':{
             k:{'kind':v.get('kind'),'value':v.get('value')}
             for k,v in c['parameter_registry'].items() if isinstance(v,dict)},
           'allowed_columns':list(c['allowed_columns']),
           'reviewer_instruction':'Assess semantic support as written for this source/context. No gate outputs or model source are supplied.'})
    return {'study_id':STUDY,'phase':'blinded_review_packet_no_arm_decisions',
            'candidates':entries,'human_reference_votes_supplied':False}


def engine_hashes(repo_root: Path) -> dict:
    paths = ['src/rule_bridge.py','src/generic_verifier.py','src/b13_4_b4_adapter.py',
             'src/b13_13_matched_pilot.py']
    return {x:sha256_file(repo_root/x) for x in paths}


def freeze(packet: dict, repo_root: Path) -> tuple[dict, dict]:
    rows = validate_packet(packet, repo_root)
    frozen = {'study_id':STUDY, 'phase':'frozen_pilot_inputs_no_gate',
              'input_canonical_sha256':canonical_hash(packet),
              'engine_file_sha256':engine_hashes(repo_root),
              'candidates':[{'candidate_id':c['candidate_id'],'domain':c['domain'],
                    'source_group':c['source_group'],'prior_exposure':c['prior_exposure'],
                    'source_sha256':c['source_sha256'],
                    'proposal_sha256':canonical_hash(c['proposal']),
                    'parameter_registry_sha256':canonical_hash(c['parameter_registry']),
                    'source_context_policy_sha256':canonical_hash(c['source_context_policy']),
                    'evidence_sha256':canonical_hash(c['policy_evidence'])} for c in rows],
              'source_eligibility_independently_confirmed_by_software':False,
              'prospective_confirmatory_cohorts':0,'gold_labels':0,'gate_executions':0}
    return frozen, blinded_review_packet(packet)


def validate_lock(packet: dict, lock: dict, repo_root: Path) -> None:
    expected, _ = freeze(packet, repo_root)
    if lock != expected:
        raise PilotError('Frozen input or engine drift: new lock requires documented protocol deviation')


def _decision(c: dict, result: Any, adapter: dict) -> tuple[dict,dict]:
    if adapter['compiler'] == 'blocked':
        return ({k:'block' for k in 'ABC'}, {k:'b4_rejected_or_blocked' for k in 'ABC'})
    if adapter['compiler'] == 'unknown':
        return ({k:'abstain' for k in 'ABC'}, {k:'b4_unresolved' for k in 'ABC'})
    out = {'A':'admit','B':'admit','C':'admit'}
    why = {'A':'typed_compilation_only','B':'metadata_supported','C':'source_policy_and_evidence_supported'}
    evidence=c['policy_evidence']; policy=c['source_context_policy']
    if evidence['metadata']=='contradicted':
        out['B']=out['C']='block'; why['B']=why['C']='metadata_contradicted'
        return out,why
    if evidence['metadata']=='unknown':
        out['B']=out['C']='abstain'; why['B']=why['C']='metadata_unknown'
    doc = evidence['documentary']; ctx=evidence['context_evidence']
    if doc['status']=='contradicted' or any(s=='contradicted' for s in ctx.values()):
        out['C']='block'; why['C']='document_or_context_contradicted'
        return out,why
    required=set(policy['required_context_keys']); declared=set(result.rule['context_keys'])
    if required - declared:
        out['C']='block'; why['C']='required_context_missing_from_compiled_rule'
        return out,why
    if policy['required_when'] is not None and result.rule.get('when')!=policy['required_when']:
        out['C']='block'; why['C']='required_applicability_predicate_not_executable'
        return out,why
    if policy['required_when'] is None and result.rule.get('when') is not None:
        out['C']='abstain'; why['C']='unreviewed_extra_applicability_predicate'
        return out,why
    if declared-required:
        out['C']='abstain'; why['C']='undeclared_source_policy_context_added'
        return out,why
    if any(policy[k]=='contradicted' for k in ('context_review','applicability_review','source_eligibility_review')):
        out['C']='block'; why['C']='source_review_contradicted'
        return out,why
    if any(policy[k]!='supported' for k in ('context_review','applicability_review','source_eligibility_review')):
        out['C']='abstain'; why['C']='source_review_not_qualified'
        return out,why
    if doc['status']!='supported' or not doc['verified']:
        out['C']='abstain'; why['C']='documentary_evidence_unverified'
        return out,why
    if any(ctx.get(key)!='supported' for key in required):
        out['C']='abstain'; why['C']='missing_context_evidence'
        return out,why
    refs=validate_rule(result.rule)
    for key in required:
        values=[]
        for column in sorted(refs):
            value=c['field_context_by_column'].get(column,{}).get(key)
            if value is None:
                out['C']='abstain'; why['C']='per_field_context_unavailable'
                return out,why
            values.append(value)
        if len({canonical_hash({'type':type(v).__name__,'value':v}) for v in values})>1:
            out['C']='block'; why['C']='incompatible_field_context_values'
            return out,why
    return out,why


def run_matched(packet: dict, lock: dict, repo_root: Path) -> dict:
    validate_lock(packet,lock,repo_root)
    outcomes=[]
    counts={k:Counter() for k in 'ABC'}
    for c in packet['candidates']:
        result=compile_proposal(c['proposal'],c['allowed_columns'],c['parameter_registry'])
        try:
            a=normalize_b4_compilation(result,c['proposal'],c['allowed_columns'],validate_rule_fn=validate_rule)
        except AdapterError as exc:
            raise PilotError('B4/B3 compiler contract does not meet frozen assumptions') from exc
        arm, reasons=_decision(c,result,a)
        if arm['C']=='admit' and arm['B']!='admit' or arm['B']=='admit' and arm['A']!='admit':
            raise PilotError('Nested admission policy broken')
        for name,status in arm.items():
            counts[name][status]+=1
        outcomes.append({'candidate_id':c['candidate_id'],'domain':c['domain'],
              'source_group':c['source_group'], 'b4_status':a['b4_status'],
              'A':arm['A'],'B':arm['B'],'C':arm['C'], 'reasons':reasons,
              'manual_source_and_documentary_evidence_not_independently_authenticated_by_software':True})
    return {'study_id':STUDY,'phase':'real_input_matched_arm_pilot_not_confirmatory',
            'input_canonical_sha256':lock['input_canonical_sha256'],
            'frozen_lock_canonical_sha256':canonical_hash(lock),
            'candidate_count':len(outcomes),'compiler_invocations':len(outcomes),
            'arm_counts':{arm:{state:counts[arm][state] for state in ('admit','abstain','block')} for arm in 'ABC'},
            'outcomes':outcomes,'gold_labels_read':False,'confirmed_gate_effect':False,
            'source_evidence_authenticity_proved':False,
            'claim':'matched_development_pilot_only_not_prospective_accuracy'}


def read_reviews(path: Path, expected_ids: set, role: str) -> tuple[dict,str]:
    with path.open('r',newline='',encoding='utf-8-sig') as f:
        dr=csv.DictReader(f)
        if dr.fieldnames != REVIEW_HEADERS:
            raise PilotError('Reviewer input schema changed: '+role)
        rows=list(dr)
    if not rows or len(rows)!=len(expected_ids):
        raise PilotError('Reviewer file incomplete: '+role)
    ids=set(); persons=set(); out={}
    for row in rows:
        if None in row or any(v is None for v in row.values()):
            raise PilotError('Malformed reviewer CSV row')
        cid=row['candidate_id']; reviewer=row['reviewer_id']
        if cid in ids or cid not in expected_ids or not _nonempty(reviewer):
            raise PilotError('Unexpected/duplicate reference review candidate')
        ids.add(cid); persons.add(reviewer)
        if row['decision'] not in VOTES or not https_url(row['evidence_url']) or not _nonempty(row['evidence_locator']) or not _rationale(row['rationale']):
            raise PilotError('Review needs vote, source, locator and rationale')
        out[cid]=row
    if ids!=expected_ids or len(persons)!=1:
        raise PilotError('Each review file needs exactly one reviewer across all candidates')
    return out,next(iter(persons))


def score_reviews(packet: dict, lock: dict, run: dict, reviewer1: dict, reviewer2: dict,
                  adjudication: dict | None, reviewer_ids: tuple[str,str], adj_id: str | None) -> dict:
    if run.get('phase')!='real_input_matched_arm_pilot_not_confirmatory' or run.get('frozen_lock_canonical_sha256')!=canonical_hash(lock):
        raise PilotError('Matched-run provenance incorrect')
    ids={c['candidate_id'] for c in packet['candidates']}
    if set(reviewer1)!=ids or set(reviewer2)!=ids or {x['candidate_id'] for x in run.get('outcomes',[])}!=ids:
        raise PilotError('Candidate sets are not identical across reviews and arms')
    people=set(reviewer_ids)
    if len(people)!=2 or not all(_nonempty(p) for p in people):
        raise PilotError('Two different independent reviewer IDs required')
    if adj_id is not None:
        if not _nonempty(adj_id) or adj_id in people:
            raise PilotError('Adjudicator must be distinct')
        people.add(adj_id)
    source_roles={c['source_context_policy']['reviewer_id'] for c in packet['candidates']}
    source_roles|={c['policy_evidence']['curator_id'] for c in packet['candidates']}
    if people & source_roles:
        raise PilotError('Reference and source evidence roles must be distinct')
    if adjudication is not None and set(adjudication)!=ids:
        raise PilotError('Adjudication must cover exact candidate set')
    by_id={row['candidate_id']:row for row in run['outcomes']}
    counts={'supported':0,'unsupported':0,'unresolved':0}
    metrics={a:{'unsupported_admitted':0,'supported_admitted':0,'abstain_unsupported':0,'abstain_supported':0} for a in 'ABC'}
    agree=0; differed=0
    for cid in sorted(ids):
        x=reviewer1[cid]['decision'];y=reviewer2[cid]['decision']
        if x==y:
            agree+=1
            label=x
        else:
            differed+=1
            label=adjudication[cid]['decision'] if adjudication is not None else 'needs_more_evidence'
        # Conditional support needs independently verified executable conditions, not just an unblinded vote.
        truth='supported' if label=='supports_as_written' else ('unsupported' if label=='not_supported' else 'unresolved')
        counts[truth]+=1
        for arm in 'ABC':
            status=by_id[cid][arm]
            if truth=='unsupported':
                metrics[arm]['unsupported_admitted']+=int(status=='admit')
                metrics[arm]['abstain_unsupported']+=int(status=='abstain')
            elif truth=='supported':
                metrics[arm]['supported_admitted']+=int(status=='admit')
                metrics[arm]['abstain_supported']+=int(status=='abstain')
    result={}
    for arm in 'ABC':
        m=metrics[arm]
        result[arm]={**m,'unsupported_admission_rate':m['unsupported_admitted']/counts['unsupported'] if counts['unsupported'] else None,
                   'supported_admission_rate':m['supported_admitted']/counts['supported'] if counts['supported'] else None}
    return {'study_id':STUDY,'phase':'human_votes_entered_exploratory_pilot_not_gold_certification',
            'frozen_lock_canonical_sha256':canonical_hash(lock),'matched_run_canonical_sha256':canonical_hash(run),
            'reviewers_different_ids':True,'human_independence_cannot_be_authenticated_by_software':True,
            'reviewer_agreements':agree,'reviewer_disagreements':differed,
            'reference_denominators':counts,'arm_metrics':result,
            'source_group_count':len({c['source_group'] for c in packet['candidates']}),
            'published_comparator_baseline_measured':False,
            'confidence_intervals_or_pvalues_computed':False,
            'claim':'descriptive_conditional_on_attested_human_votes_only_not_confirmatory'}


def exclusive_json(path: Path, value: Any) -> None:
    with path.open('x',encoding='utf-8') as f:
        json.dump(value,f,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False)
        f.write('\n')
