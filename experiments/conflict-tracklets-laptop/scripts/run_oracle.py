from isolation import BASE,PRIOR,ROOT
from pathlib import Path
import argparse,hashlib,json,time
import numpy as np
from association import associate

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',default='oracle-v1');args=parser.parse_args()
    source=PRIOR/'outputs/basketball-botsort-v1-model448'
    paths=[source/'frame-decisions.jsonl',source/'detection-embeddings.npz']
    hashes={p.name:sha(p) for p in paths}
    rows=[json.loads(x) for x in paths[0].read_text().splitlines()]
    z=np.load(paths[1],allow_pickle=False);emb=z['embeddings']
    configpath=Path(__file__).with_name('policy-v1.json');c=json.loads(configpath.read_text())
    annotations=json.loads(Path(__file__).with_name('oracle-anchors.json').read_text())
    out=ROOT/'outputs'/args.attempt;out.mkdir(parents=True,exist_ok=False)
    (out/'policy-frozen.json').write_bytes(configpath.read_bytes())
    def tracklet(anchor):
        frames=[p[0] for p in anchor['samples']];indices=[p[1] for p in anchor['samples']]
        return {'frames':frames,'boxes':[rows[f]['raw_detections_xyxy_conf_cls'][d][:4] for f,d in zip(frames,indices)],
            'features':np.array([emb[rows[f]['embedding_offset']+d] for f,d in zip(frames,indices)])}
    results=[]
    for event in annotations['events']:
        before=[tracklet(a) for a in event['before']];after=[tracklet(a) for a in event['after']]
        t=time.perf_counter();r=associate(before,after,c);elapsed=time.perf_counter()-t
        expected=[[i,j] for i,a in enumerate(event['before']) for j,b in enumerate(event['after']) if a['identity']==b['identity']]
        wrong=[pair for pair in r['best']['pairs'] if pair not in expected]
        future=max((max(a['frames']) for a in after),default=None)
        results.append({'event':event,**r,'expected_pairs_for_evaluation_only':expected,'best_wrong_pairs':wrong,
            'correctly_matched_endpoints':sum(pair in expected for pair in r['best']['pairs']),
            'future_evidence_last_frame':future,'future_evidence_last_seconds':future/30 if future is not None else None,
            'frames_after_conflict_end_until_anchor_available':future-event['conflict_frames_inclusive'][1] if future is not None else None,
            'association_seconds':elapsed,'oracle_assisted':True,'independent_human_ground_truth':False})
    assert hashes=={p.name:sha(p) for p in paths}
    result={'config_sha256':sha(configpath),'cache_hashes':hashes,'cache_unchanged':True,'events':results,
        'new_model_inference':False,'single_existing_reid_encoder':True,
        'risk_coverage':[{'gap_threshold':t,'confirmed_events':sum(r['global_gap'] is not None and r['global_gap']>=t and bool(r['best']['pairs']) for r in results),
            'wrong_pairs_in_those_events':sum(len(r['best_wrong_pairs']) for r in results if r['global_gap'] is not None and r['global_gap']>=t)} for t in c['risk_coverage_gap_thresholds']]}
    (out/'oracle-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'events':[{'name':r['event']['name'],'status':r['identity_status'],'best':r['best'],
        'gap':r['global_gap'],'wrong_pairs':r['best_wrong_pairs'],'latest_future':r['future_evidence_last_frame']} for r in results]},indent=2))
if __name__=='__main__':main()
