from isolation import BASE,PRIOR,ROOT
from evaluate_results import readrows,METHODS
import av,json
from PIL import Image,ImageDraw,ImageFont
raw=readrows(PRIOR/'outputs/holdout-r2_fast_basketball-v3/frame-decisions.jsonl')
rows={m:readrows(ROOT/'outputs/r2_fast_basketball-v1'/(m+'.jsonl')) for m in METHODS}
out=ROOT/'fast-basketball-visual-review';out.mkdir(exist_ok=False)
font=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',16)
with av.open(str(BASE/'outputs/r2_fast_basketball/input_30fps.mp4')) as video:
    for i,frame in enumerate(video.decode(video=0)):
        tile=Image.new('RGB',(480,320),'#101820');im=frame.to_image().resize((480,276));tile.paste(im,(0,44));d=ImageDraw.Draw(tile)
        ids=[rows[m][i]['target_detection'] for m in METHODS]
        d.text((5,4),f'F{i:03d} N red={ids[0]} C teal={ids[1]} O={ids[2]}',font=font,fill='white')
        d.text((5,23),'Target: pink shirt, dark shorts. AI review.',font=font,fill='white')
        for j,di in enumerate(ids):
            if di is None:continue
            b=raw[i]['raw_detections_xyxy_conf_cls'][di];coords=(b[0]*.75+j,b[1]*.75+44+j,b[2]*.75+j,b[3]*.75+44+j)
            d.rectangle(coords,outline=['#ff5967','#52e2c1','#bc9bff'][j],width=2)
        if i%16==0:page=Image.new('RGB',(1920,1280),'#101820')
        page.paste(tile,((i%4)*480,((i%16)//4)*320))
        if i%16==15 or i==len(raw)-1:page.save(out/f'all-frames-{i//16:02d}.jpg',quality=95)
print(json.dumps({'frames':len(raw),'pages':(len(raw)+15)//16}))
