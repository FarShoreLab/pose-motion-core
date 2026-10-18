"""Replay target policies on byte-frozen detections/features and tracker output. No inference."""
from isolation import BASE, ROOT
import argparse, hashlib, json, time
from pathlib import Path
import numpy as np
from target_policy_v2 import GalleryTargetPolicy

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',default='basketball-botsort-v1-model448')
    p.add_argument('--attempt',default='basketball-botsort-gallery-v2')
    p.add_argument('--policy',default='policy-v2.json')
    a=p.parse_args()
    src=ROOT/'outputs'/a.source
    out=ROOT/'outputs'/a.attempt
    out.mkdir(parents=True,exist_ok=False)
    config_path=Path(__file__).with_name(a.policy)
    config=json.loads(config_path.read_text())
    input_files=[src/'frame-decisions.jsonl',src/'detection-embeddings.npz']
    hashes={f.name:sha(f) for f in input_files}
    records=[json.loads(x) for x in input_files[0].read_text().splitlines()]
    z=np.load(input_files[1],allow_pickle=False)
    guard=GalleryTargetPolicy(config)
    output=[]
    start=time.perf_counter()
    for i,r in enumerate(records):
        dets=r['raw_detections_xyxy_conf_cls']
        lo,hi=z['offsets'][i:i+2]
        assert lo==r['embedding_offset'] and hi-lo==len(dets)
        ids={int(t[-1]):int(t[4]) for t in r['botsort_tracks_xyxy_id_conf_cls_detidx']}
        new=guard.step(i,dets,z['embeddings'][lo:hi],ids)
        for k in ['input_timestamp_ms','source_frame','source_pts_seconds','raw_detections_xyxy_conf_cls',
                  'botsort_tracks_xyxy_id_conf_cls_detidx','embedding_offset','embedding_count']:
            new[k]=r[k]
        output.append(new)
    elapsed=time.perf_counter()-start
    assert hashes=={f.name:sha(f) for f in input_files}
    (out/'frame-decisions.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in output),encoding='utf-8')
    (out/'policy-frozen.json').write_bytes(config_path.read_bytes())
    manifest=json.loads((src/'run-manifest.json').read_text())
    manifest.update({'attempt':a.attempt,'cache_source':a.source,'cache_sha256':hashes,
                     'policy':config,'policy_sha256':sha(config_path),
                     'current_code_sha256':{f.name:sha(f) for f in Path(__file__).parent.glob('*.py')},
                     'inference_executed':False,'tracker_rerun':False,'additional_keyframe_hints':0})
    (out/'run-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    summary={'frames':len(output),'observed_valid_frames':sum(r['valid'] for r in output),
             'states':{s:sum(r['state']==s for r in output) for s in sorted({r['state'] for r in output})},
             'reacquisitions':guard.recoveries,'template_updates':guard.template_updates,
             'identity_guard_seconds':elapsed,'inference_executed':False,'additional_keyframe_hints':0,
             'identity_accuracy':'PENDING visual review; validity is not correctness',
             'cache_before_after_sha256_equal':True,'real_time_claim':False}
    (out/'tracking-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
    print('VALID RANGES', [i for i,r in enumerate(output) if r['valid']])

if __name__=='__main__': main()
