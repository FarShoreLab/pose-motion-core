from isolate_env import ROOT
import av,cv2,csv,json,time
from fractions import Fraction
import numpy as np
dest=ROOT/'deliverables/round2';dest.mkdir(exist_ok=True)
MPEDGES=[(11,12),(11,13),(13,15),(12,14),(14,16),(11,23),(12,24),(23,24),(23,25),(25,27),(27,29),(29,31),(27,31),(24,26),(26,28),(28,30),(30,32),(28,32),(0,11),(0,12)]
GVEDGES=[(0,1),(0,2),(0,3),(1,4),(4,7),(7,10),(2,5),(5,8),(8,11),(3,6),(6,9),(9,12),(12,15),(12,13),(13,16),(16,18),(18,20),(12,14),(14,17),(17,19),(19,21)]
COLORS=[(255,210,40),(70,225,100),(225,140,245)]
def text(im,s,xy,color=(230,230,230),size=.5):cv2.putText(im,s,xy,0,size,color,1,cv2.LINE_AA)
def skeleton(im,xy,edges,color,conf=None):
    for a,b in edges:
        if np.isfinite(xy[[a,b]]).all():
            p=np.clip(xy[[a,b]],-4000,4000).astype(int);col=(50,80,255) if conf is not None and min(conf[a],conf[b])<.5 else color
            cv2.line(im,tuple(p[0]),tuple(p[1]),col,2,cv2.LINE_AA)
    for p in xy:
        if np.isfinite(p).all():cv2.circle(im,tuple(np.clip(p,-4000,4000).astype(int)),2,color,-1,cv2.LINE_AA)
def panel3(points,center,edges,color):
    im=np.full((360,480,3),(27,23,20),np.uint8);rel=points-center;rel=rel.copy();rel[:,1]*=-1
    yaw=np.deg2rad(35);elev=np.deg2rad(12);rotation=np.array([[np.cos(yaw),0,np.sin(yaw)],[np.sin(elev)*np.sin(yaw),np.cos(elev),-np.sin(elev)*np.cos(yaw)]])
    xy=rel@rotation.T*np.array([135,-135])+[240,175];skeleton(im,xy,edges,color)
    text(im,'Pelvis centered / fixed view / shared scale',(15,340),size=.45)
    return im
