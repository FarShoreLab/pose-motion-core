"""Verify actual output contracts and collect small auditable reports; no model inference."""
from isolation import BASE,ROOT
import csv,hashlib,importlib.metadata,json,shutil,subprocess,sys
from pathlib import Path
import av,numpy as np

CODE=Path(__file__).resolve().parent
REPORT=CODE.parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')
def cp(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)

def main():
    metrics=REPORT/'metrics';metrics.mkdir(exist_ok=False)
    versions=sorted((d.metadata['Name'],d.version) for d in importlib.metadata.distributions())
    lock='\n'.join(f'{n}=={v}' for n,v in versions)+'\n'
    (ROOT/'requirements-lock-final.txt').write_text(lock,encoding='utf-8')
    (REPORT/'requirements-lock-final.txt').write_text(lock,encoding='utf-8')
    license_metadata=[]
    for d in importlib.metadata.distributions():
        m=d.metadata
        license_metadata.append({'name':m['Name'],'version':d.version,'license_expression':m.get('License-Expression'),
            'license_metadata':m.get('License'),'license_classifiers':[v for v in m.get_all('Classifier',[]) if v.startswith('License')],
            'home_page':m.get('Home-page'),'project_urls':m.get_all('Project-URL',[])})
    write(metrics/'dependency-license-metadata.json',license_metadata)
    cp(ROOT/'asset-provenance.json',REPORT/'asset-provenance.json')
    cp(ROOT/'requirements-lock.txt',metrics/'requirements-lock-before-onnx.txt')
    for p in (ROOT/'diagnostics').rglob('*'):
        if p.is_file() and p.suffix.lower() in ['.json','.csv']:
            cp(p,metrics/p.relative_to(ROOT/'diagnostics'))
    cp(ROOT/'holdout-run-logs/batch-receipts.json',metrics/'holdouts/batch-receipts.json')
    cp(ROOT/'evidence/holdouts/holdout-summary.json',metrics/'holdouts/holdout-summary.json')
    for p in (ROOT/'evidence').glob('*.json'):cp(p,metrics/'video-verification'/p.name)
    for p in (ROOT/'evidence').glob('identity-diagnostic.*'):cp(p,REPORT/'figures'/p.name)
    audit={'outcome':'FAILED','no_pose_inference':True,'single_reid_encoder':'yolo26n-reid.onnx',
        'second_encoder_tested':False,'independent_human_ground_truth':False,'attempts':[],'inputs':[],'videos':[]}
    for attempt in sorted((ROOT/'outputs').iterdir()):
        if not attempt.is_dir():continue
        for name in ['run-manifest.json','policy-frozen.json','tracking-summary.json','runtime-failure.json']:
            p=attempt/name
            if p.exists():cp(p,metrics/'attempts'/attempt.name/name)
        fp=attempt/'frame-decisions.jsonl'
        if not fp.exists():continue
        rows=[json.loads(x) for x in fp.read_text().splitlines()]
        if not rows:
            assert (attempt/'runtime-failure.json').exists()
            audit['attempts'].append({'attempt':attempt.name,'incomplete_runtime_failure':True,'decision_frames':0})
            continue
        summary=json.loads((attempt/'tracking-summary.json').read_text())
        assert len(rows)==summary['frames']
        assert sum(r['valid'] for r in rows)==summary['observed_valid_frames']
        last=-1
        for i,r in enumerate(rows):
            assert r['input_frame']==i and r['manual_recovery_hints']==0
            if r['valid']:
                assert r['observed'] and r['bbox_xyxy'] is not None
                assert r['bbox_xyxy']==r['display_bbox_xyxy']
                assert np.isfinite(r['bbox_xyxy']).all() and r['track_id'] is not None
                assert r['bbox_xyxy']==r['raw_detections_xyxy_conf_cls'][r['detection_index']][:4]
                last=i
            else:
                assert not r['observed'] and r['bbox_xyxy'] is None and not r['template_updated']
                if r['display_bbox_xyxy'] is not None:
                    assert i-last<=5 and r['display_box_kind']=='bounded_prediction'
            if r['state']=='reacquired':assert not r['template_updated']
        fhashes={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in attempt.iterdir()
            if p.is_file() and p.suffix in ['.json','.jsonl','.npz']}
        cache=attempt/'detection-embeddings.npz'
        if cache.exists():
            with np.load(cache,allow_pickle=False) as z:
                assert len(z['offsets'])==len(rows)+1 and len(z['embeddings'])==z['offsets'][-1]
                for i,r in enumerate(rows):assert z['offsets'][i+1]-z['offsets'][i]==len(r['raw_detections_xyxy_conf_cls'])
        audit['attempts'].append({'attempt':attempt.name,'decision_frames':len(rows),'contract_verified':True,'files':fhashes})
    for source in sorted((BASE/'outputs').glob('r2_*')):
        manifest=json.loads((source/'input-manifest.json').read_text())
        actual=sha(source/'input_30fps.mp4');assert actual==manifest['input_sha256']
        for name in ['input-manifest.json','frame-map.csv','bbox-metrics.json']:
            cp(source/name,metrics/'inputs'/source.name/name)
        audit['inputs'].append({'clip':source.name,'input_frames':manifest['input_frames'],'sha256':actual,'unchanged':True})
    for p,expected in [(ROOT/'evidence/basketball-final-annotated-comparison.mp4',207),
        (ROOT/'evidence/basketball-same-input-six-methods.mp4',207),
        (ROOT/'evidence/holdouts/six-holdout-tracking-replays.mp4',1434)]:
        with av.open(str(p)) as v:
            stream=v.streams.video[0];meta={'width':stream.width,'height':stream.height,'fps':str(stream.average_rate)}
            count=sum(1 for _ in v.decode(video=0))
        assert count==expected and p.stat().st_size<20_000_000
        audit['videos'].append({'filename':p.name,'bytes':p.stat().st_size,'sha256':sha(p),'decoded_frames':count,**meta})
    tests=subprocess.run([sys.executable,'-B','-m','unittest','test_target_policy','test_target_policy_v2','-v'],
        cwd=CODE,capture_output=True,text=True,encoding='utf-8')
    (metrics/'unit-tests.txt').write_text(tests.stdout+tests.stderr,encoding='utf-8')
    assert tests.returncode==0
    audit['unit_tests']={'exit_code':tests.returncode,'count':13,'log':'unit-tests.txt'}
    qa=json.loads((ROOT/'evidence/holdouts/holdout-summary.json').read_text())
    notes={
        'r2_fast_basketball':'Sampled frames retain the intended pink-shirt target in original/raw boxes, while the guard is lost after frame 8. No accepted wrong identity seen in sampled views.',
        'r2_fast_burpees':'The sole person remains visible; sampled bending/burpee frames repeatedly become invalid. 31 frames have no detector proposal; invalid frames are not all identity-gate failures.',
        'r2_slow_overhead':'Sampled accepted boxes continue to cover the intended sole subject.',
        'r2_slow_singleleg':'Sampled accepted boxes continue to cover the intended sole subject through squat/standing changes.',
        'r2_turn_ballet_a':'Sampled subject is the sole dancer. F37 reports overlapping_people_ambiguous despite one visible person, consistent with duplicate/partial detections.',
        'r2_turn_ballet_b':'Sampled subject is the same sole dancer. F115/F218 overlap ambiguity and F70 candidate-margin ambiguity occur; final sample F239 is invalid.'}
    for q in qa:q['assistant_visual_review_note']=notes[q['clip']]
    write(metrics/'holdouts/visual-review-notes.json',{'reviewer':'assistant','all_contact_pages_inspected':True,
        'sampled_frames':sum(len(q['sampled_visual_qa_frames']) for q in qa),'identity_accuracy':'NOT MEASURED for whole holdouts','clips':qa})
    assert sum(len(q['sampled_visual_qa_frames']) for q in qa)==95
    # The selected held-out observations are QA samples, never training/recovery input.
    audit['holdout_qa']={'sampled_frames':95,'full_frame_identity_labels':False,'no_policy_tuning_after_holdouts':True}
    write(metrics/'final-audit.json',audit)
    print(json.dumps({'outcome':audit['outcome'],'attempts':len(audit['attempts']),
        'contract_verified_frames':sum(a.get('decision_frames',0) for a in audit['attempts']),
        'videos':audit['videos'],'unit_tests':audit['unit_tests']},indent=2))

if __name__=='__main__':main()
