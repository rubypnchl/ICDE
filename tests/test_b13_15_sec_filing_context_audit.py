from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.b13_14_sec_intake import (CIK,OBJ as PARENT_OBJ,RECEIPT as PARENT_RECEIPT,
    make_receipt, sha, select_filing)
from src.b13_15_sec_filing_context_audit import (FilingAuditError,RAW,RECEIPT,AUDIT,OPPORTUNITIES,
    official_source, check_filing_url, fetch_html, scan_html, serialize_opportunities,
    acquire, audit, verify, verified_raw, InlineAuditParser, EXPECTED_URL)

PLAN={'study_id':'b13_14_disjoint_sec_filing_intake_v1',
      'phase':'source_lead_not_a_qualified_candidate','cik':CIK,'form':'10-K',
      'filing_selection_cutoff':'2026-11-11',
      'selection_rule':'latest_10_K_filed_on_or_before_cutoff_by_filing_date_then_accession',
      'url':'https://data.sec.gov/submissions/CIK0001058090.json',
      'prior_exposure_independently_verified':False,
      'financial_context_independently_verified':False,
      'real_candidate_generated':False,'independent_gold_available':False,
      'claim':'official_sec_submission_fingerprint_and_filing_locator_only'}
PRIOR={'datasets':{'sec-companyfacts':{'source_urls':[
    f'https://data.sec.gov/api/xbrl/companyfacts/CIK{1000000000+i}.json' for i in range(10)]},
    'sec-edgar-xbrl':{'source_urls':['https://data.sec.gov/api/xbrl/companyconcept/CIK1000000000/us-gaap/Assets.json']}}}
SUB={'cik':'0001058090','name':'CHIPOTLE MEXICAN GRILL INC','filings':{'recent':{
    'form':['10-K'],'filingDate':['2026-02-04'],
    'accessionNumber':['0001058090-26-000009'],'reportDate':['2025-12-31'],
    'primaryDocument':['cmg-20251231.htm']}}}


def html(*, duplicate=False, with_pair=True, changed_date=False, with_dimension=False,
         entity='1058090', unlinked=False):
    period='2025-12-30' if changed_date else '2025-12-31'
    segment='<xbrli:segment><xbrldi:explicitMember dimension="us-gaap:LegalEntityAxis">cmg:MyEntityMember</xbrldi:explicitMember></xbrli:segment>' if with_dimension else ''
    s=f'''<!DOCTYPE html><html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
    <ix:header><ix:resources><xbrli:context id="c0"><xbrli:entity>
    <xbrli:identifier scheme="http://www.sec.gov/CIK">{entity}</xbrli:identifier>{segment}
    </xbrli:entity><xbrli:period><xbrli:instant>{period}</xbrli:instant></xbrli:period>
    </xbrli:context><xbrli:unit id="u0"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit></ix:resources></ix:header><body>
    <ix:nonFraction name="us-gaap:Assets" contextRef="c0" unitRef="u0">100</ix:nonFraction>
    '''
    if with_pair:
        s+='''<ix:nonFraction name="us-gaap:LiabilitiesAndStockholdersEquity" contextRef="c0" unitRef="u0">100</ix:nonFraction>'''
    if duplicate:
        s+='''<ix:nonFraction name="us-gaap:Assets" contextRef="c0" unitRef="u0">100</ix:nonFraction>'''
    if unlinked:
        s+='''<ix:nonFraction name="us-gaap:Assets" contextRef="unlinked" unitRef="u0">100</ix:nonFraction>'''
    s+='</body></html>'
    return s.encode()


def parent():
    return make_receipt(json.dumps(SUB).encode(),PLAN,PRIOR)


