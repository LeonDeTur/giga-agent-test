import importlib.util, unittest, tempfile, os, zipfile
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('dpo',Path(__file__).parent/'dpo-giga-agent/dpo.py')
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
class Tests(unittest.TestCase):
 def test_credentials(self):
  import base64
  self.assertTrue(d.validate_credentials(base64.b64encode(b'12345678-1234-1234-1234-123456789abc:12345678-1234-1234-1234-123456789abc').decode()))
  for key in ('','Basic abc','secret','!!!!'):self.assertFalse(d.validate_credentials(key))
 def test_child_default(self):
  with patch.object(d,'config',return_value={}):
   env=d.child_env();self.assertEqual(env['GIGA_AGENT_LOCAL_JUPYTER_SECURE_EXEC_DEFAULT'],'false')
 def test_long_path(self):
  with patch.object(d,'ROOT',Path('C:/'+'x'*81)),patch.object(d.os,'name','nt'):
   with self.assertRaisesRegex(d.CourseError,'Windows'):d.setup()
 def test_pack(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as td:
   root=Path(td)/'course';root.mkdir()
   for name in ('tools/uv/uv.exe','.cache/uv/pkg','.env','.giga_agent/db','data/a/output/report.txt','data/a/input/source.txt','.venv/python','litellm.yaml'):
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture')
   with patch.object(d,'ROOT',root):d.pack_offline()
   with zipfile.ZipFile(root.parent/'dpo-giga-agent-offline.zip') as z:
    names=z.namelist()
    self.assertIn('course/tools/uv/uv.exe',names);self.assertIn('course/.cache/uv/pkg',names)
    self.assertIn('course/OFFLINE',names)
    self.assertFalse(any(n.endswith(('.env','report.txt','litellm.yaml','/db','/python')) for n in names))
if __name__=='__main__':unittest.main()
