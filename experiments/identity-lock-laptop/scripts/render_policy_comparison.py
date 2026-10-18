"""All 207 real input frames, same source, six frozen tracking/policy outputs."""
from isolation import BASE,ROOT
import json
import av,numpy as np
from PIL import Image,ImageDraw,ImageFont
from render_tracking_review import box

def main():
    definitions=[
        ('basketball-botsort-v1-model448','RAW BoT-SORT initial ID2',True),
        ('basketball-botsort-v1-model448','Guard v1 / 448px (5 accepted)',False),
        ('basketball-botsort-gallery-v2','Guard v2 (17 accepted)',False),
        ('basketball-deepocsort-gallery-v3','RAW Deep OC-SORT initial ID2',True),
        ('basketball-botsort-gallery-v3','Guard v3 + BoT (83 accepted)',False),
        ('basketball-deepocsort-gallery-v3','Guard v3 + Deep (83 accepted)',False)]
    data={name:[json.loads(x) for x in (ROOT/'outputs'/name/'frame-decisions.jsonl').read_text().splitlines()] for name,_,_ in definitions}
    details=json.loads((ROOT/'diagnostics/visual-evaluation/per-attempt-identity-decisions.json').read_text())
    labels={(r['attempt'],r['frame']):r['identity'] for r in details}
    colors={'red_target':'#47ff83','wrong_blue_person':'#ff5252','ambiguous_people_overlap':'#ffbd57','missing':'#aaaaaa'}
    font=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',16)
    small=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',13)
    path=ROOT/'evidence/basketball-same-input-six-methods.mp4'
    assert not path.exists()
    v=av.open(str(path),'w');s=v.add_stream('libx264',rate=30)
    s.width,s.height,s.pix_fmt=1920,920,'yuv420p';s.options={'crf':'21','preset':'medium'}
    with av.open(str(BASE/'outputs/r2_occlusion_basketball/input_30fps.mp4')) as src:
        for i,f in enumerate(src.decode(video=0)):
            raw=f.to_image();im=Image.new('RGB',(1920,920),'#101820');d=ImageDraw.Draw(im)
            for j,(name,title,raw_id) in enumerate(definitions):
                x,y=(j%3)*640,(j//3)*440;r=data[name][i]
                label=labels[(name+('-raw-seed-id2' if raw_id else ''),i)]
                im.paste(raw,(x,y+48));d.text((x+6,y+4),title,font=font,fill='white')
                d.text((x+6,y+26),f'F{i:03d} {i/30:.3f}s | {label}',font=font,fill=colors[label])
                if raw_id:
                    t=next((t for t in r['botsort_tracks_xyxy_id_conf_cls_detidx'] if int(t[4])==2),None)
                    if t is not None:box(d,t[:4],'RAW ID2','#49cdf0',offset=(x,y+48))
                else:
                    box(d,r['display_bbox_xyxy'],'OBSERVED' if r['valid'] else 'INVALID PREDICTION',
                        '#47ff83' if r['valid'] else '#ffbd57',offset=(x,y+48),dashed=not r['valid'])
                    d.text((x+6,y+418),r['state']+' | '+r['reason'],font=small,fill='white')
            d.text((6,882),'FAILED EXPERIMENT | Assistant frame-by-frame labels, NOT independent human ground truth | One ReID encoder; no new pose inference',font=small,fill='white')
            d.text((6,902),'Azorbli / Basketball_(4).ogv / Wikimedia Commons / CC BY-SA 4.0 | Same 207 input frames, 173 unique source frames | F112: v3 accepts a truncated target box',font=small,fill='white')
            if i in [5,18,88,112,138]:im.save(ROOT/f'evidence/six-methods-frame-{i:03d}.jpg',quality=93)
            vf=av.VideoFrame.from_ndarray(np.asarray(im),format='rgb24');vf.pts=i
            for packet in s.encode(vf):v.mux(packet)
    for packet in s.encode():v.mux(packet)
    v.close()
    with av.open(str(path)) as check:decoded=sum(1 for _ in check.decode(video=0))
    assert decoded==207
    result={'video':path.name,'bytes':path.stat().st_size,'decoded_frames':decoded,'fps':30,'actual_frames':True,'model_inference':False}
    (ROOT/'evidence/six-methods-video-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))
if __name__=='__main__':main()