class Tests(unittest.TestCase):
    def setUp(self):
        self.p=parent()

    def test_receipt_selected_source(self):
        self.assertEqual(official_source(self.p),EXPECTED_URL)

    def test_refuse_different_accession(self):
        self.p['selected_filing']['accession']='0001058090-26-000010'
        with self.assertRaises(FilingAuditError):official_source(self.p)

    def test_refuse_semantic_eligibility_claim(self):
        self.p['source_semantic_eligibility_verified']=True
        with self.assertRaises(FilingAuditError):official_source(self.p)

    def test_url_rejects_host(self):
        with self.assertRaises(FilingAuditError):check_filing_url(EXPECTED_URL.replace('www.sec.gov','evil.sec.gov'))

    def test_url_rejects_query(self):
        with self.assertRaises(FilingAuditError):check_filing_url(EXPECTED_URL+'?modified=1')

    def test_url_accepts_exact(self):check_filing_url(EXPECTED_URL)

    def test_valid_context_and_matching_fact(self):
        report,rows=scan_html(html(),self.p,'parenthash')
        self.assertEqual(report['structural_opportunity_count'],1)
        self.assertEqual(report['numeric_ix_fact_count'],2)
        self.assertEqual(report['dimensionless_expected_entity_instant_contexts'],1)
        self.assertEqual(report['same_context_same_unit_target_pair_instances'],1)
        self.assertFalse(rows[0]['duplicate_or_missing_context_flag'])

    def test_no_right_concept(self):
        report,rows=scan_html(html(with_pair=False),self.p,'parenthash')
        self.assertEqual(report['structural_opportunity_count'],0)
        self.assertEqual(rows,[])

    def test_wrong_period(self):
        report,_=scan_html(html(changed_date=True),self.p,'parenthash')
        self.assertEqual(report['same_context_same_unit_target_pair_instances'],0)

    def test_dimensional_context_not_scope(self):
        report,_=scan_html(html(with_dimension=True),self.p,'parenthash')
        self.assertEqual(report['dimensionless_expected_entity_instant_contexts'],0)

    def test_entity_mismatch(self):
        report,_=scan_html(html(entity='320193'),self.p,'parenthash')
        self.assertEqual(report['same_context_same_unit_target_pair_instances'],0)

    def test_padded_entity_accepted(self):
        report,_=scan_html(html(entity=CIK),self.p,'parenthash')
        self.assertEqual(report['same_context_same_unit_target_pair_instances'],1)

    def test_duplicate_facts_flagged(self):
        report,rows=scan_html(html(duplicate=True),self.p,'parenthash')
        self.assertEqual(report['target_pair_ambiguous_duplicate_instances'],1)
        self.assertTrue(rows[0]['duplicate_or_missing_context_flag'])

    def test_unresolved_context_flagged(self):
        report,rows=scan_html(html(unlinked=True),self.p,'parenthash')
        self.assertEqual(report['numeric_facts_with_unresolved_context'],1)
        self.assertTrue(rows[0]['duplicate_or_missing_context_flag'])

    def test_no_context_stops(self):
        with self.assertRaises(FilingAuditError):scan_html(b'<html><ix:nonFraction contextRef="c0"/></html>',self.p,'hash')

    def test_no_numeric_fact_stops(self):
        with self.assertRaises(FilingAuditError):scan_html(html().replace(b'ix:nonFraction',b'ix:someOther'),self.p,'hash')

    def test_no_gold_in_report(self):
        report,rows=scan_html(html(),self.p,'parenthash')
        self.assertFalse(report['consolidation_scope_independently_qualified'])
        self.assertEqual(report['independent_gold_rules'],0)
        self.assertFalse(report['candidate_packet_created'])
        self.assertNotIn('record_level_amounts',json.dumps(report))

    def test_opportunity_has_no_financial_values(self):
        report,rows=scan_html(html(),self.p,'parenthash')
        out=serialize_opportunities(rows)
        self.assertIn('structural_co_location_only',out)
        self.assertNotIn('100',out)
        self.assertIn('opportunity_id',out)

    def test_fetch_redirect_stop(self):
        class Resp:
            headers={'Content-Type':'text/html'}
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def geturl(self):return 'https://example.org/evil'
            def read(self,n):return html()*10
        with self.assertRaises(FilingAuditError):
            fetch_html(EXPECTED_URL,'Example University contact@university.ac.uk',opener=lambda *a,**k:Resp())

    def test_fetch_accepts_official(self):
        class Resp:
            headers={'Content-Type':'text/html'}
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def geturl(self):return EXPECTED_URL
            def read(self,n):return html()*10
        out=fetch_html(EXPECTED_URL,'Example University contact@university.ac.uk',opener=lambda *a,**k:Resp())
        self.assertTrue(out.startswith(b'<!DOCTYPE'))

    def test_tampered_original_filing_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'repo';root.mkdir()
            cache=Path(td)/'cache';cache.mkdir()
            blob=json.dumps(SUB).encode()
            (cache/PARENT_OBJ).write_bytes(blob)
            (cache/PARENT_RECEIPT).write_text(json.dumps(self.p))
            acquire(cache,root,PLAN,PRIOR,'University somebody@academic.org',fetcher=lambda *args:html())
            (cache/RAW).write_bytes(html(duplicate=True))
            with self.assertRaises(FilingAuditError):verified_raw(cache,root,PLAN,PRIOR)

    def test_full_acquire_audit_verify(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'repo';root.mkdir()
            cache=Path(td)/'cache';cache.mkdir()
            blob=json.dumps(SUB).encode()
            (cache/PARENT_OBJ).write_bytes(blob)
            (cache/PARENT_RECEIPT).write_text(json.dumps(self.p))
            receipt=acquire(cache,root,PLAN,PRIOR,'University person@academic.org',fetcher=lambda *args:html())
            self.assertEqual(receipt['raw_sha256'],sha(html()))
            report,rows=audit(cache,root,PLAN,PRIOR)
            self.assertEqual(report['structural_opportunity_count'],1)
            self.assertEqual(len(rows),1)
            self.assertEqual(verify(cache,root,PLAN,PRIOR)['structural_opportunity_count'],1)
            with self.assertRaises(FilingAuditError):audit(cache,root,PLAN,PRIOR)
            with self.assertRaises(FilingAuditError):acquire(cache,root,PLAN,PRIOR,'University person@academic.org',fetcher=lambda *a:html())

    def test_tampered_audit_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'repo';root.mkdir()
            cache=Path(td)/'cache';cache.mkdir()
            (cache/PARENT_OBJ).write_bytes(json.dumps(SUB).encode())
            (cache/PARENT_RECEIPT).write_text(json.dumps(self.p))
            acquire(cache,root,PLAN,PRIOR,'University person@academic.org',fetcher=lambda *a:html())
            audit(cache,root,PLAN,PRIOR)
            text=(cache/AUDIT).read_text()
            (cache/AUDIT).write_text(text.replace('"independent_gold_rules": 0','"independent_gold_rules": 1'))
            with self.assertRaises(FilingAuditError):verify(cache,root,PLAN,PRIOR)

    def test_parent_receipt_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'repo';root.mkdir()
            cache=Path(td)/'cache';cache.mkdir()
            (cache/PARENT_OBJ).write_bytes(json.dumps(SUB).encode())
            fake=dict(self.p);fake['download_sha256']='0'*64
            (cache/PARENT_RECEIPT).write_text(json.dumps(fake))
            with self.assertRaises(ValueError):
                acquire(cache,root,PLAN,PRIOR,'University person@academic.org',fetcher=lambda *a:html())

if __name__=='__main__':unittest.main()
