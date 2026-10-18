"""Simplified 25-DoF human OpenSim IK. Not a clinical anatomical model.
All coordinates (except six-DoF root) have explicit clamped ranges.
Output has separate inference and observation status; raw input is never altered.
"""
from __future__ import annotations
import json, math, time
from pathlib import Path
import numpy as np
import opensim as osim

KEYS=[11,12,13,14,15,16,23,24,25,26,27,28]
NAMES=['LShoulder','RShoulder','LElbow','RElbow','LWrist','RWrist','LHip','RHip','LKnee','RKnee','LAnkle','RAnkle']
BONES=[(11,12),(23,24),(11,13),(13,15),(12,14),(14,16),(23,25),(25,27),(24,26),(26,28)]
DEFAULT_LENGTHS={'shoulder_width':.36,'hip_width':.22,'torso':.46,'upperarm_l':.28,'upperarm_r':.28,'forearm_l':.25,'forearm_r':.25,'thigh_l':.43,'thigh_r':.43,'shank_l':.43,'shank_r':.43}
osim.Logger.setLevelString('error')

def xyz(points):
    return np.array([[p['x'], -p['y'], -p['z']] if p is not None else [np.nan]*3 for p in points],float)

def mp_points(p):
    return [{'x':float(v[0]),'y':float(-v[1]),'z':float(-v[2])} for v in p]

def calibrate(records, max_frames=30):
    samples={k:[] for k in DEFAULT_LENGTHS}
    pairs={'shoulder_width':(11,12),'hip_width':(23,24),'upperarm_l':(11,13),'upperarm_r':(12,14),'forearm_l':(13,15),'forearm_r':(14,16),'thigh_l':(23,25),'thigh_r':(24,26),'shank_l':(25,27),'shank_r':(26,28)}
    for r in records[:max_frames]:
        if len(r.get('world_landmarks',[]))<33: continue
        p=xyz(r['world_landmarks']); q=r.get('landmarks',r['world_landmarks'])
        good=np.array([min(a.get('visibility',0),a.get('presence',0))>=.7 for a in q])
        for key,(a,b) in pairs.items():
            d=np.linalg.norm(p[a]-p[b])
            if good[a] and good[b] and .07<d<.8: samples[key].append(float(d))
        if all(good[i] for i in [11,12,23,24]):
            samples['torso'].append(float(np.linalg.norm((p[11]+p[12]-p[23]-p[24])/2)))
    lengths={k:float(np.median(v)) if len(v)>=5 else DEFAULT_LENGTHS[k] for k,v in samples.items()}
    return lengths, {k:{'samples':len(v),'fallback':len(v)<5} for k,v in samples.items()}

