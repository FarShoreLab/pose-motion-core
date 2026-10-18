from isolation import BASE,PRIOR,ROOT
from evaluate_results import readrows,METHODS,save
from pathlib import Path
from collections import Counter
import json
import av
from PIL import Image,ImageDraw,ImageFont,ImageOps

def main():
    folder=ROOT/'outputs/r2_fast_basketball-v1';raw=readrows(PRIOR/'outputs/holdout-r2_fast_basketball-v3/frame-decisions.jsonl')
    rows={m:readrows(folder/(m+'.jsonl')) for m in METHODS};details=[];metrics={}
    for m,rr in rows.items():
        for i,r in enumerate(rr):
            di=r['target_detection']
            if di is None:identity='missing'
            elif m=='causal_conflict_freeze' and 59<=i<=74:identity='wrong_black_person'
            else:identity='pink_target'
            details.append({'method':m,'frame':i,'detection_index':di,'identity':identity,'visual_reviewer':'assistant','independent_human_ground_truth':False})
        ll=[x for x in details if x['method']==m];counts=Counter(x['identity'] for x in ll);accepted=204-counts['missing']
        metrics[m]={'frames':204,'identity_counts':dict(counts),'confirmed_frames':accepted,'correct_target_coverage':counts['pink_target']/204,
            'wrong_person_risk_among_confirmed':counts['wrong_black_person']/accepted if accepted else None,
            'wrong_person_frames':[x['frame'] for x in ll if x['identity']=='wrong_black_person'],
            'unresolved_frames':counts['missing']}
    trace=rows['causal_conflict_freeze'][59];chosen=next(x for x in trace['observations'] if x['detection_index']==2)
    assessment={'clip':'r2_fast_basketball','scope':'Previously seen regression clip, not an unseen holdout.',
        'review_protocol':'Assistant inspected all 204 full-scene annotated frames in 13 contact sheets. All 47 causal confirmations were visible; F59-74 follow the black-shirt distractor. Selected crop audit covers F59 and F70-74. No independent human labels.',
        'independent_human_ground_truth':False,'identity_metrics':metrics,
        'no_protection_caution':'Pink target remains identifiable in all selected boxes; overlapping boxes may contain another person. Identity labels do not certify segmentation, complete body geometry or joint accuracy.',
        'wrong_recovery':{'first_frame':59,'last_frame':74,'duration_frames':16,'duration_seconds':16/30,
            'target_identity':trace['target_identity'],'true_target_detection_at_F59':0,'chosen_wrong_detection_at_F59':2,
            'eligible_identity_rows':trace['identity_recovery_rows'],'eligible_detection_columns':trace['identity_recovery_detection_columns'],
            'cost_terms':chosen['recovery_cost'],'global_exclusion_gap':chosen['recovery_global_gap'],
            'cause':'The true pink target remains a provisional microtrack but geometric clues reset its clear anchor window. At F59 the recovery optimization has only one eligible identity and one eligible black-person candidate. Its margin compares this wrong edge with two unmatched dummies, not with the excluded true target. Raw candidate retention did not guarantee competitor retention in recovery.',
            'gallery_contamination':'Code permits clean confirmed observations to update the gallery. The wrong F59-70 observations are clean, so their features enter the target gallery; later low coverage cannot be attributed solely to the original freeze.'},
        'offline_result':{'corrected_wrong_recovery':False,'confirmed_target_frames':0,
            'cause':'The first-frame seed has a geometric overlap clue. Reliable fragments are created only on clean frames, so no retained fragment has contains_explicit_seed=true. The target path is empty. This is an implementation failure, not evidence that two-endpoint linking is impossible.'},
        'prior_v3':'9 confirmed first frames, same selected detections as the reviewed pink target; 195 missing. Causal retains all 9 but introduces 16 wrong-person accepts.',
        'single_person_regression_review':{'all_prior_confirmed_now_missing_frames_inspected':True,
            'burpees_causal_lost':[19,22,23,27,175,181,209,215,270,271,285,297],
            'ballet_b_causal_lost':[8,12,13,17],
            'findings':'The visible person remains correctly enclosed by the prior box at these frames. The new gaps are real coverage regressions, not a disappearing subject. Slow overhead/single-leg selections match prior detection indices for every frame. Ballet A causal also retains all prior detections.',
            'limit':'No independent full-frame identity or joint labels for the five single-person clips; visual spot checks plus exhaustive index/state comparison and all lost-frame review.'},
        'decision':'FAIL integration gate. Preserve all attempts. No shared 3D inference or baseline replacement. No threshold sweep or new encoder.'}
    save(ROOT/'evaluation/fast-basketball-identity-labels.json',details);save(ROOT/'evaluation/fast-basketball-assessment.json',assessment)
    font=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',18);wanted=[59,70,71,72,73,74];page=Image.new('RGB',(1800,1100),'#101820')
    with av.open(str(BASE/'outputs/r2_fast_basketball/input_30fps.mp4')) as video:
        for i,frame in enumerate(video.decode(video=0)):
            if i not in wanted:continue
            k=wanted.index(i);tile=Image.new('RGB',(600,550),'#101820');d=ImageDraw.Draw(tile);im=frame.to_image();di=rows['causal_conflict_freeze'][i]['target_detection'];b=raw[i]['raw_detections_xyxy_conf_cls'][di]
            d.text((8,5),f'F{i}: causal selected D{di}; black distractor',font=font,fill='white');scene=im.resize((600,345));tile.paste(scene,(0,35));d=ImageDraw.Draw(tile);d.rectangle((b[0]*600/640,b[1]*600/640+35,b[2]*600/640,b[3]*600/640+35),outline='#ff6b75',width=3)
            crop=ImageOps.contain(im.crop(tuple(round(x) for x in b[:4])),(150,155),Image.Resampling.NEAREST);tile.paste(crop,(230,390));page.paste(tile,((k%3)*600,(k//3)*550))
    page.save(ROOT/'fast-basketball-visual-review/wrong-recovery-crops.jpg',quality=96)
    print(json.dumps({'identity_metrics':metrics,'wrong_recovery_cost':chosen['recovery_cost'],'margin':chosen['recovery_global_gap']},indent=2))
if __name__=='__main__':main()
