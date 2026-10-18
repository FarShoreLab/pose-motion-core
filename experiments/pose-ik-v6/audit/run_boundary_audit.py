import sys,json,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'audit/snapshot'))
from opensim_ik import HumanIK
source_hash=hashlib.sha256((ROOT/'audit/snapshot/opensim_ik.py').read_bytes()).hexdigest()
base=HumanIK();out=[]
for k,c in enumerate(base.coords):
 if not c.getDefaultClamped():continue
 gen=HumanIK();fit=HumanIK();v0=gen.initial_q[k];lo=c.getRangeMin()+np.deg2rad(1);hi=c.getRangeMax()-np.deg2rad(1)
 vals=np.r_[np.linspace(v0,lo,20),np.linspace(lo,hi,40)[1:],np.linspace(hi,v0,20)[1:]]
 errors=[];statuses=[];bound=[]
 for f,v in enumerate(vals):
  q=gen.initial_q.copy();q[k]=v;truth=gen.fk(q);r=fit.fit(truth,timestamp=f/30)
  errors.append(float(np.linalg.norm(r['points']-truth,axis=1).max()));statuses.append(r['status']);bound.append(r['max_bound_violation_rad'])
 out.append({'coordinate':c.getName(),'frames':len(vals),'max_marker_error_m':max(errors),'p95_marker_error_m':float(np.percentile(errors,95)),'frames_error_over_3p55mm':sum(x>.00355 for x in errors),'solver_errors':sum(x!='fit' for x in statuses),'max_bound_violation_rad':max(bound),'worst_frame':int(np.argmax(errors))})
print(json.dumps({'source_sha256':source_hash,'method':'Each clamped coordinate individually traversed from default to 1 degree above lower range then 1 degree below upper range, back to default. Same model truth, independent fit instance.','results':out},indent=2))
