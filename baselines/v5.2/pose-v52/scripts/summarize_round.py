#!/usr/bin/env python3
"""Summarize fresh online logs; full raw coordinates stay in the original JSON."""
import json,csv,math,statistics,collections,pathlib,sys
KEY=[11,12,13,14,15,16,23,24,25,26,27,28]
def stats(a):
 a=sorted(x for x in a if isinstance(x,(int,float)) and math.isfinite(x))
 return {} if not a else dict(n=len(a),mean=statistics.mean(a),p50=a[math.ceil(len(a)*.5)-1],p95=a[math.ceil(len(a)*.95)-1],max=max(a),min=min(a))
def summarize(path,out):
 d=json.loads(path.read_text());start,end=d['observation']['start_ms'],d['observation']['end_ms'];t=(end-start)/1000;rs=[r for r in d['inferences'] if r['disposition']=='strict_paired' and start<=r['render_submit_ms']<=end];fs=[f for f in d['frames'] if start<=f['callback_ms']<=end];ticks=[r for r in d['render_ticks'] if start<=r['wall_ms']<=end]
 loss=[];cover=[]
 for j in range(33):
  c=collections.Counter(r['filtered_observation']['states'][j] for r in rs);cover.append({'joint':j,**{k:c[k]/len(rs) for k in ['measured','uncertain','lost']}})
 recover=[];censored=[];groups=collections.defaultdict(list)
 for r in rs:groups[r['epoch']].append(r)
 for epoch,rows in groups.items():
  lastvalid=None;bad=None
  for r in rows:
   if r['filtered_valid']:
    if bad:recover.append({'epoch':epoch,'start_frame':bad['frame_id'],'recovery_frame':r['frame_id'],'source_ms':r['source_pts_ms']-bad['source_pts_ms'],'wall_ms':r['render_submit_ms']-bad['render_submit_ms'],'left_censored':lastvalid is None});bad=None
    lastvalid=r
   elif bad is None:bad=r
  if bad:censored.append({'epoch':epoch,'start_frame':bad['frame_id'],'observed_ms':rows[-1]['source_pts_ms']-bad['source_pts_ms']})
 thirds=[]
 for i in range(3):
  seg=[r for r in rs if start+t*1000*i/3<=r['render_submit_ms']<start+t*1000*(i+1)/3];cf=[f for f in fs if start+t*1000*i/3<=f['callback_ms']<start+t*1000*(i+1)/3]
  thirds.append({'third':i+1,'release_to_submit_ms':stats([r['total_delay_ms'] for r in seg]),'callback_minus_fixed_release_ms':stats([f['callback_ms']-f['scheduled_release_ms'] for f in cf]),'expected_display_minus_fixed_release_ms':stats([f['expected_display_ms']-f['scheduled_release_ms'] for f in cf])})
 loops=[]
 for a,b in zip(fs,fs[1:]):
  if a['loop_count']!=b['loop_count']:loops.append({'loop':b['loop_count'],'gap_callback_ms':b['callback_ms']-a['callback_ms'],'first_callback_minus_fixed_release_ms':b['callback_ms']-b['scheduled_release_ms'],'first_pts_ms':b['source_pts_ms']})
 s={'file':path.name,'version':d['metadata']['app_version'],'seconds':t,'counts':{'callbacks':len(fs),'all_completed':len(d['inferences']),'new_paired':len(rs),'strict12':sum(r['filtered_valid'] for r in rs),'rawvalid_paired':sum(r['valid'] for r in rs),'held_render_ticks':len(ticks),'explicit_skipped':sum(f['action']=='skip' for f in fs),'source_callback_missing':sum(e.get('missing_source_frames',0) for e in d['events'] if e['type']=='source_callback_gap')},'hz':{'new_paired':len(rs)/t,'strict12':sum(r['filtered_valid'] for r in rs)/t,'rawvalid_paired':sum(r['valid'] for r in rs)/t,'render_ticks_not_observations':len(ticks)/t},'delay_ms':stats([r['total_delay_ms'] for r in rs]),'paired_pts_error_ms':stats([abs(r['sync_error_ms']) for r in rs]),'backend_inference_ms':stats([r['inference_ms'] for r in rs]),'source_lead_ms':stats([r['source_lead_ms'] for r in rs if r['source_lead_ms']>=0]),'coverage_key_mean_measured':statistics.mean(x['measured'] for x in cover if x['joint'] in KEY),'coverage_key_mean_lost':statistics.mean(x['lost'] for x in cover if x['joint'] in KEY),'joint_coverage':cover,'recovery_events':recover,'recovery_source_ms':stats([x['source_ms'] for x in recover if not x['left_censored']]),'right_censored_dropout_events':censored,'thirds':thirds,'loop_boundaries':loops,'skip_reasons':dict(collections.Counter(f.get('skip_reason') for f in fs if f['action']=='skip')),'pending_max_observed':max(f.get('pending_after_offer',f.get('pending_at_capture',0)) for f in fs),'pending_bound':d['metadata']['queue_limit_pending'],'initial_backend_calls':d['metadata']['backend_health']['calls'],'policy_sha':d['metadata'].get('source_manifest',{}).get('files',{}).get('public/joint-policy.js'),'notice':'Coverage and confidence-gated recovery are not3D accuracy. Fixed-release→software-submit is not photon latency; held rAF and predicted points are notnew observations.'}
 out.mkdir(parents=True,exist_ok=True);(out/(path.stem+'-summary.json')).write_text(json.dumps(s,ensure_ascii=False,indent=2))
 def write(name,rows):
  fields=list(dict.fromkeys(k for r in rows for k in r));
  with (out/(path.stem+'-'+name+'.csv')).open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows([{k:json.dumps(v,separators=(',',':')) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows])
 write('frames',fs)
 write('inferences',[{k:v for k,v in r.items() if k not in ['landmarks','world_landmarks','filtered_observation','v4_filtered_observation']} for r in d['inferences']])
 write('joints',[{'frame_id':r['frame_id'],'epoch':r['epoch'],'source_pts_ms':r['source_pts_ms'],'joint':j,'state':r['filtered_observation']['states'][j],'reason':r['filtered_observation']['reasons'][j],'visibility':r['landmarks'][j].get('visibility') if len(r['landmarks'])==33 else None,'presence':r['landmarks'][j].get('presence') if len(r['landmarks'])==33 else None,**{axis:r['world_landmarks'][j][axis] if len(r['world_landmarks'])==33 else None for axis in ['x','y','z']}} for r in rs for j in range(33)])
 return s
if __name__=='__main__':
 out=pathlib.Path(sys.argv[1]);results=[summarize(pathlib.Path(x),out) for x in sys.argv[2:]];(out/'round-summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps([{k:r[k] for k in ['file','seconds','hz','delay_ms','pending_max_observed']} for r in results],indent=2))
