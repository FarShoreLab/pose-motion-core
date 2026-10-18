"""All-frame six-clip tracking replay plus explicitly sampled visual QA, no pose inference."""
from isolation import BASE,ROOT
import json,math
from pathlib import Path
import av,numpy as np,torch
from PIL import Image,ImageDraw,ImageFont

def drawbox(d,b,color,scale,offset,label):
    if b is None:return
    xy=[float(x)*scale+(offset[0] if i%2==0 else offset[1]) for i,x in enumerate(b)]
    if xy[2]<=xy[0] or xy[3]<=xy[1]:return
    d.rectangle(xy,outline=color,width=2)
    d.text((xy[0],max(offset[1],xy[1]-16)),label,fill=color,font=FONT)

FONT=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',14)
SMALL=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',12)

def main():
    out=ROOT/'evidence/holdouts';out.mkdir(exist_ok=False)
    path=out/'six-holdout-tracking-replays.mp4'
    video=av.open(str(path),'w');stream=video.add_stream('libx264',rate=30)
    stream.width,stream.height,stream.pix_fmt=1280,544,'yuv420p';stream.options={'crf':'22','preset':'medium'}
    count=0;summary=[]
    for attempt in sorted((ROOT/'outputs').glob('holdout-r2_*-v3')):
        manifest=json.loads((attempt/'run-manifest.json').read_text());clip=manifest['clip']
        rs=[json.loads(x) for x in (attempt/'frame-decisions.jsonl').read_text().splitlines()]
        sm=json.loads((attempt/'tracking-summary.json').read_text());source=BASE/'outputs'/clip
        old=torch.load(source/'bbox.pt',map_location='cpu',weights_only=True)['bbx_xyxy'].numpy()
        old_id=json.loads((source/'bbox-metrics.json').read_text())['selected_track_id']
        initial_id=rs[0]['track_id'];samples=set(np.linspace(0,len(rs)-1,12).round().astype(int).tolist())
        invalid=[r['input_frame'] for r in rs if not r['valid']]
        transitions=[i for i in range(1,len(rs)) if rs[i]['valid']!=rs[i-1]['valid']]
        samples.update(transitions[:6]);samples.update(transitions[-6:]);samples=sorted(samples)
        pages=[];sample_i=0;page=None
        with av.open(str(source/'input_30fps.mp4')) as src:
            for i,f in enumerate(src.decode(video=0)):
                raw=f.to_image();scale=min(640/raw.width,448/raw.height);scaled=raw.resize((round(raw.width*scale),round(raw.height*scale)))
                r=rs[i];im=Image.new('RGB',(1280,544),'#101820');d=ImageDraw.Draw(im)
                locs=[((640-scaled.width)//2,48),(640+(640-scaled.width)//2,48)]
                for loc in locs:im.paste(scaled,loc)
                d.text((6,5),f'{clip} | frame {i}/{len(rs)-1} | ORIGINAL bbox',font=FONT,fill='white')
                d.text((646,5),f'Frozen v3 | {r["state"]} | observed={r["valid"]}',font=FONT,fill='#47ff83' if r['valid'] else '#ffbd57')
                d.text((646,25),'cyan = raw initial ID; green = guarded target; orange = INVALID prediction',font=SMALL,fill='white')
                drawbox(d,old[i],'#ffd54f',scale,locs[0],f'old {old_id}')
                t=next((t for t in r['botsort_tracks_xyxy_id_conf_cls_detidx'] if int(t[4])==initial_id),None)
                if t is not None:drawbox(d,t[:4],'#49cdf0',scale,locs[1],f'raw {initial_id}')
                drawbox(d,r['display_bbox_xyxy'],'#47ff83' if r['valid'] else '#ffbd57',scale,locs[1],f'target {r["track_id"]}' if r['valid'] else 'INVALID')
                info=manifest['input_manifest'];d.text((6,500),f'{info["author"]} / Wikimedia Commons / {info["license"]}',font=FONT,fill='white')
                d.text((6,521),'Tracking regression only; all original input frames. No new pose inference. Valid flag is not verified identity accuracy.',font=SMALL,fill='white')
                vf=av.VideoFrame.from_ndarray(np.asarray(im),format='rgb24');vf.pts=count
                for packet in stream.encode(vf):video.mux(packet)
                count+=1
                if i in samples:
                    tile=Image.new('RGB',(640,288),'#101820');tile.paste(im.resize((640,272)),(0,0))
                    ImageDraw.Draw(tile).text((5,274),f'{clip} F{i} | {r["reason"]}',font=SMALL,fill='white')
                    if sample_i%12==0:page=Image.new('RGB',(1920,1152),'#101820')
                    page.paste(tile,((sample_i%3)*640,((sample_i%12)//3)*288))
                    if sample_i%12==11 or sample_i==len(samples)-1:
                        pp=out/f'{clip}-qa-{sample_i//12}.jpg';page.save(pp,quality=93);pages.append(pp.name)
                    sample_i+=1
        summary.append({'clip':clip,'frames':len(rs),'valid_frames':sm['observed_valid_frames'],
            'valid_fraction':sm['observed_valid_frames']/len(rs),'invalid_frames':len(invalid),
            'reacquisitions':sm['reacquisitions'],'whole_run_seconds':sm['whole_run_seconds'],
            'detector_seconds':sm['detector_seconds'],'reid_seconds':sm['reid_seconds'],
            'association_seconds':sm['association_gmc_seconds'],'guard_seconds':sm['identity_guard_seconds'],
            'sampled_visual_qa_frames':samples,'qa_pages':pages,
            'all_frames_in_replay':True,'every_frame_visually_annotated':False,'identity_accuracy':'NOT MEASURED',
            'extra_keyframe_hints':0,'new_pose_inference':False,'config_tuned_after_holdout':False})
    for packet in stream.encode():video.mux(packet)
    video.close()
    with av.open(str(path)) as check:decoded=sum(1 for _ in check.decode(video=0))
    assert decoded==count
    (out/'holdout-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps({'video':str(path),'bytes':path.stat().st_size,'frames':count,'clips':summary},indent=2))
if __name__=='__main__':main()
