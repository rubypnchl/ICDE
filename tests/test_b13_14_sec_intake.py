import copy
import json
import tempfile
import unittest
from pathlib import Path
from src.b13_14_sec_intake import (
    IntakeError,STUDY,CIK,URL,FORM,CUTOFF,OBJ,RECEIPT,canonical,
    validate_plan,excluded_ciks,validate_source_selection,select_filing,
    make_receipt,assert_external_cache,acquire,verify,_declared_user_agent,
)
ROOT=Path(__file__).resolve().parents[1]
PLAN=json.loads((ROOT/'data/evaluation/b13_14_sec_intake_plan_v1.json').read_text())
PRIOR={'datasets':{'sec-companyfacts':{'source_urls':[f'https://data.sec.gov/api/xbrl/companyfacts/CIK{x:010d}.json' for x in range(1,11)]},
                  'sec-edgar-xbrl':{'source_urls':['https://data.sec.gov/api/xbrl/companyconcept/CIK0000000001/us-gaap/Assets.json']}}}
RESPONSE={'cik':1058090,'name':'Synthetic Test Company',
          'filings':{'recent':{'form':['10-Q','10-K','10-K','10-K'],
             'filingDate':['2026-10-28','2026-02-04','2025-02-05','2027-01-01'],
             'accessionNumber':['0001058090-26-000101','0001058090-26-000011','0001058090-25-000011','0001058090-27-000001'],
             'reportDate':['2026-09-30','2025-12-31','2024-12-31','2026-12-31'],
             'primaryDocument':['q.htm','k.htm','kold.htm','future.htm']}}}
RAW=json.dumps(RESPONSE).encode()

class Tests(unittest.TestCase):
    def test_plan_valid(self):validate_plan(PLAN)
    def test_plan_tampered(self):
        p=dict(PLAN);p['independent_gold_available']=True
        with self.assertRaises(IntakeError):validate_plan(p)
    def test_excludes_listed_CIKs(self):self.assertEqual(len(excluded_ciks(PRIOR)),10)
    def test_rejects_exposed_CIK(self):
        p=dict(PLAN);p['cik']='0000000005'
        with self.assertRaises(IntakeError):validate_source_selection(p,PRIOR)
    def test_source_registry_missing(self):
        with self.assertRaises(IntakeError):excluded_ciks({'datasets':{}})
    def test_selection_latest_and_cutoff(self):
        r=select_filing(RESPONSE,PLAN)
        self.assertEqual(r['accession'],'0001058090-26-000011')
        self.assertTrue(r['filing_landing_url'].startswith('https://www.sec.gov/Archives/edgar/data/1058090/'))
    def test_does_not_select_future_or_quarterly(self):
        r=select_filing(RESPONSE,PLAN);self.assertEqual(r['form'],'10-K')
        self.assertEqual(r['filing_date'],'2026-02-04')
    def test_sec_padded_string_cik_accepted(self):
        d=copy.deepcopy(RESPONSE)
        d['cik']='0001058090'
        selected=select_filing(d,PLAN)
        self.assertEqual(selected['form'],'10-K')
        receipt=make_receipt(json.dumps(d).encode('utf-8'),PLAN,PRIOR)
        self.assertEqual(receipt['source_cik'],CIK)
        self.assertEqual(receipt['selected_filing']['accession'],selected['accession'])

    def test_unpadded_string_cik_accepted(self):
        d=copy.deepcopy(RESPONSE)
        d['cik']='1058090'
        self.assertEqual(select_filing(d,PLAN)['form'],'10-K')

    def test_other_and_malformed_ciks_still_refused(self):
        invalid=(320193,'0000320193','0001058091','10580900','00001058090',
                 '+1058090',' 0001058090','1058090 ',1058090.0,True,None)
        for value in invalid:
            with self.subTest(cik=value):
                d=copy.deepcopy(RESPONSE)
                d['cik']=value
                with self.assertRaises(IntakeError): select_filing(d,PLAN)

    def test_padded_string_acquire_verify_fake_network(self):
        d=copy.deepcopy(RESPONSE)
        d['cik']='0001058090'
        payload=json.dumps(d).encode('utf-8')
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'repo';root.mkdir()
            cache=Path(t)/'outside'
            receipt=acquire(cache,root,PLAN,PRIOR,'Research Researcher@university.ac.uk',fetcher=lambda agent:payload)
            self.assertEqual(verify(cache,root,PLAN,PRIOR),receipt)

    def test_bad_cik(self):
        d=copy.deepcopy(RESPONSE);d['cik']=320193
        with self.assertRaises(IntakeError):select_filing(d,PLAN)
    def test_missing_recent(self):
        with self.assertRaises(IntakeError):select_filing({'cik':1058090},PLAN)
    def test_mismatched_parallel_arrays(self):
        d=copy.deepcopy(RESPONSE);d['filings']['recent']['reportDate'].pop()
        with self.assertRaises(IntakeError):select_filing(d,PLAN)
    def test_unsafe_document(self):
        d=copy.deepcopy(RESPONSE);d['filings']['recent']['primaryDocument'][1]='../../evil'
        with self.assertRaises(IntakeError):select_filing(d,PLAN)
    def test_no_eligible_10k(self):
        d=copy.deepcopy(RESPONSE);d['filings']['recent']['form']=['8-K']*4
        with self.assertRaises(IntakeError):select_filing(d,PLAN)
    def test_filing_report_after_filing(self):
        d=copy.deepcopy(RESPONSE);d['filings']['recent']['reportDate'][1]='2026-12-31'
        with self.assertRaises(IntakeError):select_filing(d,PLAN)
    def test_receipt_no_gold(self):
        r=make_receipt(RAW,PLAN,PRIOR)
        self.assertFalse(r['source_semantic_eligibility_verified'])
        self.assertEqual(r['real_candidate_count'],0)
    def test_not_json(self):
        with self.assertRaises(IntakeError):make_receipt(b'<html>',PLAN,PRIOR)
    def test_external_path_required(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t)/'repo';r.mkdir()
            with self.assertRaises(IntakeError):assert_external_cache(r/'cache',r)
    def test_placeholder_agent_rejected(self):
        with self.assertRaises(IntakeError):_declared_user_agent('MetaVerify test@example.com')
    def test_real_agent_format_accepted(self):
        self.assertIn('@',_declared_user_agent('Research Group researcher@university.ac.uk'))
    def test_acquire_and_verify_fake_network(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'repo';root.mkdir()
            cache=Path(t)/'outside';fetcher=lambda agent:RAW
            rec=acquire(cache,root,PLAN,PRIOR,'Research Researcher@university.ac.uk',fetcher=fetcher)
            self.assertEqual(verify(cache,root,PLAN,PRIOR),rec)
            with self.assertRaises(IntakeError):acquire(cache,root,PLAN,PRIOR,'Research Researcher@university.ac.uk',fetcher=fetcher)
            raw=(cache/OBJ).read_bytes()
            (cache/OBJ).write_bytes(raw+b' ')
            with self.assertRaises(IntakeError):verify(cache,root,PLAN,PRIOR)
    def test_no_silent_altered_receipt(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'repo';root.mkdir();cache=Path(t)/'outside'
            acquire(cache,root,PLAN,PRIOR,'Research Researcher@university.ac.uk',fetcher=lambda agent:RAW)
            receipt=json.loads((cache/RECEIPT).read_text());receipt['independent_gold']=1
            (cache/RECEIPT).write_text(json.dumps(receipt))
            with self.assertRaises(IntakeError):verify(cache,root,PLAN,PRIOR)

if __name__=='__main__':unittest.main()
