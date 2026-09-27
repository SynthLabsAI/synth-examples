#!/usr/bin/env python3
"""Create deterministic public example ZIPs. No network, credentials or runs."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT/'dist'


def inventory(directory, allowed=None):
    result = {}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlinks are not allowed in example packages')
        if path.is_file() and '__pycache__' not in path.parts and path.name != '.DS_Store':
            result[path.relative_to(directory).as_posix()] = path.read_bytes()
    if allowed is not None and set(result) != set(allowed):
        raise ValueError('Unexpected or missing package files: ' + str(sorted(set(result) ^ set(allowed))))
    return result


def archive(files):
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, content in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 9, 26, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if name.endswith('/test.sh') else 0o100644) << 16
            bundle.writestr(info, content)
    return data.getvalue()


def build():
    DIST.mkdir(exist_ok=True)
    assets = []
    allowlists = json.loads((ROOT/'scripts/example-inventory.json').read_text())
    for name in ('review-permissions', 'review-lab'):
        directory = ROOT/'examples'/name
        files = inventory(directory, allowlists[name])
        files['LICENSE'] = (ROOT/'LICENSE').read_bytes()
        if name == 'review-lab':
            with tempfile.TemporaryDirectory() as temporary:
                built = Path(temporary)/'built'
                subprocess.run([sys.executable,'-B',str(directory/'build.py'),str(built)],
                               check=True, capture_output=True)
                files.update({'built/'+p: data for p,data in inventory(built).items()})
        hashes = {p: hashlib.sha256(data).hexdigest() for p,data in files.items()}
        files['bundle-files.json'] = (json.dumps(hashes, indent=2, sort_keys=True)+'\n').encode()
        data = archive(files)
        filename = name+'.zip'
        (DIST/filename).write_bytes(data)
        assets.append({'name':filename, 'sha256':hashlib.sha256(data).hexdigest(),
                       'bytes':len(data), 'file_count':len(files)})
    (DIST/'checksums.txt').write_text(''.join(a['sha256']+'  '+a['name']+'\n' for a in assets))
    manifest = {'schema':'synth.examples.release.v1', 'cli':'0.0.1-alpha.62',
                'license':'MIT','kind':'original teaching examples', 'assets':assets}
    (DIST/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps(manifest,indent=2))


if __name__ == '__main__':
    build()
