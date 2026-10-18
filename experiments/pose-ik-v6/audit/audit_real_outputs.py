import json,sys,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from opensim_ik import KEYS,xyz
out={}
for name in ['fast','slow','turn']:
 d=json.loads((ROOT/f'metric-reference/raw/v52-{name}-release.json').read_text());original=[r for r in d['inferences'] if r.get('disposition')=='strict_paired'];rs=original[30:];os=json.loads((ROOT/f'output/offline-{name}/constrained.json').read_text())
 assert len(rs)==len(os)
 assert all(all(r[k]==o[k] for k in ['frame_id','epoch','clip','source_pts_ms']) for r,o in zip(rs,os))
 summary={'aligned_frames':len(rs),'solver_successes':sum(o['status']=='fit' for o in os),'non_fit_frames':[{'frame_id':r['frame_id'],'epoch':r['epoch'],'pts':r['source_pts_ms'],'status':o['status'],'error':o.get('error')} for r,o in zip(rs,os) if o['status']!='fit'],'output_states':sorted(set(s for o in os for s in o['states'])),'input_states_altered_count':sum(r['filtered_observation']['states']!=o['observation_states'] for r,o in zip(rs,os))}
 for cohort in ['full','first_pass']:
  sp=[[],[]];acc=[[],[]];res=[];last=None;lastv=None;count=0
  for idx,(r,o) in enumerate(zip(rs,os)):
   if cohort=='first_pass' and r.get('virtual_loop',0)!=0:continue
   if o['status']!='fit':last=lastv=None;continue
   p=xyz(r['world_landmarks'])[KEYS];q=xyz(o['world'])[KEYS];mask=np.array([r['filtered_observation']['states'][k]=='measured' for k in KEYS]);res.extend(np.linalg.norm(p-q,axis=1)[mask]);t=r['source_pts_ms']/1000;context=(r['epoch'],r['clip']);count+=1
   if last is not None:
    lt,lp,lq,lmask,lcontext,lidx=last;dt=t-lt
    if context==lcontext and lidx+1==idx and 0<dt<=.15:
     v0=(p-lp)/dt;v1=(q-lq)/dt;m=mask&lmask
     for i,v in enumerate([v0,v1]):sp[i].extend(np.linalg.norm(v[m],axis=1))
     if lastv is not None:
      a,b,lm,ldt=lastv;vm=m&lm
      for i,(v,pv) in enumerate([(v0,a),(v1,b)]):acc[i].extend(np.linalg.norm(((v-pv)/((dt+ldt)/2))[vm],axis=1))
     lastv=(v0,v1,m,dt)
    else:lastv=None
   last=(t,p,q,mask,context,idx)
  summary[cohort]={'frames':count,'compared_joint_transitions':len(sp[0]),'raw_speed_over6':sum(v>6 for v in sp[0]),'fit_speed_over6':sum(v>6 for v in sp[1]),'raw_speed_p95':float(np.percentile(sp[0],95)),'fit_speed_p95':float(np.percentile(sp[1],95)),'raw_accel_p95':float(np.percentile(acc[0],95)),'fit_accel_p95':float(np.percentile(acc[1],95)),'residual_p95_m':float(np.percentile(res,95))}
 # Weak-perspective diagnostic: one scalar fitted on 30 calibration frames, hip-centered xy. Same fixed map used for raw and fit. This is not a calibrated physical camera.
 xx=[];yy=[]
 for r in original[:30]:
  p=np.array([[a['x'],a['y']] for a in r['world_landmarks']]);v=np.array([[a['x'],a['y']] for a in r['landmarks']]);p-=p[[23,24]].mean(0);v-=v[[23,24]].mean(0)
  w=np.array([r['filtered_observation']['states'][k]=='measured' for k in KEYS]);xx.extend(p[KEYS][w]);yy.extend(v[KEYS][w])
 xx=np.array(xx);yy=np.array(yy);scale=np.sum(xx*yy,axis=0)/np.sum(xx**2,axis=0)
 re=[];fe=[]
 for r,o in zip(rs,os):
  if o['status']!='fit':continue
  p=np.array([[a['x'],a['y']] for a in r['world_landmarks']]);v=np.array([[a['x'],a['y']] for a in r['landmarks']]);q=np.array([[o['world'][k]['x'],o['world'][k]['y']] for k in KEYS]);anchor=p[[23,24]].mean(0);vanchor=v[[23,24]].mean(0)
  w=np.array([r['filtered_observation']['states'][k]=='measured' for k in KEYS]);size=np.array([r['inference_input_width'],r['inference_input_height']]);target=v[KEYS]
  re.extend(np.linalg.norm((((p[KEYS]-anchor)*scale+vanchor)-target)*size,axis=1)[w]);fe.extend(np.linalg.norm((((q-anchor)*scale+vanchor)-target)*size,axis=1)[w])
 summary['2d_consistency_proxy']={'method':'Fixed per-axis weak-perspective scale from first30 raw frames, per-frame raw hip root anchor; same mapping for raw and fit. Camera uncalibrated and scale fit favors raw; not ground truth or reprojection accuracy.','xy_scale':scale.tolist(),'raw_p50_pixels':float(np.median(re)),'fit_p50_pixels':float(np.median(fe)),'raw_p95_pixels':float(np.percentile(re,95)),'fit_p95_pixels':float(np.percentile(fe,95))}
 out[name]=summary
(ROOT/'audit/real_output_audit.json').write_text(json.dumps(out,indent=2,default=lambda x:x.item()));print(json.dumps(out,indent=2,default=lambda x:x.item()))
