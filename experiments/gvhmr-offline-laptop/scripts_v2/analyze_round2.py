from isolate_env import ROOT
import csv,hashlib,json,pathlib
import numpy as np
REPORT=ROOT/'round2-report';REPORT.mkdir(exist_ok=True)
specs=json.loads((ROOT/'scripts_v2/clips.json').read_text(encoding='utf-8'))
MPIDS=[11,12,13,14,15,16,23,24,25,26,27,28];GVIDS=[16,17,18,19,20,21,1,2,4,5,7,8]
NAMES=['left_shoulder','right_shoulder','left_elbow','right_elbow','left_wrist','right_wrist','left_hip','right_hip','left_knee','right_knee','left_ankle','right_ankle']
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.ndarray):return clean(x.tolist())
    if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
    if isinstance(x,np.integer):return int(x)
    if isinstance(x,np.bool_):return bool(x)
    return x
def dump(path,data):path.write_text(json.dumps(clean(data),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def hinge(p,ids):
    a,b,c=(p[:,i] for i in ids);u=a-b;v=c-b;den=np.linalg.norm(u,axis=1)*np.linalg.norm(v,axis=1)
    cosine=np.divide((u*v).sum(1),den,out=np.full_like(den,np.nan),where=den>1e-12)
    return 180-np.degrees(np.arccos(np.clip(cosine,-1,1)))
def range_stats(x):
    v=np.asarray(x);v=v[np.isfinite(v)]
    return {'finite_samples':len(v),'minimum':float(v.min()) if len(v) else None,'maximum':float(v.max()) if len(v) else None,'range':float(np.ptp(v)) if len(v) else None,'p05_p95_span':float(np.percentile(v,95)-np.percentile(v,5)) if len(v) else None}
all_summaries=[];all_events=[];stage_rows=[];source_rows=[]
for spec in specs:
    out=ROOT/'outputs'/spec['name'];timing=json.loads((out/'pipeline-timings.json').read_text(encoding='utf-8'));meta=json.loads((out/'input-manifest.json').read_text(encoding='utf-8'))
    mapping=list(csv.DictReader((out/'frame-map.csv').open(encoding='utf-8')));N=len(mapping)
    mp=np.load(out/'mediapipe_raw.npz');gv=np.load(out/'gvhmr_predictions.npz');m2=mp['normalized'];m3=mp['world'][:,:,:3]
    assert m2.shape==(N,33,5) and m3.shape==(N,33,3)
    assert hashlib.sha256((out/'input_30fps.mp4').read_bytes()).hexdigest()==meta['input_sha256']==timing['input_sha256_for_both']
    assert np.allclose(np.array([float(r['input_seconds']) for r in mapping]),np.arange(N)/30)
    assert np.allclose(gv['timestamps_s'],np.arange(N)/30)
    assert all(np.isfinite(gv[k]).all() for k in gv.files)
    methods={'mediapipe_raw':m3[:,MPIDS],'gvhmr_raw':gv['raw_incam_joints22'][:,GVIDS],'gvhmr_postprocessed':gv['official_postprocessed_incam_joints22'][:,GVIDS]}
    events=[];series={'input_frame':np.arange(N),'input_seconds':np.arange(N)/30,'source_frame':np.array([int(r['source_frame']) for r in mapping]),'source_seconds':np.array([float(r['source_seconds']) for r in mapping])}
    def event(frames,kind,method='input',joint=None,values=None,threshold=None):
        for f in frames:
            r=mapping[int(f)];events.append({'clip':spec['name'],'method':method,'kind':kind,'input_frame':int(f),'input_seconds':float(r['input_seconds']),'source_frame':int(r['source_frame']),'source_seconds':float(r['source_seconds']),'joint':joint,'value':float(values[f]) if values is not None else None,'threshold':threshold,'interpretation':'diagnostic/review flag; not a verified 3D error'})
    missing=~np.isfinite(m3).all(axis=(1,2));confidence=np.minimum(m2[:,:,3],m2[:,:,4]);low=(confidence[:,MPIDS]<.5).any(axis=1)&~missing
    event(np.flatnonzero(missing),'no_pose','mediapipe_raw');event(np.flatnonzero(low),'major_joint_confidence_below_0.5','mediapipe_raw')
    series['mediapipe_missing']=missing.astype(int);series['mediapipe_major_low_confidence']=low.astype(int)
    bmetrics=json.loads((out/'bbox-metrics.json').read_text());filled=bmetrics['selected_track_missing_frames'];observed=bmetrics['selected_track_observed_frames'];first,last=min(observed),max(observed)
    internal=[i for i in filled if first<i<last];edge=[i for i in filled if i<first or i>last]
    event(internal,'chosen_bbox_linearly_interpolated','gvhmr_preprocessing');event(edge,'chosen_bbox_endpoint_held','gvhmr_preprocessing')
    bboxfilled=np.zeros(N,int);bboxfilled[filled]=1;series['chosen_bbox_filled']=bboxfilled
    yolo=json.loads((out/'yolo_raw_detections.json').read_text());target=bmetrics['selected_track_id'];identity=np.full(N,np.nan)
    for i,dets in enumerate(yolo):
        chosen=next((d for d in dets if d['id']==target),None)
        if chosen and not missing[i] and np.all(confidence[i,[23,24]]>=.5):
            hip=m2[i,[23,24],:2].mean(0)*[meta['source_stream']['width'],meta['source_stream']['height']]
            x0,y0,x1,y1=chosen['bbx_xyxy'];margin=.05*np.array([x1-x0,y1-y0]);identity[i]=not (x0-margin[0]<=hip[0]<=x1+margin[0] and y0-margin[1]<=hip[1]<=y1+margin[1])
    series['mp_hip_outside_selected_yolo_bbox']=identity
    event(np.flatnonzero(identity==1),'person_selection_or_projection_disagreement_proxy','cross_method')
    stats={}
    for method,points in methods.items():
        rel=points-points[:,[6,7]].mean(1)[:,None,:]
        steps=np.vstack([np.full((1,12),np.nan),np.linalg.norm(np.diff(rel,axis=0),axis=2)])
        yaw=np.arctan2((points[:,7]-points[:,6])[:,2],(points[:,7]-points[:,6])[:,0])
        delta=np.abs(np.angle(np.exp(1j*np.diff(yaw))))*180/np.pi;yawsteps=np.r_[np.nan,delta]
        maxstep=np.full(N,np.nan)
        validrows=np.isfinite(steps).any(1);maxstep[validrows]=np.nanmax(steps[validrows],axis=1)
        series[method+'_max_joint_step_m']=maxstep;series[method+'_hip_axis_step_deg']=yawsteps
        for j,name in enumerate(NAMES):event(np.flatnonzero(steps[:,j]>.2),'hip_centered_joint_step_over_0.2m',method,name,steps[:,j],.2)
        event(np.flatnonzero(yawsteps>45),'hip_axis_step_over_45deg',method,values=yawsteps,threshold=45)
        joint_stats={name:{'step_m':range_stats(steps[:,j]),'p95_step_m':float(np.nanpercentile(steps[:,j],95)) if np.isfinite(steps[:,j]).any() else None,'xyz_p05_p95_span_m':[range_stats(rel[:,j,k])['p05_p95_span'] for k in range(3)]} for j,name in enumerate(NAMES)}
        hinges={name:hinge(points,ids) for name,ids in {'left_knee':(6,8,10),'right_knee':(7,9,11),'left_elbow':(0,2,4),'right_elbow':(1,3,5)}.items()}
        for name,values in hinges.items():series[method+'_'+name+'_flexion_deg']=values
        flat=steps[np.isfinite(steps)];stats[method]={'common12_max_step_m':float(flat.max()) if len(flat) else None,'common12_p95_step_m':float(np.percentile(flat,95)) if len(flat) else None,'joint_transition_samples':len(flat),'frames_any_joint_step_over_0.2m':int((maxstep>.2).sum()),'hip_axis_steps_over_45deg':int((yawsteps>45).sum()),'joint_stats':joint_stats,'hinge_flexion_degrees':{k:range_stats(v) for k,v in hinges.items()}}
    pairs=json.loads((out/'vo-pair-audit.json').read_text()) if (out/'vo-pair-audit.json').exists() else []
    failed_pairs=[p for p in pairs if p['status']=='failed']
    for p in failed_pairs:event([p['input_frames'][1]],'simplevo_pair_failure_static_fallback','camera')
    for stage in timing['stage_process_timings']:
        extra=json.loads((out/(stage['stage']+'-metrics.json')).read_text())
        stage_rows.append({'clip':spec['name'],'stage':stage['stage'],'process_wall_s':stage['wall_seconds'],'sampled_peak_tree_rss_bytes':stage['peak_process_tree_rss_bytes_sampled'],'whole_device_peak_mib':stage['gpu_peak_whole_device_mib_sampled'],'torch_peak_allocated_bytes':extra.get('gpu_peak_allocated_bytes',0),'torch_peak_reserved_bytes':extra.get('gpu_peak_reserved_bytes',0),'exit_code':stage['exit_code']})
    summary={'clip':spec['name'],'category':spec['category'],'frames':N,'duration_seconds':N/30,'input_sha256':meta['input_sha256'],'source_page':spec['source_page'],'source_range_normalized_seconds':[spec['start'],spec['start']+spec['duration']],'source_fps':meta['source_fps'],'source_note':spec['source_note'],'mediapipe_missing_frames':int(missing.sum()),'mediapipe_missing_rate':float(missing.mean()),'mediapipe_low_confidence_frames':int(low.sum()),'mediapipe_low_confidence_rate_all_frames':float(low.mean()),'selected_bbox_internal_interpolation_frames':len(internal),'selected_bbox_endpoint_hold_frames':len(edge),'selected_bbox_filled_rate':len(filled)/N,'chosen_yolo_track_id':target,'person_selection_proxy_flag_frames':int((identity==1).sum()),'person_selection_proxy_eligible_frames':int(np.isfinite(identity).sum()),'camera_mode':timing['camera_mode'],'camera_warning':timing['camera_warning'],'camera_failed_pairs':failed_pairs,'mediapipe_e2e_s':timing['mediapipe_e2e_seconds'],'gvhmr_e2e_raw_and_post_s':timing['gvhmr_e2e_raw_and_official_postprocess_seconds'],'gvhmr_raw_tensor_ready_s':timing['gvhmr_e2e_raw_tensor_ready_seconds'],'mediapipe_offline_frames_per_s':N/timing['mediapipe_e2e_seconds'],'gvhmr_offline_frames_per_s':N/timing['gvhmr_e2e_raw_and_official_postprocess_seconds'],'peak_mediapipe_rss_bytes':timing['stage_process_timings'][0]['peak_process_tree_rss_bytes_sampled'],'peak_gvhmr_rss_bytes':max(r['peak_process_tree_rss_bytes_sampled'] for r in timing['stage_process_timings'][1:]),'methods':stats,'review_events':len(events),'accuracy_evaluated':False}
    dump(out/'extended-diagnostics.json',summary)
    with (out/'frame-diagnostics.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(series);w.writerows([[clean(v[i]) for v in series.values()] for i in range(N)])
    with (out/'review-events.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['clip','method','kind','input_frame','input_seconds','source_frame','source_seconds','joint','value','threshold','interpretation']);w.writeheader();w.writerows(events)
    all_summaries.append(summary);all_events+=events;source_rows.append(meta)
dump(REPORT/'metrics-full.json',all_summaries);dump(REPORT/'sources-and-sampling.json',source_rows)
for filename,rows in [('stage-timings.csv',stage_rows),('review-events.csv',all_events)]:
    if rows:
        with (REPORT/filename).open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
dump(REPORT/'validation.json',{'clips':len(all_summaries),'total_input_frames':sum(x['frames'] for x in all_summaries),'source_files':len({s['filename'] for s in specs}),'paired_input_hashes_verified':True,'timestamps_and_lengths_verified':True,'gvhmr_all_arrays_finite':True,'ground_truth_available':False,'thresholds':{'joint_jump_review_m_per_30fps_frame':.2,'hip_axis_review_deg_per_frame':45,'major_joint_min_visibility_presence':.5},'interpretation':'Flags identify review locations, not accuracy errors. Faster or smoother outputs are not proof of better 3D reconstruction. Different-person cases invalidate pointwise cross-method interpretation.'})
print(json.dumps([{'clip':s['clip'],'frames':s['frames'],'mp_s':round(s['mediapipe_e2e_s'],2),'gv_s':round(s['gvhmr_e2e_raw_and_post_s'],2),'mp_missing':s['mediapipe_missing_frames'],'bbox_fill':round(s['selected_bbox_filled_rate'],3),'camera':s['camera_mode']} for s in all_summaries]),flush=True)
