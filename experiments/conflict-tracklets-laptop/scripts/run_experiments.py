from isolation import BASE,PRIOR,ROOT
from conflict_tracker import ConflictTracker,offline_link
from pathlib import Path
import argparse,hashlib,json,time
import numpy as np

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def clean(record):return {k:v for k,v in record.items() if k!='seconds'}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--clip',default='r2_occlusion_basketball');parser.add_argument('--attempt',default='v1');args=parser.parse_args()
    source=PRIOR/'outputs'/('basketball-botsort-v1-model448' if args.clip=='r2_occlusion_basketball' else 'holdout-'+args.clip+'-v3')
    inputs=[source/'frame-decisions.jsonl',source/'detection-embeddings.npz']
    hashes={p.name:sha(p) for p in inputs};rows=[json.loads(x) for x in inputs[0].read_text().splitlines()]
    with np.load(inputs[1],allow_pickle=False) as z:features=z['embeddings'];offsets=z['offsets']
    configpath=Path(__file__).with_name('policy-v1.json');c=json.loads(configpath.read_text());priorconfig=json.loads((source/'policy-frozen.json').read_text())
    seed=priorconfig['initialization']['seed_bbox_xyxy']
    out=ROOT/'outputs'/(args.clip+'-'+args.attempt);out.mkdir(parents=True,exist_ok=False)
    (out/'policy-frozen.json').write_bytes(configpath.read_bytes())
    manifest={'clip':args.clip,'input_frames':len(rows),'cached_source':str(source),'cache_sha256':hashes,'config_sha256':sha(configpath),
        'seed':priorconfig['initialization'],'oracle_anchors_used':False,'new_model_inference':False,
        'code_sha256':{p.name:sha(p) for p in Path(__file__).parent.glob('*.py')},
        'input_sha256':json.loads((source/'run-manifest.json').read_text())['input_sha256']}
    (out/'run-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    timings={};trackers={}
    for name,protect in [('no_conflict_protection',False),('causal_conflict_freeze',True)]:
        tracker=ConflictTracker(c,seed,protect);start=time.perf_counter()
        for i,r in enumerate(rows):
            lo,hi=offsets[i:i+2]
            tracker.step(i,r['raw_detections_xyxy_conf_cls'],features[lo:hi])
        timings[name]=time.perf_counter()-start;trackers[name]=tracker
        (out/(name+'.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in tracker.records),encoding='utf-8')
    protected=trackers['causal_conflict_freeze']
    offline=offline_link(protected,c);timings['offline_link']=offline['seconds']
    (out/'offline_tracklet_reconnect.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in offline.pop('records')),encoding='utf-8')
    (out/'offline-links.json').write_text(json.dumps(offline,indent=2),encoding='utf-8')
    # Prove prefix invariance at fixed checkpoints: future input must not affect causal output.
    checked=[]
    for stop in sorted({min(len(rows),n) for n in [30,90,150]}):
        prefix=ConflictTracker(c,seed,True)
        for i,r in enumerate(rows[:stop]):
            lo,hi=offsets[i:i+2];prefix.step(i,r['raw_detections_xyxy_conf_cls'],features[lo:hi])
        assert [clean(r) for r in prefix.records]==[clean(r) for r in protected.records[:stop]]
        checked.append(stop)
    assert hashes=={p.name:sha(p) for p in inputs}
    summary={'clip':args.clip,'frames':len(rows),'causal_prefix_invariance_checkpoints':checked,'cache_hashes_unchanged':True,
        'seconds':timings,'single_existing_reid_encoder':True,'second_encoder_tested':False,'new_pose_inference':False,
        'confirmed_counts':{},'identity_accuracy':'PENDING AI visual review; confirmed state is not correctness',
        'causal_per_frame_seconds':{'median':float(np.median([r['seconds'] for r in protected.records])),
            'p95':float(np.quantile([r['seconds'] for r in protected.records],.95)),
            'max':max(r['seconds'] for r in protected.records)},
        'causal_observation_confirmation_delay_frames':c['clear_anchor_frames']-1,
        'offline_global_future_evidence_frame':len(rows)-1,'offline_fragment_count':len(offline['fragments'])}
    for name in ['no_conflict_protection','causal_conflict_freeze','offline_tracklet_reconnect']:
        rr=[json.loads(x) for x in (out/(name+'.jsonl')).read_text().splitlines()]
        summary['confirmed_counts'][name]=sum(r['target_detection'] is not None for r in rr)
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
