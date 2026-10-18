import sys,json,copy,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'audit/snapshot'))
from opensim_ik import HumanIK,fit_record,KEYS
r=json.loads((ROOT/'metric-reference/raw/v52-fast-release.json').read_text())['inferences'][0];out={}
for name in ['baseline','synthetic_missing','all_lost','no_pose','nonfinite_one','nonfinite_all']:
 x=copy.deepcopy(r)
 if name=='synthetic_missing': x['synthetic_missing_joints']=[15,27]
 if name=='all_lost': x['filtered_observation']['states']=['lost']*33
 if name=='no_pose': x['world_landmarks']=[]
 if name.startswith('nonfinite'):
  for j in ([15] if name=='nonfinite_one' else KEYS):x['world_landmarks'][j]['x']=float('nan')
 before=repr(x)
 y=fit_record(HumanIK(),x)
 z={'status':y['status'],'all_output_none':all(p is None for p in y['world']),'states':{str(j):y['states'][j] for j in KEYS},'obs_states':{str(j):y['observation_states'][j] for j in KEYS},'effective_observed_mask':y.get('effective_observed_mask'),'input_unchanged':repr(x)==before}
 assert z['input_unchanged']
 assert not any(s=='measured' for s in y['states'])
 if name in ['synthetic_missing','nonfinite_one']:
  for j in ([15,27] if name=='synthetic_missing' else [15]):
   assert y['states'][j]=='inferred_unobserved' and y['observation_states'][j]=='lost' and not y['effective_observed_mask'][j]
 if name in ['all_lost','no_pose','nonfinite_all']:assert z['all_output_none'] and y['status'] in ['no_pose','no_observation']
 z['pass']=True;out[name]=z
out={'source_sha256':hashlib.sha256((ROOT/'audit/snapshot/opensim_ik.py').read_bytes()).hexdigest(),'tests':out,'all_pass':True}
(ROOT/'audit/wrapper_results.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
