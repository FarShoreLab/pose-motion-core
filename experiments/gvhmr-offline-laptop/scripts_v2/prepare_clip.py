from isolate_env import ROOT
import argparse,av,csv,hashlib,json,time
from fractions import Fraction
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--name',required=True);args=p.parse_args()
allclips=json.loads((ROOT/'scripts_v2/clips.json').read_text(encoding='utf-8'))
spec=next(c for c in allclips if c['name']==args.name)
out=ROOT/'outputs'/args.name;out.mkdir(exist_ok=True)
dest=out/'input_30fps.mp4';assert not dest.exists(),'Existing input preserved; select a fresh run name.'
src=ROOT/'assets'/spec['filename'];started=time.perf_counter()
with av.open(str(src)) as c:
    stream=c.streams.video[0];rate=stream.average_rate or stream.base_rate or stream.guessed_rate;metadata={'width':stream.width,'height':stream.height,'fps_rational':str(rate),'fps':float(rate),'fps_field':'average_rate' if stream.average_rate else ('base_rate' if stream.base_rate else 'guessed_rate'),'codec':stream.codec_context.name}
    frame_pts=[{'pts':f.pts,'time_base':str(f.time_base),'seconds':float(f.pts*f.time_base)} for f in c.decode(video=0)]
source_exact=[Fraction(f['pts'])*Fraction(f['time_base']) for f in frame_pts]
target_exact=[source_exact[0]+Fraction(str(spec['start']))+Fraction(i,30) for i in range(round(spec['duration']*30))]
assert target_exact[-1]<=source_exact[-1]
indices=[min(range(len(source_exact)),key=lambda j:abs(source_exact[j]-t)) for t in target_exact]
rows=[{'input_frame':i,'input_pts':i,'input_time_base':'1/30','input_seconds':i/30,'input_timestamp_ms':round(i*1000/30),'target_source_seconds':float(t),'source_frame':j,'source_pts':frame_pts[j]['pts'],'source_time_base':frame_pts[j]['time_base'],'source_seconds':float(source_exact[j]),'sampling_error_ms':float((source_exact[j]-t)*1000)} for i,(t,j) in enumerate(zip(target_exact,indices))]
needed=set(indices);decoded={}
with av.open(str(src)) as c:
    for i,f in enumerate(c.decode(video=0)):
        if i in needed:decoded[i]=f.to_ndarray(format='rgb24')
        if i>=indices[-1]:break
with av.open(str(dest),'w') as c:
    s=c.add_stream('libx264',rate=30);s.width=metadata['width'];s.height=metadata['height'];s.pix_fmt='yuv420p';s.options={'crf':'18','preset':'fast'}
    for i,j in enumerate(indices):
        f=av.VideoFrame.from_ndarray(decoded[j],format='rgb24');f.pts=i;f.time_base=Fraction(1,30)
        for packet in s.encode(f):c.mux(packet)
    for packet in s.encode():c.mux(packet)
with (out/'frame-map.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
with av.open(str(dest)) as c:actual=[float(f.pts*f.time_base) for f in c.decode(video=0)]
assert len(actual)==len(rows) and np.allclose(actual,np.arange(len(rows))/30,atol=1e-7)
meta={**spec,'source':src.name,'source_stream':metadata,'source_frames':len(source_exact),'source_video_duration_seconds':float(source_exact[-1]-source_exact[0])+1/metadata['fps'],'source_first_pts_seconds':float(source_exact[0]),'original_first_pts_seconds':float(source_exact[0]),'source_start_normalized_seconds':spec['start'],'duration_seconds':spec['duration'],'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'source_fps':metadata['fps'],'input_fps':30,'input_frames':len(rows),'unique_source_frames':len(needed),'selected_source_frame_range_inclusive':[indices[0],indices[-1]],'max_absolute_sampling_error_ms':max(abs(r['sampling_error_ms']) for r in rows),'input_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'changes':['audio removed','nearest source PTS sampled to 30 fps; ties choose earlier','H264 CRF18; original dimensions retained; no interpolation'],'preparation_seconds':time.perf_counter()-started,'evaluation_mode':'offline file processing; not a realtime or 3D-accuracy measurement'}
(out/'input-manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'source-pts.json').write_text(json.dumps({'stream':metadata,'frames':frame_pts},indent=2),encoding='utf-8')
print(json.dumps({'name':args.name,'frames':len(rows),'input_sha256':meta['input_sha256'],'preparation_seconds':meta['preparation_seconds']}),flush=True)
