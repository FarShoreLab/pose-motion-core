from isolation import BASE,PRIOR,ROOT
from pathlib import Path
from collections import Counter
import csv,hashlib,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

METHODS=['no_conflict_protection','causal_conflict_freeze','offline_tracklet_reconnect']
CLIPS=['r2_fast_basketball','r2_fast_burpees','r2_slow_overhead','r2_slow_singleleg','r2_turn_ballet_a','r2_turn_ballet_b']
def readrows(path):return [json.loads(x) for x in path.read_text().splitlines()]
def intervals(flags):
    answer=[];start=None
    for i,value in enumerate(flags+[False]):
        if value and start is None:start=i
        if not value and start is not None:answer.append([start,i-1]);start=None
    return answer
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2),encoding='utf-8')

def main():
    out=ROOT/'evaluation';out.mkdir(exist_ok=False)
    gt=json.loads((PRIOR/'diagnostics/visual-evaluation/per-frame-visual-annotations.json').read_text())
    additional=json.loads(Path(__file__).with_name('additional-visual-labels.json').read_text())
    extra={(x['frame'],x['detection']):x for x in additional['labels']}
    source=ROOT/'outputs/r2_occlusion_basketball-v1'
    rows={m:readrows(source/(m+'.jsonl')) for m in METHODS}
    labels={};details=[]
    for m,records in rows.items():
        labels[m]=[]
        for i,(r,g) in enumerate(zip(records,gt)):
            d=r['target_detection'];q=g['target_detection_quality']
            if d is None:identity='missing';q='missing'
            elif d==g['primary_target_detection']:identity='red_target'
            else:
                e=extra[(i,d)];identity=e['identity'];q=e['geometry_quality']
            item={'method':m,'frame':i,'detection_index':d,'identity':identity,'geometry_quality':q,
                'algorithm_identity_status':r['target_identity_status'],'algorithm_geometry_status':r['target_geometry_status'],
                'clear_target_opportunity':g['clear_target_detection_available'],'independent_human_ground_truth':False}
            labels[m].append(item);details.append(item)
    old=json.loads((PRIOR/'diagnostics/visual-evaluation/per-attempt-identity-decisions.json').read_text())
    for name,oldname in [('raw_botsort_seed_id2','basketball-botsort-v1-model448-raw-seed-id2'),('prior_gallery_v3','basketball-botsort-gallery-v3')]:
        labels[name]=[]
        for r in [x for x in old if x['attempt']==oldname]:
            i=r['frame'];item={'method':name,'frame':i,'detection_index':r['detection_index'],'identity':r['identity'],
                'geometry_quality':gt[i]['target_detection_quality'] if r['identity']=='red_target' else r['identity'],
                'clear_target_opportunity':gt[i]['clear_target_detection_available'],'independent_human_ground_truth':False}
            labels[name].append(item);details.append(item)
        assert len(labels[name])==207
    metrics={}
    for m,ll in labels.items():
        counts=Counter(x['identity'] for x in ll);n=len(ll);accepted=n-counts['missing']
        wrong=counts['wrong_blue_person'];ambiguous=counts['ambiguous_people_overlap']
        missing=[x['identity']=='missing' for x in ll];gaps=intervals(missing)
        metrics[m]={'frames':n,'identity_counts':dict(counts),'confirmed_frames':accepted,
            'correct_target_coverage':counts['red_target']/n,'confirmed_coverage':accepted/n,
            'wrong_person_risk_among_confirmed':wrong/accepted if accepted else None,
            'wrong_or_ambiguous_risk_among_confirmed':(wrong+ambiguous)/accepted if accepted else None,
            'clear_opportunity_frames':sum(x['clear_target_opportunity'] for x in ll),
            'false_reject_clear_target_frames':sum(x['clear_target_opportunity'] and x['identity']=='missing' for x in ll),
            'clear_target_wrong_or_ambiguous_accepts':sum(x['clear_target_opportunity'] and x['identity'] not in ['missing','red_target'] for x in ll),
            'accepted_truncated_red_target_frames':sum(x['identity']=='red_target' and x['geometry_quality']=='truncated' for x in ll),
            'wrong_person_frames':[x['frame'] for x in ll if x['identity']=='wrong_blue_person'],
            'ambiguous_frames':[x['frame'] for x in ll if x['identity']=='ambiguous_people_overlap'],
            'unresolved_intervals_inclusive':gaps,'longest_unresolved_frames':max([b-a+1 for a,b in gaps],default=0),
            'wrong_person_episodes':intervals([x['identity']=='wrong_blue_person' for x in ll]),
            'new_independent_human_labels':0}
    paired={}
    for baseline in ['raw_botsort_seed_id2','prior_gallery_v3','no_conflict_protection']:
        for m in METHODS:
            if baseline==m:continue
            a=labels[baseline];b=labels[m]
            lost=[i for i in range(207) if a[i]['identity']=='red_target' and b[i]['identity']!='red_target']
            gained=[i for i in range(207) if a[i]['identity']!='red_target' and b[i]['identity']=='red_target']
            paired[baseline+' -> '+m]={'previously_correct_frames_lost':len(lost),'lost_frames':lost,
                'lost_to_missing':sum(b[i]['identity']=='missing' for i in lost),
                'lost_to_wrong_person':sum(b[i]['identity']=='wrong_blue_person' for i in lost),
                'lost_to_ambiguous':sum(b[i]['identity']=='ambiguous_people_overlap' for i in lost),
                'correct_frames_gained':len(gained),'gained_frames':gained,'net_correct_change':len(gained)-len(lost)}
    oracle=json.loads((ROOT/'outputs/oracle-v1-pair-certainty/oracle-results.json').read_text())
    events=[]
    for idx,e in enumerate(oracle['events']):
        a,b=e['event']['conflict_frames_inclusive'];next_start=oracle['events'][idx+1]['event']['conflict_frames_inclusive'][0] if idx+1<len(oracle['events']) else 207
        ev={'name':e['event']['name'],'AI_oracle_conflict_frames_inclusive':[a,b],'duration_frames':b-a+1,'duration_seconds':(b-a+1)/30,
            'right_censored':not e['event']['after'],'methods':{}}
        for m,ll in labels.items():
            first=next((f for f in range(b+1,max(b+1,next_start-2)) if all(ll[j]['identity']=='red_target' for j in range(f,f+3))),None)
            ev['methods'][m]={'correct_frames_during_conflict':sum(ll[i]['identity']=='red_target' for i in range(a,b+1)),
                'unresolved_frames_during_conflict':sum(ll[i]['identity']=='missing' for i in range(a,b+1)),
                'first_3_consecutive_correct_start_after_conflict':first,'delay_after_last_conflict_frame':None if first is None else first-b,
                'delay_seconds':None if first is None else (first-b)/30,'confirmation_evidence_frame':None if first is None else (206 if m=='offline_tracklet_reconnect' else first),
                'evaluation_uses_next_two_labels_to_verify_stability':True}
        events.append(ev)
    protected=rows['causal_conflict_freeze']
    cues=[any(gt[i]['primary_target_detection'] in p['detections'] for p in r['conflict_pairs']) for i,r in enumerate(protected)]
    alarms=[any(gt[i]['primary_target_detection'] in p['detections'] and p['identity_conflict'] for p in r['conflict_pairs']) for i,r in enumerate(protected)]
    conflict={'target_reference_geometric_clue_frames':sum(cues),'target_reference_geometric_clue_intervals':intervals(cues),
        'target_reference_pair_identity_alarm_frames':sum(alarms),'target_reference_pair_identity_alarm_intervals':intervals(alarms),
        'any_scene_geometric_clue_frames':sum(bool(r['conflict_pairs']) for r in protected),
        'identity_state_counts':dict(Counter(r['target_identity_status'] for r in protected)),
        'geometry_state_counts':dict(Counter(r['target_geometry_status'] for r in protected)),
        'scope':'Reference box is used only to score target-specific cue recall, never in tracking. Pair alarms exclude separate severe-appearance/low-margin alarms; explicit state counts are authoritative.'}
    regression=[];needs=[]
    for clip in CLIPS:
        p=PRIOR/'outputs'/('holdout-'+clip+'-v3');raw=readrows(p/'frame-decisions.jsonl')
        folder=ROOT/'outputs'/(clip+'-v1');summary=json.loads((folder/'summary.json').read_text())
        rr={m:readrows(folder/(m+'.jsonl')) for m in METHODS}
        result={'clip':clip,'frames':len(raw),'prior_v3_confirmed_frames':sum(r['valid'] for r in raw),'methods':{},'timing':summary['seconds'],
            'causal_prefix_invariance_checkpoints':summary['causal_prefix_invariance_checkpoints'],'cache_hashes_unchanged':summary['cache_hashes_unchanged'],
            'scope':'Previously seen regression clip. Counts are algorithm states, not independently annotated identity accuracy.'}
        for m,new in rr.items():
            lost=[i for i,(a,b) in enumerate(zip(raw,new)) if a['valid'] and b['target_detection'] is None]
            gain=[i for i,(a,b) in enumerate(zip(raw,new)) if not a['valid'] and b['target_detection'] is not None]
            different=[i for i,(a,b) in enumerate(zip(raw,new)) if a['valid'] and b['target_detection'] is not None and a['detection_index']!=b['target_detection']]
            result['methods'][m]={'confirmed_frames':sum(r['target_detection'] is not None for r in new),'prior_confirmed_now_missing':len(lost),'lost_frames':lost,
                'prior_missing_now_confirmed':len(gain),'gained_frames':gain,'both_confirmed_different_detection':different}
            for i in sorted(set(lost+gain+different)):needs.append({'clip':clip,'method':m,'frame':i,'reason':'lost' if i in lost else 'different' if i in different else 'gained'})
        regression.append(result)
    summary={'status':'RESEARCH_ONLY: causal coverage improved on development clip but still rejects clear targets; offline coverage fails; do not replace baseline or run shared 3D.',
        'review_protocol':additional['protocol'],'independent_human_ground_truth':False,'development_clip':'r2_occlusion_basketball','frames':207,
        'one_existing_encoder_only':True,'second_encoder_tested':False,'automatic_oracle_hints':0,'new_human_box_clicks':0,
        'methods':metrics,'paired_damage_and_gain':paired,'oracle_event_recovery':events,'automatic_conflict_diagnostics':conflict,
        'timing':json.loads((source/'summary.json').read_text()),'regression':regression}
    save(out/'evaluation-summary.json',summary);save(out/'per-frame-identity-labels.json',details);save(out/'regression-review-candidates.json',needs)
    with (out/'per-frame-identity-labels.csv').open('w',newline='',encoding='utf-8') as f:
        fields=sorted(set().union(*(set(x) for x in details)));w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(details)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
    fig,ax=plt.subplots(figsize=(10,5.5));colors=['#ef755d','#23a1c2','#a075ce','#607182','#a59162']
    names={'no_conflict_protection':'No protection','causal_conflict_freeze':'Causal freeze','offline_tracklet_reconnect':'Offline reconnect','raw_botsort_seed_id2':'Raw BoT ID2','prior_gallery_v3':'Prior gallery v3'}
    for color,(m,v) in zip(colors,metrics.items()):
        x=v['confirmed_coverage']*100;lo=v['wrong_person_risk_among_confirmed']*100;hi=v['wrong_or_ambiguous_risk_among_confirmed']*100
        ax.plot([x,x],[lo,hi],color=color,linewidth=5,alpha=.5);ax.scatter([x],[lo],color=color,s=70,label=f"{names[m]}: {v['identity_counts'].get('red_target',0)}/207 correct")
        ax.scatter([x],[hi],color=color,marker='x',s=65)
    ax.set(xlabel='Confirmed coverage (%)',ylabel='Risk among confirmed frames (%)',title='Development clip: coverage and identity risk\nDot = definite wrong; cross = wrong + ambiguous (AI review)',ylim=(-.3,7));ax.grid(alpha=.2);ax.legend(loc='upper left');fig.tight_layout();fig.savefig(out/'risk-coverage.png',dpi=160);fig.savefig(out/'risk-coverage.svg');plt.close(fig)
    print(json.dumps({'metrics':metrics,'paired':{k:{x:y for x,y in v.items() if not isinstance(y,list)} for k,v in paired.items()},'conflict':conflict,'regression':regression},indent=2))
if __name__=='__main__':main()
