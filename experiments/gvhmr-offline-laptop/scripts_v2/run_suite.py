from isolate_env import ROOT,configure,PATH_VARS
import argparse,datetime,hashlib,json,pathlib,subprocess,threading,time
import psutil
P=argparse.ArgumentParser();P.add_argument('--name');P.add_argument('--skip-prepare',action='store_true');args=P.parse_args()
SCRIPTS=ROOT/'scripts_v2';MP=ROOT/'.venv-mediapipe/Scripts/python.exe';GV=ROOT/'.venv/Scripts/python.exe'
specs=json.loads((SCRIPTS/'clips.json').read_text(encoding='utf-8'))
if args.name:specs=[s for s in specs if s['name']==args.name]
assert specs
env=configure();env['POSE_MOTION_ROOT']=str(ROOT)
audit=ROOT/'logs/round2';audit.mkdir(exist_ok=True)
(audit/'process-configuration.json').write_text(json.dumps({'isolation':'process-local variables set before third-party imports; global environment not modified','paths':{k:env[k] for k in PATH_VARS},'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2),encoding='utf-8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(script,python,argv,out,tag):
    log=out/(tag+'-process.log');start=time.perf_counter();stamp=datetime.datetime.now(datetime.timezone.utc).isoformat();stop=threading.Event();samples=[];gpu=[]
    with log.open('w',encoding='utf-8') as f:
        process=subprocess.Popen([str(python),str(SCRIPTS/script),*argv],env=env,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        def monitor():
            last_gpu=-99
            while not stop.is_set():
                now=time.perf_counter();rss=0
                try:
                    parent=psutil.Process(process.pid)
                    for child in [parent,*parent.children(recursive=True)]:
                        try:rss+=child.memory_info().rss
                        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
                except (psutil.NoSuchProcess,psutil.AccessDenied):pass
                samples.append({'elapsed_s':now-start,'rss_tree_bytes':rss})
                if now-last_gpu>=1:
                    last_gpu=now
                    try:
                        raw=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits'],text=True,timeout=3,creationflags=subprocess.CREATE_NO_WINDOW)
                        gpu.append({'elapsed_s':time.perf_counter()-start,'gpus':[list(map(int,row.strip().split(','))) for row in raw.strip().splitlines()]})
                    except Exception as error:gpu.append({'elapsed_s':time.perf_counter()-start,'error':str(error)})
                stop.wait(.05)
        thread=threading.Thread(target=monitor,daemon=True);thread.start();returncode=process.wait();end=time.perf_counter();stop.set();thread.join(timeout=4)
    result={'stage':tag,'started_utc':stamp,'wall_seconds':end-start,'exit_code':returncode,'peak_process_tree_rss_bytes_sampled':max((s['rss_tree_bytes'] for s in samples),default=0),'memory_sampling_note':'50 ms target; nvidia-smi query temporarily delays sampling; peak is a sampled lower bound','gpu_note':'whole-device nvidia-smi memory is shared with desktop/other processes; stage torch metrics separately report this process allocator peaks','gpu_peak_whole_device_mib_sampled':max((row[0] for s in gpu for row in s.get('gpus',[])),default=None)}
    (out/(tag+'-process-timing.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    (out/(tag+'-resource-samples.json')).write_text(json.dumps({'rss':samples,'whole_device_gpu':gpu}),encoding='utf-8')
    print(json.dumps({'clip':out.name,**result}),flush=True)
    return result
for spec in specs:
    out=ROOT/'outputs'/spec['name'];out.mkdir(exist_ok=True)
    assert not (out/'pipeline-timings.json').exists(),'Completed output preserved; use a new name.'
    workflow_start=time.perf_counter()
    if not args.skip_prepare:
        result=run('prepare_clip.py',MP,['--name',spec['name']],out,'prepare')
        if result['exit_code']:raise RuntimeError('Preparation failed: '+str(out))
    inputsha=sha(out/'input_30fps.mp4');results=[]
    mp_start=time.perf_counter();r=run('run_mediapipe.py',MP,['--name',spec['name']],out,'mediapipe');mp_end=time.perf_counter();results.append(r)
    if r['exit_code']:raise RuntimeError('MediaPipe failed: '+str(out))
    gv_start=time.perf_counter();camera='static';fallback=None
    for stage in ['bbox','vitpose','hmr2']+(['vo'] if spec['estimate_camera'] else [])+['gvhmr']:
        r=run('stage_gvhmr.py',GV,['--name',spec['name'],'--stage',stage,'--camera',camera],out,stage);results.append(r)
        if stage=='vo':
            if r['exit_code']:
                fallback='Official SimpleVO failed; explicit static-camera fallback. Camera/world translation unvalidated.'
                meta=json.loads((out/'input-manifest.json').read_text(encoding='utf-8'));meta['camera_assumption_warning']=fallback
                (out/'input-manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
            else:camera='simplevo'
        elif r['exit_code']:raise RuntimeError(stage+' failed: '+str(out))
    gv_end=time.perf_counter();assert inputsha==sha(out/'input_30fps.mp4')
    raw_ready=json.loads((out/'raw-output-ready.json').read_text(encoding='utf-8'))
    timing={'clip':spec['name'],'input_sha256_for_both':inputsha,'frames':round(spec['duration']*30),'input_duration_s':spec['duration'],'mediapipe_e2e_seconds':mp_end-mp_start,'gvhmr_e2e_raw_tensor_ready_seconds':raw_ready['perf_counter']-gv_start,'gvhmr_e2e_raw_and_official_postprocess_seconds':gv_end-gv_start,'timing_scope':'Measured contiguous parent perf_counter interval: process launch/imports, model loading, all video decoding/preprocessing, inference, serialization and process exit. GVHMR stages use separate serial processes to limit memory; optional VO attempt and failure included. Media preparation and review rendering separately timed. Raw-ready excludes subsequent FK NPZ export and duplicate forward for postprocess. No stage sum substituted for wall clock. Warm filesystem/model caches possible; not cold-boot benchmark.','camera_mode':camera,'camera_warning':fallback,'stage_process_timings':results}
    r=run('render_review.py',MP,['--name',spec['name']],out,'render');timing['render_seconds']=r['wall_seconds'];timing['complete_workflow_including_preparation_and_render_seconds']=time.perf_counter()-workflow_start
    (out/'pipeline-timings.json').write_text(json.dumps(timing,ensure_ascii=False,indent=2),encoding='utf-8')
    if r['exit_code']:raise RuntimeError('Render failed: '+str(out))
    print('CLIP COMPLETE '+spec['name'],flush=True)
