"""Local integration tests use artificial source BYTES, not genuine SEC source evidence."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.b13_13_matched_pilot import sha256_file, PilotError
from src.metaverify_deadline_sec_pilot import make_packet
from src.metaverify_deadline_controls import run_controls,EXPECTED,_csv,_handover
ROOT=Path(__file__).resolve().parents[1]

class ControlTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
        self.cache=Path(self.t.name)
        self.source=self.cache/'B13_15_CMG_2025_10K_original_inline.html'
        self.source.write_bytes(b'EXPLICIT SYNTHETIC STAND-IN FOR FILE FINGERPRINT TEST')
        agg={'source_filing_sha256':sha256_file(self.source)}
        with patch('src.metaverify_deadline_sec_pilot.EXPECTED_ORIGINAL_SHA256',sha256_file(self.source)):
            self.packet=make_packet(self.cache,ROOT,aggregate=agg,context_id='synthetic_c',unit_id='synthetic_u')

    def test_all_controls_match_expected_decisions(self):
        report=run_controls(self.packet,ROOT)
        self.assertEqual(report['controlled_scenarios_total'],len(EXPECTED))
        for r in report['cases']:
            self.assertEqual((r['A'],r['B'],r['C']),EXPECTED[r['scenario_id']])
        self.assertEqual(report['gold_rules'],0)
        self.assertFalse(report['measured_accuracy_or_gate_effect'])

    def test_source_drift_fails(self):
        self.source.write_bytes(b'changed')
        with self.assertRaises(PilotError):run_controls(self.packet,ROOT)

    def test_no_independent_labels_misrepresented(self):
        report=run_controls(self.packet,ROOT)
        self.assertEqual(report['candidate_count_independent'],1)
        self.assertEqual(report['scenarios_simulated_evidence_not_real'],7)
        self.assertEqual(report['human_reviewer_decisions'],0)
        self.assertIn('not independent test samples',_handover(report))
        self.assertNotIn('p-value:',_csv(report))

if __name__=='__main__': unittest.main()
