"""Verify every released byte and reject unsafe or undisclosed package content."""
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('distribution_build', ROOT/'scripts/build.py')
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class DistributionTests(unittest.TestCase):
    def test_unexpected_files_and_symlinks_fail_closed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'intended.txt').write_text('public')
            (root/'.env').write_text('not-for-publication')
            with self.assertRaisesRegex(ValueError, 'Unexpected'):
                BUILDER.inventory(root, ['intended.txt'])
            (root/'.env').unlink()
            (root/'linked').symlink_to(root/'intended.txt')
            with self.assertRaisesRegex(ValueError, 'Symlinks'):
                BUILDER.inventory(root, ['intended.txt'])

    def test_reproducible_safe_complete_archives(self):
        subprocess.run([sys.executable,'-B',str(ROOT/'scripts/build.py')],check=True,capture_output=True)
        before = {p.name:p.read_bytes() for p in (ROOT/'dist').iterdir()}
        subprocess.run([sys.executable,'-B',str(ROOT/'scripts/build.py')],check=True,capture_output=True)
        self.assertEqual(before,{p.name:p.read_bytes() for p in (ROOT/'dist').iterdir()})
        manifest = json.loads(before['manifest.json'])
        for asset in manifest['assets']:
            data = before[asset['name']]
            self.assertEqual(asset['bytes'],len(data))
            self.assertEqual(asset['sha256'],hashlib.sha256(data).hexdigest())
            with zipfile.ZipFile(ROOT/'dist'/asset['name']) as bundle:
                names = bundle.namelist()
                self.assertEqual(len(names),len(set(names)))
                self.assertEqual(len(names),asset['file_count'])
                hashes = json.loads(bundle.read('bundle-files.json'))
                self.assertEqual(set(names),set(hashes)|{'bundle-files.json'})
                self.assertTrue({'LICENSE','README.md','reviewer.json'} <= set(names))
                for name,digest in hashes.items():
                    self.assertFalse(PurePosixPath(name).is_absolute())
                    self.assertNotIn('..',PurePosixPath(name).parts)
                    content = bundle.read(name)
                    self.assertEqual(digest,hashlib.sha256(content).hexdigest())
                    for private in (b'/Users/',b'.api.dev.synthlabs.ai',b'BEGIN PRIVATE KEY'):
                        self.assertNotIn(private,content,name)
                if asset['name']=='review-permissions.zip':
                    self.assertIn('review-permissions/tests/test.sh',names)
                    docker = bundle.read('review-permissions/environment/Dockerfile').decode()
                    self.assertNotIn('COPY tests',docker)
                else:
                    self.assertIn('built/manifest.json',names)
                    self.assertIn('AGENT-GUIDE.md',names)


if __name__ == '__main__':
    unittest.main()
