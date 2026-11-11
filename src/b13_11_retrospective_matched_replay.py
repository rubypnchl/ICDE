"""B13.11: retrospective read-only B4/B3 execution on pre-exposed NHANES pairs.

This is an ENGINEERING DIAGNOSTIC, not independent human review or a prospective gate experiment.
No participant identifiers or raw values are serialized. Exact equality mismatches are NOT data errors.
"""
from __future__ import annotations

import csv
from hashlib import sha256
import io
import json
from pathlib import Path

from src.b13_7_source_acquisition import assert_external_cache, verify_existing, sha256_file, validate_registry
from src.b13_8_source_schema_audit import canonical_sha, validate_plan as validate_b138_plan, PINNED
from src.b13_9_documented_pair_consistency import validate_plan as validate_b139_plan
from src.b13_10_documentary_triage import validate_register, assess_external_cache
from src.b13_3_admission_policy import evaluate_three_arms
from src.b13_4_b4_adapter import normalize_b4_compilation, AdapterError
from src.rule_bridge import compile_proposal
from src.generic_verifier import validate_rule, evaluate_rows

STUDY = 'b13_11_real_xpt_matched_compiler_diagnostic_v1'
PAIRS = ('TRIGLY_TR_UNIT','TRIGLY_LDL_UNIT','TCHOL_TC_UNIT')
REPORTS = ('B13_8_source_schema_audit_v1.json','B13_9_documented_pair_consistency_v1.json',
           'B13_10_documentary_applicability_triage_v1.json')
OUTPUTS = ('B13_11_retrospective_matched_replay_v1.json',
           'B13_11_candidate_outcomes_v1.csv', 'B13_11_manuscript_table_v1.tex',
           'B13_11_handover_v1.md')

class ReplayError(ValueError):
    """Any missing input, unsupported claim, provenance drift or unsafe result."""


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def load_inputs(root: Path) -> tuple[dict,dict,dict,dict,dict]:
    directory=root/'data'/'evaluation'
    return tuple(read_json(directory/n) for n in (
       'b13_11_replay_spec_v1.json','b13_7_source_objects_v1.json',
       'b13_8_schema_audit_plan_v1.json','b13_9_documented_pair_plan_v1.json',
       'b13_10_evidence_applicability_register_v1.json'))


def validate_spec(spec: dict, b137: dict, b138: dict, b139: dict, b1310: dict) -> None:
    validate_registry(b137)
    validate_b138_plan(b138,b137)
    validate_b139_plan(b139)
    validate_register(b1310,b137,b139)
    if not isinstance(spec,dict) or spec.get('study_id')!=STUDY:
        raise ReplayError('Unknown replay protocol')
    if spec.get('phase')!='retrospective_pre_exposed_documented_pairs_not_prospective_not_gold':
        raise ReplayError('Prospective/independent claim forbidden')
    if spec.get('parent_b13_9_plan_canonical_sha256')!=canonical_sha(b139):
        raise ReplayError('B13.9 plan ancestry changed')
    if spec.get('parent_b13_10_register_canonical_sha256')!=canonical_sha(b1310):
        raise ReplayError('B13.10 register ancestry changed')
    if spec.get('pair_ids')!=list(PAIRS) or spec.get('dataset_ids')!=['b13_11_'+p for p in PAIRS]:
        raise ReplayError('Frozen diagnostic pairs changed')
    frozen={
        'context_key':'survey_cycle',
        'context_source':'one_source_XPT_dataset_group_not_participant_eligibility',
        'b3_numerical_assertion':'exact_equality_without_inferred_rounding_or_tolerance',
        'compiler_invocations_per_pair':1,
        'arm_policy_mode':'B13_3_deterministic_semantics_reused_for_retrospective_engineering_diagnostic_only',
        'diagnostic_metadata_signal':'supported',
        'documentary_signal':'supported',
        'documentary_independently_verified':False,
        'survey_cycle_context_signal':'supported',
        'real_source_context_policy_independently_frozen':False,
        'independent_reference_judgments':0,
        'confirmatory_candidates':0,
        'allowed_claims':['B4_B3_executed_on_locally_receipt_verified_retrospective_XPT','diagnostic_three_arm_decisions_not_semantic_accuracy','exact_equality_execution_counts_not_defect_labels'],
    }
    for key,val in frozen.items():
        if spec.get(key)!=val or type(spec.get(key)) is not type(val):
            raise ReplayError('Protocol drift: '+key)
    if set(spec.get('disallowed_claims',[]))!={'prospective_gate_effect','independent_gold','novel_constraint_discovery','natural_data_error','verified_documentary_entailment','source_eligibility_confirmed','precision_truth'}:
        raise ReplayError('Scientific limitation protections changed')


