from isolation import BASE,PRIOR,ROOT
import json
from collections import Counter
import av
from PIL import Image,ImageDraw,ImageFont

def main():
    source=PRIOR/'outputs/basketball-botsort-v1-model448'
    raw=[json.loads(x) for x in (source/'frame-decisions.jsonl').read_text().splitlines()]
    gt=json.loads((PRIOR/'diagnostics/visual-evaluation/per-frame-visual-annotations.json').read_text())
    out=ROOT/'outputs/r2_occlusion_basketball-v1';review=ROOT/'automatic-identity-review';review.mkdir(exist_ok=False)
    methods=['no_conflict_protection','causal_conflict_freeze','offline_tracklet_reconnect']
    decisions={m:[json.loads(x) for x in (out/(m+'.jsonl')).read_text().splitlines()] for m in methods}
    details=[];unreviewed=set();metrics={}
    for method,rows in decisions.items():
        for i,(r,g) in enumerate(zip(rows,gt)):
            d=r['target_detection'];label='unresolved' if d is None else 'red_target' if d==g['primary_target_detection'] else 'UNREVIEWED'
            if label=='UNREVIEWED':unreviewed.add(i)
            details.append({'method':method,'frame':i,'detection':d,'identity_label':label,
                'clear_target_opportunity':g['clear_target_detection_available'],'reference_detection':g['primary_target_detection'],
                'reference_detection_quality':g['target_detection_quality']})
        metrics[method]=dict(Counter(x['identity_label'] for x in details if x['method']==method))
    (review/'preliminary-labels.json').write_text(json.dumps(details,indent=2),encoding='utf-8')
    (review/'unreviewed-frames.json').write_text(json.dumps(sorted(unreviewed)),encoding='utf-8')
    font=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',15);small=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',13)
    colors=['#ff5252','#51d9ff','#d28fff'];seen=0;page=None
    with av.open(str(BASE/'outputs/r2_occlusion_basketball/input_30fps.mp4')) as v:
        for i,f in enumerate(v.decode(video=0)):
            if i not in unreviewed:continue
            im=Image.new('RGB',(640,418),'#101820');im.paste(f.to_image(),(0,50));d=ImageDraw.Draw(im)
            ids=[decisions[m][i]['target_detection'] for m in methods]
            reference=gt[i]['primary_target_detection']
            d.text((5,4),f'F{i:03d} N/C/O={ids} | AI reference R={reference}',font=font,fill='white')
            d.text((5,25),gt[i]['target_detection_quality']+' | N red; C cyan; O purple; reference green',font=small,fill='white')
            if reference is not None:
                b=raw[i]['raw_detections_xyxy_conf_cls'][reference];d.rectangle((b[0],b[1]+50,b[2],b[3]+50),outline='#57ff71',width=5)
            for j,index in enumerate(ids):
                if index is None:continue
                b=raw[i]['raw_detections_xyxy_conf_cls'][index]
                d.rectangle((b[0]+j,b[1]+50+j,b[2]+j,b[3]+50+j),outline=colors[j],width=2)
                d.text((b[0],max(50,b[1]+30)+j*16),f'{"NCO"[j]} D{index}',font=font,fill=colors[j],stroke_width=1,stroke_fill='black')
            if seen%9==0:page=Image.new('RGB',(1920,1254),'#101820')
            page.paste(im,((seen%3)*640,((seen%9)//3)*418))
            if seen%9==8 or seen==len(unreviewed)-1:page.save(review/f'new-selections-{seen//9:02d}.jpg',quality=94)
            seen+=1
    print(json.dumps({'preliminary_counts':metrics,'unreviewed_frames':sorted(unreviewed),'pages':(seen+8)//9},indent=2))
if __name__=='__main__':main()
