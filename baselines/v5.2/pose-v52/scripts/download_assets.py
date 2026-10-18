#!/usr/bin/env python3
"""Fetch pinned model plus attributed public test inputs. No model outputs are downloaded."""
import pathlib,json,hashlib,urllib.request
root=pathlib.Path(__file__).resolve().parents[1]
manifest=json.loads((root/'assets/videos/manifest.json').read_text())
def fetch(url,path,sha=None):
 path.parent.mkdir(parents=True,exist_ok=True)
 if not path.exists():
  print('Downloading',path.name,flush=True)
  with urllib.request.urlopen(url) as src,path.open('wb') as out:
   while block:=src.read(1024*1024):out.write(block)
 actual=hashlib.sha256(path.read_bytes()).hexdigest()
 if sha and actual!=sha:raise RuntimeError('SHA256 mismatch: '+str(path))
 print(path.name,actual)
for c in manifest['clips']:fetch(c['source']['download_url'],root/c['relative_path'],c['sha256'])
fetch('https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task',root/'assets/pose_landmarker_lite.task','59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a')
fetch('https://raw.githubusercontent.com/tensorflow/tfjs-models/master/pose-detection/test_data/pose_squats.mp4',root/'assets/pose_squats.mp4','ea9151e447b301985d5d65666551ef863b369a2e0f3a71ddd58abef2e722f96a')
