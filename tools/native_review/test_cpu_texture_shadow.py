"""Execute the production CPU-atlas shadow helper, including failure paths."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

class CpuTextureShadow(unittest.TestCase):
    def test_exact_content_and_bounded_conservative_fallback(self):
        root=Path(__file__).resolve().parents[2]/'ports/ultratears-linux'
        compiler=shutil.which('cc')
        self.assertIsNotNone(compiler,'A native C compiler is required')
        with tempfile.TemporaryDirectory(prefix='nativedeck-cpu-shadow-') as temp:
            binary=Path(temp)/'shadow-test'
            subprocess.run([compiler,'-std=c11','-O2','-Wall','-Wextra','-Werror','-pthread',
                '-I'+str(root/'overlay/src/gfx'),str(root/'controller-runtime/test_cpu_texture_shadow.c'),
                '-o',str(binary)],check=True,capture_output=True,text=True,timeout=45)
            result=subprocess.run([str(binary)],check=True,capture_output=True,text=True,timeout=45)
            self.assertIn('release: PASS',result.stdout)

if __name__=='__main__':unittest.main(verbosity=2)