allresults=[]
specs=json.loads((ROOT/'scripts_v2/clips.json').read_text(encoding='utf-8'))
for spec in specs:
    begin=time.perf_counter();out=ROOT/'outputs'/spec['name'];mp=np.load(out/'mediapipe_raw.npz');gv=np.load(out/'gvhmr_predictions.npz')
    meta=json.loads((out/'input-manifest.json').read_text(encoding='utf-8'));diag=json.loads((out/'extended-diagnostics.json').read_text(encoding='utf-8'));maps=list(csv.DictReader((out/'frame-map.csv').open()))
    m2=mp['normalized'];m3=mp['world'][:,:,:3];filename=spec['name']+'-raw-and-post.mp4';target=dest/filename;snaps={0,len(maps)//3,2*len(maps)//3,len(maps)-1}
    with av.open(str(out/'input_30fps.mp4')) as reader,av.open(str(target),'w') as writer:
        writer.metadata.update({'title':spec['name']+' MediaPipe raw / GVHMR raw / GVHMR official postprocess','artist':spec['author'],'copyright':spec['license']+' '+spec['license_url'],'comment':'Source '+spec['source_page']+'; trimmed, sampled to30fps, re-encoded, pose overlays added. No 3D ground truth.'})
        stream=writer.add_stream('libx264',rate=30);stream.width=1440;stream.height=820;stream.pix_fmt='yuv420p';stream.options={'crf':'20','preset':'fast'}
        for i,frame in enumerate(reader.decode(video=0)):
            original=frame.to_ndarray(format='bgr24');h,w=original.shape[:2];scale=min(480/w,270/h);rw,rh=round(w*scale),round(h*scale);offset=np.array([(480-rw)//2,(270-rh)//2]);photo=np.zeros((270,480,3),np.uint8);photo[offset[1]:offset[1]+rh,offset[0]:offset[0]+rw]=cv2.resize(original,(rw,rh))
            canvas=np.zeros((820,1440,3),np.uint8);joints=[m3[i],gv['raw_incam_joints22'][i],gv['official_postprocessed_incam_joints22'][i]];centers=[m3[i,[23,24]].mean(0),joints[1][0],joints[2][0]]
            titles=['MediaPipe 1.1.0 | RAW VIDEO','GVHMR | RAW prediction','GVHMR | OFFICIAL postprocess']
            for c in range(3):
                tile=photo.copy()
                if c==0:xy=m2[i,:,:2]*[rw,rh]+offset;edges=MPEDGES;conf=np.minimum(m2[i,:,3],m2[i,:,4])
                else:proj=joints[c]@gv['K_fullimg'][i].T;xy=proj[:,:2]/proj[:,2:3]*[rw/w,rh/h]+offset;edges=GVEDGES;conf=None
                skeleton(tile,xy,edges,COLORS[c],conf);canvas[40:310,c*480:(c+1)*480]=tile;text(canvas,titles[c],(c*480+12,26),COLORS[c],.52)
                text(canvas,'Original output; no external filter' if c==0 else ('Before official output postprocess' if c==1 else 'Official translation correction + IK'),(c*480+12,332),COLORS[c],.45)
                canvas[350:710,c*480:(c+1)*480]=panel3(joints[c],centers[c],edges,COLORS[c])
            row=maps[i];text(canvas,f"{spec['name']} | frame {i} | input {float(row['input_seconds']):.3f}s | selected source frame {row['source_frame']} at {float(row['source_seconds']):.3f}s",(15,738),size=.52)
            if meta.get('camera_assumption_warning'):notice='CAMERA FALLBACK: SimpleVO failed; static assumption. Global motion is not validated.';color=(60,190,255)
            else:notice='Camera: '+('SimpleVO estimated rotation, no calibration/ground truth' if diag['camera_mode']=='simplevo' else 'explicit static-camera assumption; no calibration');color=(190,190,190)
            text(canvas,notice,(15,762),color,.5)
            text(canvas,f"Source: {spec['author']} | {spec['license']} | {meta['source_fps']:.3f} -> 30 fps nearest-PTS, no interpolation",(15,786),size=.5)
            text(canvas,'OFFLINE review / no 3D accuracy claim / red MediaPipe edges: min(visibility,presence) < 0.5 / source URLs in accompanying manifest',(15,808),size=.46)
            if i in snaps:cv2.imwrite(str(out/f'delivery-frame-{i:04d}.jpg'),canvas)
            vf=av.VideoFrame.from_ndarray(canvas,format='bgr24');vf.pts=i;vf.time_base=Fraction(1,30)
            for packet in stream.encode(vf):writer.mux(packet)
        for packet in stream.encode():writer.mux(packet)
    with av.open(str(target)) as c:
        pts=[float(f.pts*f.time_base) for f in c.decode(video=0)]
    assert len(pts)==len(maps) and np.allclose(pts,np.arange(len(maps))/30,atol=1e-7)
    result={'clip':spec['name'],'filename':filename,'frames':len(pts),'duration_seconds':len(pts)/30,'render_and_decode_validation_seconds':time.perf_counter()-begin,'source':spec['source_page'],'license':spec['license'],'license_url':spec['license_url'],'changes':'trimmed, nearest-PTS30fps sampling, re-encoded, pose overlays and separate3D views; aspect ratio preserved'}
    allresults.append(result);print(json.dumps(result),flush=True)
(ROOT/'round2-report/delivery-videos.json').write_text(json.dumps(allresults,indent=2),encoding='utf-8')
