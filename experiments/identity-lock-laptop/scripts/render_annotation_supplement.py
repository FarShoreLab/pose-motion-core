from isolation import BASE,ROOT
import json
import av
from PIL import Image,ImageDraw,ImageFont

def main():
    src=ROOT/'outputs/basketball-botsort-v1-model448'
    rs=[json.loads(x) for x in (src/'frame-decisions.jsonl').read_text().splitlines()]
    wanted=[25,26,27,28,29,86,87,88,90,179,180,182,186,188,200]
    out=ROOT/'diagnostics/annotation-supplement';out.mkdir(exist_ok=False)
    font=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',14)
    idx=0
    with av.open(str(BASE/'outputs/r2_occlusion_basketball/input_30fps.mp4')) as v:
        for i,f in enumerate(v.decode(video=0)):
            if i not in wanted:continue
            im=f.to_image();r=rs[i];ids={int(t[-1]):int(t[4]) for t in r['botsort_tracks_xyxy_id_conf_cls_detidx']}
            tile=Image.new('RGB',(1820,248),'#101820');d=ImageDraw.Draw(tile)
            tile.paste(im.resize((320,184)),(0,40));d.text((5,5),f'ALL DETECTIONS F{i}',font=font,fill='white')
            for j,b in enumerate(r['raw_detections_xyxy_conf_cls']):
                x=325+j*105;box=[max(0,int(b[0])),max(0,int(b[1])),min(640,int(b[2])),min(368,int(b[3]))]
                crop=im.crop(box);crop.thumbnail((100,180));tile.paste(crop,(x,45))
                d.text((x,5),f'd{j} ID{ids.get(j,"-")}',font=font,fill='#7be5ff')
                d.text((x,26),f'{b[4]:.2f}',font=font,fill='white')
            if idx%4==0:page=Image.new('RGB',(1820,992),'#101820')
            page.paste(tile,(0,(idx%4)*248))
            if idx%4==3 or idx==len(wanted)-1:page.save(out/f'all-candidates-page-{idx//4}.jpg',quality=95)
            idx+=1
    print(str(out))
if __name__=='__main__':main()
