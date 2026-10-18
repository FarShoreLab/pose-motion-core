#!/usr/bin/env python3
"""Portable source-only checks. Does not install packages or run model inference."""
from pathlib import Path
import ast
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'baselines/v5.2'
EXPERIMENT = ROOT / 'experiments/pose-ik-v6'
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')


def run(cmd, cwd=ROOT):
    print('\nCHECK ' + str(cwd.relative_to(ROOT)) + ': ' + ' '.join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, env=ENV, check=True)


def main():
    for command in ['python3', 'node', 'sh']:
        if not shutil.which(command):
            raise SystemExit('Missing required command: ' + command)
    run([sys.executable, 'scripts/verify_backup.py'])
    counts = {'python_syntax': 0, 'json_parse': 0, 'shell_syntax': 0, 'osim_xml_parse': 0}
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file() or any(x in path.parts for x in ('.git', '.venv', 'node_modules', '__pycache__')):
            continue
        if path.suffix == '.py':
            ast.parse(path.read_text(), filename=str(path)); counts['python_syntax'] += 1
        elif path.suffix == '.json':
            json.loads(path.read_text()); counts['json_parse'] += 1
        elif path.suffix == '.sh':
            subprocess.run(['sh', '-n', str(path)], check=True); counts['shell_syntax'] += 1
        elif path.suffix == '.osim':
            ET.parse(path); counts['osim_xml_parse'] += 1
    print('STATIC CHECKS ' + json.dumps(counts), flush=True)
    # All three archived test.mjs files use standard-library stubs rather than models.
    for frontend in [ROOT / 'baselines/pose-live-v4', BASE / 'pose-v52', EXPERIMENT / 'live-app/pose-v52']:
        run(['node', 'test.mjs'], frontend)
    for backend in [BASE / 'pose-v52-python', EXPERIMENT / 'live-app/pose-v52-python']:
        run([sys.executable, 'test_epoch_clock.py'], backend)
        run([sys.executable, 'test_epoch_backend.py'], backend)
    run([sys.executable, 'scripts/verify_backup.py'])
    print('\nPASS: source syntax, archival hashes, JS policy/queue/worker contracts, epoch unit tests and HTTP Range checks.')
    print('NOT RUN: dependency install, native MediaPipe/OpenSim, test_api.py, test_live_ik.py, real-output audits, browser/video/inference/performance tests.')


if __name__ == '__main__':
    main()
