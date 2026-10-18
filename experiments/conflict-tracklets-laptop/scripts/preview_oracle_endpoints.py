from isolation import BASE,PRIOR,ROOT
import argparse,json
import av
from PIL import Image,ImageDraw,ImageFont

p=argparse.ArgumentParser();p.add_argument('--frames');p.add_argument('--batch',default='oracle-preview');a=p.parse_args()
frames=[int(x) for x in a.frames.split(',')] if a.frames else [18,19,20,31,32,33,73,74,75,114,115,116,141,142,143,189,190,191,196,197,198,204,205,206]
rows=[json.loads(x) for x in (PRIOR/'outputs/basketball-botsort-v1-model448/frame-decisions.jsonl').read_text().splitlines()]
out=ROOT/a.batch;out.mkdir(exist_ok=False)
font=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',16)
colors=['#ff4d4d','#5be4ff','#ffcd45','#75ff88','#e594ff','#f5ab67','#ffffff','#97b6ff']
page=None;count=0
with av.open(str(BASE/'outputs/r2_occlusion_basketball/input_30fps.mp4')) as v:
    for i,f in enumerate(v.decode(video=0)):
        if i not in frames:continue
        im=Image.new('RGB',(640,408),'#101820');im.paste(f.to_image(),(0,40));d=ImageDraw.Draw(im)
        d.text((5,5),f'F{i:03d} ALL DETECTIONS | AI endpoint review',font=font,fill='white')
        for j,b in enumerate(rows[i]['raw_detections_xyxy_conf_cls']):
            x1,y1,x2,y2=b[:4];c=colors[j%len(colors)]
            d.rectangle((x1,y1+40,x2,y2+40),outline=c,width=2)
            d.text((x1,max(42,y1+22)),f'D{j} {b[4]:.2f}',font=font,fill=c,stroke_width=1,stroke_fill='black')
        if count%6==0:page=Image.new('RGB',(1920,816),'#101820')
        page.paste(im,((count%3)*640,((count%6)//3)*408))
        if count%6==5 or count==len(frames)-1:page.save(out/f'endpoints-{count//6}.jpg',quality=95)
        count+=1
print(json.dumps({'pages':(len(frames)+5)//6,'frames':frames}))
