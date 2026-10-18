from isolate_env import ROOT
import csv,hashlib,html,json,pathlib,shutil
report=ROOT/'round2-report';summaries=json.loads((report/'metrics-full.json').read_text(encoding='utf-8'));sources=json.loads((report/'sources-and-sampling.json').read_text(encoding='utf-8'))
stages=list(csv.DictReader((report/'stage-timings.csv').open()));events=list(csv.DictReader((report/'review-events.csv').open()))
labels={'r2_slow_overhead':'慢：过顶深蹲','r2_slow_singleleg':'慢：侧向单腿深蹲','r2_fast_burpees':'快：开合跳／波比跳','r2_fast_basketball':'快：篮球投篮','r2_turn_ballet_a':'转身：芭蕾 A','r2_turn_ballet_b':'转身：芭蕾 B','r2_occlusion_basketball':'额外：篮球多人遮挡'}
lines=['# 七段离线对照实测：MediaPipe 与 GVHMR','','日期：2026-10-18 UTC。设备：Windows laptop，RTX 4060 Laptop 8GB。MediaPipe 1.1.0 / Python 3.13.1 / CPU；GVHMR / Python 3.10.22 / PyTorch 2.3.0+cu121。','',
'**七段、六个源文件、共 54.7 秒／1,641 帧已真实执行并校验。此次证明流水线能运行、暴露具体失败；没有 3D 真值，不能据此宣称 GVHMR 更准确或可以替换实时基线。** 七段各运行一次；模型/文件缓存可能已热，不是冷启动统计或重复试验置信区间。两段芭蕾来自同一视频的不重叠区间，篮球两片来自同一场地；不能视为七个独立受试者。','',
'## 完整墙钟耗时与缺失','','每种方法使用同一 MP4 字节、同一逐帧 PTS。表中 GVHMR 时间包含 YOLO、ViTPose、HMR2、需要时的 SimpleVO、主网络原始输出、第二次官方后处理 forward、FK 导出和序列化。每阶段单独进程以控制内存，因此含重复 Python 导入与模型加载成本。MediaPipe 包含一个进程从启动到保存退出。准备视频和渲染另计，完整工作流时间也在逐片 JSON 中保留。','',
'|片段|时长/帧|MP 完整秒|GVHMR 完整秒|MP 无姿态帧|MP 低置信帧¹|选中 bbox 补全帧²|相机条件|','|---|---:|---:|---:|---:|---:|---:|---|']
for s in summaries:
    camera='SimpleVO 完成' if s['camera_mode']=='simplevo' else ('VO 失败→static' if s['camera_warning'] else 'static 假设')
    lines.append(f"|{labels[s['clip']]}|{s['duration_seconds']:g}s / {s['frames']}|{s['mediapipe_e2e_s']:.2f}|{s['gvhmr_e2e_raw_and_post_s']:.2f}|{s['mediapipe_missing_frames']}|{s['mediapipe_low_confidence_frames']}|{s['selected_bbox_internal_interpolation_frames']+s['selected_bbox_endpoint_hold_frames']} ({s['selected_bbox_filled_rate']:.1%})|{camera}|")
lines+=['','¹ 至少一个公共主要关节的 min(visibility,presence)<0.5；排除无姿态帧，比例分母仍为全部输入帧。它不是 v5.2 完整状态门控，也不是“整个姿态错误”。侧向单腿深蹲虽然每帧都有姿态，但全部帧都有至少一处低置信主要关节。',
'² 以实际被选中的 YOLO 轨迹为准；区间内线性插值与首尾保持分开记录。波比跳为 70 帧内部插值；芭蕾 B 为 15 帧内部插值、1 帧端点保持。GVHMR 因插值和时序先验每帧都有输出，不等于每帧均有观测。','',
f"样本中 MediaPipe 进程树 RSS 峰值约 {max(s['peak_mediapipe_rss_bytes'] for s in summaries)/2**20:.1f} MiB；GVHMR 最大约 {max(s['peak_gvhmr_rss_bytes'] for s in summaries)/2**30:.2f} GiB。PyTorch 分配显存最大 {max(int(s['torch_peak_allocated_bytes']) for s in stages)/2**30:.2f} GiB、保留显存最大 {max(int(s['torch_peak_reserved_bytes']) for s in stages)/2**30:.2f} GiB。整卡 nvidia-smi 数字包含桌面和其他进程，不可归因全部属于本实验。采样峰值是下界，详见资源样本。",'',
'## 跳变与动作幅度','','公共 12 点先按左右髋中点平移对齐；不做旋转/尺度拟合。相邻 30fps 输入帧的欧氏位移 >0.2m（相当于 6m/s）或髋轴投影方向变化 >45° 只用于定位审阅。真实快动作、低置信、身份变化、初始化均可能触发；它不是验证过的错误检测器。缺失点不补成 MP 观测，跨缺失区间不算连续步长。','',
'|片段|最大公共点步长 MP / GV raw (m)|>0.2m 的帧 MP / GV raw|髋轴 >45° MP / GV raw|','|---|---:|---:|---:|']
for s in summaries:
    a=s['methods']['mediapipe_raw'];b=s['methods']['gvhmr_raw']
    lines.append(f"|{labels[s['clip']]}|{a['common12_max_step_m']:.3f} / {b['common12_max_step_m']:.3f}|{a['frames_any_joint_step_over_0.2m']} / {b['frames_any_joint_step_over_0.2m']}|{a['hip_axis_steps_over_45deg']} / {b['hip_axis_steps_over_45deg']}|")
