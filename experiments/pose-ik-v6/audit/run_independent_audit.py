"""Independent known-truth controls; never modifies implementation sources."""
import sys,json,hashlib,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'audit/snapshot'))
from opensim_ik import HumanIK,KEYS,fit_record
OUT=ROOT/'audit'
FPS=30;N=240;SEED=20261014

def motion():
    gen=HumanIK(); ids={c.getName():i for i,c in enumerate(gen.coords)}
    qs=[];truth=[]
    for f in range(N):
        t=f/FPS;q=gen.initial_q.copy()
        # Start exactly at initial configuration, then smooth varied true motion.
        envelope=min(1,f/20)
        for name,v in {
            'root_0':.15*np.sin(2*np.pi*.3*t),
            'root_1':2*np.pi*max(0,t-1)/6,
            'root_2':.1*np.sin(2*np.pi*.2*t),
            'root_3':.12*np.sin(2*np.pi*.4*t),
            'root_4':.06*np.sin(2*np.pi*.6*t),
            'root_5':.07*np.sin(2*np.pi*.3*t),
            'lumbar_0':.25*np.sin(2*np.pi*.5*t),
            'lumbar_1':.2*np.sin(2*np.pi*.3*t),
            'lumbar_2':.12*np.sin(2*np.pi*.2*t),
            'shoulder_l_0':-.7*(1-np.cos(2*np.pi*.6*t)),
            'shoulder_r_0':-.7*(1-np.cos(2*np.pi*.5*t)),
            'shoulder_l_2':.8*(1-np.cos(2*np.pi*.8*t)),
            'shoulder_r_2':-.8*(1-np.cos(2*np.pi*.8*t)),
            'elbow_l_0':.9*(1-np.cos(2*np.pi*1.2*t)),
            'elbow_r_0':.9*(1-np.cos(2*np.pi*1.0*t)),
            'hip_l_0':-.6*(1-np.cos(2*np.pi*.7*t)),
            'hip_r_0':-.6*(1-np.cos(2*np.pi*.7*t+.1)),
            'hip_l_2':.2*np.sin(2*np.pi*.4*t),
            'hip_r_2':-.2*np.sin(2*np.pi*.4*t),
            'knee_l_0':.8*(1-np.cos(2*np.pi*.7*t)),
            'knee_r_0':.8*(1-np.cos(2*np.pi*.7*t+.1)),
        }.items(): q[ids[name]]=(1-envelope)*q[ids[name]]+envelope*v
        qs.append(q.copy());truth.append(gen.fk(q))
    return gen,np.array(qs),np.array(truth)

def solve(obs,weights=None):
    model=HumanIK(); rows=[]; out=[]
    for f,p in enumerate(obs):
        r=model.fit(p,None if weights is None else weights[f],f/FPS)
        out.append(r['points']);rows.append({k:r[k] for k in ['ms','status','error','max_bound_violation_rad']})
    return np.array(out), rows

def metrics(output,truth):
    e=np.linalg.norm(output-truth,axis=-1)
    amp=np.percentile(output,95,axis=0)-np.percentile(output,5,axis=0)
    truthamp=np.percentile(truth,95,axis=0)-np.percentile(truth,5,axis=0)
    active=truthamp>.1;ratio=amp[active]/truthamp[active]
    # Global lag minimizing error. Frozen output has no meaningful lag.
    if np.max(np.std(output,axis=0))<1e-8: lag=None
    else:
        scores={}
        for k in range(-5,6):
            a=output[max(0,k):min(N,N+k)];b=truth[max(0,-k):min(N,N-k)]
            scores[k]=float(np.mean((a-b)**2))
        lag=min(scores,key=scores.get)
    return {'mpjpe_m':float(e.mean()),'p95_error_m':float(np.percentile(e,95)), 'max_error_m':float(e.max()),'amplitude_ratio_min':float(ratio.min()),'amplitude_ratio_max':float(ratio.max()),'amplitude_ratio_median':float(np.median(ratio)),'lag_frames':lag}

