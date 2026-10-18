"""Stage audited evidence, verify frozen bytes, and package this failed experiment."""
from isolation import BASE,PRIOR,ROOT
from evaluate_results import readrows,METHODS,CLIPS,sha,save
from pathlib import Path
import argparse,base64,html,json,shutil,subprocess,sys,zipfile
import av

CODE=Path(__file__).parent
REPO=CODE.parent
ALLCLIPS=['r2_occlusion_basketball']+CLIPS

def copy_tree(source,dest):
    dest.mkdir(parents=True,exist_ok=True)
    for p in source.rglob('*'):
        if p.is_file():
            target=dest/p.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)

def stage():
    for name in ['README.md','REPRODUCE.md']:
        shutil.copy2(CODE/name,REPO/name)
    old=BASE/'repo-identity-lock/experiments/identity-lock-laptop'
    third=(old/'THIRD_PARTY.md').read_text(encoding='utf-8')
    third+='\n\n本轮 conflict-tracklets 实验仅复用上述输入和缓存，不安装依赖、不推理模型、不分发权重。视频改动为新增框、状态、成本与 AI 审查标签；第一篮球回放为 0.5 倍速。素材对应片段及截图继续按原 CC BY-SA 版本提供，作者/来源/修改记录随包保留。GTA 与 AFLink 只作为方法参考，没有复制或安装其仓库。\n'
    (REPO/'THIRD_PARTY.md').write_text(third,encoding='utf-8')
    shutil.copy2(PRIOR/'requirements-lock-final.txt',REPO/'requirements-lock-final.txt')
    shutil.copy2(PRIOR/'asset-provenance.json',REPO/'asset-provenance.json')
    (REPO/'.gitignore').write_text('__pycache__/\n*.pyc\n.venv/\ncache/\n*.mp4\n*.npz\n*.zip\n',encoding='utf-8')
    copy_tree(ROOT/'outputs',REPO/'metrics/runs');copy_tree(ROOT/'evaluation',REPO/'metrics/evaluation');copy_tree(ROOT/'archive',REPO/'metrics/archive')
    figures=REPO/'figures';figures.mkdir(exist_ok=True)
    for source,name in [(ROOT/'evaluation/risk-coverage.png','risk-coverage.png'),(ROOT/'evaluation/risk-coverage.svg','risk-coverage.svg'),
        (ROOT/'fast-basketball-visual-review/wrong-recovery-crops.jpg','wrong-recovery-crops.jpg'),
        (ROOT/'delivery/preview-review-F104.jpg','development-wrong-person.jpg'),(ROOT/'delivery/preview-review-F186.jpg','oracle-group-ambiguity.jpg')]:
        shutil.copy2(source,figures/name)
    p=figures/'risk-coverage.svg';p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines())+'\n',encoding='utf-8')
    provenance=[]
    for clip in ALLCLIPS:
        target=REPO/'metrics/inputs'/clip;target.mkdir(parents=True,exist_ok=True)
        for name in ['input-manifest.json','frame-map.csv']:
            p=BASE/'outputs'/clip/name
            if p.exists():shutil.copy2(p,target/name)
        a=json.loads((target/'input-manifest.json').read_text());provenance.append({k:a[k] for k in ['name','source_page','author','license','license_url','input_sha256','input_frames','unique_source_frames','changes']})
    save(REPO/'metrics/input-provenance.json',provenance)
    return provenance

