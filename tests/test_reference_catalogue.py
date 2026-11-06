"""B6 audit regressions. Entirely offline, synthetic metadata fixtures; no claim of real-data validation."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'audit_b6_catalogue.py'
spec=importlib.util.spec_from_file_location('audit_b6_catalogue',SCRIPT)
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class B6CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.cat=json.loads((ROOT/'data/evaluation/b6_reference_catalogue.json').read_text(encoding='utf-8-sig'))
        self.protocol=json.loads((ROOT/'data/evaluation/b6_protocol_v1.json').read_text(encoding='utf-8-sig'))
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        for domain,(dataset_id,filename) in audit.META.items():
            path=self.root/filename
            path.parent.mkdir(parents=True,exist_ok=True)
            cols=set()
            for entry in self.cat['entries']:
                if entry['domain']==domain and entry['metadata_scope']=='repository_columns':
                    cols.update(entry['columns'])
            path.write_text(json.dumps({'dataset':{'id':dataset_id},'columns':[{'name':col} for col in sorted(cols)]}),encoding='utf-8')

    def check(self,cat=None,protocol=None):
        return audit.check_catalogue(self.root,self.cat if cat is None else cat,self.protocol if protocol is None else protocol)

    def test_seed_is_auditable_and_not_final_gold(self):
        result=self.check()
        self.assertEqual(result['entry_count'],5)
        self.assertEqual(result['final_gold_eligible_count'],0)
        self.assertEqual(result['status_counts']['provisional_source_supported'],2)

    def test_all_domains_are_present(self):
        self.assertEqual({e['domain'] for e in self.cat['entries']},set(audit.META))

    def test_duplicate_rule_id_rejected(self):
        changed=copy.deepcopy(self.cat)
        changed['entries'].append(copy.deepcopy(changed['entries'][0]))
        with self.assertRaisesRegex(ValueError,'duplicate'):
            self.check(changed)

    def test_provisional_cannot_claim_gold_status(self):
        changed=copy.deepcopy(self.cat)
        changed['entries'][3]['scoring_eligible']=True
        with self.assertRaisesRegex(ValueError,'final gold'):
            self.check(changed)

    def test_case_sensitive_metadata_mismatch_rejected(self):
        changed=copy.deepcopy(self.cat)
        entry=changed['entries'][3]
        entry['columns']=[x.lower() if x=='Machine failure' else x for x in entry['columns']]
        with self.assertRaisesRegex(ValueError,'absent from metadata'):
            self.check(changed)

    def test_proposal_and_reference_columns_match(self):
        changed=copy.deepcopy(self.cat)
        changed['entries'][4]['columns'].append('Unexpected')
        with self.assertRaisesRegex(ValueError,'absent from metadata'):
            self.check(changed)

    def test_rule_id_mismatch_rejected(self):
        changed=copy.deepcopy(self.cat)
        changed['entries'][3]['reference_rule']['id']='WRONG'
        with self.assertRaisesRegex(ValueError,'identity mismatch'):
            self.check(changed)

    def test_excluded_rule_cannot_execute(self):
        changed=copy.deepcopy(self.cat)
        changed['entries'][2]['reference_rule']=copy.deepcopy(changed['entries'][1]['reference_rule'])
        with self.assertRaisesRegex(ValueError,'excluded rule'):
            self.check(changed)

    def test_external_finance_scope_cannot_claim_source_qualified(self):
        changed=copy.deepcopy(self.cat)
        changed['entries'][1]['status']='provisional_source_supported'
        with self.assertRaisesRegex(ValueError,'external taxonomy'):
            self.check(changed)

    def test_missing_metadata_file_rejected(self):
        (self.root/'data/metadata/cic-ids2017.json').unlink()
        with self.assertRaisesRegex(ValueError,'metadata missing'):
            self.check()

    def test_protocol_mismatch_rejected(self):
        changed=copy.deepcopy(self.protocol)
        changed['protocol_id']='other'
        with self.assertRaisesRegex(ValueError,'identifier mismatch'):
            self.check(protocol=changed)

    def test_frozen_protocol_required(self):
        changed=copy.deepcopy(self.protocol)
        changed['frozen_before_future_paid_comparison']=False
        with self.assertRaisesRegex(ValueError,'freeze'):
            self.check(protocol=changed)

    def test_fake_source_url_rejected(self):
        changed=copy.deepcopy(self.cat)
        changed['entries'][0]['evidence'][0]['url']='not-a-url'
        with self.assertRaisesRegex(ValueError,'source/evidence URL'):
            self.check(changed)

    def test_all_nonexcluded_dsl_rules_parse(self):
        for entry in self.cat['entries']:
            rule=entry['reference_rule']
            if rule:
                self.assertTrue(audit.validate_rule(rule))

    def test_no_gold_denominator_before_review(self):
        self.assertEqual(sum(bool(e['scoring_eligible']) for e in self.cat['entries']),0)

if __name__=='__main__':
    unittest.main()
