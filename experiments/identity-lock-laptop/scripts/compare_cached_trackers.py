"""Exactly one Deep OC-SORT comparison with the same frozen detections and genuine ReID vectors."""
from isolation import BASE, ROOT
import hashlib,json,time
from pathlib import Path
from types import SimpleNamespace
import av,numpy as np
from ultralytics.engine.results import Boxes
from ultralytics.trackers.bot_sort import BOTSORT
from ultralytics.trackers.deep_oc_sort import DeepOCSORT
from target_policy_v2 import GalleryTargetPolicy

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

class AuditedDeepOCSORT(DeepOCSORT):
    def __init__(self,args):
        self.appearance_calls=0;self.appearance_pairs=0
        super().__init__(args)
    def _fuse_appearance(self,dists,tracks,detections,iou_dists=None):
        if tracks and detections:
            assert all(t.smooth_feat is not None for t in tracks)
            assert all(t.curr_feat is not None for t in detections)
            self.appearance_calls+=1;self.appearance_pairs+=len(tracks)*len(detections)
        return super()._fuse_appearance(dists,tracks,detections,iou_dists)

def main():
    src=ROOT/'outputs/basketball-botsort-v1-model448'
    out=ROOT/'outputs/basketball-deepocsort-gallery-v3'
    out.mkdir(parents=True,exist_ok=False)
    c=json.loads(Path(__file__).with_name('policy-v3.json').read_text())
    keys=['track_high_thresh','track_low_thresh','new_track_thresh','track_buffer','match_thresh',
          'fuse_score','gmc_method','proximity_thresh','appearance_thresh']
    common={k:c[k] for k in keys}
    common.update(with_reid=True,model='auto',device='cpu')
    bot=BOTSORT(SimpleNamespace(**common))
    deep_config=dict(common,delta_t=3,inertia=.2,use_byte=True,alpha_fixed_emb=.95)
    deep=AuditedDeepOCSORT(SimpleNamespace(**deep_config))
    guard=GalleryTargetPolicy(c)
    files=[src/'frame-decisions.jsonl',src/'detection-embeddings.npz']
    hashes={p.name:sha(p) for p in files}
    records=[json.loads(x) for x in files[0].read_text().splitlines()]
    cache=np.load(files[1],allow_pickle=False)
    manifest=json.loads((src/'run-manifest.json').read_text())
    manifest.update({'attempt':out.name,'tracker_name':'Deep OC-SORT','cache_source':src.name,
        'cache_sha256':hashes,'tracker_config':deep_config,'policy':c,
        'policy_sha256':sha(Path(__file__).with_name('policy-v3.json')),
        'inference_executed':False,'encoder_mode':'auto pass-through of cached yolo26n-reid.onnx 448px vectors; NOT detector features',
        'configuration_basis':'common detection/association thresholds equal BoT-SORT; Deep OC-SORT delta_t/inertia/EMA official defaults; low-score pass enabled; same sparseOptFlow GMC',
        'additional_mature_tracker_candidates':1,'code_sha256':sha(__file__)})
    (out/'run-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (out/'policy-frozen.json').write_text(json.dumps(c,indent=2),encoding='utf-8')
    output=[];differences=[];bot_s=deep_s=guard_s=0.
    with av.open(str(BASE/'outputs/r2_occlusion_basketball/input_30fps.mp4')) as v:
        for i,f in enumerate(v.decode(video=0)):
            r=records[i];dets=np.asarray(r['raw_detections_xyxy_conf_cls'],dtype=np.float32)
            boxes=Boxes(dets,(368,640));bgr=f.to_ndarray(format='bgr24')
            lo,hi=cache['offsets'][i:i+2];feats=cache['embeddings'][lo:hi]
            assert len(feats)==len(dets)
            t=time.perf_counter();bt=bot.update(boxes,bgr,feats=feats.copy());bot_s+=time.perf_counter()-t
            expected=np.asarray(r['botsort_tracks_xyxy_id_conf_cls_detidx'],dtype=np.float32)
            if bt.shape!=expected.shape or not np.allclose(bt,expected,rtol=0,atol=.0001):differences.append(i)
            t=time.perf_counter();dt=deep.update(boxes,bgr,feats=feats.copy());deep_s+=time.perf_counter()-t
            ids={int(t[-1]):int(t[4]) for t in dt}
            t=time.perf_counter();new=guard.step(i,dets,feats,ids);guard_s+=time.perf_counter()-t
            for k in ['input_timestamp_ms','source_frame','source_pts_seconds','raw_detections_xyxy_conf_cls','embedding_offset','embedding_count']:
                new[k]=r[k]
            new['botsort_tracks_xyxy_id_conf_cls_detidx']=dt.tolist() # compatibility with the review renderer
            new['raw_tracker_name']='Deep OC-SORT'
            output.append(new)
    assert hashes=={p.name:sha(p) for p in files}
    assert deep.appearance_pairs>0
    (out/'frame-decisions.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in output),encoding='utf-8')
    summary={'frames':len(output),'observed_valid_frames':sum(r['valid'] for r in output),
        'states':{s:sum(r['state']==s for r in output) for s in sorted({r['state'] for r in output})},
        'reacquisitions':guard.recoveries,'template_updates':guard.template_updates,
        'bot_replay_mismatched_frames':differences,'bot_replay_atol':.0001,
        'bot_association_seconds':bot_s,'deep_association_seconds':deep_s,'identity_guard_seconds':guard_s,
        'deep_real_appearance_cost_calls':deep.appearance_calls,'deep_real_appearance_cost_pairs':deep.appearance_pairs,
        'inference_executed':False,'additional_keyframe_hints':0,'cache_hashes_unchanged':True,
        'identity_accuracy':'PENDING visual review','real_time_claim':False}
    (out/'tracking-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
