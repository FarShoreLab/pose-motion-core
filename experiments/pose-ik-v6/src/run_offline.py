import argparse,csv,json,time,hashlib
from pathlib import Path
import numpy as np
from opensim_ik import HumanIK,fit_record,calibrate,KEYS,xyz

def perc(v,p):
    a=np.array(v,float);a=a[np.isfinite(a)];return float(np.percentile(a,p)) if len(a) else None

def analyze(records,outputs):
    rows=[]; raw_steps=[];fit_steps=[]; raw_acc=[];fit_acc=[];res=[];ms=[]; raws=[];fits=[];msk=[];last=None;lastv=None
    for r,o in zip(records,outputs):
        if o['status']!='fit':
            last=None;lastv=None;continue
        rp=xyz(r['world_landmarks'])[KEYS];fp=xyz(o['world'])[KEYS];eligible=np.array([o['observation_states'][i]=='measured' for i in KEYS]);weights=np.array([o['weights'][str(i)] for i in KEYS]);t=r.get('source_unwrapped_pts_ms',r['source_pts_ms'])/1000
        raws.append(rp);fits.append(fp);msk.append(eligible);ms.append(o['solver_ms']);res.extend(np.linalg.norm(rp-fp,axis=1)[eligible])
        if last:
            dt=t-last[0];valid=eligible&last[3]
            if 0<dt<=.15 and last[4]==(r.get('clip'),r.get('epoch')):
                rv=(rp-last[1])/dt;fv=(fp-last[2])/dt;raw_steps.extend(np.linalg.norm(rv[valid],axis=1));fit_steps.extend(np.linalg.norm(fv[valid],axis=1))
                if lastv is not None:
                    okay=valid&lastv[2];raw_acc.extend(np.linalg.norm((rv-lastv[0])[okay]/dt,axis=1));fit_acc.extend(np.linalg.norm((fv-lastv[1])[okay]/dt,axis=1))
                lastv=(rv,fv,valid)
            else:lastv=None
        last=(t,rp,fp,eligible,(r.get('clip'),r.get('epoch')))
        rows.append({'frame_id':r['frame_id'],'pts_ms':r['source_pts_ms'],'source_unwrapped_pts_ms':t*1000,'solver_ms':o['solver_ms'],'observed_residual_p50_m':perc(np.linalg.norm(rp-fp,axis=1)[eligible],50),'observed_residual_max_m':float(np.max(np.linalg.norm(rp-fp,axis=1)[eligible])) if any(eligible) else None,'observed_count':int(sum(eligible)),'inferred_count':sum(s=='inferred_unobserved' for s in o['states']),'max_bound_violation_rad':o['max_bound_violation_rad']})
    amplitudes={}
    R=np.array(raws);F=np.array(fits);M=np.array(msk)
    for j,k in enumerate(KEYS):
        good=M[:,j];r=R[good,j];f=F[good,j]
        if len(r)>5:
            ra=float(np.linalg.norm(np.percentile(r,95,axis=0)-np.percentile(r,5,axis=0)));fa=float(np.linalg.norm(np.percentile(f,95,axis=0)-np.percentile(f,5,axis=0)));amplitudes[str(k)]={'raw_p05_p95_extent_m':ra,'fit_p05_p95_extent_m':fa,'ratio':fa/ra if ra>.001 else None}
    return {'frames':len(records),'fit_frames':len(rows),'unfitted_frames':sum(o['status']!='fit' for o in outputs),'solver_errors':sum(o['status']=='solver_error' for o in outputs),'no_pose_frames':sum(o['status']=='no_pose' for o in outputs),'no_observation_frames':sum(o['status']=='no_observation' for o in outputs),'solver_ms_p50':perc(ms,50),'solver_ms_p95':perc(ms,95),'residual_measured_m_p50':perc(res,50),'residual_measured_m_p95':perc(res,95),'raw_speed_m_s_p95':perc(raw_steps,95),'fit_speed_m_s_p95':perc(fit_steps,95),'raw_speed_over6_count':int(sum(s>6 for s in raw_steps)),'fit_speed_over6_count':int(sum(s>6 for s in fit_steps)),'compared_joint_transitions':len(raw_steps),'raw_accel_p95':perc(raw_acc,95),'fit_accel_p95':perc(fit_acc,95),'amplitude':amplitudes,'max_bound_violation_rad':max((o.get('max_bound_violation_rad',0) for o in outputs),default=0)},rows

def main():
    ap=argparse.ArgumentParser();ap.add_argument('input');ap.add_argument('--limit',type=int,default=0);ap.add_argument('--out',required=True);ap.add_argument('--temporal',type=float,default=0);args=ap.parse_args()
    source=Path(args.input);data=json.loads(source.read_text());rs=[r for r in data['inferences'] if r.get('disposition')=='strict_paired'];lengths,cal=calibrate(rs)
    rs=rs[30:];rs=rs[:args.limit] if args.limit else rs;out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    m=HumanIK(lengths,temporal_weight=args.temporal);m.export(out/'model.osim');outputs=[]
    for i,r in enumerate(rs):
        o=fit_record(m,r);o.update({k:r.get(k) for k in ['frame_id','epoch','clip','source_pts_ms','source_unwrapped_pts_ms','virtual_loop','backend_input_sha256']});outputs.append(o)
        if i%200==0:print(i,o['solver_ms'],flush=True)
    summary,rows=analyze(rs,outputs)
    primary=[i for i,r in enumerate(rs) if r.get('virtual_loop',0)==0];summary['first_unique_source_pass'],_=analyze([rs[i] for i in primary],[outputs[i] for i in primary]);summary.update({'source':str(source.resolve()),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'calibration':cal,'lengths':lengths,'calibration_frames_excluded':30,'temporal_weight':args.temporal,'coordinate_specs':m.coord_specs,'note':'Offline paired raw sequence, not realtime performance. MP world hip centered; uncalibrated. Repeat loops are not independent motion samples.'})
    (out/'summary.json').write_text(json.dumps(summary,indent=2));(out/'constrained.json').write_text(json.dumps(outputs,separators=(',',':'),allow_nan=False))
    with (out/'frames.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps({k:v for k,v in summary.items() if k not in ['amplitude','first_unique_source_pass','coordinate_specs','calibration']},indent=2))
if __name__=='__main__':main()
