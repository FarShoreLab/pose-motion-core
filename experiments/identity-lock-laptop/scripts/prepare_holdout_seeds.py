from isolation import BASE,ROOT
import json
import av,torch
from PIL import Image,ImageDraw,ImageFont

def main():
    clips=[x for x in json.loads((BASE/'scripts_v2/clips.json').read_text()) if x['name']!='r2_occlusion_basketball']
    canvas=Image.new('RGB',(1920,960),'#101820');font=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',16)
    seeds=[]
    for i,c in enumerate(clips):
        p=BASE/'outputs'/c['name']
        with av.open(str(p/'input_30fps.mp4')) as v:im=next(v.decode(video=0)).to_image()
        b=torch.load(p/'bbox.pt',map_location='cpu',weights_only=True)['bbx_xyxy'][0].tolist()
        d=ImageDraw.Draw(im);d.rectangle(b,outline='#47ff83',width=4)
        im.thumbnail((630,425));tile=Image.new('RGB',(640,480),'#101820');tile.paste(im,((640-im.width)//2,40))
        ImageDraw.Draw(tile).text((6,6),c['name']+' | proposed initial seed',font=font,fill='white')
        canvas.paste(tile,((i%3)*640,(i//3)*480))
        seeds.append({'clip':c['name'],'input_frame':0,'seed_bbox_xyxy':b,'target_description':c['motion']})
    canvas.save(ROOT/'diagnostics/holdout-initial-seeds.jpg',quality=95)
    (ROOT/'diagnostics/holdout-seeds-proposed.json').write_text(json.dumps(seeds,indent=2),encoding='utf-8')
    print(json.dumps(seeds,indent=2))
if __name__=='__main__':main()
