#!/usr/bin/env python3
"""Prepare source/media ZIPs only after an explicit --build. Default is a dry-run inventory.
Top-level layout keeps pose-v5 and pose-v5-python as siblings. No caches/venv/results.
"""
from pathlib import Path
import argparse, hashlib, json, zipfile, sys
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent
PY=BASE/'pose-v5-python'
p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');p.add_argument('--output',default=str(ROOT/'delivery'));p.add_argument('--videos',action='store_true');p.add_argument('--release',default='v5');p.add_argument('--candidate-ids',default='');args=p.parse_args()
if not args.release or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_' for c in args.release):raise ValueError('Unsafe release label')
files={}
def add(path,arc=None):
 path=Path(path)
 if not path.is_file():raise FileNotFoundError(path)
 key=arc or str(path.relative_to(BASE))
 if '..' in Path(key).parts:raise ValueError('Unsafe member path')
 files[key]=path
for name in ['app.js','app-v4-reference.js','joint-policy.js','joint-policy-v4.js','frame-queue.js','pose-worker.js','index.html','style.css','source-manifest.json']:
 add(ROOT/'public'/name)
for name in ['server.py','start.sh','package.json','package-lock.json','test.mjs','test-output-v5.txt','README-zh.md']:
 add(ROOT/name)
for f in sorted((ROOT/'tests').glob('*.mjs')):add(f)
for name in ['hash_source.py','package_delivery.py','test_range.py','download_assets.py']:add(ROOT/'scripts'/name)
for f in (ROOT/'node_modules/@mediapipe/tasks-vision').iterdir():
 if f.is_file() and f.name in ['vision_bundle.js','vision_bundle.mjs','package.json','README.md']:add(f)
for f in sorted((ROOT/'node_modules/@mediapipe/tasks-vision/wasm').glob('*')):
 if f.is_file() and f.suffix in ['.js','.wasm']:add(f)
for name in ['build/three.module.js','build/three.core.js','examples/jsm/controls/OrbitControls.js','package.json','LICENSE']:add(ROOT/'node_modules/three'/name)
add(ROOT/'assets/pose_landmarker_lite.task');add(ROOT/'assets/model-manifest.json')
for name in ['manifest.json','SOURCES.md','active-inputs.json','alternative-input-manifest.json','ALTERNATIVE-SOURCES.md','intel-LICENSE','restoration-report.json']:
 if (ROOT/'assets/videos'/name).is_file():add(ROOT/'assets/videos'/name)
manifest=json.loads((PY/'distribution-manifest.json').read_text())
for rel,entry in manifest['files'].items():
 f=PY/rel
 actual=hashlib.sha256(f.read_bytes()).hexdigest()
 if actual!=entry['sha256']:raise ValueError(f'Backend distribution allowlist hash stale: {rel}')
 # Evidence already goes in the independent evidence ZIP.
 if f.suffix in ['.log'] or f.name.endswith(('-results.json','-evidence.json','-check.json')) or 'provenance' in f.parts:continue
 add(f)
add(PY/'distribution-manifest.json')
for name in ['CHANGELOG-v5.1.md','v5-to-v5.1-inputs.diff']:
 if (ROOT/name).is_file():add(ROOT/name)
if (ROOT/'assets/videos/active-candidates.json').is_file():add(ROOT/'assets/videos/active-candidates.json')
for name in ['COMMONS-SOURCES.md','commons-derived-manifest.json','derived-input-manifest.json']:
 if (ROOT/'assets/videos'/name).is_file():add(ROOT/'assets/videos'/name)
for key in files:
 if any(s in Path(key).parts for s in ['.venv','venv','__pycache__','.cache','.mplconfig','results','candidates-openmmlab','system-libs']):raise AssertionError('Forbidden package member '+key)
