import hashlib,json,zipfile
from pathlib import Path
BASE=Path(r'C:\Users\Construct\Downloads\pose-motion-core\gvhmr-comparison-laptop')
PRIOR=BASE/'identity-lock-2026-10-18'
ROOT=BASE/'conflict-tracklets-2026-10-18'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
ROOT.mkdir(exist_ok=False)
out=ROOT/'archive';out.mkdir()
delivery=json.loads((PRIOR/'deliverables/library-delivery-receipt.json').read_text())
live=json.loads(Path(__file__).with_name('prior-library-check.json').read_text())
indexed={x['library_file_id']:x for x in live};checks=[]
for r in delivery['artifacts']:
    p=Path(r['local_path']);now=indexed[r['library_file_id']]
    assert p.stat().st_size==now['size_bytes']==r['file_size_bytes']
    assert now['file_id']==r['file_id'] and sha(p)==r['sha256']
    if p.suffix=='.zip':
        with zipfile.ZipFile(p) as z:assert z.testzip() is None
    checks.append(dict(r,local_sha256_rechecked=True,library_identity_and_size_unchanged=True))
inputs=[]
for attempt in sorted((PRIOR/'outputs').iterdir()):
    for name in ['frame-decisions.jsonl','detection-embeddings.npz','policy-frozen.json']:
        p=attempt/name
        if p.exists():inputs.append({'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)})
result={'archived_commit':'c76521b983a05d86b684b45d57771c347b5524f0','old_branch':'research/identity-lock-2026-10-18',
    'old_outputs_overwritten':False,'library_files':checks,'frozen_prior_inputs':inputs,
    'verification_scope':'local bytes SHA256 and ZIP CRC freshly verified; Library current immutable file IDs and sizes match delivery receipt; no redownload'}
(out/'previous-release-verified.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'archived_artifacts':len(checks),'frozen_input_files':len(inputs),'root':str(ROOT)}))
