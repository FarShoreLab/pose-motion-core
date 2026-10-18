"""Detection-based continuity, explicit conflict state, and global partial identity recovery.

No oracle annotations or color labels are read here. Cached numeric tracker IDs
are audit metadata only and do not enter association costs or identity decisions.
"""
import time
import numpy as np
from association import unit,center,scale,iou,overlap,pair_cost,joint_assignment

class ConflictTracker:
    def __init__(self,c,seed,protect=True):
        self.c=c;self.seed=np.asarray(seed);self.protect=protect
        self.micro={};self.identities={};self.next_micro=1;self.next_identity=1
        self.target=None;self.records=[];self.fragments=[];self.open_fragments={}

    def create_identity(self,track,frame):
        identity=self.next_identity;self.next_identity+=1
        self.identities[identity]={'frames':[frame],'boxes':[track['box'].tolist()],
            'features':[track['feature'].copy()],'last_frame':frame}
        track['identity']=identity;track['proposal']=identity
        return identity

    def append_anchor(self,identity,track,frame):
        a=self.identities[identity]
        if a['frames'][-1]==frame:return
        a['frames'].append(frame);a['boxes'].append(track['box'].tolist());a['features'].append(track['feature'].copy());a['last_frame']=frame
        if len(a['frames'])>self.c['gallery_max']:
            for key in ['frames','boxes','features']:a[key]=a[key][:1]+a[key][-(self.c['gallery_max']-1):]

    def step(self,frame,detections,features):
        begin=time.perf_counter();dets=np.asarray(detections,float).reshape(-1,6);feats=unit(features)
        candidates=sorted([i for i,b in enumerate(dets) if b[4]>=self.c['detector_confidence_min']],key=lambda i:-dets[i,4])
        keep=[];duplicates=[]
        for i in candidates:
            dup=next((j for j in keep if iou(dets[i],dets[j])>=self.c['duplicate_iou'] and float(feats[i]@feats[j])>=self.c['duplicate_cosine']),None)
            if dup is None:keep.append(i)
            else:duplicates.append({'detection':i,'duplicate_of':dup})
        active=[t for t in self.micro.values() if frame-t['frame']<=self.c['microtrack_max_gap']]
        costs=np.full((len(active),len(keep)),np.inf)
        evidence={}
        for i,t in enumerate(active):
            gap=frame-t['frame'];pred=t['box']+t['velocity']*gap;diag=max(np.linalg.norm(scale(t['box'])),1.)
            for j,d in enumerate(keep):
                distance=float(np.linalg.norm(center(dets[d])-center(pred))/diag)
                ratio=float(np.max(np.maximum(scale(dets[d])/scale(t['box']),scale(t['box'])/scale(dets[d]))))
                similarity=float(t['feature']@feats[d])
                if distance<=1.5 and ratio<=5:
                    costs[i,j]=.6*(1-iou(pred,dets[d]))+.25*min(distance,1)+.15*(1-similarity)
                evidence[i,j]={'appearance_similarity_to_last':similarity,'motion_distance_diagonals':distance,'size_ratio':ratio}
        local=joint_assignment(costs,.5)
        pair_map={j:i for i,j in local['best']['pairs']};margins={tuple(x['pair']):x['global_exclusion_gap'] for x in local['pair_certainty']}
        current=[]
        for j,d in enumerate(keep):
            if j in pair_map:
                i=pair_map[j];t=active[i];gap=frame-t['frame'];oldbox=t['box'].copy()
                t['velocity']=.5*t['velocity']+.5*(dets[d,:4]-oldbox)/gap
                t['local_gap']=margins[(i,j)];t['local_evidence']=evidence[i,j]
                t['consecutive']=t['consecutive']+1 if gap==1 else 1
                if gap!=1:
                    t['clear_frames']=[];t['clear_boxes']=[];t['clear_features']=[];t['needs_recovery']=True
                    if self.protect:
                        t['proposal']=t['identity'] if t['identity'] is not None else t['proposal'];t['identity']=None
            else:
                mid=self.next_micro;self.next_micro+=1
                t={'micro_id':mid,'velocity':np.zeros(4),'identity':None,'proposal':None,'consecutive':1,
                    'clear_frames':[],'clear_boxes':[],'clear_features':[],'needs_recovery':True,'local_gap':None,'local_evidence':{}}
                self.micro[mid]=t
            t.update(frame=frame,box=dets[d,:4].copy(),feature=feats[d].copy(),detection_index=d,
                confidence=float(dets[d,4]),geometric_clue=False,conflict=False,conflict_pairs=[])
            current.append(t)
        pair_clues=[]
        for ia,a in enumerate(current):
            for b in current[ia+1:]:
                ov=overlap(a['box'],b['box'])
                cd=np.linalg.norm(center(a['box'])-center(b['box']))/max((scale(a['box'])[0]+scale(b['box'])[0])/2,1)
                vertical=max(0,min(a['box'][3],b['box'][3])-max(a['box'][1],b['box'][1]))/max(min(scale(a['box'])[1],scale(b['box'])[1]),1)
                geometry=ov>=self.c['overlap_clue_min_fraction'] or (cd<self.c['center_clue_width_fraction'] and vertical>.5)
                if not geometry:continue
                ambiguous=any(t['local_gap'] is not None and t['local_gap']<self.c['local_assignment_margin'] for t in [a,b])
                changed=any(t['local_evidence'].get('appearance_similarity_to_last',1)<.6 for t in [a,b])
                conflict=ambiguous or (ov>.5 and changed)
                clue={'detections':[a['detection_index'],b['detection_index']],'overlap_fraction':float(ov),
                    'center_distance_widths':float(cd),'assignment_ambiguous':ambiguous,'appearance_changed':changed,
                    'identity_conflict':bool(conflict),'template_freeze':True}
                pair_clues.append(clue)
                for t in [a,b]:t['geometric_clue']=True;t['conflict']|=conflict;t['conflict_pairs'].append(clue)
        # Explicit initialization is one reviewed first-frame seed, never a later hint.
        if frame==0:
            selected=max(current,key=lambda t:iou(t['box'],self.seed))
            assert iou(selected['box'],self.seed)>=.5
            for t in current:
                if not t['geometric_clue'] or t is selected:
                    identity=self.create_identity(t,frame);t['needs_recovery']=False
                    if t is selected:self.target=identity
        for t in current:
            severe=t['local_evidence'].get('appearance_similarity_to_last',1)<.25
            identity_alarm=(t['conflict'] or severe or (t['local_gap'] is not None and t['local_gap']<self.c['local_assignment_margin'])) and self.protect
            if identity_alarm:
                t['proposal']=t['identity'] if t['identity'] is not None else t['proposal']
                t['identity']=None;t['needs_recovery']=True
            clean=not t['geometric_clue'] and not severe and (t['local_gap'] is None or t['local_gap']>=self.c['local_assignment_margin'])
            t['clean']=clean
            if clean:
                t['clear_frames'].append(frame);t['clear_boxes'].append(t['box'].tolist());t['clear_features'].append(t['feature'].copy())
            else:
                t['clear_frames']=[];t['clear_boxes']=[];t['clear_features']=[]
            # A reliable tracklet is split on any conflict clue, even if the numeric ID persists.
            mid=t['micro_id']
            if not clean:self.open_fragments.pop(mid,None)
            else:
                frag=self.open_fragments.get(mid)
                if frag is None or frag['frames'][-1]!=frame-1:
                    frag={'fragment_id':len(self.fragments),'micro_id':mid,'frames':[],'boxes':[],'features':[],'detections':[],
                        'contains_explicit_seed':bool(frame==0 and t['identity']==self.target)}
                    self.fragments.append(frag);self.open_fragments[mid]=frag
                frag['frames'].append(frame);frag['boxes'].append(t['box'].tolist());frag['features'].append(t['feature'].copy());frag['detections'].append(t['detection_index'])
            t['fragment_id']=self.open_fragments[mid]['fragment_id'] if mid in self.open_fragments else None
        occupied={t['identity'] for t in current if t['identity'] is not None}
        need=[t for t in current if t['identity'] is None and (len(t['clear_frames'])>=self.c['clear_anchor_frames'] or not self.protect)]
        identities=[(identity,a) for identity,a in self.identities.items() if identity not in occupied and frame-a['last_frame']<=self.c['max_reconnect_gap_frames']]
        recovery={'best':{'pairs':[]},'pair_certainty':[],'global_gap':None};recovery_evidence={}
        if need:
            rc=np.full((len(identities),len(need)),np.inf)
            for i,(identity,a) in enumerate(identities):
                for j,t in enumerate(need):
                    after={'frames':t['clear_frames'][-3:] or [frame], 'boxes':t['clear_boxes'][-3:] or [t['box'].tolist()],
                        'features':t['clear_features'][-3:] or [t['feature']]}
                    e=pair_cost(a,after,self.c);recovery_evidence[i,j]=e;rc[i,j]=e['cost']
            recovery=joint_assignment(rc,self.c['unmatched_cost_per_endpoint'])
            cert={tuple(p['pair']):p['global_exclusion_gap'] for p in recovery['pair_certainty']}
            matched=set()
            for i,j in recovery['best']['pairs']:
                t=need[j];identity=identities[i][0];e=recovery_evidence[i,j];gap=cert[(i,j)]
                t['proposal']=identity;t['recovery_cost']=e;t['recovery_global_gap']=gap
                if not self.protect or (gap is not None and gap>=self.c['joint_assignment_min_gap'] and e['appearance_similarity']>=self.c['joint_assignment_similarity_floor']):
                    t['identity']=identity;t['needs_recovery']=False;matched.add(j)
            # Truly unmatched clear tracklets get anonymous birth IDs; uncertain matches stay provisional.
            for j in recovery['best']['unmatched_after']:
                t=need[j]
                if t['proposal'] is None:self.create_identity(t,frame);t['needs_recovery']=False
        observations=[]
        for t in current:
            identity=t['identity']
            if identity is not None and (t['clean'] or not self.protect):self.append_anchor(identity,t,frame)
            status='confirmed' if identity is not None else 'provisional' if t['proposal'] is not None else 'unresolved'
            observations.append({'detection_index':t['detection_index'],'bbox_xyxy':t['box'].tolist(),'micro_id':t['micro_id'],
                'identity':identity,'proposed_identity':t['proposal'],'identity_status':status,'geometry_status':'observed',
                'geometric_conflict_clue':t['geometric_clue'],'identity_conflict_alarm':t['conflict'],'template_frozen':bool(self.protect and not t['clean']),
                'fragment_id':t['fragment_id'],'local_assignment_gap':t['local_gap'],'local_evidence':t['local_evidence'],
                'recovery_cost':t.get('recovery_cost'),'recovery_global_gap':t.get('recovery_global_gap'),
                'evidence_last_frame':frame,'future_frames_used':0})
        accepted=[o for o in observations if o['identity']==self.target]
        assert len(accepted)<=1
        provisional=[o for o in observations if o['proposed_identity']==self.target and o['identity_status']!='confirmed']
        chosen=accepted[0] if accepted else provisional[0] if len(provisional)==1 else None
        record={'frame':frame,'target_identity':self.target,'target_detection':accepted[0]['detection_index'] if accepted else None,
            'target_identity_status':'confirmed' if accepted else 'provisional' if chosen else 'unresolved',
            'target_geometry_status':'observed' if chosen else 'missing','target_candidate_detection':chosen['detection_index'] if chosen else None,
            'observations':observations,'conflict_pairs':pair_clues,'duplicates':duplicates,'all_raw_detection_count':len(dets),
            'identity_recovery_assignment':recovery,'identity_recovery_rows':[x[0] for x in identities],
            'identity_recovery_detection_columns':[t['detection_index'] for t in need],
            'evidence_last_frame':frame,'future_frames_used':0,'seconds':time.perf_counter()-begin}
        self.records.append(record)
        return record

