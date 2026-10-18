import pathlib,subprocess,os,json,time,sys
r=pathlib.Path(__file__).resolve().parent
name=sys.argv[1] if len(sys.argv)>1 else 'live-v4'
seconds=sys.argv[2] if len(sys.argv)>2 else '100'
cmd=['ffmpeg','-hide_banner','-loglevel','warning','-y','-f','x11grab','-framerate','30','-video_size','1364x1024','-i',os.environ.get('DISPLAY',':0'),'-t',seconds,'-c:v','libx264','-preset','ultrafast','-crf','23','-pix_fmt','yuv420p',str(r/'results'/f'{name}.mp4')]
(r/'results'/f'{name}-command.json').write_text(json.dumps({'command':cmd,'started_wall_epoch':time.time()},indent=2))
p=subprocess.Popen(cmd,stdout=open(r/'results'/f'{name}.log','w'),stderr=subprocess.STDOUT);print('Recording desktop process',p.pid,flush=True);p.wait();print('recording finished',flush=True)