def make_candidate(item: dict, group: str, spec: dict) -> tuple[dict,dict,list[str]]:
    """Explicit hand-authored retrospective translation of a published pair, not model discovery."""
    pid=item['pair_id']
    if pid not in PAIRS or item.get('factor') not in ('0.01129','0.02586') or group!='nhanes_2015_2016_cycle':
        raise ReplayError('Unrecognized retrospective candidate')
    ds='b13_11_'+pid
    left,right=item['left_column'],item['right_column']
    context=spec['context_key']
    proposal={
        'proposal_version':'metaverify-proposal-v0.1', 'id':ds,
        'dataset_id':ds, 'origin':'hand_curated_from_previously_exposed_CDC_documentation_B13_9',
        'assertions':[{'left':{'column':right},'op':'eq',
                       'right':{'multiply':[{'column':left},{'parameter':'published_factor'}]}}],
        'context_keys':[context]
    }
    registry={f'{ds}:published_factor':{
        'kind':'number','value':item['factor'],'origin':'documented_reference',
        'source_url':item['documentation_url'],
        'rationale':'Previously exposed CDC codebook factor; no independent reviewer, precision rule, or source eligibility established.'
    }}
    return proposal,registry,[left,right]


def diagnostic_admission(proposal:dict, compilation:object, columns:list[str], item:dict, spec:dict) -> tuple[dict,dict]:
    try:
        adapter=normalize_b4_compilation(compilation,proposal,columns,validate_rule_fn=validate_rule)
    except (AdapterError, ValueError, TypeError) as exc:
        raise ReplayError("B4/B3 adapter rejected compiled candidate") from exc
    if adapter['compiler']!='compiled':
        raise ReplayError('Known published factor did not compile under actual B4')
    rule=compilation.rule
    context=spec['context_key']
    if not isinstance(rule,dict) or set(rule.get('context_keys',[]))!={context}:
        raise ReplayError('Missing/extra compiled context: refuse real-source diagnostic')
    for key in columns:
        if key not in validate_rule(rule):
            raise ReplayError('Compiler dropped a pair variable')
    # This calls the deterministic decision semantics previously exercised in B13.3,
    # but DOES NOT promote its toy-only policy into a independently frozen real policy.
    case={'candidate_id':proposal['id'],'compiler':adapter['compiler'],
          'metadata':spec['diagnostic_metadata_signal'],
          'documentary':{'status':spec['documentary_signal'],
                         'verified':spec['documentary_independently_verified'],
                         'evidence_url':item['documentation_url'],
                         'evidence_locator':item['documentation_section']},
          'required_contexts':[context],
          'context_evidence':{context:spec['survey_cycle_context_signal']}}
    decisions=evaluate_three_arms(case)
    if decisions != {'A':'admit','B':'admit','C':'abstain'}:
        raise ReplayError('Diagnostic gate policy diverged: documentary evidence unreviewed')
    return adapter,decisions


