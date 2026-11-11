import copy
from decimal import Decimal
import json
import tempfile
import unittest
from pathlib import Path

from src.b13_9_documented_pair_consistency import (
    PairAuditError, PAIRS, BINS, validate_plan, summarize_pair, _percentile,
    _check_b138_report, exclusive_save,
)
from src.b13_8_source_schema_audit import canonical_sha, PINNED, STUDY as B138_STUDY

ROOT = Path(__file__).resolve().parents[1]
PLAN = json.loads((ROOT / 'data/evaluation/b13_9_documented_pair_plan_v1.json').read_text())
REG = json.loads((ROOT / 'data/evaluation/b13_7_source_objects_v1.json').read_text())
B138 = json.loads((ROOT / 'data/evaluation/b13_8_schema_audit_plan_v1.json').read_text())

class PairTests(unittest.TestCase):
    def test_plan_valid(self):
        validate_plan(PLAN)
    def test_three_published_pairs_only(self):
        self.assertEqual(len(PAIRS), 3)
    def test_tampered_factor_rejected(self):
        v = copy.deepcopy(PLAN); v['pairs'][0]['factor'] = '1.2'
        with self.assertRaises(PairAuditError): validate_plan(v)
    def test_tampered_documentary_source_rejected(self):
        v = copy.deepcopy(PLAN); v['pairs'][1]['documentation_url'] = 'https://example.org'
        with self.assertRaises(PairAuditError): validate_plan(v)
    def test_tampered_threshold_rejected(self):
        v = copy.deepcopy(PLAN); v['absolute_residual_thresholds_mmol_l'].append('1')
        with self.assertRaises(PairAuditError): validate_plan(v)
    def test_tampered_discovery_claim_rejected(self):
        v = copy.deepcopy(PLAN); v['source_eligibility_confirmed'] = True
        with self.assertRaises(PairAuditError): validate_plan(v)
    def test_tampered_output_policy_rejected(self):
        v = copy.deepcopy(PLAN); v['output_policy'] = 'write_rows'
        with self.assertRaises(PairAuditError): validate_plan(v)
    def test_basic_residual_counts(self):
        out = summarize_pair([100, 200, 300], [1.129, 2.258, 3.39], '0.01129')
        self.assertEqual(out['rows_total'], 3)
        self.assertEqual(out['paired_nonmissing'], 3)
        self.assertEqual(out['absolute_residual_mmol_l']['max'], '0.00300')
        self.assertEqual(out['absolute_residual_mmol_l']['threshold_counts_cumulative']['0.005'], 3)
    def test_missingness_distinguished(self):
        out = summarize_pair([None, 2, float('nan'), 4], [None, None, 1, 8], '2')
        self.assertEqual(out['both_missing'], 1)
        self.assertEqual(out['only_right_missing'], 1)
        self.assertEqual(out['only_left_missing'], 1)
        self.assertEqual(out['paired_nonmissing'], 1)
    def test_no_paired_values_not_falsely_zero_accuracy(self):
        out = summarize_pair([None], [None], '2')
        self.assertIsNone(out['absolute_residual_mmol_l']['median'])
        self.assertEqual(out['paired_nonmissing'], 0)
    def test_misaligned_rejected(self):
        with self.assertRaises(PairAuditError): summarize_pair([1], [1,2], '2')
    def test_invalid_factor_rejected(self):
        with self.assertRaises(PairAuditError): summarize_pair([1], [2], '0')
    def test_nonfinite_rejected(self):
        with self.assertRaises(PairAuditError): summarize_pair([float('inf')], [1], '2')
    def test_nonnumeric_rejected(self):
        with self.assertRaises(PairAuditError): summarize_pair(['cat'], [1], '2')
    def test_boolean_rejected(self):
        with self.assertRaises(PairAuditError): summarize_pair([True], [1], '2')
    def test_bins_must_increase(self):
        with self.assertRaises(PairAuditError): summarize_pair([1], [1], '2', ('0.1', '0.01'))
    def test_percentile_one_value(self):
        self.assertEqual(_percentile([Decimal('0.04')], 95), '0.04')
    def test_parent_report_ancestry_tamper_rejected(self):
        rep = {
            'study_id': B138_STUDY, 'classification': 'exploratory_source_schema_characterization_only',
            'source_registry_canonical_sha256': canonical_sha(REG), 'b13_8_plan_canonical_sha256':canonical_sha(B138),
            'source_file_receipts': [{'source_id': sid, 'source_group': t[3], 'sha256': t[1], 'size_bytes':t[2]} for sid,t in PINNED.items()],
            'real_candidates_generated': 0, 'real_gate_executions': 0, 'independently_adjudicated_gold_rules': 0,
            'source_semantic_eligibility_verified': False, 'healthcare':[{'source_id':'B13S-HLT-01'},{'source_id':'B13S-HLT-02'}],
            'nhanes_cycle_join_inventory': {'raw_identifiers_emitted': False}
        }
        _check_b138_report(rep, REG, B138)
        rep['real_gate_executions'] = 1
        with self.assertRaises(PairAuditError): _check_b138_report(rep, REG, B138)
    def test_report_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / 'cache'
            cache.mkdir()
            first = exclusive_save(cache, Path(tmp) / 'repo', {'study_id':'toy'})
            self.assertTrue(first.exists())
            with self.assertRaises(FileExistsError): exclusive_save(cache, Path(tmp) / 'repo', {'study_id':'overwrite'})

if __name__ == '__main__': unittest.main()
