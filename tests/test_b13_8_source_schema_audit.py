"""B13.8 offline tests use artificial tables/ZIPs; never ship source records."""
from __future__ import annotations

import copy
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from src.b13_8_source_schema_audit import (
    AuditError, PINNED, FAULT_LABELS, _ids, _safe_zip_info, audit_faults_zip,
    canonical_sha, exclusive_save, read_xpt_aggregates, summarize_xpt_frame, validate_plan,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN = json.loads((ROOT/'data/evaluation/b13_8_schema_audit_plan_v1.json').read_text(encoding='utf-8'))
REG = json.loads((ROOT/'data/evaluation/b13_7_source_objects_v1.json').read_text(encoding='utf-8'))
VARS = ("X_Minimum X_Maximum Y_Minimum Y_Maximum Pixels_Areas X_Perimeter Y_Perimeter Sum_of_Luminosity "
        "Minimum_of_Luminosity Maximum_of_Luminosity Length_of_Conveyer TypeOfSteel_A300 TypeOfSteel_A400 "
        "Steel_Plate_Thickness Edges_Index Empty_Index Square_Index Outside_X_Index Edges_X_Index Edges_Y_Index "
        "Outside_Global_Index LogOfAreas Log_X_Index Log_Y_Index Orientation_Index Luminosity_Index SigmoidOfAreas ") + " ".join(FAULT_LABELS)

class FakeNullCount:
    def __init__(self, missing): self.missing = missing
    def sum(self): return self.missing

class FakeSeries:
    def __init__(self, values): self.values = values; self.dtype = 'float64'
    def isna(self): return FakeNullCount(sum(x is None or (isinstance(x,float) and math.isnan(x)) for x in self.values))
    def __iter__(self): return iter(self.values)

class FakeFrame:
    def __init__(self, values): self._values = {key:FakeSeries(value) for key,value in values.items()}; self.columns = list(values)
    def __len__(self): return len(next(iter(self._values.values())).values)
    def __getitem__(self,key): return self._values[key]

def frame_for(sid):
    cols = PLAN['objects'][0 if sid.endswith('01') else 1]['minimum_expected_columns']
    return FakeFrame({col: [1001.0, 1002.0, float('nan')] if col == 'SEQN' else [1.2, None, 3.2] for col in cols})

def fake_zip(path, *, rows=None, names=VARS, member='Faults.NNA'):
    rows = rows if rows is not None else [' '.join(['1']*27+['1','0','0','0','0','0','0'])]
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('Faults27x7_var', names)
        z.writestr(member, '\n'.join(rows))

class Tests(unittest.TestCase):
    def test_frozen_plan_valid(self): validate_plan(PLAN,REG)
    def test_parent_hash_pinned(self):
        other = copy.deepcopy(REG); other['source_ids'][0]['documentation_url'] += '?changed'
        with self.assertRaises(Exception): validate_plan(PLAN, other)
    def test_source_hash_tamper_rejected(self):
        other = copy.deepcopy(PLAN); other['objects'][0]['sha256'] = '0'*64
        with self.assertRaises(AuditError): validate_plan(other,REG)
    def test_cannot_set_gold(self):
        other = copy.deepcopy(PLAN); other['reference_semantic_truth_confirmed'] = True
        with self.assertRaises(AuditError): validate_plan(other,REG)
    def test_cannot_enable_gate(self):
        other = copy.deepcopy(PLAN); other['prospective_rule_discovery_or_gate_allowed'] = True
        with self.assertRaises(AuditError): validate_plan(other,REG)
    def test_healthcare_shared_cycle(self):
        self.assertEqual(PLAN['objects'][0]['source_group'], PLAN['objects'][1]['source_group'])
    def test_seqn_counts_only(self):
        ids,missing,duplicates=_ids([1001.0,1002.,1002.,float('nan')]);self.assertEqual((len(ids),missing,duplicates),(2,1,1))
    def test_invalid_seqn_rejected(self):
        with self.assertRaises(AuditError): _ids([3.5])
    def test_xpt_aggregate_schema_only(self):
        d,ids=summarize_xpt_frame(frame_for('B13S-HLT-01'), 'B13S-HLT-01')
        self.assertEqual(d['row_count'],3)
        self.assertEqual(d['seqn_missing'],1)
        self.assertEqual(d['columns'][1]['missing'],1)
        self.assertEqual(ids,{1001,1002})
        self.assertNotIn('rows',d)
        self.assertNotIn('identifiers',d)
    def test_missing_relevant_xpt_variable_fails(self):
        with self.assertRaises(AuditError): summarize_xpt_frame(FakeFrame({'SEQN':[1]}),'B13S-HLT-02')
    def test_xpt_reader_metadata_contract(self):
        class Meta: column_names = list(frame_for('B13S-HLT-02').columns)
        class Stub: read_xport = lambda self,p: (frame_for('B13S-HLT-02'),Meta())
        with patch.dict(sys.modules, {'pyreadstat': Stub()}):
            res,_ = read_xpt_aggregates(Path('dummy.XPT'),'B13S-HLT-02')
        self.assertEqual(res['column_count'],2)
    def test_zip_summary_small_fixture(self):
        with tempfile.TemporaryDirectory() as p:
            path=Path(p)/'tiny.zip';fake_zip(path)
            rep=audit_faults_zip(path)
            self.assertEqual(rep['row_count'],1)
            self.assertEqual(rep['label_positive_count_per_row']['1'],1)
            self.assertEqual(rep['fault_label_positive_counts']['Pastry'],1)
            self.assertNotIn('records',rep)
    def test_zip_multi_hot_records_observed_not_truth(self):
        with tempfile.TemporaryDirectory() as p:
            path=Path(p)/'tiny.zip';fake_zip(path, rows=[' '.join(['2']*27 + ['1','1','0','0','0','0','0'])])
            rep=audit_faults_zip(path)
            self.assertEqual(rep['label_positive_count_per_row']['2'],1)
            self.assertIn('not_semantically_adjudicated',rep['source_claim'])
    def test_zip_bad_nonbinary_fails(self):
        with tempfile.TemporaryDirectory() as p:
            path=Path(p)/'bad.zip';fake_zip(path, rows=[' '.join(['2']*27 + ['0.5','0','0','0','0','0','0'])])
            with self.assertRaises(AuditError): audit_faults_zip(path)
    def test_zip_missing_columns_fails(self):
        with tempfile.TemporaryDirectory() as p:
            path=Path(p)/'bad.zip';fake_zip(path, rows=[' '.join(['0']*33)])
            with self.assertRaises(AuditError): audit_faults_zip(path)
    def test_zip_unsafe_member_fails(self):
        with self.assertRaises(AuditError): _safe_zip_info(zipfile.ZipInfo('../Faults.NNA'))
    def test_zip_wrong_members_fails(self):
        with tempfile.TemporaryDirectory() as p:
            path=Path(p)/'bad.zip';fake_zip(path, member='other.csv')
            with self.assertRaises(AuditError): audit_faults_zip(path)
    def test_exclusive_output_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as root:
            repo=Path(root)/'ICDE';repo.mkdir();cache=Path(root)/'separate';cache.mkdir()
            path=cache/'B13_8_source_schema_audit_v1.json'
            exclusive_save(path,{'count':1},cache,repo)
            with self.assertRaises(FileExistsError): exclusive_save(path,{'count':2},cache,repo)
    def test_preflight_has_no_source_access(self):
        r=subprocess.run([sys.executable,str(ROOT/'scripts/run_b13_8_source_schema_audit.py'),'--preflight'],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('NO source read',r.stdout)
        self.assertNotIn('AUDIT COMPLETE',r.stdout)
    def test_fingerprints_are_prior_receipts(self):
        self.assertEqual(PINNED['B13S-HLT-01'][1], 'dd5a24f7b3bff19f899db38b766445bc4217b6ec6d1bd1accf7065a037e8a59d')
        self.assertEqual(PINNED['B13S-MAN-01'][2],100890)

if __name__ == '__main__': unittest.main()
