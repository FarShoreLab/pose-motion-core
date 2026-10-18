from isolation import BASE, PRIOR, ROOT
import json
import av
from PIL import Image, ImageDraw, ImageFont, ImageOps

source = PRIOR/'outputs/basketball-botsort-v1-model448'
raw = [json.loads(x) for x in (source/'frame-decisions.jsonl').read_text().splitlines()]
gt = json.loads((PRIOR/'diagnostics/visual-evaluation/per-frame-visual-annotations.json').read_text())
out = ROOT/'outputs/r2_occlusion_basketball-v1'
methods = ['no_conflict_protection', 'causal_conflict_freeze']
rows = {m:[json.loads(x) for x in (out/(m+'.jsonl')).read_text().splitlines()] for m in methods}
frames = json.loads((ROOT/'automatic-identity-review/unreviewed-frames.json').read_text())
font = ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',18)
small = ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',14)
seen = 0
with av.open(str(BASE/'outputs/r2_occlusion_basketball/input_30fps.mp4')) as video:
    for i,frame in enumerate(video.decode(video=0)):
        if i not in frames: continue
        im = frame.to_image()
        tile = Image.new('RGB',(1440,420),'#101820')
        tile.paste(im,(0,52))
        draw = ImageDraw.Draw(tile)
        method = 'causal_conflict_freeze' if i==113 else 'no_conflict_protection'
        selected = rows[method][i]['target_detection']
        reference = gt[i]['primary_target_detection']
        draw.text((8,6),f'F{i:03d} {method}: D{selected}; reference D{reference}',font=font,fill='white')
        for k,(det,label,color) in enumerate([(selected,'Selected','#ff6060'),(reference,'Reference','#60ff90')]):
            b=raw[i]['raw_detections_xyxy_conf_cls'][det]
            box=tuple(round(v) for v in b[:4])
            crop=im.crop(box)
            crop=ImageOps.contain(crop,(390,350),Image.Resampling.NEAREST)
            x=650+400*k
            tile.paste(crop,(x+(390-crop.width)//2,65))
            draw.rectangle((b[0],b[1]+52,b[2],b[3]+52),outline=color,width=2)
            draw.text((x,28),f'{label} D{det} conf={b[4]:.3f}',font=font,fill=color)
        if seen%3==0: page=Image.new('RGB',(1440,1260),'#101820')
        page.paste(tile,(0,420*(seen%3)))
        if seen%3==2 or seen==len(frames)-1:
            page.save(ROOT/'automatic-identity-review'/f'crop-review-{seen//3:02d}.jpg',quality=96)
        seen+=1
print(json.dumps({'reviewed_frames':frames,'pages':(seen+2)//3}))