def offline_link(tracker,c):
    begin=time.perf_counter()
    fragments=[f for f in tracker.fragments if len(f['frames'])>=c['clear_anchor_frames'] or f['contains_explicit_seed']]
    n=len(fragments);costs=np.full((n,n),np.inf);evidence={}
    for i,a in enumerate(fragments):
        for j,b in enumerate(fragments):
            gap=b['frames'][0]-a['frames'][-1]
            if not 1<=gap<=c['max_reconnect_gap_frames']:continue
            e=pair_cost(a,b,c)
            costs[i,j]=e['cost']+.001*gap;evidence[i,j]=e
    assignment=joint_assignment(costs,c['unmatched_cost_per_endpoint'])
    cert={tuple(p['pair']):p['global_exclusion_gap'] for p in assignment['pair_certainty']}
    accepted=[];incoming={};outgoing={};edge_details=[]
    for i,j in assignment['best']['pairs']:
        e=evidence[i,j];margin=cert[(i,j)]
        confirmed=margin is not None and margin>=c['joint_assignment_min_gap'] and e['appearance_similarity']>=c['joint_assignment_similarity_floor']
        edge_details.append({'before_fragment':fragments[i]['fragment_id'],'after_fragment':fragments[j]['fragment_id'],
            'global_exclusion_gap':margin,'confirmed':bool(confirmed),'cost_terms':e,
            'anchor_future_last_frame':fragments[j]['frames'][-1]})
        if confirmed:incoming[j]=i;outgoing[i]=j;accepted.append([i,j])
    seeds=[i for i,f in enumerate(fragments) if f['contains_explicit_seed']]
    target_nodes=set()
    for i in seeds:
        while i not in target_nodes:
            target_nodes.add(i)
            if i not in outgoing:break
            i=outgoing[i]
    target_by_frame={frame:det for i in target_nodes for frame,det in zip(fragments[i]['frames'],fragments[i]['detections'])}
    last=len(tracker.records)-1
    records=[]
    for r in tracker.records:
        frame=r['frame'];det=target_by_frame.get(frame)
        records.append({'frame':frame,'target_detection':det,'target_identity_status':'confirmed' if det is not None else 'unresolved',
            'target_geometry_status':'observed' if det is not None else 'missing','evidence_last_frame':last,
            'future_frames_used':max(last-frame,0),'all_candidates_preserved':True})
    serial=[{k:v for k,v in f.items() if k!='features'} for f in fragments]
    return {'records':records,'fragments':serial,'assignment':assignment,'edges':edge_details,
        'target_fragment_ids':[fragments[i]['fragment_id'] for i in sorted(target_nodes)],
        'global_evidence_last_frame':last,'seconds':time.perf_counter()-begin,
        'method':'offline partial one-to-one DAG path cover; reliable tracklet observations only, no interpolation'}
