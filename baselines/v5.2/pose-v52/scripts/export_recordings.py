import pathlib,subprocess,json,hashlib
W=pathlib.Path(__file__).resolve().parents[2];source=W/'pose-v52-evidence/recordings';target=W/'pose-v52-delivery';target.mkdir(exist_ok=True);reports=[]
names=['baseline-fast-final','baseline-slow','baseline-turn','v52-fast-release','v52-slow-release','v52-turn-release']
for name in names:
 a=source/(name+'.mp4');b=target/('pose-live-v5.2-'+name+'.mp4')
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(a),'-c:v','libx264','-preset','medium','-crf','24','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart','-an','-y',str(b)],check=True)
 def probe(p):return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration,size:stream=codec_name,width,height,avg_frame_rate,nb_frames','-of','json',str(p)]))
 pa,pb=probe(a),probe(b);assert float(pb['format']['duration'])>=65;assert pa['streams'][0]['nb_frames']==pb['streams'][0]['nb_frames'];assert pa['streams'][0]['avg_frame_rate']==pb['streams'][0]['avg_frame_rate']
 reports.append({'name':name,'capture':pa,'delivery':pb,'capture_sha256':hashlib.sha256(a.read_bytes()).hexdigest(),'delivery_sha256':hashlib.sha256(b.read_bytes()).hexdigest(),'no_retiming':True,'frames_unchanged':True,'notice':'Real desktop capture; video compression export only, no pose/metric overlays added in post.'})
 print(name,pb['format']['size'],flush=True)
(W/'pose-v52-evidence/recording-validation.json').write_text(json.dumps(reports,indent=2))
