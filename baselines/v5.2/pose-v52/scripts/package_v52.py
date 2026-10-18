#!/usr/bin/env python3
from pathlib import Path
import zipfile,json,hashlib,shutil
W=Path(__file__).resolve().parents[2];out=W/'pose-v52-delivery';out.mkdir(exist_ok=True)
def zip_paths(name,items):
 with zipfile.ZipFile(out/name,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for path,arc in items:z.write(path,arc)
 print(name,(out/name).stat().st_size)
front=W/'pose-v52';back=W/'pose-v52-python'
items=[]
for p in front.rglob('*'):
 if not p.is_file():continue
 r=p.relative_to(front)
 if r.parts[0] in ('results','.cache','.mplconfig','__pycache__'):continue
 if p.suffix in ('.mp4','.webm','.ogv','.png','.jpg'):continue
 if p.suffix in ('.pyc','.log','.pid'):continue
 if p.name.startswith('test-output'):continue
 items.append((p,Path('pose-v52')/r))
backend_names=['server_epoch_modes.py','epoch_clock.py','start.sh','start-epoch-modes.sh','install-linux.sh','fetch-debian-libgles.sh','requirements-lock.txt','requirements-observed.txt','verify_layout.py','INSTALL.md','EPOCH-MODES.md','test_epoch_clock.py','test_epoch_backend.py','test_api.py','collect_environment.py']
for name in backend_names:items.append((back/name,Path('pose-v52-python')/name))
zip_paths('pose-live-v5.2-source.zip',items)
attr=(W/'pose-v51-baseline/ATTRIBUTION.txt').read_text().replace('pose-v5/','pose-v52/')+'\nV5.2 seamless input pack: source compressed sample bytes unchanged, no re-encoding, no new or interpolated frames. fMP4 container remux only. Turn fMP4 media origin is+80ms; app subtracts fixed80ms after startup positioning, retaining original framePTS and17.36s period. Fast retains33/34ms frame durations and599frames. Each manifest gives source/fragment hashes and original framePTS. Recordings add live2D/3D overlays and metrics; applicable CC BY-SA terms and authorship above remain.\n'
(out/'ATTRIBUTION.txt').write_text(attr)
items=[(p,Path('pose-v52/assets/videos/seamless')/p.name) for p in (front/'assets/videos/seamless').iterdir() if p.is_file()]
items += [(out/'ATTRIBUTION.txt','ATTRIBUTION.txt'),(front/'assets/videos/COMMONS-SOURCES.md','pose-v52/assets/videos/COMMONS-SOURCES.md')]
zip_paths('pose-live-v5.2-seamless-inputs.zip',items)
metric=W/'pose-v52-evidence/final-metrics'
for label,b,c in [('slow','baseline-slow','v52-slow-release'),('fast','baseline-fast-final','v52-fast-release'),('turn','baseline-turn','v52-turn-release')]:
 items=[(W/f'pose-v51-baseline/pose-v5/results/{b}.json',f'raw/{b}.json'),(front/f'results/{c}.json',f'raw/{c}.json')]
 items +=[(p,Path('metrics')/p.name) for p in metric.iterdir() if p.name.startswith((b+'-',c+'-'))]
 items +=[(out/'ATTRIBUTION.txt','ATTRIBUTION.txt')]
 zip_paths(f'pose-live-v5.2-{label}-metrics.zip',items)
# Preserve the rejected single-pending experiment and its matched baseline.
items=[(front/'results/candidate-fast.json','candidate-fast-rejected-q1.json'),(W/'pose-v51-baseline/pose-v5/results/baseline-fast.json','baseline-fast-for-q1.json'),(front/'results/candidate-fast-q2.json','candidate-fast-q2-early.json')]
zip_paths('pose-live-v5.2-earlier-experiments.zip',items)
# Source replay and proof scripts, summary data, timing/provenance/tests and independent audit.
items=[]
for folder,prefix in [(W/'pose-next-audit','independent-audit'),(W/'pose-v52-evidence','validation')]:
 for p in folder.iterdir():
  if p.is_file() and p.suffix in ('.json','.txt','.sha256','.py','.mjs') and 'server' not in p.name:items.append((p,Path(prefix)/p.name))
items +=[(metric/'round-summary.json','round-summary.json'),(front/'results/transport-equivalence.json','transport-same-canvas-png-rgba.json')]
zip_paths('pose-live-v5.2-validation.zip',items)
manifest={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in out.iterdir() if p.is_file() and p.name!='DELIVERY-MANIFEST.json'}
(out/'DELIVERY-MANIFEST.json').write_text(json.dumps(manifest,indent=2))
