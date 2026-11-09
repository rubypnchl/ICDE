"""Offline fixture tests for the source-verified four-domain reviewer packet exporter."""
import csv
import hashlib
import json
import pathlib
import shutil
import tempfile
import types
import sys
import unittest
from unittest.mock import patch
from scripts import prepare_four_domain_review as m

class Tests(unittest.TestCase):
    def test_rule_roster_and_empty_votes(self):
        self.assertEqual(len(m.RULES),5)
        self.assertEqual(sum(r['domain']=='finance' for r in m.RULES),2)
        self.assertEqual(m.VOTE,['reviewer_id','decision','evidence_url','evidence_locator','rationale'])
    def test_numeric_rounding_and_invalid(self):
        self.assertEqual(m.sig_round(m.Decimal('5.5511')),m.Decimal('5.55'))
        self.assertEqual(m.numeric('-1.20'),m.Decimal('-1.20'))
        self.assertIsNone(m.numeric('NaN'))
        self.assertIsNone(m.numeric(''))
    def test_frozen_manufacturing_rows_are_not_relabelled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);path=root/m.MAN_SRC
            path.parent.mkdir(parents=True)
            # Fixture modelled on frozen 18/9 B6.3 categories; used only for testing.
            rows=[]
            for i in range(27):
                row={k:'' for k in m.MAN_FIELDS}
                row.update(reference_id='B6-MAN-001',source_sha256=m.MAN_SHA,UDI=str(i+1),
                           case='forward_frozen_rule_violation' if i<18 else 'reverse_exploratory_only_not_frozen_rule')
                rows.append(row)
            m.write_csv(path,m.MAN_FIELDS,rows)
            raw=root/'data/originals/ai4i/ai4i2020.csv';raw.parent.mkdir(parents=True)
            with raw.open('w',encoding='utf-8',newline='') as f:
                w=csv.DictWriter(f,fieldnames=['UDI','TWF','HDF','PWF','OSF','RNF','Machine failure']);w.writeheader()
                for r in rows:w.writerow({k:r[k] for k in w.fieldnames})
                for i in range(28,10001):w.writerow({'UDI':i,'TWF':0,'HDF':0,'PWF':0,'OSF':0,'RNF':0,'Machine failure':0})
            with patch.object(m,'verify',return_value=m.MAN_SHA):
                self.assertEqual(len(m.load_man(root)),27)
            rows[0]['decision']='supported_discrepancy'
            with path.open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=m.MAN_FIELDS);w.writeheader();w.writerows(rows)
            with self.assertRaises(ValueError):m.load_man(root)
    def test_sha_does_not_accept_different_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/'source.csv';p.write_bytes(b'some altered bytes')
            with self.assertRaises(ValueError):m.verify(p,'0'*64)
    def test_sec_real_context_join_and_no_source_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);p=root/'data/originals/sec/companyfacts/0000000001_fixture.json';p.parent.mkdir(parents=True)
            content={'cik':1,'entityName':'TEST FIXTURE ONLY','facts':{'us-gaap':{}}}
            for tag,v in [('Assets',12),('Liabilities',8),('StockholdersEquity',4),('LiabilitiesAndStockholdersEquity',12)]:
                facts=[]
                for j in range(12):
                    facts.append({'end':f'20{j+12}-12-31','accn':f'0001-{j:02}-000001','form':'10-K','filed':f'20{j+13}-03-31','val':v})
                content['facts']['us-gaap'][tag]={'units':{'USD':facts}}
            p.write_text(json.dumps(content))
            b=m.sha(p)
            meta=root/'data/metadata/sec-companyfacts-0000000001.json';meta.parent.mkdir(parents=True)
            meta.write_text(json.dumps({'provenance':{'sources':[{'file':p.relative_to(root).as_posix(),'sha256':b}]}}))
            rows,sources,counts=m.load_fin(root)
            self.assertEqual(len(rows),20)
            self.assertEqual(counts['B6-FIN-001']['selected'],10)
            self.assertEqual(counts['B6-FIN-002']['selected'],10)
            self.assertTrue(all(r['accounting_scope_evidence_status'].startswith('UNKNOWN') for r in rows))
            self.assertEqual(b,m.sha(p))

    def test_cic_20_rows_stratified_and_exact_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp)
            p=root/m.CYB_SRC;p.parent.mkdir(parents=True)
            fields=[' Label',' Total Fwd Packets',' Fwd Packet Length Min',
                    ' Fwd Packet Length Mean',' Fwd Packet Length Max',' Fwd Header Length',' Fwd Header Length']
            with p.open('w',encoding='utf-8',newline='') as f:
                w=csv.writer(f);w.writerow(fields)
                for i in range(50000):
                    w.writerow([['BENIGN','DDoS','PortScan'][i%3],'2','1','1.5','2','3','4'])
            with patch.object(m,'verify',return_value=m.CYB_SHA):
                records=m.load_cyb(root)
            self.assertEqual(len(records),20)
            self.assertEqual(len({r['source_data_row_1based'] for r in records}),20)
            self.assertTrue(all(r['observed_test_status']=='satisfied_provisional_expression' for r in records))
            self.assertEqual(set(x['selection_stratum'] for x in records),{'BENIGN','DDoS','PortScan'})
    def test_health_20_original_source_rows_and_missing_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp)
            p=root/m.HLT_SRC;p.parent.mkdir(parents=True);p.write_bytes(b'TEST XPORT STUB')
            data={'SEQN':list(range(1,3037)),
                  'LBXGLU':[float(70+i%320) for i in range(3036)],
                  'LBDGLUSI':[float(m.sig_round(m.Decimal(str(70+i%320))*m.Decimal('0.05551'))) for i in range(3036)]}
            for i in range(45):data['LBDGLUSI'][i]=float('nan')
            stub=types.SimpleNamespace(read_xport=lambda *a,**k:(data,None))
            with patch.object(m,'verify',return_value=m.HLT_SHA):
                with patch.dict(sys.modules,{'pyreadstat':stub}):
                    records=m.load_hlt(root)
            self.assertEqual(len(records),20)
            self.assertEqual(sum(x['selection_stratum']=='missingness_control' for x in records),4)
            self.assertEqual(sum(x['selection_stratum'].startswith('glucose_quartile') for x in records),16)
            self.assertEqual(len({x['SEQN'] for x in records}),20)
    def test_no_overwrite_of_previous_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=pathlib.Path(tmp)/'out';target.mkdir()
            with self.assertRaises(FileExistsError):m.prepare(pathlib.Path(tmp),target)
    def test_header_preserves_cic_whitespace(self):
        self.assertIn(' Fwd Packet Length Min',m.CYB_FIELDS)
        self.assertIn(' Total Fwd Packets',m.CYB_FIELDS)
        self.assertIn(' Label',m.CYB_FIELDS)

if __name__=='__main__':unittest.main()
