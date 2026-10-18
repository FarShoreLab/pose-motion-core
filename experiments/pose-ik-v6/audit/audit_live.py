"""Read-only audit of recorded live raw/IK provenance, timing and labels."""
import json,hashlib,collections,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];results=ROOT/'live-app/pose-v52/results';KEYS=[11,12,13,14,15,16,23,24,25,26,27,28]
def canonical_numbers(x):
 if isinstance(x,bool) or x is None:return x
 if isinstance(x,(int,float)):return 0.0 if x==0 else float(x)
 if isinstance(x,list):return [canonical_numbers(v) for v in x]
 if isinstance(x,dict):return {k:canonical_numbers(v) for k,v in x.items()}
 return x
def digest(x):return hashlib.sha256(json.dumps(canonical_numbers(x),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def stats(x):
 x=[v for v in x if isinstance(v,(int,float)) and np.isfinite(v)]
 return {'n':len(x),'p50':float(np.median(x)) if x else None,'p95':float(np.percentile(x,95)) if x else None,'max':max(x) if x else None}
raw={};derived={};duplicates=[];ordererrors=[]
for path in results.glob('immutable-live*.jsonl'):
 latest=None
 for lineno,line in enumerate(path.open()):
  item=json.loads(line);v=item['data'];key=(v['epoch'],v['frame_id'])
  if item['kind']=='raw_mediapipe_output':
   if key in raw:duplicates.append(key)
   raw[key]={'digest':digest([v.get('landmarks'),v.get('world_landmarks')]),'input_sha256':v['input_sha256'],'sequence':v.get('backend_sequence'),'pts':v['source_pts_ms'],'cache':v.get('pose_output_cache_used'),'path':path.name,'line':lineno};latest=key
  else:
   if key!=latest:ordererrors.append(key)
   if key in derived:duplicates.append(key)
   derived[key]={'digest':digest({k:v[k] for k in ['world','states','observation_states','status']}),'pts':v['source_pts_ms'],'input_sha256':v['input_sha256']}
report={'native_provenance':{'number_comparison':'Exact parsed numeric values, normalizing only JSON 1/1.0 and signed-zero representations','includes_prior_smoke_sessions':True,'raw_records':len(raw),'derived_records':len(derived),'duplicate_identity_count':len(duplicates),'nonlatest_fit_count':len(ordererrors)},'runs':{}}
for name in ['slow','fast','turn']:
 path=results/f'v6-live-{name}.json';d=json.loads(path.read_text());rows=d['inferences'];paired=[r for r in rows if r.get('disposition')=='strict_paired'];fits=[r for r in paired if r['ik']['status']=='fit'];cal=[r for r in rows if r['ik']['status']=='calibrating'];sec=(d['observation']['end_ms']-d['observation']['start_ms'])/1000
 error=collections.Counter();sequences=[];seen=set();step_sums=[];timing_slacks=[];native_paths=set();states=collections.Counter();inferred=0
 for r in rows:
  ik=r['ik'];key=(r['backend_expected_epoch'],r['frame_id']);seen.add(key);nr=raw.get(key);nf=derived.get(key)
  if nr is None or nf is None:error['native_missing']+=1;continue
  native_paths.add(nr['path']);sequences.append(nr['sequence'])
  if nr['digest']!=digest([[r['landmarks']] if r['landmarks'] else [],[r['world_landmarks']] if r['world_landmarks'] else []]):error['raw_landmark_changed']+=1
  if nf['digest']!=digest({k:ik[k] for k in ['world','states','observation_states','status']}):error['derived_output_changed']+=1
  if not(ik['frame_id']==r['frame_id'] and ik['epoch']==r['backend_expected_epoch'] and ik['source_pts_ms']==r['source_pts_ms']==nr['pts']==nf['pts'] and ik['input_sha256']==r['backend_input_sha256']==nr['input_sha256']==nf['input_sha256']):error['identity_mismatch']+=1
  if nr['cache'] is not False or r.get('backend_pose_output_cache_used') is not False:error['cache_flag']+=1
  if ik.get('new_measurement') is not False:error['ik_marked_new_measurement']+=1
  states.update(ik['states']);inferred+=sum(s=='inferred_unobserved' for s in ik['states'])
  if any(s=='measured' for s in ik['states']):error['fit_marked_measured']+=1
  if ik['status']=='calibrating' and any(p is not None for p in ik['world']):error['calibration_geometry']+=1
  if ik['status']!='fit' and any(p is not None for p in ik['world']):error['failed_or_absent_geometry']+=1
  if r.get('disposition')=='strict_paired':
   obs=r['filtered_observation']['states']
   if obs!=ik['observation_states']:error['observation_state_changed']+=1
   if ik['status']=='fit':
    for j in KEYS:
     if obs[j]=='lost' and (ik['states'][j]!='inferred_unobserved' or ik['effective_observed_mask'][j]):error['lost_promoted']+=1
   if abs(r['total_delay_ms']-(r['render_submit_ms']-r['scheduled_release_ms']))>1e-6:error['e2e_formula']+=1
   if not (r['scheduled_release_ms']<=r['dispatch_ms']+.001<=r['processing_start_ms']+.01<=r['processing_end_ms']+.01<=r['result_received_ms']+.01<=r['render_submit_ms']+.01):error['timing_order']+=1
   if abs(r['worker_processing_total_ms']-(r['processing_end_ms']-r['processing_start_ms']))>1e-6:error['worker_time_formula']+=1
   parts=r['stages_ms'];ss=sum(parts[k] for k in ['release_to_capture','capture','capture_to_dispatch','dispatch_to_worker','worker_processing','result_transfer','result_to_atomic_submit']);step_sums.append(abs(ss-r['total_delay_ms']))
   slack=r['worker_processing_total_ms']-r['backend_input_encode_ms']-r['backend_http_ms']-r['ik_http_ms'];timing_slacks.append(slack)
   if slack<-.05:error['ik_http_outside_worker_time']+=1
 if len(seen)!=len(rows):error['duplicate_browser_identity']+=1
 if any(b<=a for a,b in zip(sequences,sequences[1:])):error['backend_sequence_nonmonotonic']+=1
 if len(cal)!=30 or [r['ik']['live_output_index'] for r in cal]!=list(range(1,31)):error['calibration_count_or_order']+=1
 calib=d['metadata']['ik_calibration'];calids=[(r['backend_expected_epoch'],r['frame_id'],r['source_pts_ms']) for r in rows[:30]]
 if calids!=[(r['epoch'],r['frame_id'],r['source_pts_ms']) for r in calib['frames']]:error['calibration_not_first30']+=1
 if any(r['ik']['live_output_index']<=30 for r in fits):error['calibration_counted_as_fit']+=1
 post=[r for r in paired if r['ik']['live_output_index']>30]
 summary={'seconds':sec,'inferences':len(rows),'paired':len(paired),'fit_paired':len(fits),'calibrating':len(cal),'status_counts':dict(collections.Counter(r['ik']['status'] for r in rows)),'dispositions':dict(collections.Counter(r['disposition'] for r in rows)),'paired_hz_including_calibration_window':len(paired)/sec,'fit_hz_including_calibration_window':len(fits)/sec,'strict12_raw_valid_hz':sum(r['filtered_valid'] for r in paired)/sec,'observation_window_end_ms':d['observation']['end_ms'],'last_paired_submit_ms':paired[-1]['render_submit_ms'],'last_inference_received_ms':rows[-1]['result_received_ms'],'calibration_30th_frame_id':cal[-1]['frame_id'],'calibration_30th_submit_delay_ms':cal[-1].get('total_delay_ms'),'calibration_model_initialization_ms':cal[-1]['ik']['model_initialization_ms'],'first_fit_source_ms':fits[0]['source_pts_ms'],'e2e_all_paired_ms':stats([r['total_delay_ms'] for r in paired]),'e2e_post_calibration_ms':stats([r['total_delay_ms'] for r in post]),'ik_solver_ms':stats([r['ik_solver_ms'] for r in fits]),'ik_http_ms':stats([r['ik_http_ms'] for r in fits]),'e2e_stage_sum_abs_error_ms':stats(step_sums),'worker_time_minus_encode_and_both_http_ms':stats(timing_slacks),'max_pose_pts_difference_ms':max(abs(r['source_pts_ms']-r['ik']['source_pts_ms']) for r in rows),'output_states':dict(states),'inferred_unobserved_joint_outputs':inferred,'explicit_skipped_callbacks':sum(r['action']=='skip' for r in d['frames']),'source_callback_gap_frames':sum(e.get('missing_source_frames',0) for e in d['events'] if e['type']=='source_callback_gap'),'source_stalls':sum(e['type'] in ['source_waiting','source_stalled'] for e in d['events']),'max_pending':max(r.get('pending_after_offer',0) for r in d['frames']),'max_inflight':max(r.get('inflight_at_capture',0) for r in d['frames']),'new_render_observations':sum(r['new_observation'] for r in d['renders']),'new_render_tick_observations':sum(r.get('new_observation',False) for r in d['render_ticks']),'native_provenance_files':sorted(native_paths),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'model_source_sha256':calib['model_source_sha256'],'errors':dict(error)}
 report['runs'][name]=summary
report['verdict']='Live provenance, timing and uncertainty audit passes' if not duplicates and not ordererrors and not any(x['errors'] for x in report['runs'].values()) else 'Review listed live audit errors'
report['limits']=['Timing includes the complete recording-enabled two-HTTP-request implementation; difference from an older baseline cannot be attributed to IK arithmetic alone.','No calibrated real 3D truth; live execution does not reverse offline quality failures.','Native inference sequence and immutable raw/derived logs support fresh computation; tracker state reuse is distinct from output caching.','Calibration occupies 30 first live outputs and remains in whole-window throughput denominator; it produces no fitted geometry.','Rendered repeats are retained display frames, not new measurements.','E2E ends at software draw submission, not display photons.']
paths=['src/opensim_ik.py','live-app/pose-v52/public/app.js','live-app/pose-v52/public/pose-worker.js','live-app/pose-v52/public/record-comparison.js','live-app/pose-v52/public/joint-policy-v51.js','live-app/pose-v52-python/live_ik.py','live-app/pose-v52-python/server_epoch_modes.py']
report['inspected_integration_code_sha256']={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in paths}
report['unchanged_v52_joint_policy_verified']=hashlib.sha256((ROOT/'baseline-v5.2/pose-v52/public/joint-policy-v51.js').read_bytes()).hexdigest()==report['inspected_integration_code_sha256']['live-app/pose-v52/public/joint-policy-v51.js']
report['runtime_backend_hash_matches_inspected_code']={name:json.loads((results/f'v6-live-{name}-summary.json').read_text())['metadata']['backend_health']['backend_source_sha256']==report['inspected_integration_code_sha256']['live-app/pose-v52-python/server_epoch_modes.py'] for name in ['slow','fast','turn']}
(ROOT/'audit/live_addendum.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
