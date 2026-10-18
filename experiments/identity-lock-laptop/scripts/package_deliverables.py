"""Package bounded independent failure evidence; no weights, source videos or credentials."""
from isolation import BASE,ROOT
import hashlib,json,shutil,subprocess,zipfile
from pathlib import Path

REPORT=Path(__file__).resolve().parent.parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def archive(path,entries,receipt):
    assert len({name for _,name in entries})==len(entries)
    hashes=[]
    with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for src,name in sorted(entries,key=lambda x:x[1]):
            z.write(src,name);hashes.append(f'{sha(src)}  {name}')
        z.writestr('SHA256SUMS.txt','\n'.join(hashes)+'\n')
        z.writestr('BRANCH-RECEIPT.json',json.dumps(receipt,indent=2))
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        checks=z.read('SHA256SUMS.txt').decode().splitlines()
        for line in checks:
            digest,name=line.split('  ',1)
            assert hashlib.sha256(z.read(name)).hexdigest()==digest
    assert path.stat().st_size<20_000_000
    return {'filename':path.name,'bytes':path.stat().st_size,'sha256':sha(path),'zip_crc_and_every_entry_sha256':'PASS','entries':len(entries)+2}

def main():
    out=ROOT/'deliverables';out.mkdir(exist_ok=False)
    commit=subprocess.check_output(['git','-C',str(REPORT.parents[1]),'rev-parse','HEAD'],text=True).strip()
    receipt={'branch':'research/identity-lock-2026-10-18','commit':commit,
        'repository':'https://github.com/FarShoreLab/pose-motion-core','result':'FAILED',
        'main_unchanged':'e9d7eb38f24f901d7935fde0e3da4907b9a562a9',
        'previous_research_unchanged':'424b277bfd5562c19f34c8a4d0f638e4a78ec783'}
    entries=[]
    allowed={'.md','.py','.json','.csv','.txt','.png','.svg','.gitignore'}
    for p in REPORT.rglob('*'):
        if p.is_file() and (p.suffix in allowed or p.name=='.gitignore'):
            entries.append((p,'source/experiments/identity-lock-laptop/'+p.relative_to(REPORT).as_posix()))
    for p in (ROOT/'outputs').rglob('*'):
        if p.is_file() and p.suffix in {'.json','.jsonl','.npz'}:
            entries.append((p,'experiment-data/'+p.relative_to(ROOT).as_posix()))
    for p in (ROOT/'diagnostics').rglob('*'):
        if p.is_file() and p.suffix in {'.json','.csv'}:
            entries.append((p,'experiment-data/'+p.relative_to(ROOT).as_posix()))
    for p in (ROOT/'evidence').rglob('*.json'):
        entries.append((p,'experiment-data/'+p.relative_to(ROOT).as_posix()))
    for source in sorted((BASE/'outputs').glob('r2_*')):
        for name in ['input-manifest.json','frame-map.csv','bbox.pt','bbox-metrics.json']:
            p=source/name;entries.append((p,'baseline-reference/outputs/'+source.name+'/'+name))
    p=BASE/'outputs/r2_occlusion_basketball/mediapipe_raw.npz'
    entries.append((p,'baseline-reference/outputs/r2_occlusion_basketball/'+p.name))
    results=[archive(out/'identity-lock-failure-diagnostics-2026-10-18.zip',entries,receipt)]
    visual=[]
    for dirname in ['detection-annotation-sheets','annotation-supplement']:
        for p in (ROOT/'diagnostics'/dirname).glob('*.jpg'):
            visual.append((p,'visual-review/'+dirname+'/'+p.name))
    for p in (ROOT/'evidence/holdouts').glob('*.jpg'):visual.append((p,'visual-review/holdouts/'+p.name))
    for name in ['first-refusal-official-reid-crops.png','holdout-initial-seeds.jpg']:
        p=ROOT/'diagnostics'/name;visual.append((p,'visual-review/'+p.name))
    for name in ['annotated-frame-088.jpg','annotated-frame-112.jpg','annotated-frame-138.jpg','six-methods-frame-018.jpg','six-methods-frame-088.jpg']:
        p=ROOT/'evidence'/name;visual.append((p,'visual-review/'+p.name))
    for name in ['README.md','THIRD_PARTY.md']:
        visual.append((REPORT/name,name))
    results.append(archive(out/'identity-lock-visual-review-2026-10-18.zip',visual,receipt))
    for p in [ROOT/'evidence/basketball-final-annotated-comparison.mp4',ROOT/'evidence/basketball-same-input-six-methods.mp4',
              ROOT/'evidence/holdouts/six-holdout-tracking-replays.mp4']:
        target=out/p.name;shutil.copy2(p,target)
        assert sha(p)==sha(target) and target.stat().st_size<20_000_000
        results.append({'filename':target.name,'bytes':target.stat().st_size,'sha256':sha(target),'decoded_frame_check':'metrics/final-audit.json'})
    manifest={'result':'FAILED - not a production fix','branch':receipt,'artifacts':results,'individual_limit_bytes':20_000_000,
        'zip_integrity':'CRC + all archived file SHA256 verified','videos':'Full decode frame counts verified before packaging',
        'no_weights_in_archives':True,'new_pose_inference':False}
    (out/'delivery-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (out/'SHA256SUMS.txt').write_text(''.join(f'{r["sha256"]}  {r["filename"]}\n' for r in results),encoding='utf-8')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
