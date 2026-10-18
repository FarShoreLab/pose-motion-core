from isolate_env import ROOT as root
import argparse,av,csv,hashlib,json,pathlib,sys,threading,time,os
import mediapipe as mp,numpy as np,psutil
parser=argparse.ArgumentParser();parser.add_argument('--name',default='smoke');args=parser.parse_args()
out=root/'outputs'/args.name;model=root/'assets'/'pose_landmarker_lite.task'
assert hashlib.sha256(model.read_bytes()).hexdigest()=='59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a'
mapping=list(csv.DictReader((out/'frame-map.csv').open(encoding='utf-8')))
process=psutil.Process();peak=[process.memory_info().rss];stop=threading.Event()
def monitor():
    while not stop.wait(.1):peak[0]=max(peak[0],process.memory_info().rss)
threading.Thread(target=monitor,daemon=True).start()
opts=mp.tasks.vision.PoseLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(model),delegate=mp.tasks.BaseOptions.Delegate.CPU),running_mode=mp.tasks.vision.RunningMode.VIDEO,num_poses=1,min_pose_detection_confidence=.5,min_pose_presence_confidence=.5,min_tracking_confidence=.5,output_segmentation_masks=False)
started=time.perf_counter();landmarker=mp.tasks.vision.PoseLandmarker.create_from_options(opts);load_seconds=time.perf_counter()-started
results=[];normalized=np.full((len(mapping),33,5),np.nan);world=normalized.copy();times=[]
def convert(points):return [[float(p.x),float(p.y),float(p.z),float(p.visibility),float(p.presence)] for p in points]
started=time.perf_counter();decode_s=0
with av.open(str(out/'input_30fps.mp4')) as container:
    for i,frame in enumerate(container.decode(video=0)):
        start=time.perf_counter();rgb=frame.to_ndarray(format='rgb24');image=mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb);decode_s+=time.perf_counter()-start
        timestamp=int(mapping[i]['input_timestamp_ms']);start=time.perf_counter();result=landmarker.detect_for_video(image,timestamp);elapsed=time.perf_counter()-start;times.append(elapsed)
        record={'input_frame':i,'input_timestamp_ms':timestamp,'source_frame':int(mapping[i]['source_frame']),'source_pts_seconds':float(mapping[i]['source_seconds']),'inference_seconds':elapsed,'pose_landmarks':[],'pose_world_landmarks':[]}
        if result.pose_landmarks:
            normalized[i]=convert(result.pose_landmarks[0]);world[i]=convert(result.pose_world_landmarks[0]);record['pose_landmarks']=normalized[i].tolist();record['pose_world_landmarks']=world[i].tolist()
        results.append(record)
        if i%15==0:print(f'MediaPipe {i+1}/{len(mapping)}',flush=True)
elapsed_total=time.perf_counter()-started;landmarker.close();stop.set()
np.savez_compressed(out/'mediapipe_raw.npz',normalized=normalized,world=world)
with (out/'mediapipe_raw.jsonl').open('w',encoding='utf-8') as f:
    for result in results:f.write(json.dumps(result)+'\n')
metrics={'stage':'mediapipe','runtime_version':mp.__version__,'python':sys.version,'delegate':'CPU','running_mode':'VIDEO','num_frames':len(results),'detected_frames':int(np.isfinite(normalized[:,0,0]).sum()),'model_load_seconds':load_seconds,'inference_seconds':sum(times),'decode_conversion_seconds':decode_s,'loop_wall_seconds':elapsed_total,'p50_frame_ms':float(np.percentile(times,50)*1000),'p95_frame_ms':float(np.percentile(times,95)*1000),'peak_rss_bytes_sampled':peak[0],'memory_sample_interval_seconds':.1,'gpu_memory_bytes':0,'note':'Raw outputs; no external smoothing, IK or v6 constraints. Offline file decoding, not live latency. Built-in MediaPipe temporal tracking retained.'}
(out/'mediapipe-metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8');print(json.dumps(metrics),flush=True)
