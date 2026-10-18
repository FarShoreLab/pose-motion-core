from isolation import BASE,PRIOR,ROOT
from evaluate_results import readrows,METHODS,CLIPS
from pathlib import Path
import json
import av
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageOps

BG='#111b25';FG='#edf2f5';MUTED='#a8b5c3';TEAL='#52e2c1';AMBER='#ffca6b';RED='#ff6b75';PURPLE='#bc9bff'
FONTS={n:ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',n) for n in [12,13,14,15,16,18,20,24,28]}
def text(draw,xy,value,size=16,fill=FG):draw.text(xy,str(value),font=FONTS[size],fill=fill,stroke_width=0)
def fit(im,size):return ImageOps.contain(im,size,Image.Resampling.LANCZOS)
def label_color(identity):return TEAL if identity=='red_target' else RED if identity=='wrong_blue_person' else AMBER if identity=='ambiguous_people_overlap' else MUTED
def box(draw,b,color,width=2,scale=1,offset=(0,0)):
    draw.rectangle(tuple(float(b[k])*scale+offset[k%2] for k in range(4)),outline=color,width=width)
def writer(path,width,height,fps=30):
    container=av.open(str(path),'w');stream=container.add_stream('libx264',rate=fps);stream.width=width;stream.height=height;stream.pix_fmt='yuv420p';stream.options={'crf':'22','preset':'medium'}
    return container,stream
def emit(container,stream,im):
    for packet in stream.encode(av.VideoFrame.from_image(im)):container.mux(packet)
def finish(container,stream):
    for packet in stream.encode():container.mux(packet)
    container.close()
def raw_scene(im,raw,record):
    scene=im.copy();d=ImageDraw.Draw(scene);obs={x['detection_index']:x for x in record['observations']}
    for i,b in enumerate(raw):
        o=obs.get(i);color=MUTED if o is None else TEAL if o['identity_status']=='confirmed' else AMBER if o['identity_status']=='provisional' else FG
        if o is not None and o['template_frozen']:color=AMBER
        box(d,b,color,1)
        tag=f'D{i} {b[4]:.2f}'
        if o:tag+=f" I{o['identity'] if o['identity'] is not None else '?'}"
        y=max(0,min(350,b[1]-14));d.text((b[0],y),tag,font=FONTS[12],fill=color,stroke_width=1,stroke_fill='#101010')
    for p in record['conflict_pairs']:
        a,b=[raw[i] for i in p['detections']];points=[((a[0]+a[2])/2,(a[1]+a[3])/2),((b[0]+b[2])/2,(b[1]+b[3])/2)]
        d.line(points,fill=RED if p['identity_conflict'] else AMBER,width=2)
    if record['target_candidate_detection'] is not None:
        b=raw[record['target_candidate_detection']];box(d,b,TEAL if record['target_detection'] is not None else AMBER,4)
    return scene

def development(out):
    folder=ROOT/'outputs/r2_occlusion_basketball-v1';raw=readrows(PRIOR/'outputs/basketball-botsort-v1-model448/frame-decisions.jsonl')
    rows={m:readrows(folder/(m+'.jsonl')) for m in METHODS}
    labeled=json.loads((ROOT/'evaluation/per-frame-identity-labels.json').read_text());labels={m:[x for x in labeled if x['method']==m] for m in METHODS}
    oracle=json.loads((ROOT/'outputs/oracle-v1-pair-certainty/oracle-results.json').read_text())['events']
    frames=[]
    with av.open(str(BASE/'outputs/r2_occlusion_basketball/input_30fps.mp4')) as v:frames=[f.to_image() for f in v.decode(video=0)]
    cont,stream=writer(out/'basketball-conflict-preview.mp4',1280,840,15)
    review_frames=[0,24,37,86,104,113,121,176,186,194,206]
    captions=['No conflict protection','Causal conflict freeze','Offline tracklet reconnect']
    for i,im in enumerate(frames):
        canvas=Image.new('RGB',(1280,840),BG);d=ImageDraw.Draw(canvas)
        text(d,(12,8),'Conflict-aware identity experiment',24)
        text(d,(12,40),f'F{i:03d}/206 | source t={i/30:.2f}s | replay 0.5x | frozen detections + one existing ReID encoder',16,MUTED)
        causal=rows[METHODS[1]][i];canvas.paste(raw_scene(im,raw[i]['raw_detections_xyxy_conf_cls'],causal),(12,76))
        text(d,(12,449),f"Causal target: {causal['target_identity_status']} / geometry {causal['target_geometry_status']}",18,TEAL if causal['target_detection'] is not None else AMBER)
        text(d,(12,474),'All candidates shown | amber: template frozen | red line: identity conflict | no future input',13,MUTED)
        event=oracle[0 if i<51 else 1 if i<141 else 2 if i<199 else 3];e=event['event'];short={'red_target':'R','lightblue':'L','beige':'T','brightblue':'B','bright_blue':'B'}
        x=672
        text(d,(x,76),'ORACLE FEASIBILITY - AI-picked anchors',18,AMBER)
        text(d,(x,100),'Separate diagnostic; these anchors are NOT causal inputs.',14,MUTED)
        text(d,(x,122),e['name'],16)
        text(d,(x,145),f"Conflict F{e['conflict_frames_inclusive'][0]}-{e['conflict_frames_inclusive'][1]}",14,MUTED)
        for side,offset in [('before',0),('after',300)]:
            items=e[side];latest=max([s[0] for a in items for s in a['samples']],default=None)
            text(d,(x+offset,166),f'{side.upper()} latest F{latest}' if latest is not None else 'AFTER: absent / right censored',14,FG)
            for k,a in enumerate(items):
                f,di=a['samples'][-1];b=raw[f]['raw_detections_xyxy_conf_cls'][di];crop=fit(frames[f].crop(tuple(round(z) for z in b[:4])),(64,85))
                canvas.paste(crop,(x+offset+k*70+(64-crop.width)//2,190));text(d,(x+offset+k*70,278),short.get(a['identity'],a['identity'][:1].upper()),14,TEAL if a['identity']=='red_target' else FG)
        text(d,(x,302),'Joint costs (row pre -> column post); dummies allowed',14,MUTED)
        matrix=event['cost_matrix'];selected={tuple(p) for p in event['best']['pairs']}
        for j,a in enumerate(e['after']):text(d,(x+75+j*74,323),short.get(a['identity'],a['identity'][:1].upper()),14)
        for row,a in enumerate(e['before']):
            text(d,(x+8,345+row*20),short.get(a['identity'],a['identity'][:1].upper()),14)
            for col,value in enumerate(matrix[row]):
                wrong=a['identity']!=e['after'][col]['identity'];color=RED if (row,col) in selected and wrong else TEAL if (row,col) in selected else MUTED
                text(d,(x+65+col*74,345+row*20),f'{value:.3f}',14,color)
        gap=event['global_gap'];text(d,(x+360,326),f"Global gap: {gap:.3f}" if gap is not None else 'Global gap: n/a',15)
        text(d,(x+360,348),f"Group: {event['identity_status']}",14,TEAL if event['identity_status']=='confirmed' else AMBER)
        for k,p in enumerate(event['pair_certainty']):
            a,b=p['pair'];g=p['global_exclusion_gap'];name=short.get(e['before'][a]['identity'],'?');text(d,(x+360,370+k*18),f'{name} exclusion gap {g:.3f}',13,TEAL if p['confirmed'] else AMBER)
        latest=max([s[0] for a in e['after'] for s in a['samples']],default=None)
        text(d,(x,449),f'Oracle post evidence F{latest}; future from current: {max(latest-i,0)} frames' if latest is not None else 'No future endpoint: unmatched identities remain unresolved.',14,AMBER)
        text(d,(x,473),'R=red target, L=light blue, T=beige, B=bright blue. AI labels only.',13,MUTED)
        for j,m in enumerate(METHODS):
            x0=12+j*424;r=rows[m][i];lab=labels[m][i];color=label_color(lab['identity'])
            text(d,(x0,508),captions[j],18)
            text(d,(x0,532),f"{r['target_identity_status']} | AI: {lab['identity']}",13,color)
            scene=im.resize((412,237),Image.Resampling.LANCZOS);sd=ImageDraw.Draw(scene)
            if r['target_detection'] is not None:box(sd,raw[i]['raw_detections_xyxy_conf_cls'][r['target_detection']],color,3,412/640)
            elif m==METHODS[1] and r['target_candidate_detection'] is not None:box(sd,raw[i]['raw_detections_xyxy_conf_cls'][r['target_candidate_detection']],AMBER,2,412/640)
            canvas.paste(scene,(x0,554))
            for f,ll in enumerate(labels[m]):
                xx=x0+int(f*412/207);d.rectangle((xx,797,xx+2,807),fill=label_color(ll['identity']))
            xx=x0+int(i*412/207);d.line((xx,793,xx,811),fill=FG,width=2)
            text(d,(x0,815),'Future evidence: none' if m!=METHODS[2] else f'Full-clip evidence F206; lookahead {(206-i)/30:.2f}s',13,MUTED)
        emit(cont,stream,canvas)
        if i in review_frames:canvas.save(out/f'preview-review-F{i:03d}.jpg',quality=94)
    finish(cont,stream)

def regression(out):
    cont,stream=writer(out/'six-regression-conflict-replays.mp4',1280,840,30)
    evaluation=json.loads((ROOT/'evaluation/evaluation-summary.json').read_text())
    fast_labels=json.loads((ROOT/'evaluation/fast-basketball-identity-labels.json').read_text())
    page=[];page_count=0;review_manifest=[]
    for clip in CLIPS:
        source=PRIOR/'outputs'/('holdout-'+clip+'-v3');raw=readrows(source/'frame-decisions.jsonl');folder=ROOT/'outputs'/(clip+'-v1')
        rows={m:readrows(folder/(m+'.jsonl')) for m in METHODS}
        result=next(x for x in evaluation['regression'] if x['clip']==clip)
        lost=set(i for m in METHODS for i in result['methods'][m]['lost_frames'])
        sample={0,len(raw)//3,2*len(raw)//3,len(raw)-1}
        if clip=='r2_fast_basketball':sample|={9,20,30,31,58,59,68,74,75,100,150}
        else:sample|=lost
        with av.open(str(BASE/'outputs'/clip/'input_30fps.mp4')) as v:
            for i,frame in enumerate(v.decode(video=0)):
                im=frame.to_image();canvas=Image.new('RGB',(1280,840),BG);d=ImageDraw.Draw(canvas)
                text(d,(12,8),f'{clip} | F{i}/{len(raw)-1} | previously seen regression clip',24)
                text(d,(12,42),'Basketball: all-frame AI identity review, not independent GT. Other clips: states and lost-frame review.',16,MUTED)
                for j,m in enumerate(['prior_v3']+METHODS):
                    x=(j%2)*640;y=82+(j//2)*376
                    r=raw[i] if j==0 else rows[m][i];di=r['detection_index'] if j==0 and r['valid'] else None if j==0 else r['target_detection']
                    status=('confirmed' if r['valid'] else 'unresolved') if j==0 else r['target_identity_status']
                    identity=next((a['identity'] for a in fast_labels if a['method']==m and a['frame']==i),None) if clip=='r2_fast_basketball' else None
                    color=RED if identity=='wrong_black_person' else TEAL if di is not None else AMBER
                    suffix=' | AI: '+identity if identity else ''
                    text(d,(x+12,y),f'{m}: {status}'+suffix,16,color)
                    scene=fit(im,(628,342));sx=x+6+(628-scene.width)//2;sy=y+27
                    canvas.paste(scene,(sx,sy));sd=ImageDraw.Draw(canvas);ratio=scene.width/im.width
                    if di is not None:box(sd,raw[i]['raw_detections_xyxy_conf_cls'][di],color,3,ratio,(sx,sy))
                    if j==2 and di is None and r['target_candidate_detection'] is not None:box(sd,raw[i]['raw_detections_xyxy_conf_cls'][r['target_candidate_detection']],AMBER,2,ratio,(sx,sy))
                emit(cont,stream,canvas)
                if i in sample:
                    thumb=Image.new('RGB',(640,420),BG);td=ImageDraw.Draw(thumb);text(td,(8,4),clip+f' F{i}',18)
                    scene=fit(im,(640,365));sx=(640-scene.width)//2;sy=48;thumb.paste(scene,(sx,sy));td=ImageDraw.Draw(thumb);ratio=scene.width/im.width
                    texts=[]
                    if raw[i]['valid']:
                        box(td,raw[i]['raw_detections_xyxy_conf_cls'][raw[i]['detection_index']],FG,5,ratio,(sx,sy))
                    for j,m in enumerate(METHODS):
                        di=rows[m][i]['target_detection'];texts.append(f'{"NCO"[j]}={di}')
                        if di is not None:box(td,raw[i]['raw_detections_xyxy_conf_cls'][di],[RED,TEAL,PURPLE][j],2,ratio,(sx+j,sy+j))
                    text(td,(8,27),'Prior white; N red C teal O purple | '+' '.join(texts),14)
                    page.append(thumb);review_manifest.append({'clip':clip,'frame':i,'prior_valid':raw[i]['valid'],'lost_in_any_variant':i in lost})
                    if len(page)==9:
                        sheet=Image.new('RGB',(1920,1260),BG)
                        for n,t in enumerate(page):sheet.paste(t,((n%3)*640,(n//3)*420))
                        sheet.save(out/f'regression-review-{page_count:02d}.jpg',quality=94);page_count+=1;page=[]
        print(json.dumps({'rendered_regression':clip,'reviewed_sample_frames':sorted(sample)}),flush=True)
    if page:
        sheet=Image.new('RGB',(1920,1260),BG)
        for n,t in enumerate(page):sheet.paste(t,((n%3)*640,(n//3)*420))
        sheet.save(out/f'regression-review-{page_count:02d}.jpg',quality=94)
    finish(cont,stream)
    (out/'regression-review-manifest.json').write_text(json.dumps(review_manifest,indent=2),encoding='utf-8')

if __name__=='__main__':
    out=ROOT/'delivery';out.mkdir(exist_ok=False);development(out);regression(out)
    print(json.dumps({p.name:p.stat().st_size for p in out.glob('*.mp4')}))