gen,qs,truth=motion();tol=.01*np.median([gen.lengths[k] for k in ['upperarm_l','upperarm_r','forearm_l','forearm_r','thigh_l','thigh_r','shank_l','shank_r']])
clean,cleanrows=solve(truth)
frozen=np.repeat(clean[:1],N,axis=0)
rng=np.random.default_rng(SEED);noise=rng.normal(0,.02,truth.shape);noisy=truth+noise
spikeframes=np.array([45,75,105,135,165,195,225]);spikejoint=KEYS.index(15)
noisy[spikeframes,spikejoint]+=np.array([.25,0,0])
corrupt,corruptrows=solve(noisy)
mask=np.ones((N,12));mask[90:100,KEYS.index(15)]=0;mask[150:160,KEYS.index(27)]=0
missingobs=truth.copy();missingobs[mask==0]=np.nan
missing,missingrows=solve(missingobs,mask)
statictruth=np.repeat(truth[:1],20,axis=0);static,staticrows=solve(statictruth)
summary={'scope':'Independent same-model known-truth engineering tests. Does not validate anatomical axes or real-video accuracy.', 'source_sha256':hashlib.sha256((ROOT/'audit/snapshot/opensim_ik.py').read_bytes()).hexdigest(),'frames':N,'fps':FPS,'seed':SEED,'clean_tolerance_m':float(tol),'clean':metrics(clean,truth),'frozen':metrics(frozen,truth),'corrupt_raw':metrics(noisy,truth),'corrupt_fit':metrics(corrupt,truth),'missing':metrics(missing,truth),'static_max_error_m':float(np.linalg.norm(static-statictruth,axis=-1).max()),'recovery':[],'solver':{}}
for f,j in [(100,KEYS.index(15)),(160,KEYS.index(27))]:
    errors=np.linalg.norm(missing[f:f+8,j]-truth[f:f+8,j],axis=-1)
    ok=np.flatnonzero(errors<=tol)
    summary['recovery'].append({'first_observed_frame':f,'joint':KEYS[j],'errors_first_eight_m':errors.tolist(),'frames_to_tolerance':int(ok[0]) if len(ok) else None})
for name,rows in [('clean',cleanrows),('corrupt',corruptrows),('missing',missingrows),('static',staticrows)]:
    ms=[r['ms'] for r in rows]
    summary['solver'][name]={'errors':sum(r['status']!='fit' for r in rows),'max_bound_violation_rad':max(r['max_bound_violation_rad'] for r in rows),'latency_ms_p50':float(np.median(ms)),'latency_ms_p95':float(np.percentile(ms,95)),'latency_ms_max':max(ms)}
summary['clean_pass']=summary['clean']['max_error_m']<=tol and .95<=summary['clean']['amplitude_ratio_min'] and summary['clean']['amplitude_ratio_max']<=1.05 and abs(summary['clean']['lag_frames'])<=1
summary['frozen_correctly_fails']=not(summary['frozen']['max_error_m']<=tol and .95<=summary['frozen']['amplitude_ratio_min'] and summary['frozen']['amplitude_ratio_max']<=1.05)
summary['spikes']={'raw_error_m':np.linalg.norm(noisy[spikeframes,spikejoint]-truth[spikeframes,spikejoint],axis=-1).tolist(),'fit_error_m':np.linalg.norm(corrupt[spikeframes,spikejoint]-truth[spikeframes,spikejoint],axis=-1).tolist()}
summary['joint_observation_flags']='fit() has no observation-state return; fit_record wrapper tested separately.'
(OUT/'synthetic_results.json').write_text(json.dumps(summary,indent=2))
np.savez_compressed(OUT/'synthetic_arrays.npz',truth=truth,q=qs,clean=clean,frozen=frozen,noisy=noisy,corrupt=corrupt,missing=missing,mask=mask)
print(json.dumps(summary,indent=2))
