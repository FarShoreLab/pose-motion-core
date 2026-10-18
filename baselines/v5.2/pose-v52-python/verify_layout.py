#!/usr/bin/env python3
"""Read-only layout/model verification. No package install, model load, or inference."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--skip-js-deps', action='store_true', help='Use before npm ci; final startup requires JS deps')
args = parser.parse_args()
here = Path(__file__).resolve().parent
root = here.parent / 'pose-v52'
required = ['public/seamless-source.js','public/index.html', 'public/app.js', 'public/pose-worker.js', 'public/joint-policy.js', 'public/joint-policy-v4.js', 'public/frame-queue.js', 'public/style.css', 'package.json', 'package-lock.json', 'assets/model-manifest.json', 'assets/pose_landmarker_lite.task']
if not args.skip_js_deps:
    required += ['node_modules/three/build/three.module.js', 'node_modules/three/build/three.core.js', 'node_modules/three/examples/jsm/controls/OrbitControls.js']
missing = [x for x in required if not (root / x).is_file()]
model = root / 'assets/pose_landmarker_lite.task'
expected = '59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a'
actual = hashlib.sha256(model.read_bytes()).hexdigest() if model.is_file() else None
report = {'ok': not missing and actual == expected, 'backend_directory': here.name, 'frontend_sibling_directory': root.name, 'missing_required': missing, 'model_sha256': actual, 'model_matches': actual == expected, 'js_dependencies_checked': not args.skip_js_deps, 'available_test_videos': [p.name for p in (root/'assets/videos').glob('seamless/*.mp4')], 'scope': 'layout and bytes only; server startup, native dependencies, API, browser playback and realtime performance are not checked'}
print(json.dumps(report, indent=2))
sys.exit(0 if report['ok'] else 1)
