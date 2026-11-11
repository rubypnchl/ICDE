"""Offline contract tests; fixture numbers do not constitute SEC empirical results."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.b13_13_matched_pilot import freeze,run_matched,sha256_file
from src.metaverify_deadline_sec_pilot import audited_pair, make_packet,run, PilotError
from src.b13_15_sec_filing_context_audit import InlineAuditParser

ROOT=Path(__file__).resolve().parents[1]

def fixture(duplicate=False, dimensional=False, date='2025-12-31', entity='1058090'):
    seg='<xbrli:segment><xbrldi:explicitMember dimension="abc:a">abc:b</xbrldi:explicitMember></xbrli:segment>' if dimensional else ''
    dup='<ix:nonFraction name="us-gaap:Assets" contextRef="c1" unitRef="u1">100</ix:nonFraction>' if duplicate else ''
    return (f'''<!DOCTYPE html><html><ix:header><ix:resources>
<xbrli:context id="c1"><xbrli:entity><xbrli:identifier>{entity}</xbrli:identifier>{seg}</xbrli:entity><xbrli:period><xbrli:instant>{date}</xbrli:instant></xbrli:period></xbrli:context>
<xbrli:unit id="u1"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
</ix:resources></ix:header><body>
<ix:nonFraction name="us-gaap:Assets" contextRef="c1" unitRef="u1">100</ix:nonFraction>
<ix:nonFraction name="us-gaap:LiabilitiesAndStockholdersEquity" contextRef="c1" unitRef="u1">100</ix:nonFraction>{dup}</body></html>''').encode()

def aggregate(source):
    return dict(source_filing_sha256=sha256_file(source),numeric_ix_fact_count=2,
                same_context_same_unit_target_pair_instances=1,
                target_pair_ambiguous_duplicate_instances=0,
                structural_opportunity_count=1,
                xbrl_context_count=1)

class DeadlineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache=Path(self.temp.name)
        self.source=self.cache/'B13_15_CMG_2025_10K_original_inline.html'
        self.source.write_bytes(fixture())
        self.audit=aggregate(self.source)

    def test_pair_is_one_and_scoped(self):
        self.assertEqual(audited_pair(self.source.read_bytes(),self.audit),('c1','u1'))

    def test_duplicate_blocks(self):
        with self.assertRaises(PilotError):audited_pair(fixture(duplicate=True),self.audit)

    def test_different_date_blocks(self):
        with self.assertRaises(PilotError):audited_pair(fixture(date='2024-12-31'),self.audit)

    def test_dimension_blocks(self):
        with self.assertRaises(PilotError):audited_pair(fixture(dimensional=True),self.audit)

    def test_different_entity_blocks(self):
        with self.assertRaises(PilotError):audited_pair(fixture(entity='320193'),self.audit)

    def test_packet_freeze_matched_and_no_gold(self):
        with patch('src.metaverify_deadline_sec_pilot.EXPECTED_ORIGINAL_SHA256',sha256_file(self.source)):
            packet=make_packet(self.cache,ROOT,aggregate=self.audit,context_id='c1',unit_id='u1')
            lock,blind=freeze(packet,ROOT)
            result=run_matched(packet,lock,ROOT)
        self.assertEqual(result['compiler_invocations'],1)
        self.assertEqual(result['arm_counts']['A']['admit'],1)
        self.assertEqual(result['arm_counts']['B']['admit'],1)
        self.assertEqual(result['arm_counts']['C']['abstain'],1)
        self.assertNotIn('origin',blind['candidates'][0]['proposal_without_model_origin'])
        self.assertIs(result['gold_labels_read'], False)
        self.assertNotIn('monetary_amount',json.dumps(result))

    def test_one_step_no_overwrite(self):
        with patch('src.metaverify_deadline_sec_pilot.EXPECTED_ORIGINAL_SHA256',sha256_file(self.source)), \
             patch('src.metaverify_deadline_sec_pilot.verify_b1315',return_value=self.audit):
            report,files=run(self.cache,ROOT)
            self.assertEqual(len(files),5)
            self.assertTrue(all(f.exists() for f in files))
            with self.assertRaises(PilotError):run(self.cache,ROOT)

    def test_source_hash_change_stops(self):
        with self.assertRaises(PilotError):make_packet(self.cache,ROOT,aggregate=self.audit,context_id='c1',unit_id='u1')

if __name__=='__main__':unittest.main()