class HumanIK:
    def __init__(self,lengths=None,temporal_weight=0.0):
        self.lengths=dict(DEFAULT_LENGTHS if lengths is None else lengths)
        self.temporal_weight=temporal_weight
        self.model=osim.Model();self.model.setName('simplified_human_25dof_v6')
        self.coord_specs=[]; self.markers=[]; self.last_q=None
        self._build();self.state=self.model.initSystem()
        for c in self.coords:
            if c.getDefaultClamped(): c.setClamped(self.state,True)
        self.initial_q=np.array([c.getValue(self.state) for c in self.coords])
        self.frame=0
    def _body(self,name):
        b=osim.Body(name,1,osim.Vec3(0),osim.Inertia(1));self.model.addBody(b);return b
    def _joint(self,typ,name,parent,child,location=(0,0,0),orientation=(0,0,0),ranges=None):
        j=typ(name,parent,osim.Vec3(*location),osim.Vec3(*orientation),child,osim.Vec3(0),osim.Vec3(*orientation))
        self.model.addJoint(j)
        for i in range(j.numCoordinates()):
            c=j.upd_coordinates(i);c.setName(f'{name}_{i}')
            if ranges is not None:
                lo,hi=ranges[i];c.setRangeMin(math.radians(lo));c.setRangeMax(math.radians(hi));c.setDefaultClamped(True)
                c.setDefaultValue(math.radians(15) if 'elbow' in name or 'knee' in name else 0)
            self.coord_specs.append({'name':c.getName(),'range_degrees':ranges[i] if ranges else None,'clamped':ranges is not None})
        return j
    def _marker(self,index,body,loc):
        m=osim.Marker(NAMES[KEYS.index(index)],body,osim.Vec3(*loc));self.model.addMarker(m);self.markers.append((index,m))
    def _build(self):
        L=self.lengths;p=self._body('pelvis');t=self._body('torso')
        self._joint(osim.FreeJoint,'root',self.model.getGround(),p)
        self._joint(osim.BallJoint,'lumbar',p,t,ranges=[(-90,90),(-80,80),(-60,60)])
        for side,sign,shoulder,elbow,wrist,hip,knee,ankle in [('l',1,11,13,15,23,25,27),('r',-1,12,14,16,24,26,28)]:
            a=self._body('upperarm_'+side);f=self._body('forearm_'+side);th=self._body('thigh_'+side);sh=self._body('shank_'+side)
            spos=(sign*L['shoulder_width']/2,L['torso'],0);hpos=(sign*L['hip_width']/2,0,0)
            self._joint(osim.BallJoint,'shoulder_'+side,t,a,spos,ranges=[(-180,60),(-100,100),(-40,180) if sign==1 else (-180,40)])
            self._joint(osim.PinJoint,'elbow_'+side,a,f,(0,-L['upperarm_'+side],0),(0,-math.pi/2,0),ranges=[(0,155)])
            self._joint(osim.BallJoint,'hip_'+side,p,th,hpos,ranges=[(-150,45),(-60,60),(-40,80) if sign==1 else (-80,40)])
            self._joint(osim.PinJoint,'knee_'+side,th,sh,(0,-L['thigh_'+side],0),(0,math.pi/2,0),ranges=[(-5,165)])
            self._marker(shoulder,t,spos);self._marker(elbow,a,(0,-L['upperarm_'+side],0));self._marker(wrist,f,(0,-L['forearm_'+side],0))
            self._marker(hip,p,hpos);self._marker(knee,th,(0,-L['thigh_'+side],0));self._marker(ankle,sh,(0,-L['shank_'+side],0))
        self.model.finalizeConnections();self.coords=[self.model.updCoordinateSet().get(i) for i in range(self.model.getCoordinateSet().getSize())]
        self.markers.sort(key=lambda x:KEYS.index(x[0]))
    def fk(self,q=None):
        if q is not None:
            for c,v in zip(self.coords,q): c.setValue(self.state,float(v),False)
        self.model.realizePosition(self.state)
        return np.array([[m.getLocationInGround(self.state).get(i) for i in range(3)] for _,m in self.markers])
    def fit(self,points,weights=None,timestamp=0.0):
        """Fit 12 OpenSim-axis xyz points. Zero weights exclude missing observations."""
        start=time.perf_counter(); p=np.asarray(points,float);weights=np.ones(len(KEYS)) if weights is None else np.array(weights,float)
        weights[~np.isfinite(p).all(1)]=0
        table=osim.TimeSeriesTableVec3();labels=osim.StdVectorString()
        for name in NAMES: labels.append(name)
        table.setColumnLabels(labels);table.addTableMetaDataString('units','m')
        row=osim.RowVectorVec3(len(KEYS));wset=osim.SetMarkerWeights()
        for i,name in enumerate(NAMES):
            # Placeholder coordinates for zero-weight rows are not observations.
            v=p[i] if weights[i]>0 else np.zeros(3)
            row[i]=osim.Vec3(*v);wset.cloneAndAppend(osim.MarkerWeight(name,float(weights[i])))
        table.appendRow(float(timestamp),row);table.appendRow(float(timestamp+.001),row)
        reference=osim.MarkersReference(table,wset);refs=osim.SimTKArrayCoordinateReference()
        if self.last_q is not None and self.temporal_weight>0:
            for c,v in zip(self.coords,self.last_q):
                cr=osim.CoordinateReference(c.getName(),osim.Constant(float(v)));cr.setWeight(self.temporal_weight);refs.push_back(cr)
        self.state.setTime(float(timestamp))
        solver=osim.InverseKinematicsSolver(self.model,reference,refs)
        solver.setAccuracy(1e-4)
        status='fit';error=None
        try: solver.assemble(self.state)
        except Exception as exc: status='solver_error';error=str(exc)
        fitted=self.fk();q=np.array([c.getValue(self.state) for c in self.coords]);self.last_q=q.copy();self.frame+=1
        bounds=[max(0,c.getRangeMin()-v,v-c.getRangeMax()) if c.getDefaultClamped() else 0 for c,v in zip(self.coords,q)]
        residual=np.linalg.norm(fitted-p,axis=1)
        return {'points':fitted,'q':q,'weights':weights,'residual_m':residual,'ms':(time.perf_counter()-start)*1000,'status':status,'error':error,'max_bound_violation_rad':max(bounds)}
    def export(self,path): self.model.printToXML(str(path))

