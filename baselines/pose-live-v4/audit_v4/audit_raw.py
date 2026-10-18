#!/usr/bin/env python3
"""Independent v4 exported-log audit. No synthetic poses, rendering or app edits.
Usage: python3 audit_v4/audit_raw.py results/run.json --out audit_v4/run.audit.json
This audits software submissions and sampled prediction events, not display photons.
"""
import argparse, collections, hashlib, json, math
from pathlib import Path
KEY=[11,12,13,14,15,16,23,24,25,26,27,28]
def finite(v): return isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v)
def dist(xs):
 xs=sorted(x for x in xs if finite(x))
 return {'n':len(xs),'p50':xs[math.ceil(len(xs)*.5)-1] if xs else None,'p95':xs[math.ceil(len(xs)*.95)-1] if xs else None,'max':xs[-1] if xs else None}
def ident(x):return (x.get('epoch'),x.get('frame_id'))
def visibility_age(d,start,end,im):
 """Continuous image-age accounting includes held paired images and reset blanks."""
 timeline=[]
 for r in d.get('renders',[]):
  a=im.get((r.get('epoch'),r.get('video_frame_id')))
  if a:timeline.append((r['wall_ms'],'pair',a))
 for e in d.get('events',[]):
  if e.get('type') in ['reset','replay_started']:timeline.append((e['wall_ms'],'blank',None))
 timeline.sort(key=lambda t:t[0]);last=start;state=None;intervals=[];blank=0
 for wall,kind,value in timeline+[(end,'end',None)]:
  if wall>end:continue
  if wall>start:
   length=wall-last
   if length>0:
    if state is None:blank+=length
    else:intervals.append((last-state['scheduled_release_ms'],wall-state['scheduled_release_ms'],length))
   last=wall
  if kind!='end':state=value if kind=='pair' else None
 visible=sum(x[2] for x in intervals)
 def percentile(q):
  if not intervals:return None
  lo=min(x[0] for x in intervals);hi=max(x[1] for x in intervals);target=q*visible
  for _ in range(80):
   mid=(lo+hi)/2;mass=sum(max(0,min(b,mid)-a) for a,b,_ in intervals)
   if mass<target:lo=mid
   else:hi=mid
  return hi
 return {'paired_image_visible_ms':visible,'blank_ms':blank,'p50_ms':percentile(.5),'p95_ms':percentile(.95),'max_ms':max((x[1] for x in intervals),default=None),'mean_ms':sum((a+b)/2*w for a,b,w in intervals)/visible if visible else None,'age_above_200ms_ms':sum(max(0,b-max(200,a)) for a,b,_ in intervals),'note':'Age grows while exact paired snapshot is held; resets clear the image. Not physical photon latency.'}
