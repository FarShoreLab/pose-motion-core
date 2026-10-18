from isolate_env import ROOT as root
import argparse,av,csv,json,pathlib,time,os
from fractions import Fraction
import cv2,numpy as np

p=argparse.ArgumentParser();p.add_argument('--name',default='smoke');p.add_argument('--mediapipe-only',action='store_true');args=p.parse_args();out=root/'outputs'/args.name
mp=np.load(out/'mediapipe_raw.npz');mp2=mp['normalized'];mp3=mp['world'];meta=json.loads((out/'input-manifest.json').read_text())
g=None if args.mediapipe_only else np.load(out/'gvhmr_predictions.npz')
mpedges=[(11,12),(11,13),(13,15),(12,14),(14,16),(11,23),(12,24),(23,24),(23,25),(25,27),(27,29),(29,31),(27,31),(24,26),(26,28),(28,30),(30,32),(28,32),(0,11),(0,12)]
gedges=[(0,1),(0,2),(0,3),(1,4),(4,7),(7,10),(2,5),(5,8),(8,11),(3,6),(6,9),(9,12),(12,15),(12,13),(13,16),(16,18),(18,20),(12,14),(14,17),(17,19),(19,21)]
cyan=(255,210,40);green=(70,225,100);red=(60,80,255)
def text(image,s,xy,color=(230,230,230),size=.55):cv2.putText(image,s,xy,cv2.FONT_HERSHEY_SIMPLEX,size,color,1,cv2.LINE_AA)
def skeleton(image,xy,edges,color,confidence=None):
    for a,b in edges:
        if np.isfinite(xy[[a,b]]).all():
            points=np.clip(xy[[a,b]],-4000,4000).astype(int)
            c=red if confidence is not None and min(confidence[a],confidence[b])<.5 else color
            cv2.line(image,tuple(points[0]),tuple(points[1]),c,2,cv2.LINE_AA)
    for point in xy:
        if np.isfinite(point).all():cv2.circle(image,tuple(np.clip(point,-4000,4000).astype(int)),3,color,-1,cv2.LINE_AA)
def panel3d(joints,center,edges,label,color):
    panel=np.full((400,640,3),(28,23,20),dtype=np.uint8)
    relative=joints-center;relative=relative.copy();relative[:,1]*=-1
    yaw=np.deg2rad(35);elev=np.deg2rad(12)
    rot=np.array([[np.cos(yaw),0,np.sin(yaw)],[np.sin(elev)*np.sin(yaw),np.cos(elev),-np.sin(elev)*np.cos(yaw)]])
    xy=relative@rot.T*np.array([140,-140])+[320,220]
    for i,(label_axis,col) in enumerate(zip(['X','Y up','Z depth'],[(90,90,240),(90,240,90),(240,130,70)])):
        v=rot[:,i]*np.array([55,-55]);a=np.array([65,320]);cv2.arrowedLine(panel,tuple(a),tuple((a+v).astype(int)),col,1,cv2.LINE_AA);text(panel,label_axis,tuple((a+v+[3,0]).astype(int)),col,.4)
    skeleton(panel,xy,edges,color);text(panel,label,(15,25),color,.6);text(panel,'Pelvis centered | shared meter scale | fixed 3D view',(15,382),size=.5)
    return panel