def execute_pair(frame:object, item:dict, group:str, spec:dict, *, compiler=compile_proposal,
                 row_evaluator=evaluate_rows) -> dict:
    proposal,registry,columns=make_candidate(item,group,spec)
    if not all(c in frame.columns for c in columns):
        raise ReplayError('Real XPT lacks documented pair column')
    compilation=compiler(proposal,columns,registry)  # exactly once; same result all arms
    adapter,decisions=diagnostic_admission(proposal,compilation,columns,item,spec)
    refs=validate_rule(compilation.rule)
    if refs!=set(columns):
        raise ReplayError('Unexpected references in compiled expression')
    context=spec['context_key']
    # Per-field source group is independently assigned from the pre-existing XPT
    # registry identity, NOT from a LLM and NOT a clinical eligibility assertion.
    context_template={c:{context:group} for c in columns}
    values=(frame[columns[0]],frame[columns[1]])
    rows=({'_field_context':context_template, columns[0]:x, columns[1]:y}
          for x,y in zip(*values))
    outcome=row_evaluator(compilation.rule,rows)
    if outcome.get('record_count')!=len(frame) or set(outcome.get('counts',{}))!={'satisfied','violated','not_applicable','abstained'}:
        raise ReplayError('Unexpected B3 result structure')
    counts=outcome['counts']
    if any(type(v) is not int or v<0 for v in counts.values()) or sum(counts.values())!=len(frame):
        raise ReplayError('Invalid executable B3 counts')
    if counts['not_applicable']!=0:
        raise ReplayError('No applicability predicate exists; not_applicable must be zero')
    if outcome['evaluated_records'] != counts['satisfied']+counts['violated']:
        raise ReplayError('B3 evaluated count mismatch')
    return {'pair_id':item['pair_id'],'source_id':item['source_id'],
            'source_group':group,'b4_status':adapter['b4_status'],
            'compiler_parameter_origin':'documented_reference_previously_exposed',
            'b4_compiler_calls':1,'declared_compiled_context_keys':[context],
            'b3_counts':counts,'record_count':len(frame),'evaluated_records':outcome['evaluated_records'],
            'A':decisions['A'],'B':decisions['B'],'C':decisions['C'],
            'documentary_verification_independent':False,
            'applicability_review_complete':False,'exact_equality_only':True,
            'violations_mean_real_errors':False,'independent_gold_available':False,
            'candidate_origin':'hand_curated_known_documented_relationship'}


def _check_reports(cache:Path,root:Path,b137:dict,b138:dict,b139:dict,b1310:dict) -> tuple[dict,dict,dict,dict]:
    before={p:sha256_file(cache/p) for p in REPORTS}
    rpt={p:read_json(cache/p) for p in REPORTS}
    validated=assess_external_cache(cache,root,b1310,b137,b138,b139)
    if canonical_sha(validated)!=canonical_sha(rpt[REPORTS[2]]):
        raise ReplayError('B13.10 external report no longer matches validated B13.8/9 lineage')
    if any(sha256_file(cache/p)!=h for p,h in before.items()):
        raise ReplayError('A parent aggregate report changed while reading')
    return rpt[REPORTS[0]],rpt[REPORTS[1]],rpt[REPORTS[2]],before


