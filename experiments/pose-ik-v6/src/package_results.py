from pathlib import Path
import zipfile,json,hashlib
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'delivery';OUT.mkdir(exist_ok=True)
def archive(name,pairs):
 seen=set()
 with zipfile.ZipFile(OUT/name,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p,arc in pairs:
   if arc not in seen:z.write(p,arc);seen.add(arc)
 print(name,(OUT/name).stat().st_size)
source=[]
for base in ['src','audit','live-app']:
 for p in (ROOT/base).rglob('*'):
  if not p.is_file():continue
  rel=p.relative_to(ROOT)
  if any(s in ['__pycache__','results','qa','.cache','.mplconfig','system-libs'] for s in rel.parts):continue
  if p.suffix in ['.log','.zip','.webm','.mp4','.png','.npz'] and 'assets' not in rel.parts:continue
  if p.name in ['launch-native.sh','restart-native.sh']:continue
  source.append((p,str(Path('pose-ik-v6')/rel)))
for name in ['README-zh.md','INSTALL-zh.md','requirements-minimal.txt','requirements-environment.txt','baseline-sha256.txt','live-summary.json','environment.json']:
 p=ROOT/name
 if p.exists():source.append((p,'pose-ik-v6/'+name))
archive('pose-ik-v6-experimental-source.zip',source)
offline=[]
for base in ['output','audit']:
 for p in (ROOT/base).rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.png':offline.append((p,str(p.relative_to(ROOT))))
for p in (ROOT/'metric-reference/raw').glob('v52-*-release.json'):offline.append((p,str(p.relative_to(ROOT))))
for name in ['README-zh.md','live-summary.json','environment.json']:
 p=ROOT/name
 if p.exists():offline.append((p,name))
archive('pose-ik-v6-offline-raw-and-controls.zip',offline)
live=[]
for p in (ROOT/'live-app/pose-v52/results').glob('*'):
 if p.is_file():live.append((p,'results/'+p.name))
for p in (ROOT/'live-app/qa').glob('*'):
 if p.is_file() and p.suffix!='.png':live.append((p,'qa/'+p.name))
for name in ['README-zh.md','live-summary.json','environment.json']:
 p=ROOT/name
 if p.exists():live.append((p,name))
archive('pose-ik-v6-live-raw-metrics.zip',live)
archive('pose-ik-v6-full-live-recordings.zip',[(p,p.name) for p in (ROOT/'recordings').glob('*.webm')])
manifest={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in OUT.iterdir() if p.is_file() and p.name!='sha256-manifest.json'};(OUT/'sha256-manifest.json').write_text(json.dumps(manifest,indent=2))
