#!/usr/bin/env python3
import pathlib,zipfile,json,hashlib
root=pathlib.Path(__file__).resolve().parents[1];out=root/'deliverables'
core=['public/app.js','public/joint-policy.js','public/pose-worker.js','public/index.html','public/a.html','public/r.html','public/style.css','server.py','package.json','package-lock.json','test.mjs','start.sh','README-zh.md','REPORT-zh.md','record.py','scripts/download_assets.py','scripts/test_range.py','scripts/package_v4.py','assets/model-manifest.json','assets/videos/manifest.json','assets/videos/SOURCES.md']
core += [str(p.relative_to(root)) for p in (root/'audit_v4').glob('*.py')]+[str(p.relative_to(root)) for p in (root/'audit_v4').glob('*.mjs')]
core += [str(p.relative_to(root)) for p in (root/'audit_v4').glob('*verdict.md')]
with zipfile.ZipFile(out/'pose-live-v4-runtime.zip','w',zipfile.ZIP_DEFLATED,6) as z:
 for n in core:
  p=root/n
  if p.is_file():z.write(p,'pose-live-v4/'+n)
 for p in (root/'node_modules/@mediapipe/tasks-vision').rglob('*'):
  if p.is_file():z.write(p,'pose-live-v4/'+str(p.relative_to(root)))
 for folder in ['node_modules/three/build']:
  for p in (root/folder).rglob('*'):
   if p.is_file():z.write(p,'pose-live-v4/'+str(p.relative_to(root)))
 for n in ['node_modules/three/examples/jsm/controls/OrbitControls.js','node_modules/three/package.json','node_modules/three/LICENSE','assets/pose_landmarker_lite.task']:
  z.write(root/n,'pose-live-v4/'+n)
with zipfile.ZipFile(out/'pose-live-v4-source-and-evidence.zip','w',zipfile.ZIP_DEFLATED,6) as z:
 for n in core:
  p=root/n
  if p.is_file():z.write(p,'pose-live-v4/'+n)
 for p in (root/'results').glob('*.json'):z.write(p,'pose-live-v4/'+str(p.relative_to(root)))
 for p in (root/'audit_v4').glob('*.audit.json'):z.write(p,'pose-live-v4/'+str(p.relative_to(root)))
 for p in (root/'results/source-snapshot').glob('*'):z.write(p,'pose-live-v4/'+str(p.relative_to(root)))
 z.write(root/'results/test-output.txt','pose-live-v4/results/test-output.txt')
for p in out.glob('*.zip'):
 with zipfile.ZipFile(p) as z:assert z.testzip() is None
 print(p.name,p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest())