def report(provenance):
    s=json.loads((ROOT/'evaluation/evaluation-summary.json').read_text());fast=json.loads((ROOT/'evaluation/fast-basketball-assessment.json').read_text())
    def image(path):return 'data:image/'+('png' if path.suffix=='.png' else 'jpeg')+';base64,'+base64.b64encode(path.read_bytes()).decode()
    def table(head,rows):return '<table><thead><tr>'+''.join('<th>'+html.escape(str(x))+'</th>' for x in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'
    names={'raw_botsort_seed_id2':'原始 BoT-SORT ID2','prior_gallery_v3':'上一版 v3','no_conflict_protection':'无冲突保护','causal_conflict_freeze':'因果冲突冻结','offline_tracklet_reconnect':'离线轨段重连'}
    dev=[]
    for m in ['raw_botsort_seed_id2','prior_gallery_v3']+METHODS:
        v=s['methods'][m];c=v['identity_counts'];dev.append([names[m],c.get('red_target',0),c.get('wrong_blue_person',0),c.get('ambiguous_people_overlap',0),c.get('missing',0),f"{100*v['correct_target_coverage']:.1f}%",v['false_reject_clear_target_frames']])
    rr=[]
    for x in s['regression']:
        rr.append([x['clip'].replace('r2_',''),x['frames'],x['prior_v3_confirmed_frames']]+[x['methods'][m]['confirmed_frames'] for m in METHODS]+[x['methods'][METHODS[1]]['prior_confirmed_now_missing']])
    credits='<ul>'+''.join('<li><a href="'+html.escape(x['source_page'],quote=True)+'">'+html.escape(x['name'])+'</a> — '+html.escape(x['author'])+'；<a href="'+html.escape(x['license_url'],quote=True)+'">'+html.escape(x['license'])+'</a></li>' for x in provenance)+'</ul>'
    content='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>冲突轨段实验：结果与失败证据</title><style>
    :root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#edf1f4;color:#172b3a;font-family:"Microsoft YaHei","Noto Sans CJK SC",system-ui,sans-serif;line-height:1.75}main{max-width:1140px;margin:40px auto;padding:40px;background:white;border-radius:16px}h1{font-size:32px;line-height:1.3;margin:0 0 20px}h2{font-size:22px;margin-top:34px;border-top:1px solid #dce4e9;padding-top:24px}p{max-width:980px}.eyebrow{letter-spacing:2px;color:#4d6c7f;font-size:13px}.alert{padding:22px;background:#fff1ed;border-left:5px solid #c94a40;border-radius:5px}.muted,figcaption{color:#526b7b;font-size:14px}table{border-collapse:collapse;width:100%;font-size:14px;margin:20px 0}th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #dce5eb}th{background:#eaf1f5}td:not(:first-child){font-variant-numeric:tabular-nums}figure{margin:24px 0}img{display:block;max-width:100%;height:auto;border:1px solid #dce4e9}a{color:#15678e}code{background:#edf3f6;padding:2px 4px}li{margin:5px 0}@media(max-width:700px){main{margin:0;padding:20px;border-radius:0}h1{font-size:25px}table{font-size:11px}th,td{padding:6px}h2{font-size:20px}}@media print{body{background:white}main{margin:0;padding:0}h2{break-after:avoid}figure,table{break-inside:avoid}}</style><main>
    <p class="eyebrow">POSE MOTION CORE · 2026-10-18 · FROZEN-CACHE RESEARCH</p><h1>前后端证据有用，自动恢复仍未可靠</h1>
    <div class="alert"><strong>本轮未通过集成门槛。</strong>开发篮球的因果版提高了覆盖；另一篮球出现 16 帧明确错人，单人回归也产生新增缺口。离线版未纠正这些问题。结果与失败日志均保留，不替换基线，不接入共享 3D 推理。</div>
    <p>用户思路是：冲突前后可以建立可靠身份，中间允许未知，而非逐帧强行确认。本轮先做 AI 手选端点的可行性检查，再在完全相同的检测和 ReID 缓存上比较无保护、因果冻结、离线重连。只使用已有的一个 yolo26n-ReID 编码器。</p>
    <h2>开发篮球：风险与覆盖一起看</h2>'''+table(['方法','正确','错人','歧义','未确认','正确覆盖','清晰框误拒/121'],dev)+'''
    <p>因果版相对上一版 v3 净增 43 个正确帧，但相对原始 BoT-SORT 仍丢掉 40 个原本正确的帧，同时补回 65 帧。其 81 个未确认帧包括 44 个临时身份候选和 37 个 unresolved；临时候选有真实检测框，也不能当成已确认目标。</p>
    <figure><img src="'''+image(ROOT/'evaluation/risk-coverage.png')+'''" alt="开发片段风险与覆盖图"><figcaption>点为明确错人率，叉为错人加歧义率。它们是不同方法的固定工作点，不是为取得最佳数字而调出来的阈值曲线。</figcaption></figure>
    <h2>另一篮球：47 次确认中，16 次恢复成了错人</h2>
    <p>逐帧检查全部 204 帧后，无保护版 204 帧目标身份可辨；因果版只有 F0–30 的 31 帧正确，F59–74 连到了黑衣、红短裤干扰者，157 帧未确认。错误确认持续 0.533 秒，占其确认帧的 34.0%。离线版 0 帧确认，不能称为纠正了错误。</p>
    <figure><img src="'''+image(ROOT/'fast-basketball-visual-review/wrong-recovery-crops.jpg')+'''" alt="第二篮球F59及F70至74错误恢复框和放大图"><figcaption>起始目标是粉衣、深色短裤人物。红框标出错误恢复到黑衣人的检测；AI 目视审查，不是独立人工真值。</figcaption></figure>
    <p>F59 真目标 D0 仍保存在原始候选和临时轨道中，但几何冲突重置了三个清晰帧窗口，使它未进入恢复候选集。优化只剩目标身份与黑衣候选 D2：边成本 0.487468，对照两个 unmatched dummy 成本 0.7，给出了 0.212532 的“高间隔”。它没有比较被过滤掉的真目标。错人的清晰观测随后还能污染目标外观库。</p>
    <p>离线失败还有明确的结构原因：首帧目标带重叠线索，可靠轨段生成器没有留下包含显式种子的轨段，目标路径因此为空。保存全部检测并不足以确保它们进入正确的联合优化。</p>
    <h2>AI 端点 oracle：两次可连接，一次整组不确定，一次无后端</h2>'''+table(['事件','冲突帧/时长','前端末帧→后端末帧','联合结果'],[
        ['A','21–30 / 0.333s','12→42','正确交换，间隔0.3030'],['B','77–119 / 1.433s','62→122','正确交换，间隔0.2692'],['C','145–193 / 1.633s','141→196','浅蓝/米色错配，间隔0.04493；整组拒绝'],['D','200–206 / 0.233s','198→无','未匹配，右删失']])+'''
    <p>C 中红衣与亮蓝的单条边仍有较大的全局排除间隔（0.31217、0.28266），但两条错误边被拒绝，不代表全组恢复成功。早期整组 oracle 输出未覆盖；逐边排除诊断是在观察 C 后加入，成本与阈值未改。oracle 不是自动结果，也不是独立真值。</p>
    <h2>因果时间与离线未来证据</h2>
    <p>因果版每一帧只用到当时及过去的缓存。开发片段关联计算 0.4124 秒，无保护 0.2988 秒；差值约 0.55ms/帧。单帧中位数 1.67ms、p95 4.09ms。三个清晰帧确认最低额外等待 66.7ms。这里不含检测、ReID、姿态或显示，不能宣称端到端实时。</p>
    <p>按事后连续三个正确帧的起点核对，事件 A/B/C 的因果恢复为 F37/F121/F194，距冲突末帧 233/67/33ms；D 未恢复。开发片段最长未确认段 38 帧。离线连接耗时 0.05255 秒（另加轨段构建），全局使用到 F206；所有输出明确标出未来证据。离线开发目标链止于 F65，关键边排除间隔仅 0.00952。没有补不存在的检测框或关节点。</p>
    <h2>六段旧素材回归</h2>'''+table(['片段','总帧','上版确认','无保护','因果','离线','因果丢掉旧确认'],rr)+'''
    <p>篮球的因果 47 帧包含上述 16 次错人。其他五段数值是算法确认状态；检查了全量索引/状态、代表帧及所有旧版确认而新版缺失的帧。波比跳新增丢失 12 帧，芭蕾 B 新增丢失 4 帧，均可见目标仍在旧框内。单人不退步门槛未通过。这些素材此前已看过，是回归集；芭蕾 A/B 来自同一人和同一原视频。</p>
    <h2>审查范围与可以得出的结论</h2>
    <p>开发片段复用全部 207 帧的既有 AI 目视标签，再对 11 个新选择做全场景和放大框检查；第二篮球新审查全部 204 帧。没有独立人工真值，不能把这些数字当成标准 MOT IDF1/HOTA、关节精度或独立样本统计。正确身份不保证完整人体框。</p>
    <p>六个关联单元测试通过；七段缓存哈希未变，并分别通过 30/90/150 帧因果前缀检查。旧提交 c76521b、五个旧 Library 交付及 32 项冻结输入已存档。自动算法只跑这一轮冻结配置，没有为了结果继续调参或换编码器。</p>
    <p>下一步结构问题是保留冲突组内真实竞争者参与恢复比较，以及把显式初始身份可靠传递到后来清晰轨段。修复后仍需新的独立人工标注素材。当前证据支持有条件的双端连接可行性，不支持系统已可靠落地。</p>
    <p>方法参考：<a href="https://github.com/sjc042/gta-link">GTA 仓库</a>、<a href="https://arxiv.org/html/2411.08216v1">GTA 论文</a>、<a href="https://github.com/dyhBUPT/StrongSORT/blob/master/AFLink/AppFreeLink.py">AFLink 实现</a>。本代码是最小自定义试验，不是论文复现。GTA 使用 SportsMOT 训练的 OSNet，本轮只用已有 yolo26n-ReID；AFLink 关联与 GSI 插值不同，本轮没有实施后者。</p>
    <h2>视频与证据包</h2><ul><li>basketball-conflict-preview.mp4：207 真实帧、0.5 倍回放，含全部候选、冲突、AI 前后锚、成本/间隔及三个消融。</li><li>six-regression-conflict-replays.mp4：六段、1434 帧，含错误恢复 AI 标签及旧版对照。</li><li>diagnostics ZIP：源码、冻结缓存、原始输出、最终标签、开发视觉证据与校验记录。</li><li>regression-review ZIP：第二篮球所有帧及单人损失帧证据。</li><li>input-clips ZIP：七段同一输入视频、来源与帧映射。每个附件不超过20,000,000字节；不分发依赖或模型权重。</li></ul>
    <h2>素材来源与许可</h2>'''+credits+'''<p class="muted">使用已有裁剪视频，按源 PTS 最近邻采样到30fps，无新插帧；新增检测框、状态和诊断文字，开发回放减速。各片段及截图按对应 CC BY-SA 版本保留作者、来源与修改标记。完整算法细节、复现说明和依赖来源见诊断包与独立 Git 分支。</p></main></html>'''
    (ROOT/'delivery/conflict-tracklets-report-2026-10-18.html').write_text(content,encoding='utf-8')

def validate():
    archive=json.loads((ROOT/'archive/previous-release-verified.json').read_text());checks=[]
    for item in archive['frozen_prior_inputs']:
        p=Path(item['path']);actual=sha(p);assert actual==item['sha256'];assert p.stat().st_size==item['bytes'];checks.append({'path':str(p),'sha256':actual})
    for item in archive['library_files']:
        p=Path(item['local_path']);assert sha(p)==item['sha256']
    codechecks=[];video_checks=[]
    for clip in ALLCLIPS:
        folder=ROOT/'outputs'/(clip+'-v1');manifest=json.loads((folder/'run-manifest.json').read_text())
        for name in ['association.py','conflict_tracker.py','policy-v1.json']:
            expected=manifest['config_sha256'] if name.endswith('.json') else manifest['code_sha256'][name]
            assert sha(CODE/name)==expected
        n=manifest['input_frames'];raw=readrows(Path(manifest['cached_source'])/'frame-decisions.jsonl')
        for m in METHODS:
            rows=readrows(folder/(m+'.jsonl'));assert len(rows)==n
            for i,r in enumerate(rows):
                assert r['frame']==i
                if r['target_detection'] is not None:assert 0<=r['target_detection']<len(raw[i]['raw_detections_xyxy_conf_cls'])
                assert r['target_geometry_status'] in ['observed','missing']
                if m!=METHODS[2]:assert r['evidence_last_frame']==i and r['future_frames_used']==0
                else:assert r['evidence_last_frame']==n-1 and r['future_frames_used']==n-1-i
        codechecks.append({'clip':clip,'algorithm_and_policy_hashes_unchanged_since_run':True,'raw_index_and_future_evidence_checks':True})
    for name,frames,fps in [('basketball-conflict-preview.mp4',207,15),('six-regression-conflict-replays.mp4',1434,30)]:
        p=ROOT/'delivery'/name;times=[];sample=104 if frames==207 else 59
        with av.open(str(p)) as v:
            stream=v.streams.video[0];assert float(stream.average_rate)==fps
            for i,f in enumerate(v.decode(video=0)):
                times.append(float(f.pts*f.time_base))
                if i==sample:f.to_image().save(ROOT/'delivery'/(name.replace('.mp4','-decoded-QA.jpg')),quality=94)
        assert len(times)==frames;assert all(b>a for a,b in zip(times,times[1:]));assert p.stat().st_size<=20000000
        video_checks.append({'file':name,'frames':frames,'fps':fps,'duration_seconds':frames/fps,'all_frames_decoded':True,'monotonic_pts':True,'sha256':sha(p),'bytes':p.stat().st_size})
    # Meaningful association tests already ran before the experiments; final result is captured for release evidence.
    result=subprocess.run([sys.executable,'-B','-X','utf8',str(CODE/'test_association.py')],capture_output=True,text=True,check=False)
    assert result.returncode==0
    verification={'frozen_prior_inputs_rechecked':len(checks),'old_local_deliverable_hashes_rechecked':len(archive['library_files']),
        'input_checks':checks,'algorithm_checks':codechecks,'video_checks':video_checks,'association_tests':{'returncode':result.returncode,'output':result.stdout+result.stderr},
        'limits':'Local archive hashes rechecked; original remote Library immutable identities and sizes were checked when archiving, not re-downloaded. AI visual labels are not independent human GT.'}
    save(ROOT/'archive/final-validation.json',verification);shutil.copy2(ROOT/'archive/final-validation.json',REPO/'metrics/archive/final-validation.json')
    print(json.dumps({'validated_prior_inputs':len(checks),'videos':video_checks,'tests_passed':True},indent=2))

def zip_items(path,items):
    assert not path.exists(),str(path)
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for source,name in sorted(items,key=lambda x:x[1]):z.write(source,name)
    with zipfile.ZipFile(path) as z:assert z.testzip() is None
    assert path.stat().st_size<=20000000,(str(path),path.stat().st_size)
    return {'file_name':path.name,'local_path':str(path),'bytes':path.stat().st_size,'sha256':sha(path),'zip_crc_checked':True}
def gather(root,prefix):return [(p,prefix+'/'+p.relative_to(root).as_posix()) for p in root.rglob('*') if p.is_file()]

def package():
    delivery=ROOT/'delivery';items=[]
    for p in CODE.iterdir():
        if p.is_file() and p.suffix in ['.py','.json']:items.append((p,'scripts/'+p.name))
    for name in ['README.md','REPRODUCE.md','THIRD_PARTY.md','requirements-lock-final.txt','asset-provenance.json']:
        items.append((REPO/name,name))
    for folder in ['outputs','evaluation','archive','automatic-identity-review','oracle-preview','oracle-preview-2']:
        items+=gather(ROOT/folder,'conflict-tracklets-2026-10-18/'+folder)
    items+=gather(PRIOR/'diagnostics/visual-evaluation','identity-lock-2026-10-18/diagnostics/visual-evaluation')
    for clip in ALLCLIPS:
        source=PRIOR/'outputs'/('basketball-botsort-v1-model448' if clip==ALLCLIPS[0] else 'holdout-'+clip+'-v3')
        for name in ['frame-decisions.jsonl','detection-embeddings.npz','policy-frozen.json','run-manifest.json']:
            items.append((source/name,'identity-lock-2026-10-18/outputs/'+source.name+'/'+name))
    results=[zip_items(delivery/'conflict-tracklets-diagnostics-2026-10-18.zip',items)]
    items=gather(ROOT/'fast-basketball-visual-review','fast-basketball-visual-review')
    items += [(p,'regression-review/'+p.name) for p in delivery.glob('regression-review-*')]
    items += [(REPO/'THIRD_PARTY.md','THIRD_PARTY.md'),(REPO/'README.md','README.md')]
    results.append(zip_items(delivery/'conflict-tracklets-regression-review-2026-10-18.zip',items))
    items=[]
    for clip in ALLCLIPS:
        for name in ['input_30fps.mp4','input-manifest.json','frame-map.csv']:
            p=BASE/'outputs'/clip/name
            if p.exists():items.append((p,'outputs/'+clip+'/'+name))
    items.append((REPO/'THIRD_PARTY.md','THIRD_PARTY.md'));results.append(zip_items(delivery/'conflict-tracklets-input-clips-2026-10-18.zip',items))
    for name in ['basketball-conflict-preview.mp4','six-regression-conflict-replays.mp4','conflict-tracklets-report-2026-10-18.html']:
        p=delivery/name;assert p.stat().st_size<=20000000;results.append({'file_name':name,'local_path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)})
    order=['basketball-conflict-preview.mp4','six-regression-conflict-replays.mp4','conflict-tracklets-report-2026-10-18.html','conflict-tracklets-diagnostics-2026-10-18.zip','conflict-tracklets-regression-review-2026-10-18.zip','conflict-tracklets-input-clips-2026-10-18.zip']
    results.sort(key=lambda x:order.index(x['file_name']));save(delivery/'delivery-manifest.json',results);save(REPO/'metrics/delivery-manifest.json',results)
    print(json.dumps(results,indent=2))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--phase',choices=['stage','validate','package'],required=True);args=a.parse_args()
    if args.phase=='stage':report(stage())
    elif args.phase=='validate':validate()
    else:package()