name='mediapipe-review.mp4' if g is None else 'raw-comparison.mp4'
dest=out/name;snaps=[];start=time.perf_counter();count=0
with av.open(str(out/'input_30fps.mp4')) as reader,av.open(str(dest),'w') as writer:
    height=460 if g is None else 840
    stream=writer.add_stream('libx264',rate=30);stream.width=1280;stream.height=height;stream.pix_fmt='yuv420p';stream.options={'crf':'20','preset':'fast'}
    for i,frame in enumerate(reader.decode(video=0)):
        original=frame.to_ndarray(format='bgr24');h,w=original.shape[:2];scale=min(640/w,360/h);rw,rh=round(w*scale),round(h*scale);offset=np.array([(640-rw)//2,(360-rh)//2]);blank=np.zeros((360,640,3),np.uint8);blank[offset[1]:offset[1]+rh,offset[0]:offset[0]+rw]=cv2.resize(original,(rw,rh));left=blank.copy()
        skeleton(left,mp2[i,:,:2]*[rw,rh]+offset,mpedges,cyan,mp2[i,:,3]);text(left,'MediaPipe 1.1.0 | raw VIDEO output',(12,26),cyan)
        center=(mp3[i,23,:3]+mp3[i,24,:3])/2
        mpview=panel3d(mp3[i,:,:3],center,mpedges,'MediaPipe raw world landmarks',cyan)
        canvas=np.zeros((height,1280,3),dtype=np.uint8)
        if g is None:
            canvas[20:380,:640]=left;canvas[:400,640:]=mpview
        else:
            joints=g['raw_incam_joints22'][i];K=g['K_fullimg'][i];proj=joints@K.T;xy=proj[:,:2]/proj[:,2:3]
            right=blank.copy();skeleton(right,xy*[rw/w,rh/h]+offset,gedges,green);text(right,'GVHMR | raw prediction projected',(12,26),green)
            canvas[:360,:640]=left;canvas[:360,640:]=right;canvas[380:780,:640]=mpview;canvas[380:780,640:]=panel3d(joints,joints[0],gedges,'GVHMR raw camera joints',green)
        if meta.get('camera_assumption_warning'):text(canvas,'EXPLORATORY: static-camera assumption; camera estimation failed. World motion not validated.',(15,height-56),(80,190,255),.55)
        text(canvas,f'Offline | input {i/30:.3f}s | source {meta["source_start_normalized_seconds"]+meta["original_first_pts_seconds"]+i/30:.3f}s | no 3D ground truth',(15,height-34),size=.55)
        text(canvas,f"Source: {meta['author']} | {meta['license']} | sampled {meta['source_fps']:.3f} to 30 fps",(15,height-10),size=.5)
        if i in {0,len(mp2)//3,2*len(mp2)//3,len(mp2)-1}:snaps.append(canvas.copy())
        vf=av.VideoFrame.from_ndarray(canvas,format='bgr24');vf.pts=i;vf.time_base=Fraction(1,30)
        for packet in stream.encode(vf):writer.mux(packet)
        count+=1
    for packet in stream.encode():writer.mux(packet)
assert count==len(mp2)
for i,s in enumerate(snaps):cv2.imwrite(str(out/(('mediapipe' if g is None else 'comparison')+f'-frame-{i}.jpg')),s)
def flexion(points,ids):
    a,b,c=points[:,ids[0]],points[:,ids[1]],points[:,ids[2]];u=a-b;v=c-b
    cosine=(u*v).sum(1)/(np.linalg.norm(u,axis=1)*np.linalg.norm(v,axis=1));return 180-np.degrees(np.arccos(np.clip(cosine,-1,1)))
series={'MediaPipe left knee':flexion(mp3[:,:,:3],(23,25,27)),'MediaPipe right knee':flexion(mp3[:,:,:3],(24,26,28))}
if g is not None:
    for side,ids in [('left',(1,4,7)),('right',(2,5,8))]:
        for label in ['raw','official_postprocessed']:series['GVHMR '+label+' '+side+' knee']=flexion(g[label+'_incam_joints22'],ids)
diagnostics={'frames':count,'render_seconds':time.perf_counter()-start,'video':str(dest),'motion':meta.get('motion','front-facing overhead squat'),'missing_mediapipe_frames':int((~np.isfinite(mp3[:,0,0])).sum()),'mediapipe_major_joint_visibility_below_0_5_frames':int((mp2[:,[11,12,13,14,15,16,23,24,25,26,27,28],3]<.5).any(axis=1).sum()),'knee_flexion_degrees':{k:{'min':float(np.nanmin(v)),'max':float(np.nanmax(v)),'range':float(np.nanmax(v)-np.nanmin(v))} for k,v in series.items()},'interpretation':'Internal motion diagnostics only; no 3D ground truth or accuracy claim. Original points and model parameters retained. MediaPipe has no world translation, so absolute foot slide cannot be compared.'}
if g is not None:
    diagnostics['camera_assumption_warning']=meta.get('camera_assumption_warning')
    raw=g['raw_incam_joints22'];post=g['official_postprocessed_incam_joints22'];glob=g['raw_global_joints22'];rawrel=raw-raw[:,[0]];postrel=post-post[:,[0]]
    diagnostics['gvhmr_raw_pelvis_depth_m']={'min':float(raw[:,0,2].min()),'max':float(raw[:,0,2].max())}
    diagnostics['gvhmr_max_pelvis_relative_joint_step_m']=float(np.linalg.norm(np.diff(rawrel,axis=0),axis=-1).max())
    diagnostics['official_postprocess_max_joint_change_m']=float(np.linalg.norm(postrel-rawrel,axis=-1).max())
    diagnostics['gvhmr_raw_ankle_horizontal_path_m']={label:float(np.linalg.norm(np.diff(glob[:,j][:,[0,2]],axis=0),axis=1).sum()) for label,j in [('left',7),('right',8)]}
    diagnostics['ankle_path_note']='Uncalibrated inferred world coordinates, entire clip, no contact ground truth; not measured foot-slide error.'
(out/('mediapipe-diagnostics.json' if g is None else 'comparison-diagnostics.json')).write_text(json.dumps(diagnostics,indent=2),encoding='utf-8')
with (out/'knee-flexion.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.writer(f);w.writerow(['input_seconds']+list(series));w.writerows([[i/30]+[float(v[i]) for v in series.values()] for i in range(count)])
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,ax=plt.subplots(figsize=(10,4))
for k,v in series.items():ax.plot(np.arange(count)/30,v,label=k,linestyle='--' if 'postprocessed' in k else '-')
ax.set(xlabel='Input time (s)',ylabel='3D knee flexion (degrees)',title='Raw motion range diagnostics; no ground-truth accuracy');ax.legend(fontsize=8);ax.grid(alpha=.2);fig.tight_layout();fig.savefig(out/'knee-flexion.png',dpi=160);plt.close(fig)
if g is not None:
    mp_rel=mp3[:,:,:3]-(mp3[:,23:24,:3]+mp3[:,24:25,:3])/2
    jointsets={'MediaPipe':(mp_rel,(23,24),(27,28)),'GVHMR raw':(rawrel,(1,2),(7,8)),'GVHMR official postprocess':(postrel,(1,2),(7,8))}
    fig,axes=plt.subplots(3,1,figsize=(11,9),sharex=True)
    motion_series={};diagnostics['temporal_motion_diagnostics']={}
    for label,(points,hips,ankles) in jointsets.items():
        hip_axis=points[:,hips[1]]-points[:,hips[0]]
        angle=np.arctan2(hip_axis[:,2],hip_axis[:,0])
        # Preserve gaps; unwrap each continuous valid run separately.
        valid=np.isfinite(angle);unwrapped=np.full_like(angle,np.nan)
        runs=np.split(np.where(valid)[0],np.where(np.diff(np.where(valid)[0])>1)[0]+1)
        for run in runs:
            if len(run):unwrapped[run]=np.degrees(np.unwrap(angle[run]))
        steps=np.linalg.norm(np.diff(points,axis=0),axis=-1)
        axes[0].plot(np.arange(count)/30,unwrapped,label=label)
        axes[1].plot(np.arange(count)/30,points[:,ankles[0],2],label=label+' left')
        axes[2].plot(np.arange(count)/30,points[:,ankles[1],2],label=label+' right')
        motion_series[label+' hip_axis_degrees']=unwrapped
        motion_series[label+' left_ankle_relative_depth_m']=points[:,ankles[0],2]
        motion_series[label+' right_ankle_relative_depth_m']=points[:,ankles[1],2]
        yawstep=np.abs(np.diff(unwrapped))
        common_ids=[11,12,13,14,15,16,23,24,25,26,27,28] if label=='MediaPipe' else [16,17,18,19,20,21,1,2,4,5,7,8]
        centered=points-(points[:,hips[0]:hips[0]+1]+points[:,hips[1]:hips[1]+1])/2
        common_steps=np.linalg.norm(np.diff(centered[:,common_ids],axis=0),axis=-1)
        diagnostics['temporal_motion_diagnostics'][label]={'max_joint_step_m':float(np.nanmax(steps)),'common12_hip_centered_max_step_m':float(np.nanmax(common_steps)),'common12_hip_centered_p95_step_m':float(np.nanpercentile(common_steps,95)),'hip_axis_angle_span_degrees':float(np.nanmax(unwrapped)-np.nanmin(unwrapped)),'max_hip_axis_angle_step_degrees':float(np.nanmax(yawstep)),'hip_axis_steps_over_45_degrees':int((yawstep>45).sum()),'valid_orientation_frames':int(valid.sum())}
    for ax,ylabel in zip(axes,['Hip-axis angle (deg)','Left ankle relative Z (m)','Right ankle relative Z (m)']):ax.set_ylabel(ylabel);ax.grid(alpha=.2);ax.legend(fontsize=8)
    axes[0].set_title('Raw temporal depth and turn diagnostics; threshold flags are not verified errors')
    axes[-1].set_xlabel('Input time (s)');fig.tight_layout();fig.savefig(out/'depth-and-turn.png',dpi=160);plt.close(fig)
    with (out/'depth-and-turn.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['input_seconds']+list(motion_series));w.writerows([[i/30]+[float(v[i]) for v in motion_series.values()] for i in range(count)])
    fig,ax=plt.subplots(figsize=(7,6))
    for label in ['raw','official_postprocessed']:
        joints=g[label+'_global_joints22']
        for side,j in [('left',7),('right',8)]:
            points=joints[:,j][:,[0,2]];points=points-points[0]
            ax.plot(points[:,0],points[:,1],label=label+' '+side);ax.scatter(*points[0],s=20)
    ax.set(xlabel='Ankle X displacement from first frame (m)',ylabel='Ankle Z displacement from first frame (m)',title='GVHMR inferred world ankle paths; not foot-slide error');ax.axis('equal');ax.grid(alpha=.2);ax.legend(fontsize=8);fig.tight_layout();fig.savefig(out/'world-ankle-path.png',dpi=160);plt.close(fig)
    diagnostics['temporal_diagnostic_note']='Hip-axis projected heading is unreliable when the hip line points almost vertically in the image; a >45 degree per-frame flag is only a review cue. No external filter applied. Global ankle paths include intended movement; no verified contact intervals.'
    (out/'comparison-diagnostics.json').write_text(json.dumps(diagnostics,indent=2),encoding='utf-8')
print(json.dumps(diagnostics),flush=True)
