"""Readable, annotated actual-frame evidence; no fabricated frames and no model inference."""
from isolation import BASE,ROOT
import json,math
import av,numpy as np,torch
from PIL import Image,ImageDraw,ImageFont
from render_tracking_review import box,mp_box

def read(name):return [json.loads(x) for x in (ROOT/'outputs'/name/'frame-decisions.jsonl').read_text().splitlines()]
def main():
    out=ROOT/'evidence';out.mkdir(exist_ok=False)
    source=BASE/'outputs/r2_occlusion_basketball'
    bot=read('basketball-botsort-v1-model448');deep=read('basketball-deepocsort-gallery-v3');guard=read('basketball-botsort-gallery-v3')
    annotations=json.loads((ROOT/'diagnostics/visual-evaluation/per-frame-visual-annotations.json').read_text())
    detailed=json.loads((ROOT/'diagnostics/visual-evaluation/per-attempt-identity-decisions.json').read_text())
    labels={(r['attempt'],r['frame']):r['identity'] for r in detailed}
    old=torch.load(source/'bbox.pt',map_location='cpu',weights_only=True)['bbx_xyxy'].numpy()
    mp=np.load(source/'mediapipe_raw.npz',allow_pickle=False)['normalized']
    font=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',15)
    small=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',13)
    colors={'red_target':'#47ff83','wrong_blue_person':'#ff5252','ambiguous_people_overlap':'#ffbd57','missing':'#aaaaaa'}
    path=out/'basketball-final-annotated-comparison.mp4'
    v=av.open(str(path),'w');s=v.add_stream('libx264',rate=30);s.width=1280;s.height=912;s.pix_fmt='yuv420p';s.options={'crf':'20','preset':'medium'}
    with av.open(str(source/'input_30fps.mp4')) as src:
        for i,frame in enumerate(src.decode(video=0)):
            raw=frame.to_image();im=Image.new('RGB',(1280,912),'#101820');d=ImageDraw.Draw(im)
            layouts=[(0,0),(640,0),(0,440),(640,440)]
            texts=[('ORIGINAL GVHMR ID2 + MP',annotations[i]['old_gvhmr_identity']),
                ('BoT-SORT + genuine ReID | initial ID2',labels[('basketball-botsort-v1-model448-raw-seed-id2',i)]),
                ('Deep OC-SORT | same detections / embeddings',labels[('basketball-deepocsort-gallery-v3-raw-seed-id2',i)]),
                ('Protected gallery v3 | NOT ACCEPTED FOR USE',labels[('basketball-botsort-gallery-v3',i)])]
            for (x,y),(title,label) in zip(layouts,texts):
                im.paste(raw,(x,y+48));d.text((x+6,y+4),title,font=font,fill='white')
                d.text((x+6,y+25),f'F{i:03d}  {i/30:.3f}s  {label}',font=font,fill=colors.get(label,'#ffbd57'))
            box(d,old[i],'GV 2','#ffd54f',offset=(0,48));box(d,mp_box(mp[i],640,368),'MP','#ed6bf5',offset=(0,48))
            for rr,(x,y) in [(bot[i],layouts[1]),(deep[i],layouts[2])]:
                t=next((t for t in rr['botsort_tracks_xyxy_id_conf_cls_detidx'] if int(t[4])==2),None)
                if t is not None:box(d,t[:4],'RAW ID2','#49cdf0',offset=(x,y+48))
            r=guard[i];box(d,r['display_bbox_xyxy'],'VALID' if r['valid'] else 'PREDICTED / INVALID',
                '#47ff83' if r['valid'] else '#ffbd57',offset=(640,488),dashed=not r['valid'])
            d.text((646,858),f'{r["state"]} | {r["reason"]} | hints 0',font=small,fill='white')
            if i==112:d.text((646,838),'CAVEAT: accepted target box truncates the legs',font=font,fill='#ff5252')
            d.text((6,882),'Assistant visual annotations; NOT independent human GT. All 207 input frames at 30fps. Offline processing.',font=small,fill='white')
            d.text((6,898),'Azorbli / Basketball_(4).ogv / Wikimedia Commons / CC BY-SA 4.0. No real-time claim.',font=small,fill='white')
            if i in [0,5,35,69,88,90,112,138,195]:im.save(out/f'annotated-frame-{i:03d}.jpg',quality=93)
            vf=av.VideoFrame.from_ndarray(np.asarray(im),format='rgb24');vf.pts=i
            for packet in s.encode(vf):v.mux(packet)
    for packet in s.encode():v.mux(packet)
    v.close()
    with av.open(str(path)) as check:count=sum(1 for _ in check.decode(video=0))
    assert count==207
    (out/'basketball-video-verification.json').write_text(json.dumps({'video':str(path),'bytes':path.stat().st_size,
        'decoded_frames':count,'fps':30,'contains_all_input_frames':True,'interpolated_images':False},indent=2))
    print(json.dumps({'video':str(path),'bytes':path.stat().st_size,'frames':count}))
if __name__=='__main__':main()
