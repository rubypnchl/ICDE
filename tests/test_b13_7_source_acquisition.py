import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from src.b13_7_source_acquisition import (
  EXPECTED, SourceError, acquire, assert_external_cache, sha256_file, validate_content,
  validate_registry, verify_existing,
)
ROOT=Path(__file__).resolve().parents[1]
REGISTRY=json.loads((ROOT/'data/evaluation/b13_7_source_objects_v1.json').read_text())

class FakeResponse:
 def __init__(self, url, b): self.url=url;self.buf=io.BytesIO(b)
 def __enter__(self): return self
 def __exit__(self,*a): self.buf.close()
 def geturl(self): return self.url
 def read(self,n): return self.buf.read(n)

class Tests(unittest.TestCase):
 def test_valid_registry(self):self.assertEqual(len(validate_registry(REGISTRY)),3)
 def test_one_cycle_for_healthcare(self):
  items=validate_registry(REGISTRY)
  self.assertEqual(items[0]['source_group'],items[1]['source_group'])
 def test_no_gold(self):
  for x in validate_registry(REGISTRY):self.assertFalse(x['reference_truth_available'])
 def test_changed_url_rejected(self):
  r=copy.deepcopy(REGISTRY);r['source_ids'][0]['download_url']='https://example.net/evil'
  with self.assertRaises(SourceError):validate_registry(r)
 def test_duplicate_rejected(self):
  r=copy.deepcopy(REGISTRY);r['source_ids'][1]['source_id']=r['source_ids'][0]['source_id']
  with self.assertRaises(SourceError):validate_registry(r)
 def test_changed_eligibility_rejected(self):
  r=copy.deepcopy(REGISTRY);r['source_ids'][0]['source_specific_eligibility_verified']=True
  with self.assertRaises(SourceError):validate_registry(r)
 def test_repo_cache_rejected(self):
  with self.assertRaises(SourceError):assert_external_cache(ROOT/'download',ROOT)
 def test_external_cache_accepted(self):
  with tempfile.TemporaryDirectory() as d:self.assertNotEqual(assert_external_cache(Path(d),ROOT),ROOT)
 def test_html_masquerading_xpt_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'fake.XPT';p.write_text('<html>Error</html>')
   with self.assertRaises(SourceError):validate_content(p,'sas_xpt')
 def test_zip_ok(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'fixture.zip'
   with zipfile.ZipFile(p,'w') as z:z.writestr('Faults.NNA','toy fake data')
   validate_content(p,'zip')
 def test_invalid_zip_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.zip';p.write_bytes(b'not a zip')
   with self.assertRaises(SourceError):validate_content(p,'zip')
 def test_download_and_verify_offline_mock(self):
  item=validate_registry(REGISTRY)[2]
  z=io.BytesIO()
  with zipfile.ZipFile(z,'w') as archive:archive.writestr('Faults.NNA','toy data')
  fake=lambda req,timeout:FakeResponse(req.full_url,z.getvalue())
  with tempfile.TemporaryDirectory() as d:
   receipt=acquire(item,Path(d),opener=fake)
   self.assertEqual(receipt['sha256'],hashlib.sha256(z.getvalue()).hexdigest())
   self.assertEqual(verify_existing(item,Path(d))['sha256'],receipt['sha256'])
 def test_no_overwrite(self):
  item=validate_registry(REGISTRY)[2]
  with tempfile.TemporaryDirectory() as d:
   (Path(d)/item['object_name']).write_bytes(b'x')
   with self.assertRaises(SourceError):acquire(item,Path(d),opener=lambda *x:None)
 def test_tamper_detected(self):
  item=validate_registry(REGISTRY)[2]
  z=io.BytesIO()
  with zipfile.ZipFile(z,'w') as archive:archive.writestr('Faults.NNA','toy data')
  fake=lambda req,timeout:FakeResponse(req.full_url,z.getvalue())
  with tempfile.TemporaryDirectory() as d:
   acquire(item,Path(d),opener=fake)
   with (Path(d)/item['object_name']).open('ab') as out:out.write(b'altered')
   with self.assertRaises(SourceError):verify_existing(item,Path(d))
 def test_failed_download_part_removed(self):
  item=validate_registry(REGISTRY)[2]
  fake=lambda req,timeout:FakeResponse(req.full_url,b'<html>blocked</html>')
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(SourceError):acquire(item,Path(d),opener=fake)
   self.assertEqual(list(Path(d).iterdir()),[])
 def test_redirect_rejected(self):
  item=validate_registry(REGISTRY)[2]
  fake=lambda req,timeout:FakeResponse('https://evil.net/redirect',b'not data')
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(SourceError):acquire(item,Path(d),opener=fake)
   self.assertEqual(list(Path(d).iterdir()),[])
if __name__ == '__main__':unittest.main()
