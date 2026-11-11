"""Synthetic mutation tests: structural readiness ONLY, no source eligibility truth."""
from __future__ import annotations
import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path
from src.b13_6_source_context_readiness import (ReadinessError,validate_readiness,
    validate_blank_template,canonical_sha,REVIEW_FIELDS)
ROOT=Path(__file__).resolve().parents[1]
REG=json.loads((ROOT/'data/evaluation/b13_6_source_context_questions_v1.json').read_text(encoding='utf-8'))
PARENT=json.loads((ROOT/'data/evaluation/b13_2_source_screening_v1.json').read_text(encoding='utf-8'))

def altered(mut):
    val=copy.deepcopy(REG);mut(val);return val
class B136Tests(unittest.TestCase):
    def test_initial_preflight(self):
        a=validate_readiness(REG,PARENT)
        self.assertEqual(a['source_entries'],5)
        self.assertEqual(a['eligible_confirmatory_cohorts'],0)
        self.assertGreaterEqual(a['questions_pending'],20)
    def test_canonical_hash_stable_across_json_formatting(self):
        self.assertEqual(canonical_sha(REG),canonical_sha(json.loads(json.dumps(REG,indent=5))))
    def test_no_empty_ids(self):
        with self.assertRaises(ReadinessError):validate_readiness(altered(lambda d:d['sources'][0].update(source_id='')),PARENT)
    def test_no_duplicate_source(self):
        with self.assertRaises(ReadinessError):validate_readiness(altered(lambda d:d['sources'][1].update(source_id=d['sources'][0]['source_id'])),PARENT)
    def test_no_fake_domain(self):
        with self.assertRaises(ReadinessError):validate_readiness(altered(lambda d:d['sources'][0].update(domain='healthcare')),PARENT)
    def test_no_rogue_url(self):
        with self.assertRaises(ReadinessError):validate_readiness(altered(lambda d:d['sources'][0].update(official_url='https://example.org/')),PARENT)
    def test_no_claim_source_selected(self):
        with self.assertRaises(ReadinessError):validate_readiness(altered(lambda d:d['sources'][0].update(source_selection_status='selected')),PARENT)
    def test_no_gold_count(self):
        with self.assertRaises(ReadinessError):validate_readiness(altered(lambda d:d.update(gold_rule_count=1)),PARENT)
    def test_no_fake_truth(self):
        with self.assertRaises(ReadinessError):validate_readiness(altered(lambda d:d['sources'][0]['questions'][0].update(documentary_entailment_confirmed=True)),PARENT)
    def test_no_freeze_required_context(self):
        with self.assertRaises(ReadinessError):validate_readiness(altered(lambda d:d['sources'][0].update(required_b4_context_keys_frozen=True)),PARENT)
    def test_no_sha_claim(self):
        with self.assertRaises(ReadinessError):validate_readiness(altered(lambda d:d['sources'][0].update(local_source_object_sha256='0'*64)),PARENT)
    def test_no_new_candidates(self):
        with self.assertRaises(ReadinessError):validate_readiness(altered(lambda d:d['sources'][0].update(new_candidate_count=1)),PARENT)
    def test_no_altered_ancestry(self):
        with self.assertRaises(ReadinessError):validate_readiness(altered(lambda d:d.update(policy_ancestry='verified_real_policy')),PARENT)
    def test_question_required(self):
        with self.assertRaises(ReadinessError):validate_readiness(altered(lambda d:d['sources'][0].update(questions=[])),PARENT)
    def test_question_duplicate_rejected(self):
        with self.assertRaises(ReadinessError):validate_readiness(altered(lambda d:d['sources'][0]['questions'].append(copy.deepcopy(d['sources'][0]['questions'][0]))),PARENT)
    def test_exposure_must_be_disclosed(self):
        with self.assertRaises(ReadinessError):validate_readiness(altered(lambda d:d['sources'][0].update(documentation_exposure='unseen')),PARENT)
    def test_tampered_parent_source(self):
        p=copy.deepcopy(PARENT);p['source_shortlist'][0]['official_url']='https://example.org/'
        with self.assertRaises(ReadinessError):validate_readiness(REG,p)
    def test_template_header_only(self):
        validate_blank_template(ROOT/'data/evaluation/b13_6_manual_source_review_TEMPLATE.csv')
    def test_template_cannot_contain_reviews(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'form.csv'
            with path.open('w',newline='',encoding='utf-8') as f:
                w=csv.writer(f);w.writerow(REVIEW_FIELDS);w.writerow(['id']+['']*(len(REVIEW_FIELDS)-1))
            with self.assertRaises(ReadinessError):validate_blank_template(path)

if __name__=='__main__':unittest.main()
