"""Small fixture tests; real completed reviewer ZIPs stay outside the Git repository."""
import copy
import io
import unittest
import zipfile
from scripts.analyze_b6_two_reviewer_audit import (
    ReviewError, first_sheet_rows, compare_case_bases, evaluate_review_bundles
)


def fixture():
    d={}
    rules={
        'cybersecurity':[('B6-CYB-001','Needs more evidence','Supported with conditions')],
        'finance':[('B6-FIN-001','Supported with conditions','Supported with conditions'),
                   ('B6-FIN-002','Not supported','Not supported as written')],
        'healthcare':[('B6-HLT-001','Not supported','Not supported as written')],
        'manufacturing':[('B6-MAN-001','Supported','Supported with conditions')],
    }
    for domain,items in rules.items():
        for number in (1,2):
            d[(number,domain,'rules')]=[
                {'reference_id':cid,'domain':domain,'proposed_constraint':'unchanged',
                 'decision':a if number==1 else b,'reviewer_id':f'Rev_{number}'}
                for cid,a,b in items]
    for number in (1,2):
        d[(number,'cybersecurity','cases')]=[
            {'reference_id':'B6-CYB-001','source_sha256':'a'*64,
             'source_data_row_1based':'101','row_sha256':'b'*64,'observed_test_status':'satisfied',
             'decision':'No discrepancy (rule satisfied)' if number==1 else 'No discrepancy found. Rule satisfied'}]
        d[(number,'healthcare','cases')]=[
            {'reference_id':'B6-HLT-001','source_sha256':'c'*64,'source_data_row_1based':'200',
             'row_sha256':'d'*64,'decision':'Unclear'}]
        d[(number,'finance','cases')]=[
            {'reference_id':'B6-FIN-001','source_sha256':'e'*64,'CIK':'100','accession':'acc-1',
             'reporting_end':'2022-12-31','unit':'USD','Assets':'100' if number==1 else '101',
             'decision':'No numerical discrepancy (scope unverified)' if number==1 else 'Numerical match; filing context not fully verified'},
            {'reference_id':'B6-FIN-002','source_sha256':'e'*64,'CIK':'101','accession':'acc-2',
             'reporting_end':'2021-12-31','unit':'USD','Assets':'123',
             'decision':'Explainable exception' if number==1 else 'Explained by noncontrolling interests'}]
        d[(number,'manufacturing','cases')]=[
            {'reference_id':'B6-MAN-001','source_sha256':'f'*64,'UDI':'10',
             'case':'forward_frozen_rule_violation',
             'decision':'Genuine discrepancy' if number==1 else 'Documented-rule conflict; cause unresolved'},
            {'reference_id':'B6-MAN-001','source_sha256':'f'*64,'UDI':'11',
             'case':'reverse_exploratory_only_not_frozen_rule',
             'decision':'Unclear' if number==1 else 'Not a violation of the one-way rule'},
        ]
    return ({(domain,kind):d[(1,domain,kind)] for domain in rules for kind in ('rules','cases')},
            {(domain,kind):d[(2,domain,kind)] for domain in rules for kind in ('rules','cases')})


class B6ReviewAuditTests(unittest.TestCase):
    def test_minimal_excel_shared_string_reader(self):
        sheet='''<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
          <row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="inlineStr"><is><t>decision</t></is></c></row>
          <row r="2"><c r="A2" t="s"><v>1</v></c><c r="B2" t="inlineStr"><is><t>Supported</t></is></c></row>
          </sheetData></worksheet>'''
        strings='''<?xml version="1.0"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>reference_id</t></si><si><t>B6-FIN-001</t></si></sst>'''
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:
            z.writestr('xl/worksheets/sheet1.xml',sheet)
            z.writestr('xl/sharedStrings.xml',strings)
        self.assertEqual(first_sheet_rows(stream.getvalue()),[{'reference_id':'B6-FIN-001','decision':'Supported'}])

    def test_accurate_pairing_and_no_gold(self):
        a,b=fixture()
        report=evaluate_review_bundles(a,b)
        self.assertEqual(report['rule_reference_count'],5)
        self.assertEqual(report['rule_decision_exact_category_agreements'],3)
        self.assertEqual(report['cases']['matched_case_ids'],6)
        self.assertEqual(report['cases']['identical_case_inputs'],5)
        self.assertEqual(len(report['changed_source_inputs']),1)
        self.assertEqual(report['case_strata']['manufacturing']['both_identify_forward_rule_conflict_but_cause_disputed'],1)
        self.assertIsNone(report['not_estimable']['published_sota_performance'])

    def test_unmatched_case_excluded(self):
        a,b=fixture()
        b[('manufacturing','cases')].pop()
        result=evaluate_review_bundles(a,b)
        self.assertEqual(len(result['unpaired_cases']),1)
        self.assertEqual(result['case_strata']['manufacturing']['only_reviewer1'],1)

    def test_rejects_unrecognised_or_changed_reference(self):
        a,b=fixture();a[('cybersecurity','rules')][0]['decision']='Definitely correct'
        with self.assertRaises(ReviewError):evaluate_review_bundles(a,b)
        a,b=fixture();b[('finance','rules')][0]['proposed_constraint']='tampered'
        with self.assertRaises(ReviewError):evaluate_review_bundles(a,b)

if __name__=='__main__':unittest.main()
