#!/usr/bin/env python3
"""Explicit opt-in restore of the pinned model; never downloads test videos."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--frontend', required=True, help='Frontend path relative to the repository root')
args = parser.parse_args()
frontend = (ROOT / args.frontend).resolve()
if not frontend.is_relative_to(ROOT):
    raise SystemExit('Frontend must be inside this repository')
manifest = json.loads((frontend / 'assets/model-manifest.json').read_text())
url = urllib.parse.urlparse(manifest['url'])
if url.scheme != 'https' or url.hostname != 'storage.googleapis.com':
    raise SystemExit('Expected the archived official HTTPS model host')
target = frontend / 'assets/pose_landmarker_lite.task'
expected = manifest['sha256']
expected_bytes = manifest['bytes']
if target.exists():
    if target.is_file() and target.stat().st_size == expected_bytes and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
        print('Existing model matches the archived size and SHA-256.')
        raise SystemExit(0)
    raise SystemExit('Existing model differs; refusing to overwrite it')
target.parent.mkdir(parents=True, exist_ok=True)
temp = None
try:
    digest = hashlib.sha256()
    count = 0
    request = urllib.request.Request(manifest['url'], headers={'User-Agent': 'PoseMotionCore-ArchiveRestore/1.0'})
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.model-download-', delete=False) as stream:
        temp = Path(stream.name)
        with urllib.request.urlopen(request, timeout=60) as source:
            while block := source.read(1024 * 1024):
                count += len(block)
                if count > expected_bytes:
                    raise RuntimeError('Downloaded content exceeds the archived size')
                digest.update(block); stream.write(block)
    if count != expected_bytes or digest.hexdigest() != expected:
        raise RuntimeError('Model size/SHA-256 mismatch; the download will not be installed')
    if target.exists():
        raise RuntimeError('Destination appeared during download; refusing to overwrite')
    temp.replace(target)
    temp = None
    print('Restored pinned model to ' + str(target.relative_to(ROOT)))
finally:
    if temp is not None:
        temp.unlink(missing_ok=True)
