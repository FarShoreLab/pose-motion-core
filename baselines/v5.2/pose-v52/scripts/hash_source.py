#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,datetime
root=Path(__file__).resolve().parents[1]
files=['public/seamless-source.js','public/joint-policy-v51.js','public/app.js','public/frame-queue.js','public/joint-policy.js','public/joint-policy-v4.js','public/pose-worker.js','public/index.html','public/style.css','server.py','package.json','node_modules/@mediapipe/tasks-vision/vision_bundle.js','node_modules/three/build/three.module.js','assets/pose_landmarker_lite.task']
m={'version':json.loads((root/'package.json').read_text())['version'],'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':{p:{'sha256':hashlib.sha256((root/p).read_bytes()).hexdigest(),'bytes':(root/p).stat().st_size} for p in files}}
(root/'public/source-manifest.json').write_text(json.dumps(m,indent=2))
print('Written public/source-manifest.json')
