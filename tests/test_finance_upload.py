import base64
import importlib.util
import io
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
import zipfile

BASE=Path(__file__).resolve().parent

class UploadTests(unittest.TestCase):
    def setUp(self):
        auth=types.ModuleType('auth')
        auth.authenticate=lambda header:({'team':'Finance','role':'finance_reader'} if header=='Bearer test-finance' else ({'team':'HR','role':'hr_reader'} if header=='Bearer test-hr' else None))
        with patch.dict(sys.modules,{'auth':auth}):
            spec=importlib.util.spec_from_file_location('upload_test',BASE.parent/'project/mcp-lab/aitob_finance_upload.py')
            self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
    def call(self,raw,name='input.xlsx'):
        return self.m.process_for_key('Bearer test-finance',{'filename':name,'content_base64':base64.b64encode(raw).decode()})
    def fixture(self):return (BASE.parent/'fixtures/AItoB_ค่าใช้จ่ายสังเคราะห์.xlsx').read_bytes()
    def changed_xlsx(self,change):
        out=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.fixture())) as source,zipfile.ZipFile(out,'w') as target:
            for info in source.infolist():target.writestr(info.filename,change(info.filename,source.read(info)))
        return out.getvalue()
    def test_real_xlsx_fixture(self):
        status,result=self.call(self.fixture());self.assertEqual(status,200)
        s=result['summary'];self.assertEqual([s[k] for k in ['input_rows','cleaned_rows','duplicate_rows','rejected_rows','total_amount']],[6,3,1,2,'2000.00'])
    def test_csv_same_records_and_totals(self):
        rows=self.m.read_upload(self.fixture(),'fixture.xlsx')
        import csv
        stream=io.StringIO();csv.writer(stream).writerows([self.m.HEADER]+[r for _,r in rows])
        self.assertEqual(self.call(stream.getvalue().encode(),'fixture.csv')[1]['summary']['total_amount'],'2000.00')
    def test_unauthorized_before_decode_or_parse(self):
        with patch.object(self.m.base64,'b64decode',side_effect=AssertionError('decode_called')),patch.object(self.m,'read_upload',side_effect=AssertionError('parse_called')):
            for key,status in [('',401),('Bearer invalid',401),('Bearer test-hr',403)]:
                self.assertEqual(self.m.process_for_key(key,{'role':'Finance','bad':object()})[0],status)
    def test_formula_block(self):
        raw=self.changed_xlsx(lambda name,data:data.replace(b'<x:v>1200</x:v>',b'<x:f>600+600</x:f><x:v>1200</x:v>') if name=='xl/worksheets/sheet1.xml' else data)
        self.assertEqual(self.call(raw)[1]['error'],'formulas_not_allowed')
    def test_external_relationship_block(self):
        raw=self.changed_xlsx(lambda name,data:data.replace(b'</Relationships>',b'<Relationship Id="bad" Target="https://example.test/" TargetMode="External" Type="x"/></Relationships>') if name.endswith('.rels') and b'</Relationships>' in data else data)
        # Exporter namespaces can vary; use a targeted replacement of the closing element.
        if raw==self.fixture():self.skipTest('fixture relationship serialization differs')
        self.assertEqual(self.call(raw)[0],422)
    def test_precision_conflict_and_injection(self):
        _,audit,s=self.m.clean_rows([(2,['A','Shop','0.10']),(3,['B','Taxi','0.20']),(4,['A','Other','1']),(5,['C','=cmd','1']),(6,['D','Cafe','0.001'])])
        self.assertEqual(s['total_amount'],'0.30');self.assertEqual(s['rejected_rows'],3)
    def test_unknown_request_fields(self):
        self.assertEqual(self.m.process_for_key('Bearer test-finance',{'path':'/etc/passwd'})[0],400)
    def test_filename_and_size_limits(self):
        self.assertEqual(self.call(b'a','../source.csv')[0],422)
        self.assertEqual(self.call(b'a'*1000001,'source.csv')[0],413)
    def test_bad_archive_and_bad_header(self):
        self.assertEqual(self.call(b'not-a-zip')[0],422)
        self.assertEqual(self.call(b'wrong,columns\nx,y\n','data.csv')[0],422)
    def test_no_fixed_output_write(self):
        raw=self.fixture()
        with patch.object(Path,'open',side_effect=AssertionError('disk_access')):
            self.assertEqual(self.call(raw)[0],200)

if __name__=='__main__':unittest.main()