provenance={'files':{key:{'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'bytes':f.stat().st_size} for key,f in files.items()},'legacy_source_references':{}}
for version,relative in [('v3','pose-delivery/pose-live-program-source.zip'),('v4','pose-v4-delivery/pose-live-program-source.zip')]:
 f=BASE/relative
 if f.is_file():provenance['legacy_source_references'][version]={'existing_delivery_filename':'pose-live-program-source.zip','sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'not_duplicated_in_this_archive':True}
print(json.dumps({'members':len(files),'uncompressed_bytes':sum(f.stat().st_size for f in files.values()),'mode':'build' if args.build else 'dry-run','python_whitelist_verified':True},indent=2))
if not args.build:sys.exit(0)
out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
source=out/f'pose-live-{args.release}-source.zip'
if source.exists():raise FileExistsError('Refusing to overwrite '+str(source))
with zipfile.ZipFile(source,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for key,f in files.items():z.write(f,key)
 z.writestr('PACKAGE-MANIFEST.json',json.dumps(provenance,indent=2,ensure_ascii=False))
with zipfile.ZipFile(source) as z:assert z.testzip() is None
if source.stat().st_size>=20_000_000:raise RuntimeError(f'Source ZIP exceeds 20 MB target: {source.stat().st_size}')
print('SOURCE',source,source.stat().st_size,hashlib.sha256(source.read_bytes()).hexdigest())
if args.videos:
 for clip,filename in [('worker','intel-worker-zone-detection.mp4'),('aisle','intel-store-aisle-detection.mp4')]:
  videos=out/f'pose-live-{args.release}-input-{clip}.zip'
  if videos.exists():raise FileExistsError('Refusing to overwrite '+str(videos))
  names=[filename,'alternative-input-manifest.json','ALTERNATIVE-SOURCES.md','intel-LICENSE']
  with zipfile.ZipFile(videos,'w',compression=zipfile.ZIP_STORED) as z:
   for name in names:z.write(ROOT/'assets/videos'/name,'pose-v5/assets/videos/'+name)
   z.writestr('INPUT-PACKAGE.txt',f'Input: {clip}\nExtract beside the source package, preserving pose-v5/assets/videos/.\nOriginal downloaded video bytes; no frame-rate conversion.\nSee included Intel CC-BY 4.0 license and source manifest.\n')
  with zipfile.ZipFile(videos) as z:assert z.testzip() is None
  if videos.stat().st_size>=20_000_000:raise RuntimeError(f'Input ZIP exceeds 20 MB: {videos.stat().st_size}')
  print('VIDEO',videos,videos.stat().st_size,hashlib.sha256(videos.read_bytes()).hexdigest())

if args.candidate_ids:
 ids=[x.strip() for x in args.candidate_ids.split(',') if x.strip()]
 catalog=json.loads((ROOT/'assets/videos/active-candidates.json').read_text())
 selected={key:catalog[key] for key in ids}
 member_files={}
 for key,data in selected.items():
  if data.get('license') not in ['CC BY-SA 4.0','CC BY-SA 3.0','CC BY 4.0']:raise ValueError('Review license before packaging '+key)
  for field in ['src','metadata_path','audit_path','frame_map_path','derivation_path','provenance_path']:
   if not data.get(field):continue
   rel=data[field].removeprefix('./').lstrip('/')
   f=(ROOT/rel).resolve()
   if not f.is_relative_to(ROOT.resolve()):raise ValueError('Unsafe candidate path')
   if f.is_file():member_files[str(f.relative_to(BASE))]=f
  media=ROOT/data['src'].removeprefix('./').lstrip('/')
  if hashlib.sha256(media.read_bytes()).hexdigest()!=data['sha256']:raise ValueError('Candidate media hash differs: '+key)
  frame_map=media.with_suffix('.source-frame-map.csv')
  if frame_map.is_file():member_files[str(frame_map.relative_to(BASE))]=frame_map
 videozip=out/f'pose-live-{args.release}-primary-inputs.zip'
 if videozip.exists():raise FileExistsError('Refusing to overwrite '+str(videozip))
 attribution='Primary licensed test inputs. Extract beside the source ZIP, preserving pose-v5/assets/videos/.\nNo source frame-rate upsampling or generated frames. See per-input notes and audit.\n\n'
 for key,d in selected.items():
  attribution+=f"{key}: {d['label']}\nAuthor: {d['author']}\nSource: {d['source_url']}\nLicense: {d['license']} {d['license_url']}\nPackaged SHA256: {d['sha256']}\nChanges/notes: {d.get('notes','')}\nTransformations: {', '.join(d.get('changes',[]))}\nOriginal source SHA256: {d.get('source_sha256',d['sha256'])}\n\n"
 with zipfile.ZipFile(videozip,'w',compression=zipfile.ZIP_STORED) as z:
  for key,f in member_files.items():z.write(f,key)
  z.writestr('ATTRIBUTION.txt',attribution)
  z.writestr('SELECTED-INPUT-MANIFEST.json',json.dumps(selected,indent=2,ensure_ascii=False))
 with zipfile.ZipFile(videozip) as z:assert z.testzip() is None
 if videozip.stat().st_size>=20_000_000:raise RuntimeError(f'Primary inputs ZIP too large; split selected IDs: {videozip.stat().st_size}')
 print('PRIMARY VIDEOS',videozip,videozip.stat().st_size,hashlib.sha256(videozip.read_bytes()).hexdigest())