def fit_record(model,r):
    full=r.get('world_landmarks',[]); obs=r.get('filtered_observation',{}); states=list(obs.get('states',[]))
    if len(full)<33:
        return {'status':'no_pose','world':[None]*33,'states':['lost']*33,'observation_states':['lost']*33,'solver_ms':0}
    p=xyz(full)[KEYS];conf=np.array([min(r['landmarks'][i].get('presence',0),r['landmarks'][i].get('visibility',0)) for i in KEYS])
    if not states: states=['measured' if min(x.get('presence',0),x.get('visibility',0))>=.65 else 'uncertain' if min(x.get('presence',0),x.get('visibility',0))>=.35 else 'lost' for x in r['landmarks']]
    w=conf**2*np.array([1 if states[i]=='measured' else .1 if states[i]=='uncertain' else 0 for i in KEYS])
    for j,i in enumerate(KEYS):
        if not np.isfinite(p[j]).all() or not np.isfinite(w[j]):
            w[j]=0; states[i]='lost'
        if i in r.get('synthetic_missing_joints',[]):
            w[j]=0; states[i]='lost'
    if not np.any(w>0):
        return {'status':'no_observation','world':[None]*33,'states':['lost']*33,'observation_states':states,'effective_observed_mask':[False]*33,'solver_ms':0}
    res=model.fit(p,w,r.get('source_unwrapped_pts_ms',r['source_pts_ms'])/1000)
    w=res['weights']
    if res['status']!='fit':
        return {'status':res['status'],'world':[None]*33,'states':['lost']*33,'observation_states':states,'effective_observed_mask':[bool(w[KEYS.index(i)]>0) if i in KEYS else False for i in range(33)],'solver_ms':res['ms'],'error':res['error']}
    world=[None]*33;outstates=['unmodelled']*33;residuals=[None]*33
    for j,i in enumerate(KEYS):
        world[i]=mp_points(res['points'][j:j+1])[0]
        outstates[i]='fitted' if w[j]>0 else 'inferred_unobserved'
        residuals[i]=float(res['residual_m'][j]) if w[j]>0 else None
    return {'status':res['status'],'world':world,'states':outstates,'observation_states':list(states),'solver_ms':res['ms'],'residual_m':residuals,'effective_observed_mask':[bool(w[KEYS.index(i)]>0) if i in KEYS else False for i in range(33)],'weights':dict(zip(map(str,KEYS),map(float,w))),'q':res['q'].tolist(),'coordinate_names':[c.getName() for c in model.coords],'max_bound_violation_rad':res['max_bound_violation_rad'],'error':res['error']}

if __name__=='__main__':
    m=HumanIK();truth=m.fk();print('DOF',len(m.coords));print(m.fit(truth));m.export(Path(__file__).parent/'simplified_human.osim')