def run_replay(cache:Path,root:Path,spec:dict,b137:dict,b138:dict,b139:dict,b1310:dict,
               *, reader=None, compiler=compile_proposal, row_evaluator=evaluate_rows) -> dict:
    validate_spec(spec,b137,b138,b139,b1310)
    cache=assert_external_cache(cache,root)
    r8,r9,r10,parents=_check_reports(cache,root,b137,b138,b139,b1310)
    if any(r10.get(k)!=0 for k in ('source_documentary_reviews_independently_adjudicated',
                                    'eligible_confirmatory_relationships','independent_gold_rules')):
        raise ReplayError('Unexpected B13.10 independent reference outcomes')
    sources={x['source_id']:x for x in b137['source_ids']}
    pair_map={x['pair_id']:x for x in b139['pairs']}
    reg={}
    for sid in ('B13S-HLT-01','B13S-HLT-02'):
        receipt=verify_existing(sources[sid],cache)
        if (receipt['object_name'],receipt['sha256'],receipt['size_bytes'],receipt['source_group'])!=PINNED[sid]:
            raise ReplayError('Pinned B13.8 source bytes changed')
        reg[sid]=receipt
    if reader is None:
        try:
            import pyreadstat
        except ImportError as exc:
            raise ReplayError('Install pyreadstat and pandas into $py') from exc
        reader=pyreadstat.read_xport
    frames={}
    for sid in reg:
        frame,_=reader(str(cache/reg[sid]['object_name']))
        if len(frame)!=next(x['row_count'] for x in r8['healthcare'] if x['source_id']==sid):
            raise ReplayError('XPT row count differs from B13.8')
        frames[sid]=frame
    summary=[]
    pairs_by_id={p['pair_id']:p for p in r9['conversion_pairs']}
    for pid in PAIRS:
        p=pair_map[pid]
        sid=p['source_id'];group=reg[sid]['source_group']
        candidate=execute_pair(frames[sid],p,group,spec,compiler=compiler,row_evaluator=row_evaluator)
        if candidate['evaluated_records'] != pairs_by_id[pid]['aggregates']['paired_nonmissing']:
            raise ReplayError('B3 complete-pair count does not match B13.9')
        summary.append(candidate)
    if any(sha256_file(cache/reg[sid]['object_name'])!=reg[sid]['sha256'] for sid in reg):
        raise ReplayError('XPT source altered during evaluation')
    if any(sha256_file(cache/p)!=h for p,h in parents.items()):
        raise ReplayError('Parent report altered during execution')
    totals={arm:{s:sum(row[arm]==s for row in summary) for s in ('admit','abstain','block')} for arm in ('A','B','C')}
    return {
      'study_id':STUDY,
      'classification':'retrospective_real_data_engineering_replay_not_prospective_no_gold',
      'spec_sha256':canonical_sha(spec),
      'parent_aggregate_sha256':parents,
      'data_source_receipts_sha256':{sid:reg[sid]['sha256'] for sid in reg},
      'shared_source_cluster':'nhanes_2015_2016_cycle',
      'pair_candidates_hand_curated':len(summary),
      'source_clusters':1,
      'B4_compiler_invocations':sum(x['b4_compiler_calls'] for x in summary),
      'B3_execution_on_source_records':True,
      'policy_mode':'diagnostic_deterministic_B13_3_semantics_not_frozen_real_policy',
      'arm_counts':totals,
      'pair_outcomes':summary,
      'gold_rules':0,'independent_documentary_reviews':0,'confirmatory_candidates':0,
      'matched_arm_semantic_accuracy_defined':False,
      'exact_equality_mismatch_counts_are_data_errors':False,
      'prior_formula_exposure':True,
      'interpretation':'B4/B3 implementation and diagnostic arm decisions on pre-exposed source pairs; no precision truth, independent reference labels, or causal gate benefit.'
    }


def render_csv(report:dict)->str:
    f=io.StringIO(newline='')
    w=csv.writer(f,lineterminator='\n')
    w.writerow(['pair_id','source_id','source_group','records','evaluated','exact_satisfied','exact_mismatched','abstained','A','B','C','gold'])
    for r in report['pair_outcomes']:
        c=r['b3_counts']
        w.writerow([r['pair_id'],r['source_id'],r['source_group'],r['record_count'],r['evaluated_records'],
                    c['satisfied'],c['violated'],c['abstained'],r['A'],r['B'],r['C'],'NO'])
    return f.getvalue()


