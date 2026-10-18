import sys,json,csv,collections,hashlib
from pathlib import Path
import numpy as np

def pct(a,p):
 a=[x for x in a if x is not None and np.isfinite(x)];return float(np.percentile(a,p)) if a else None

def summarize(path):
 d=json.loads(path.read_text());r=d['inferences'];paired=[x for x in r if x.get('disposition')=='strict_paired'];fit=[x for x in paired if x.get('ik',{}).get('status')=='fit'];sec=(d['observation']['end_ms']-d['observation']['start_ms'])/1000
 out={'source_file':str(path),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'seconds':sec,'inferences':len(r),'paired':len(paired),'fits':len(fit),'infer_hz':len(r)/sec,'paired_hz':len(paired)/sec,'strict12_raw_valid_hz':sum(x.get('filtered_valid',False) for x in paired)/sec,'ik_status_counts':dict(collections.Counter(x.get('ik',{}).get('status') for x in r)),'identity_errors':sum(x.get('ik',{}).get('frame_id')!=x['frame_id'] or x.get('ik',{}).get('source_pts_ms')!=x['source_pts_ms'] for x in r),'state_mask_errors':sum(x.get('ik',{}).get('observation_states')!=x.get('filtered_observation',{}).get('states') for x in paired),'sync_max_abs_ms':max(abs(x.get('sync_error_ms',0)) for x in paired),'ik_sync_max_abs_ms':max(abs(x.get('ik_sync_error_ms') or 0) for x in paired),'source_waiting_count':sum(x.get('type')=='source_waiting' for x in d['events']),'source_stalled_count':sum(x.get('type')=='source_stalled' for x in d['events']),'max_waiting':max((x.get('pending_after_offer',0) for x in d['frames']),default=0),'max_inflight_at_capture':max((x.get('inflight_at_capture',0) for x in d['frames']),default=0),'segments':d['segments'],'metadata':d['metadata']}
 for key in ['total_delay_ms','inference_ms','ik_http_ms','ik_solver_ms','ik_stage_processing_ms','worker_processing_total_ms','pending_wait_ms']:
  seq=fit if key.startswith('ik_') else paired
  out[key]={'p50':pct([x.get(key) for x in seq],50),'p95':pct([x.get(key) for x in seq],95),'max':pct([x.get(key) for x in seq],100)}
 out['measurement_notice']='New live CPU inference, source1x MSE continuous. E2E scheduled browser source release to draw submission, includes recorder overhead and second HTTP IK stage, not photons. Raw and IK same displayed frame, no synthetic observations. No inference cache.'
 return out
if __name__=='__main__':
 for p in map(Path,sys.argv[1:]):
  out=summarize(p);dest=p.parent/(p.stem+'-summary.json');dest.write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k not in ['metadata','segments']},indent=2))