lines+=['','官方后处理在本轮多数片段上没有消除这些大跳变。过顶深蹲左膝原始 GVHMR 峰值 130.44°、官方后处理 119.81°；最大—最小范围 117.70°→107.03°。这说明后处理会改变动作幅度，不能只凭更平滑评价改进。逐片左/右膝与肘的几何屈曲范围、P05–P95 范围、逐关节 XYZ 幅度保存在 metrics-full.json / frame-diagnostics.csv；这些是模型关节点几何角，不是临床关节角。','',
'## 具体审阅位置','','所有事件都在 review-events.csv 中保留 input_frame、input_seconds、source_frame 和实际 source_seconds；不是只给整段平均数。以下是代表性位置：','',
'|片段|输入时间|实际源帧时间|观察／诊断|','|---|---:|---:|---|']
for s in summaries:
    subset=[e for e in events if e['clip']==s['clip'] and e['kind']=='hip_centered_joint_step_over_0.2m']
    if subset:
        e=max(subset,key=lambda e:float(e['value']))
        lines.append(f"|{labels[s['clip']]}|{float(e['input_seconds']):.3f}s|{float(e['source_seconds']):.3f}s|{e['method']} / {e['joint']} 单步 {float(e['value']):.3f}m，需看片审阅|")
lines+=['|篮球多人遮挡|2.300s|2.317s|已看图确认：MediaPipe 取蓝衣球员，GVHMR 取红衣球员，不能逐点比较|','',
'多人遮挡片段中，179 帧可计算 MP 髋中点与选中 YOLO bbox 的代理检查，75 帧落在该 bbox（加 5% 边距）之外。代理检查不是身份真值，但上面的具体画面确认了至少一处人物不一致。篮球投篮片段该代理未报警，也不能替代完整身份标注。','',
'相机估计失败：芭蕾 A 在输入帧对 16→24（0.533→0.800s，实际源 0.600→0.880s）失败；芭蕾 B 在 0→8（0→0.267s，源 8.080→8.360s）失败。官方 pycolmap 路径返回空变换，触发 AttributeError；没有伪造成功轨迹。两个片段随后明确采用 static 假设，失败耗时包含在完整流水线时间内。篮球两片 SimpleVO 成功完成，但无相机真值，成功不等于旋转准确。','',
'## 来源与取样','','所有源均来自 Wikimedia Commons，作者、许可证、准确下载 URL、原始/派生文件 SHA-256、源 PTS、取样范围和编码输入哈希保存在 sources-and-sampling.json 与逐片 input-manifest.json。最近邻 PTS 采样到 30fps，平局取较早帧；不做光流插帧或改变播放速度。保留各片原尺寸；最终对照画面等比例留边。','',
'|片段|原始 FPS / 本地载体 FPS|源归一化区间|来源与许可|','|---|---|---|---|']
for s,meta in zip(summaries,sources):lines.append(f"|{labels[s['clip']]}|{meta['source_fps']:.3f}|[{meta['start']:g}, {meta['start']+meta['duration']:g})s|[{meta['author']}]({meta['source_page']}) · [{meta['license']}]({meta['license_url']})|")
lines+=['','篮球投篮原片约 6.865s、遮挡原片约 6.992s，因此实际使用 6.8s / 6.9s（约 7 秒），未补静帧凑长。芭蕾用先前已核验的 720p 派生文件，源原片为 1080p/25fps；434 帧全部保留，本地 fMP4 首 PTS 为 0.08s，取样已计入该偏移。芭蕾 A/B 同源、互不重叠。','',
'## 可复核产物与边界','','最终七个视频均为三栏：MediaPipe 原始、GVHMR 原始、GVHMR 官方后处理；标注每一帧实际选中的源 PTS。完整证据包包含共同编码输入、frame-map、原始 MediaPipe NPZ/JSONL、GVHMR 原始与处理后参数/关节 NPZ、VO 轨迹/失败帧对、YOLO 原始轨迹、逐帧诊断、阶段日志、资源样本、图表和脚本。预训练权重、SMPL-X、虚拟环境、原视频全集不打包。','',
'Git 分支只放可复现脚本、经过校验的兼容补丁、版本锁、公开来源清单、小型指标和架构图文；完整数据与视频交付 Library。原始 pilot 的 smoke/squat6s/turn3s 输出保持不变。','',
'本轮进程在任何第三方 import 前设置实验目录内的 YOLO、Matplotlib、Torch、HuggingFace、CUDA、临时文件等配置路径；没有恢复或猜测此前未知全局设置。此前诊断造成的 Ultralytics 全局配置重置仍在旧记录中披露，本轮开始和结束哈希必须相同，见 environment-isolation-verification.json。','',
'当前判断：GVHMR 可继续作为离线重建研究路线，前处理和模型启动占主要墙钟成本；多人身份选择、VO 失败、转身跳变和后处理改变动作幅度均需要后续解决。当前数据不支持替换 v5.2 实时基线，也不足以比较绝对世界平移或脚滑精度。','']
(report/'README-zh.md').write_text('\n'.join(lines),encoding='utf-8')
summaryrows=[]
for s in summaries:summaryrows.append({k:s[k] for k in ['clip','category','frames','duration_seconds','mediapipe_e2e_s','gvhmr_e2e_raw_and_post_s','gvhmr_raw_tensor_ready_s','mediapipe_missing_frames','mediapipe_low_confidence_frames','selected_bbox_filled_rate','camera_mode','peak_mediapipe_rss_bytes','peak_gvhmr_rss_bytes']})
with (report/'metrics-summary.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(summaryrows[0]));w.writeheader();w.writerows(summaryrows)
cards=[]
for s in summaries:
    name=s['clip'];note='相机估计失败：static 降级' if s['camera_warning'] else ('SimpleVO 完成，未标定' if s['camera_mode']=='simplevo' else 'static 假设')
    cards.append(f'<section><h2>{html.escape(labels[name])}</h2><p>{s["frames"]} 帧 · {s["duration_seconds"]:g}s · MP {s["mediapipe_e2e_s"]:.2f}s / GVHMR {s["gvhmr_e2e_raw_and_post_s"]:.2f}s · {note}</p><video controls preload="metadata" src="videos/{name}-raw-and-post.mp4"></video><p>MP 无姿态 {s["mediapipe_missing_frames"]} 帧；选中 bbox 补全率 {s["selected_bbox_filled_rate"]:.1%}。<a href="outputs/{name}/frame-diagnostics.csv">逐帧指标</a> · <a href="outputs/{name}/review-events.csv">事件时间点</a> · <a href="{s["source_page"]}">源素材</a></p></section>')
page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>七段离线对照实测</title><style>body{font:16px/1.7 system-ui,sans-serif;max-width:1320px;margin:40px auto;padding:0 24px;color:#25354b;background:#f4f7fa}h1{font-size:32px}h2{font-size:23px}section{background:white;border:1px solid #dce4ed;border-radius:14px;padding:24px;margin:22px 0}video,img{width:100%;height:auto}a{color:#146b9c}.warning{border-left:5px solid #c08137;padding:16px;background:#fff3df}</style><h1>MediaPipe × GVHMR：七段真实离线测试</h1><p>2026-10-18 · 54.7 秒 / 1,641 帧 · 三栏分别保留 MP 原始、GVHMR 原始、GVHMR 官方后处理。</p><p class="warning">没有 3D 真值；不据平滑程度推断准确率。多人遮挡片段 2.300 秒已确认人物选择不同；芭蕾两片相机估计失败并明确降级。</p><p><a href="README-zh.md">完整中文报告</a> · <a href="ARCHITECTURE-zh.md">代码架构</a> · <a href="sources-and-sampling.json">来源与许可证</a> · <a href="metrics-summary.csv">指标汇总</a></p><img src="architecture.png" alt="实际代码架构">'+''.join(cards)+'</html>'
(report/'index.html').write_text(page,encoding='utf-8')
print('Chinese report, CSV summary and offline review index generated.')
