"""Visual annotation aid. Color orders thumbnails only; it never supplies tracking or ground truth."""
from isolation import BASE, ROOT
import json, math
import av, cv2, numpy as np
from PIL import Image,ImageDraw,ImageFont

def main():
    src=ROOT/'outputs/basketball-botsort-v1-model448'
    out=ROOT/'diagnostics/detection-annotation-sheets'
    out.mkdir(exist_ok=False)
    rows=[json.loads(x) for x in (src/'frame-decisions.jsonl').read_text().splitlines()]
    font=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',14)
    proposed=[]
    with av.open(str(BASE/'outputs/r2_occlusion_basketball/input_30fps.mp4')) as v:
        for i,f in enumerate(v.decode(video=0)):
            im=f.to_image(); rgb=np.asarray(im); hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
            red=((hsv[:,:,0]<12)|(hsv[:,:,0]>170))&(hsv[:,:,1]>90)&(hsv[:,:,2]>70)
            dets=rows[i]['raw_detections_xyxy_conf_cls']; ids={int(t[-1]):int(t[4]) for t in rows[i]['botsort_tracks_xyxy_id_conf_cls_detidx']}
            rank=[]
            for j,b in enumerate(dets):
                x1,y1,x2,y2=np.rint(b[:4]).astype(int); x1,y1=max(0,x1),max(0,y1);x2,y2=min(640,x2),min(368,y2)
                patch=red[y1:y2,x1:x2]
                rank.append((float(patch.sum())/max(float(patch.size)**.65,1),j))
            order=[j for _,j in sorted(rank,reverse=True)[:3]]
            proposed.append({'frame':i,'proposal_order':order,'ranker':'red-pixel ordering for visual review only, NOT GT or tracking input'})
            tile=Image.new('RGB',(640,248),'#101820');d=ImageDraw.Draw(tile)
            tile.paste(im.resize((320,184)),(0,34))
            d.text((5,5),f'F{i:03d} | top 3 color-ordered candidates; reviewer selects identity',font=font,fill='white')
            for k,j in enumerate(order):
                b=dets[j];box=[max(0,int(b[0])),max(0,int(b[1])),min(640,int(b[2])),min(368,int(b[3]))]
                crop=im.crop(box);crop.thumbnail((100,180));tile.paste(crop,(325+k*105,54))
                d.text((325+k*105,33),f'd{j} ID{ids.get(j,"-")}',font=font,fill=['#47ff83','#ffe364','#ef9cff'][k])
                d.text((325+k*105,231),f'conf {b[4]:.2f}',font=font,fill='white')
                d.rectangle((b[0]/2,b[1]/2+34,b[2]/2,b[3]/2+34),outline=['#47ff83','#ffe364','#ef9cff'][k],width=1)
            if i%12==0:page=Image.new('RGB',(1920,992),'#101820')
            page.paste(tile,((i%3)*640,((i%12)//3)*248))
            if i%12==11 or i==len(rows)-1:page.save(out/f'detections-{i//12*12:03d}-{i:03d}.jpg',quality=94)
    (out/'thumbnail-order.json').write_text(json.dumps(proposed,indent=2),encoding='utf-8')
    print(json.dumps({'frames':len(rows),'sheets':math.ceil(len(rows)/12),'path':str(out)}))

if __name__=='__main__':main()
