import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.b13_13_matched_pilot import (STUDY,PHASE,PilotError, canonical_hash,
    validate_packet, freeze,validate_lock,run_matched,blinded_review_packet,
    read_reviews,score_reviews,exclusive_json)
from src.b13_7_source_acquisition import sha256_file

ROOT=Path(__file__).resolve().parents[1]

class PilotTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.temp=Path(self.t.name)
        self.src=self.temp/'new_source.bin'
        self.src.write_bytes(b'illustrative source object - not a public dataset\n')
        self.cand=self._candidate()
        self.packet={'study_id':STUDY,'phase':PHASE,'candidates':[self.cand]}

    def _candidate(self, cid='FRESH-01'):
        return {'candidate_id':cid,'domain':'finance','source_group':'new_filing_group_alpha',
          'source_file':str(self.src),'source_sha256':sha256_file(self.src),
          'source_evidence_url':'https://example.org/source-doc','source_evidence_locator':'section 4',
          'prior_exposure':'new_disjoint_human_attested',
          'proposal':{'proposal_version':'metaverify-proposal-v0.1', 'id':cid,
            'dataset_id':'new-file-v1','origin':'fixture_only',
            'assertions':[{'left':{'column':'x'},'op':'eq','right':{'column':'y'}}],
            'context_keys':['source_version']},
          'allowed_columns':['x','y'],'parameter_registry':{},
          'source_context_policy':{'required_context_keys':['source_version'],'required_when':None,
              'context_review':'supported','applicability_review':'supported',
              'source_eligibility_review':'supported','reviewer_id':'source-curator-1',
              'basis_url':'https://example.org/source-doc','basis_locator':'context-versions'},
          'policy_evidence':{'metadata':'supported','documentary':{'status':'supported','verified':True,
              'evidence_url':'https://example.org/source-doc','evidence_locator':'rule evidence section'},
              'context_evidence':{'source_version':'supported'},'curator_id':'evidence-curator-2'},
          'field_context_by_column':{'x':{'source_version':'2026-v1'},'y':{'source_version':'2026-v1'}}}

    def _run(self):
        lock,_=freeze(self.packet,ROOT)
        return lock,run_matched(self.packet,lock,ROOT)

    def _votes(self,d1='supports_as_written',d2='not_supported'):
        return ({'FRESH-01':{'decision':d1}}, {'FRESH-01':{'decision':d2}})

    def test_valid_packet(self):
        self.assertEqual(len(validate_packet(self.packet,ROOT)),1)
    def test_empty_is_not_a_real_cohort(self):
        self.packet['candidates']=[]
        with self.assertRaises(PilotError):validate_packet(self.packet,ROOT)
    def test_byte_changed_refused(self):
        self.src.write_bytes(b'mutated source!')
        with self.assertRaises(PilotError):validate_packet(self.packet,ROOT)
    def test_non_string_hash_refused(self):
        self.cand['source_sha256']=None
        with self.assertRaises(PilotError):validate_packet(self.packet,ROOT)
    def test_missing_source_refused(self):
        self.src.unlink()
        with self.assertRaises(PilotError):validate_packet(self.packet,ROOT)
    def test_duplicate_candidate_refused(self):
        self.packet['candidates'].append(copy.deepcopy(self.cand))
        with self.assertRaises(PilotError):validate_packet(self.packet,ROOT)
    def test_gold_leakage_rejected(self):
        self.cand['gold_label']='supported'
        with self.assertRaises(PilotError):validate_packet(self.packet,ROOT)
    def test_bad_source_url_rejected(self):
        self.cand['source_evidence_url']='http://no.example'
        with self.assertRaises(PilotError):validate_packet(self.packet,ROOT)
    def test_proposal_identity_rejected(self):
        self.cand['proposal']['id']='OTHER'
        with self.assertRaises(PilotError):validate_packet(self.packet,ROOT)
    def test_fake_doc_verified_refused(self):
        self.cand['policy_evidence']['documentary']['status']='unknown'
        with self.assertRaises(PilotError):validate_packet(self.packet,ROOT)
    def test_invalid_context_evidence_refused(self):
        self.cand['policy_evidence']['context_evidence']={'fake':'supported'}
        with self.assertRaises(PilotError):validate_packet(self.packet,ROOT)
    def test_lock_changes_rejected(self):
        lock,_=freeze(self.packet,ROOT)
        self.cand['policy_evidence']['metadata']='unknown'
        with self.assertRaises(PilotError):validate_lock(self.packet,lock,ROOT)
    def test_lock_is_hash_only(self):
        lock,_=freeze(self.packet,ROOT)
        text=json.dumps(lock)
        self.assertNotIn(str(self.src),text)
        self.assertNotIn('2026-v1',text)
        self.assertEqual(lock['gate_executions'],0)
    def test_blinded_packet_strips_model_and_gate_decisions(self):
        a=blinded_review_packet(self.packet)
        s=json.dumps(a)
        self.assertNotIn('fixture_only',s)
        self.assertNotIn('metadata_supported',s)
        self.assertNotIn('evidence-curator-2',s)
        self.assertNotIn('arm_counts',s)
    def test_real_engine_compiles_one_candidate(self):
        lock,run=self._run()
        self.assertEqual(run['compiler_invocations'],1)
        self.assertEqual(run['outcomes'][0]['b4_status'],'candidate_executable_unverified')
        self.assertEqual([run['outcomes'][0][x] for x in 'ABC'],['admit']*3)
        self.assertFalse(run['confirmed_gate_effect'])
    def test_compiles_only_once_per_candidate(self):
        import src.b13_13_matched_pilot as module
        original=module.compile_proposal
        calls=[]
        def track(*a,**k):
            calls.append(1);return original(*a,**k)
        lock,_=freeze(self.packet,ROOT)
        with patch.object(module,'compile_proposal',side_effect=track):run_matched(self.packet,lock,ROOT)
        self.assertEqual(len(calls),1)
    def test_missing_compiled_required_context_blocks_C(self):
        self.cand['proposal']['context_keys']=[]
        lock,run=self._run()
        self.assertEqual([run['outcomes'][0][x] for x in 'ABC'],['admit','admit','block'])
    def test_extra_context_abstains_C(self):
        self.cand['proposal']['context_keys'].append('other')
        lock,run=self._run()
        self.assertEqual(run['outcomes'][0]['C'],'abstain')
    def test_mismatched_context_blocks_C(self):
        self.cand['field_context_by_column']['y']['source_version']='2025-v2'
        lock,run=self._run()
        self.assertEqual(run['outcomes'][0]['C'],'block')
    def test_context_type_mismatch_blocks_C(self):
        self.cand['field_context_by_column']['x']['source_version']=1
        self.cand['field_context_by_column']['y']['source_version']='1'
        lock,run=self._run()
        self.assertEqual(run['outcomes'][0]['C'],'block')
    def test_no_field_context_abstains_C(self):
        self.cand['field_context_by_column']={}
        lock,run=self._run()
        self.assertEqual(run['outcomes'][0]['C'],'abstain')
    def test_unverified_doc_abstains_C(self):
        self.cand['policy_evidence']['documentary']['verified']=False
        lock,run=self._run()
        self.assertEqual(run['outcomes'][0]['C'],'abstain')
    def test_contradicted_document_blocks_even_unknown_metadata(self):
        self.cand['policy_evidence']['metadata']='unknown'
        self.cand['policy_evidence']['documentary'].update(status='contradicted',verified=False)
        lock,run=self._run()
        self.assertEqual([run['outcomes'][0][x] for x in 'ABC'],['admit','abstain','block'])
    def test_unknown_metadata_abstains_B_C(self):
        self.cand['policy_evidence']['metadata']='unknown'
        lock,run=self._run()
        self.assertEqual([run['outcomes'][0][x] for x in 'ABC'],['admit','abstain','abstain'])
    def test_source_review_unknown_abstains_C(self):
        self.cand['source_context_policy']['source_eligibility_review']='unknown'
        lock,run=self._run()
        self.assertEqual(run['outcomes'][0]['C'],'abstain')
    def test_source_review_contradiction_blocks_C(self):
        self.cand['source_context_policy']['source_eligibility_review']='contradicted'
        lock,run=self._run()
        self.assertEqual(run['outcomes'][0]['C'],'block')
    def test_missing_when_blocks_C(self):
        self.cand['source_context_policy']['required_when']={'column':'age','op':'gte','value':'18'}
        lock,run=self._run()
        self.assertEqual(run['outcomes'][0]['C'],'block')
    def test_unreviewed_extra_when_abstains_C(self):
        self.cand['allowed_columns'].append('age')
        self.cand['proposal']['when']={'column':'age','op':'gte','value':{'parameter':'adult_age'}}
        self.cand['parameter_registry']['new-file-v1:adult_age']={
            'kind':'number','origin':'fixture_only','rationale':'toy-only','value':'18'}
        lock,run=self._run()
        self.assertEqual(run['outcomes'][0]['C'],'abstain')
    def test_compiler_invalid_blocks_all(self):
        self.cand['proposal']['assertions'][0]['left']={'column':'nonexistent'}
        lock,run=self._run()
        self.assertEqual([run['outcomes'][0][x] for x in 'ABC'],['block']*3)
    def test_scoring_with_unsupported_admission(self):
        lock,run=self._run()
        a,b=self._votes('not_supported','not_supported')
        out=score_reviews(self.packet,lock,run,a,b,None,('blind1','blind2'),None)
        self.assertEqual(out['reference_denominators']['unsupported'],1)
        self.assertEqual(out['arm_metrics']['C']['unsupported_admission_rate'],1)
    def test_scores_null_denominator_without_reference_truth(self):
        lock,run=self._run()
        a,b=self._votes('needs_more_evidence','needs_more_evidence')
        out=score_reviews(self.packet,lock,run,a,b,None,('blind1','blind2'),None)
        self.assertIsNone(out['arm_metrics']['C']['unsupported_admission_rate'])
        self.assertEqual(out['reference_denominators']['unresolved'],1)
    def test_disagreement_without_adjudicator_unresolved(self):
        lock,run=self._run()
        a,b=self._votes()
        out=score_reviews(self.packet,lock,run,a,b,None,('blind1','blind2'),None)
        self.assertEqual(out['reference_denominators']['unresolved'],1)
    def test_disagreement_with_distinct_adjudicator(self):
        lock,run=self._run()
        a,b=self._votes()
        out=score_reviews(self.packet,lock,run,a,b,{'FRESH-01':{'decision':'not_supported'}},
                          ('blind1','blind2'),'independent3')
        self.assertEqual(out['reference_denominators']['unsupported'],1)
    def test_same_reviewer_and_curator_denied(self):
        lock,run=self._run();a,b=self._votes()
        with self.assertRaises(PilotError):
            score_reviews(self.packet,lock,run,a,b,None,('source-curator-1','blind2'),None)
    def test_duplicate_reviewer_identity_denied(self):
        lock,run=self._run();a,b=self._votes()
        with self.assertRaises(PilotError):score_reviews(self.packet,lock,run,a,b,None,('blind1','blind1'),None)
    def test_exclusive_file_no_overwrite(self):
        p=self.temp/'report.json';exclusive_json(p,{'v':1})
        with self.assertRaises(FileExistsError):exclusive_json(p,{'v':2})
    def test_reviewer_csv(self):
        path=self.temp/'review.csv'
        with path.open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=['candidate_id','reviewer_id','decision','evidence_url','evidence_locator','rationale'])
            writer.writeheader();writer.writerow({'candidate_id':'FRESH-01','reviewer_id':'blind1',
                'decision':'supports_as_written','evidence_url':'https://example.org/doc',
                'evidence_locator':'Section A','rationale':'Independent example review'})
        reviews,rid=read_reviews(path,{'FRESH-01'},'reviewer1')
        self.assertEqual(rid,'blind1');self.assertEqual(reviews['FRESH-01']['decision'],'supports_as_written')

if __name__=='__main__': unittest.main()