def audit(d):
 errors=[];notes=[]
 def check(ok,code,detail):
  if not ok:errors.append({'code':code,'detail':str(detail)})
 obs=d.get('observation',{});start,end=obs.get('start_ms'),obs.get('end_ms')
 check(finite(start) and finite(end) and end>start,'observation_window',obs)
 if not(finite(start) and finite(end) and end>start): return {'pass':False,'errors':errors}
 inside=lambda t:finite(t) and start<=t<=end
 duration=(end-start)/1000
 frames=d.get('frames',[]);infs=d.get('inferences',[]);renders=d.get('renders',[]);events=d.get('events',[]);replays=d.get('replay_renders',[])
 check(bool(frames and infs and renders),'nonempty_evidence',f'frames={len(frames)}, infs={len(infs)}, renders={len(renders)}')
 fm={ident(x):x for x in frames};im={ident(x):x for x in infs};sm={x.get('segment_id'):x for x in d.get('segments',[])}
 check(len(fm)==len(frames),'unique_frames',len(frames)-len(fm));check(len(im)==len(infs),'unique_inferences',len(infs)-len(im))
 for r in frames:
  s=sm.get(r.get('segment_id'))
  check(bool(s),'segment_exists',ident(r))
  if s:
   check(s.get('playback_rate')==1,'original_speed',s)
   expected=s['wall_anchor_ms']+(r['source_pts_ms']-s['source_anchor_ms'])/s['playback_rate']
   check(abs(r['scheduled_release_ms']-expected)<.01,'original_source_clock',ident(r))
 for r in infs:
  k=ident(r);f=fm.get(k);check(bool(f),'inference_source_frame',k)
  if f:
   for field in ['source_pts_ms','scheduled_release_ms','clip','segment_id']:check(r.get(field)==f.get(field),'inference_identity_'+field,k)
  times=[r.get(t) for t in ['scheduled_release_ms','dispatch_ms','processing_start_ms','processing_end_ms','result_received_ms']]
  check(all(finite(t) for t in times),'phase_times_finite',k)
  if all(finite(t) for t in times):
   check(all(a<=b+.5 for a,b in zip(times,times[1:])),'causal_phase_order',k)
   check(abs(r['inference_ms']-(times[3]-times[2]))<.01,'inference_duration',k)
  filt=r.get('filtered_observation')
  if filt:
   for field in ['frame_id','epoch','clip','source_pts_ms']:check(filt.get(field)==r.get(field),'filtered_identity_'+field,k)
   for field in ['states','reasons','world','landmarks']:check(len(filt.get(field,[]))==33,'filtered_33_'+field,k)
   if len(filt.get('states',[]))==33:
    for i,state in enumerate(filt['states']):
     check(state in ['measured','uncertain','lost'],'live_state_not_estimate',(k,i,state))
     for filtered,raw in [('world','world_landmarks'),('landmarks','landmarks')]:
      p=filt[filtered][i]
      if state=='measured':
       q=r[raw][i];check(p is not None and all(p.get(a)==q.get(a) for a in ['x','y','z']),'measured_coordinates_equal_raw',(k,i,filtered))
      else:check(p is None,'unsupported_joint_hidden',(k,i,filtered))
     if state=='measured':
      q=r['landmarks'][i];check(min(q.get('visibility',0),q.get('presence',0))>=.5,'measured_confidence_supported',(k,i))
     if i in r.get('synthetic_missing_joints',[]):check(filt['reasons'][i]=='synthetic_missing_mask' and state=='lost','synthetic_mask_labeled',(k,i))
    valid=all(filt['states'][i]=='measured' for i in KEY)
    check(filt.get('valid')==valid and r.get('filtered_valid')==valid,'strict_valid_definition',k)
  if r.get('render_submit_ms') is not None:
   check(r.get('disposition')=='strict_paired','paired_disposition',k)
   check(abs(r['total_delay_ms']-(r['render_submit_ms']-r['scheduled_release_ms']))<.01,'total_includes_release_to_submit',k)
   for field in ['display_frame_id','observed_2d_frame_id','observed_3d_frame_id']:check(r.get(field)==r['frame_id'],'paired_result_'+field,k)
   check(r.get('display_pts_ms')==r['source_pts_ms']==r.get('pose_pts_ms'),'paired_result_pts',k)
 paired_ids=[]
 for r in renders:
  k=(r.get('epoch'),r.get('video_frame_id'));paired_ids.append(k);a=im.get(k)
  check(bool(a),'render_inference_exists',k)
  check(r.get('video_frame_id')==r.get('observed_2d_frame_id')==r.get('observed_3d_frame_id'),'strict_video_2d_3d_frame_identity',k)
  check(r.get('display_pts_ms')==r.get('pose_pts_ms') and r.get('sync_error_ms')==0,'strict_pair_pts',k)
  if a:
   check(r.get('shown_joint_states')==a['filtered_observation']['states'],'live_render_is_observation',k)
   check(r.get('new_observation') is True and r.get('new_valid_pose')==a['filtered_valid'],'counts_observations_only',k)
   check(abs(r['wall_ms']-a['render_submit_ms'])<.01,'render_submission_timestamp',k)
 check(len(set(paired_ids))==len(paired_ids),'unique_new_observations',len(paired_ids)-len(set(paired_ids)))
 predicted=0
 for e in events:
  if e.get('type')!='prediction_preview':continue
  check(e.get('new_valid_pose') is False,'prediction_not_detection',e.get('wall_ms'))
  target=e.get('target_source_pts_ms');states=e.get('states',[]);bases=e.get('basis',[])
  check(len(states)==33 and len(bases)==33,'prediction_has_33_states',e.get('wall_ms'))
  for i,(state,base) in enumerate(zip(states,bases)):
   if state=='lost':check(base is None,'lost_prediction_has_no_basis',i);continue
   predicted+=1;check(state=='predicted' and isinstance(base,dict),'estimate_labeled',(i,state))
   if not isinstance(base,dict):continue
   age=target-base['last_source_pts_ms'];check(0<=age<=150+.00001,'prediction_bounded_causal',(i,age))
   check(abs(age-base['horizon_ms'])<.01,'prediction_age_arithmetic',i)
   check(base['previous_source_pts_ms']<base['last_source_pts_ms']<=target,'past_only_prediction_basis',i)
   a=im.get((e['epoch'],base['last_frame_id']));check(bool(a),'prediction_last_basis_same_epoch',(e['epoch'],base['last_frame_id']))
   if a:
    check(a['source_pts_ms']==base['last_source_pts_ms'],'prediction_basis_pts',i)
    check(a['filtered_observation']['states'][i]=='measured','prediction_basis_was_measured',i)
    check(a['render_submit_ms']<=e['wall_ms']+.5,'prediction_does_not_access_later_result',i)
 repaired=0;unrepaired_toggles=0
 for r in replays:
  k=ident(r);a=im.get(k);check(bool(a),'replay_record_exists',k)
  if not a:continue
  states=r.get('shown_joint_states',[]);repairs=r.get('repairs',[])
  if not r.get('repair_enabled'):
   unrepaired_toggles+=1;check(states==a['filtered_observation']['states'] and not repairs,'original_toggle_preserves_observations',k)
  for repair in repairs:
   repaired+=1;i=repair['joint'];l=im.get((r['epoch'],repair['left_frame_id']));q=im.get((r['epoch'],repair['right_frame_id']))
   check(states[i]=='repaired','replay_estimate_labeled',(k,i))
   check(bool(l and q),'replay_endpoint_identity',(k,i))
   if not(l and q):continue
   check(l['clip']==a['clip']==q['clip'],'replay_endpoints_same_clip',(k,i))
   gap=q['source_pts_ms']-l['source_pts_ms'];check(0<gap<=350+.00001,'replay_short_bracket_only',(k,i,gap))
   check(l['source_pts_ms']<a['source_pts_ms']<q['source_pts_ms'],'replay_actually_bracketed',(k,i))
   check(abs(gap-repair['bracket_ms'])<.01,'replay_bracket_arithmetic',(k,i))
   check(l['filtered_observation']['states'][i]=='measured' and q['filtered_observation']['states'][i]=='measured','replay_measured_endpoints',(k,i))
 raw_window=[r for r in infs if inside(r.get('result_received_ms'))]
 pairs_window=[r for r in infs if inside(r.get('render_submit_ms'))]
 notes.extend(['Frame pairing uses exact IDs and stored bitmap code path; JSON alone cannot establish pixel identity.','Prediction events are sampled (~200 ms); 150 ms expiry between samples is additionally covered by pure-policy tests and code review.','Raw-model-valid FPS uses v3 average confidence definition; strict-valid FPS uses all 12 major joints supported and is not directly comparable.','This is sparse paired observation playback; zero pair skew does not prove low total latency or native source cadence.'])
 return {'pass':not errors,'errors':errors,'observation_seconds':duration,'counts':{'source_callbacks':len([r for r in frames if inside(r.get('callback_ms'))]),'completed_inferences':len(raw_window),'paired_observations':len(pairs_window),'raw_valid_paired':sum(r.get('valid') is True for r in pairs_window),'strict_valid_paired':sum(r.get('filtered_valid') is True for r in pairs_window),'prediction_joint_samples':predicted,'repaired_joint_displays':repaired,'original_toggle_displays':unrepaired_toggles},'fps':{'inference':len(raw_window)/duration,'paired':len(pairs_window)/duration,'raw_valid_paired':sum(r.get('valid') is True for r in pairs_window)/duration,'strict_valid_paired':sum(r.get('filtered_valid') is True for r in pairs_window)/duration},'time_weighted_visible_image_age':visibility_age(d,start,end,im),'paired_update_gap_ms':dist(b['render_submit_ms']-a['render_submit_ms'] for a,b in zip(pairs_window,pairs_window[1:])), 'total_delay_ms':dist(r['total_delay_ms'] for r in pairs_window),'inference_ms':dist(r['inference_ms'] for r in raw_window),'joint_state_counts':dict(collections.Counter(s for r in pairs_window for s in r['filtered_observation']['states'])),'synthetic_fault_injection':d.get('metadata',{}).get('synthetic_fault_injection'),'notes':notes}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('log');p.add_argument('--out');args=p.parse_args();source=Path(args.log);result=audit(json.loads(source.read_text()));result['raw_log']=str(source);result['raw_sha256']=hashlib.sha256(source.read_bytes()).hexdigest();out=json.dumps(result,indent=2)+'\n'
 if args.out:Path(args.out).write_text(out)
 print(out)
 raise SystemExit(0 if result['pass'] else 1)