def render_tex(report:dict)->str:
    lines=['% B13.11 retrospective diagnostic; NOT prospective accuracy evidence.',
           '% Exact-equality mismatches are NOT adjudicated natural data errors.',
           r'\begin{tabular}{lrrrrccc}',r'\toprule',
           r'Pair & Paired & Exact match & Mismatch & Abstain & A & B & C \\',r'\midrule']
    for r in report['pair_outcomes']:
        c=r['b3_counts']
        pair_tex=r["pair_id"].replace("_",r"\_")
        lines.append(f"{pair_tex} & {r['evaluated_records']:,} & {c['satisfied']:,} & {c['violated']:,} & {c['abstained']:,} & {r['A']} & {r['B']} & {r['C']} " + chr(92)*2)
    lines.extend([r'\bottomrule',r'\end{tabular}',
      r'% One NHANES survey-cycle cluster; 0 independent gold; 0 prospective gate results.'])
    return '\n'.join(lines)+'\n'


def render_handover(report:dict)->str:
    rs=report['pair_outcomes']
    pairtext='; '.join(f"{r['pair_id']}: {r['evaluated_records']:,} complete, {r['b3_counts']['satisfied']:,} exact matches, {r['b3_counts']['violated']:,} mismatches, {r['b3_counts']['abstained']:,} abstentions" for r in rs)
    return f'''# B13.11 — Results handover to manuscript coauthor (retrospective engineering diagnostic)

## Ready-to-adapt text

We conducted a retrospective executable-rule diagnostic on three previously documented unit conversions from two NHANES 2015–2016 laboratory releases. Hand-curated typed hypotheses were safely compiled once per relationship using MetaVerify's B4 compiler with previously published, provenance-registered conversion factors, and executed by the B3 verifier on locally fingerprint-checked XPT records. The three relationships yielded {pairtext}. The executable assertions intentionally used strict equality without a fitted or independently established rounding/tolerance specification. Consequently, numerical mismatches cannot be interpreted as natural data errors. Applying the deterministic three-arm admission semantics as a diagnostic (not a frozen real-source policy), arms A and B admitted all three compilable hypotheses, while arm C abstained on all three because independent documentary verification and applicability adjudication were unavailable. The three relationships originate from one previously inspected NHANES cycle; there was no independent gold, no novel discovery, and no prospective estimate of gate effectiveness.

## Decisions and limitations

- **May include:** Source-count reproducibility, compilation statuses, row-level interpreter execution counts, diagnostic arm decisions, and context/documentary uncertainty.
- **Must not include:** Precision/recall, false-positive reductions, verified semantic correctness, natural-defect counts, causal evidence-gate gains, or three independent cohorts.
- **Do not confuse:** B13.11's unreviewed diagnostic evidence signals with a real source-qualified evidence policy; B13.5's original source policy was toy-only.
- **Unit:** 3 hand-curated previously published pairs from one NHANES cycle, NOT three independent discovery trials.
- **Next requirement:** Independent adjudication on newly frozen hypotheses and actual applicability-context enforcement for publication-grade effectiveness claims.

## Provenance

- Source object receipts: {report['data_source_receipts_sha256']}
- Replay specification fingerprint: {report['spec_sha256']}
- B4 compiler calls: {report['B4_compiler_invocations']}; independent gold rules: 0

The accompanying CSV and LaTeX table are descriptive engineering diagnostic results, not inference about the proposed gate's accuracy.
'''


def exclusive_write_outputs(cache:Path,root:Path,report:dict)->list[Path]:
    cache=assert_external_cache(cache,root)
    if not cache.is_dir():
        raise ReplayError('Missing external cache')
    names=[cache/n for n in OUTPUTS]
    if any(p.exists() for p in names):
        raise ReplayError('At least one output exists; refusing to overwrite')
    payloads=[json.dumps(report,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n',
              render_csv(report),render_tex(report),render_handover(report)]
    created=[]
    try:
        for target,data in zip(names,payloads):
            with target.open('x',encoding='utf-8',newline='') as f:
                f.write(data)
            created.append(target)
    except BaseException:
        for path in created:
            if path.exists():path.unlink()
        raise
    return names
