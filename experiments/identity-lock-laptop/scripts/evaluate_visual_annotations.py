"""Materialize explicit assistant visual annotations and score frozen attempts against them.

Every frame was inspected in the full scene and detection contact sheets. Thumbnail
ordering is NOT a label: the overrides below record the actual visual decisions.
These are not independent human ground truth or a held-out evaluation.
"""
from isolation import BASE,ROOT
import csv,hashlib,json
from collections import Counter
import numpy as np
from target_policy import iou

def rows(name):return [json.loads(x) for x in (ROOT/'outputs'/name/'frame-decisions.jsonl').read_text().splitlines()]
def intervals(values):
    out=[]
    for v in values:
        if out and out[-1][1]==v-1:out[-1][1]=v
        else:out.append([v,v])
    return out
def q(values):return {str(p):float(np.quantile(values,p)) for p in [0,.05,.25,.5,.75,.95,1]} if values else {}

def main():
    base=rows('basketball-botsort-v1-model448')
    order=json.loads((ROOT/'diagnostics/detection-annotation-sheets/thumbnail-order.json').read_text())
    overrides={24:3,25:3,26:None,27:4,28:4,29:3,30:3,83:4,87:2,88:2,89:3,90:2,91:4,
        93:2,94:2,95:2,98:2,99:2,100:2,101:2,102:2,105:5,106:5,107:3,108:3,109:3,
        110:3,111:3,112:3,113:3,117:3,118:3,119:3,138:5,179:2,180:2,181:2,182:3,
        183:4,184:4,185:3,186:4,188:3,198:0,199:3,200:3}
    overlap=set(range(21,31))|set(range(77,105))|set(range(145,151))|set(range(156,184))|set(range(186,189))|{201}
    truncated={107,108,110,111,112,185,200}
    annotations=[]
    for i,r in enumerate(base):
        index=overrides.get(i,order[i]['proposal_order'][0])
        quality='no_isolated_target_detection' if index is None else 'truncated' if i in truncated else 'overlap' if i in overlap else 'clear'
        det=r['raw_detections_xyxy_conf_cls'][index] if index is not None else None
        old='ambiguous_people_overlap' if 25<=i<=29 or 80<=i<=100 else 'wrong_blue_person' if i>=101 else 'red_target'
        annotations.append({'frame':i,'timestamp_seconds':i/30,'target_present':'red_shirt_light_shorts_visible',
            'primary_target_detection':index,'target_detection_confidence':det[4] if det else None,
            'target_detection_quality':quality,'clear_target_detection_available':bool(det and det[4]>=.2 and quality=='clear'),
            'old_gvhmr_identity':old,'visual_reviewer':'assistant','independent_human_ground_truth':False,
            'used_for_algorithm_initialization':i==0,'used_as_recovery_hint':False})
    attempts=['basketball-botsort-v1-run2','basketball-botsort-v1-model448','basketball-botsort-gallery-v2',
              'basketball-botsort-gallery-v3','basketball-deepocsort-gallery-v3']
    metrics={};details=[];unreviewed=[]
    for name in attempts:
        rr=rows(name)
        assert all(r['raw_detections_xyxy_conf_cls']==b['raw_detections_xyxy_conf_cls'] for r,b in zip(rr,base))
        frames=[]
        for i,(r,a) in enumerate(zip(rr,annotations)):
            index=r.get('detection_index') if r['valid'] else None
            if index is None:label='missing'
            elif index==a['primary_target_detection']:label='red_target'
            else:
                label='UNREVIEWED';unreviewed.append([name,i,index,a['primary_target_detection']])
            frames.append({'frame':i,'valid':r['valid'],'identity':label,'detection_index':index,
                'state':r['state'],'wrong_rejection_clear_target':label=='missing' and a['clear_target_detection_available'],
                'accepted_truncated_target':label=='red_target' and a['target_detection_quality']=='truncated'})
            details.append(dict(attempt=name,**frames[-1]))
        counts=Counter(f['identity'] for f in frames)
        gaps=intervals([f['frame'] for f in frames if f['identity']=='missing'])
        metrics[name]={'identity_counts':dict(counts),'correct_target_coverage':counts['red_target']/len(frames),
            'wrong_accepts':counts['wrong_blue_person'],'unreviewed_accepts':counts['UNREVIEWED'],
            'wrong_rejections_when_clear_target_detection_exists':sum(f['wrong_rejection_clear_target'] for f in frames),
            'accepted_truncated_target_boxes':sum(f['accepted_truncated_target'] for f in frames),
            'missing_intervals_inclusive':gaps,'longest_missing_frames':max((b-a+1 for a,b in gaps),default=0),
            'recovery_frames':[i for i,r in enumerate(rr) if r['state']=='reacquired'],
            'additional_keyframe_hints':0}
    for name in ['basketball-botsort-v1-model448','basketball-deepocsort-gallery-v3']:
        raw=[]
        for i,(r,a) in enumerate(zip(rows(name),annotations)):
            t=next((t for t in r['botsort_tracks_xyxy_id_conf_cls_detidx'] if int(t[4])==2),None)
            index=int(t[7]) if t is not None else None
            if index is None:label='missing'
            elif name.startswith('basketball-deep') and i in [88,90]:label='wrong_blue_person'
            elif name.startswith('basketball-deep') and i in [86,87]:label='ambiguous_people_overlap'
            elif name.startswith('basketball-botsort') and 105<=i<=108:label='ambiguous_people_overlap'
            elif index==a['primary_target_detection']:label='red_target'
            else:label='UNREVIEWED';unreviewed.append([name+'-raw',i,index,a['primary_target_detection']])
            raw.append({'attempt':name+'-raw-seed-id2','frame':i,'detection_index':index,'identity':label})
        details.extend(raw);counts=Counter(f['identity'] for f in raw)
        metrics[name+'-raw-seed-id2']={'identity_counts':dict(counts),
            'correct_target_coverage':counts['red_target']/207,'wrong_accepts':counts['wrong_blue_person'],
            'missing_intervals_inclusive':intervals([f['frame'] for f in raw if f['identity']=='missing']),
            'wrong_person_frames':[f['frame'] for f in raw if f['identity']=='wrong_blue_person'],
            'ambiguous_frames':[f['frame'] for f in raw if f['identity']=='ambiguous_people_overlap']}
    metrics['original_gvhmr_id2']={'identity_counts':dict(Counter(a['old_gvhmr_identity'] for a in annotations)),
        'first_definite_wrong_person_frame':101,'transition_uncertainty_frames':[80,100],
        'caution':'Visual identity labels; no claim that ID switch happened exactly at frame 101.'}
    z=np.load(ROOT/'outputs/basketball-botsort-v1-model448/detection-embeddings.npz',allow_pickle=False)
    features=z['embeddings'];anchor=features[1];pos=[];neg=[];separation=[]
    for a,r in zip(annotations,base):
        i=a['frame'];di=a['primary_target_detection'];off=r['embedding_offset']
        if not a['clear_target_detection_available'] or i==0:continue
        target=r['raw_detections_xyxy_conf_cls'][di][:4]
        positive=float(features[off+di]@anchor);pos.append(positive)
        # Main bright-blue distractor ID1 is visually verified throughout. Exclude mixed crops.
        bt=next((t for t in r['botsort_tracks_xyxy_id_conf_cls_detidx'] if int(t[4])==1),None)
        negative=None
        if bt is not None:
            nd=int(bt[7]);b=r['raw_detections_xyxy_conf_cls'][nd][:4]
            if iou(target,b)<.05:
                negative=float(features[off+nd]@anchor);neg.append(negative)
        separation.append({'frame':i,'target_detection_index':di,'positive_anchor_cosine':positive,'blue_anchor_cosine':negative})
    summary={'review_protocol':'Assistant inspected all 207 full frames, all 207 top-three candidate strips, and all candidates in 15 difficult frames; not independent human GT.',
        'development_set':True,'initial_assistant_visual_seed':1,'human_box_clicks':0,'additional_keyframe_hints':0,
        'target_detection_availability':dict(Counter(a['target_detection_quality'] for a in annotations)),
        'clear_target_opportunity_frames':sum(a['clear_target_detection_available'] for a in annotations),
        'metrics':metrics,'anchor_feature_diagnostic':{'clean_positive_count':len(pos),'clean_negative_count':len(neg),
            'positive_quantiles':q(pos),'negative_quantiles':q(neg),'range_overlap':bool(pos and neg and min(pos)<=max(neg)),
            'positive_below_v1_070':sum(x<.7 for x in pos),'positive_below_v1_recovery_078':sum(x<.78 for x in pos),
            'scope':'Only clean target crops and visually verified bright-blue distractor crops; descriptive development-set diagnostic, not a calibrated ReID ROC.'},
        'unreviewed_selected_detections':unreviewed,'result':'FAILED: prolonged false rejections; do not integrate into shared pose inference.'}
    out=ROOT/'diagnostics/visual-evaluation';out.mkdir(exist_ok=False)
    for name,data in [('per-frame-visual-annotations',annotations),('per-attempt-identity-decisions',details),('feature-separation',separation)]:
        (out/(name+'.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')
        fields=list(dict.fromkeys(k for row in data for k in row))
        with (out/(name+'.csv')).open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
    (out/'evaluation-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
