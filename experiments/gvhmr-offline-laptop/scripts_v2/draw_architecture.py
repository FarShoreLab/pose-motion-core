from isolate_env import ROOT
import hashlib,json,pathlib,subprocess,os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
from matplotlib.font_manager import FontProperties
report=ROOT/'round2-report';report.mkdir(exist_ok=True)
fontpath=pathlib.Path(r'C:\Windows\Fonts\msyh.ttc')
fp=FontProperties(fname=str(fontpath)) if fontpath.exists() else FontProperties(family='sans-serif')
plt.rcParams['svg.fonttype']='path'
fig=plt.figure(figsize=(18,12),facecolor='#f4f7fa');ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(0,180),ylim=(0,120));ax.axis('off')
def text(x,y,s,size=11,color='#233247',weight='normal',ha='left'):
    ax.text(x,y,s,fontproperties=fp,fontsize=size,color=color,weight=weight,va='top',ha=ha,linespacing=1.55)
def box(x,y,w,h,title,body,accent):
    ax.add_patch(FancyBboxPatch((x,y-h),w,h,boxstyle='round,pad=0.6,rounding_size=1.2',facecolor='white',edgecolor='#d7dfe9',linewidth=1))
    ax.plot([x+1,x+w-1],[y-.9,y-.9],color=accent,lw=3)
    text(x+2,y-2,title,12,accent,'bold');text(x+2,y-6.3,body,10)
def arrow(x,y,xx,yy,color='#728399'):
    ax.add_patch(FancyArrowPatch((x,y),(xx,yy),arrowstyle='-|>',mutation_scale=14,color=color,lw=1.4))
text(6,116,'pose-motion-core · 实际代码与数据路径',24,'#13273d','bold')
text(6,110.5,'2026-10-18 代码核查  |  基线 e9d7eb3  |  v4 / v5.2 / v6 为目录，新增 research/gvhmr-expanded-2026-10-18 分支',11)
rows=[
 ('v4','因果实时',100,'#167d94',[
 ('源帧与身份','video → rVFC / 源 PTS\n最多 12 张捕获缓存；1 在途\n保存精确位图、frame_id、epoch'),
 ('MediaPipe → 逐关节门控','CPU / VIDEO / Lite → 原始 33 点\n0.65 / 0.50 迟滞；2 次恢复\nuncertain / lost 不显示观测点'),
 ('同帧显示与独立派生','原位图 + 2D + 3D 一起提交\n预测 ≤150ms；单独标 predicted\n回放修复 ≤350ms，使用未来端点')]),
 ('v5.2','因果实时',78,'#2672b3',[
 ('稳定源时钟与有限队列','seamless-source.js / MSE\nframe-queue.js：2 等待 + 1 在途\n原始 / loop / unwrapped PTS'),
 ('可选后端 + 状态策略','Worker JS 或 RGBA → Python /infer\nepoch_clock：warm / cold 单调时钟\n分组门限；uncertain 明确标色'),
 ('身份核对与观测展示','核对 frame_id / epoch / PTS\n原始点独立；门控不改原坐标\n预测 / 回放不增加新检测计数')]),
 ('v6','约束实验',56,'#8057a9',[
 ('保留 v5.2 观测链','复制的 v5.2 源时钟 / 队列 / 后端\nWorker JointTracker → /fit-ik\n服务端先保存 immutable raw'),
 ('LiveIK → HumanIK / OpenSim','只拟合最新真实结果，禁止重复\n前 30 次校准；固定骨长；25 DOF\n12 标记，19 个 clamped 坐标'),
 ('拟合结果另存另显','fitted / inferred_unobserved\nlost 不变成 measured；全失无姿态\n历史候选未改善：保留 v5.2 基线')]),
 ('GVHMR','整段离线',34,'#a56527',[
 ('统一编码输入与预处理','同一 MP4 / SHA-256 / frame-map\nYOLO 轨迹 + bbox 插值 / 平滑\nViTPose 17 点 + HMR2 图像特征'),
 ('相机条件 → 时序网络','SimpleVO 或明确 static 假设\n失败帧对留证；降级明确标记\n主网络 float32；整段可用未来帧'),
 ('原始与官方后处理分开','raw 参数 / 22 joints 单独保存\n另跑官方平移修正 + IK 分支\nNPZ / JSONL / CSV / 视频 / 计时')])]
for label,mode,y,color,items in rows:
    text(6,y-.5,label,20,color,'bold');text(6,y-6,mode,10,color)
    for x,(title,body) in zip([28,79,130],items):box(x,y,44,17.3,title,body,color)
    arrow(73,y-8.5,78,y-8.5);arrow(124,y-8.5,129,y-8.5)
text(6,12.8,'共享关系',11,'#13273d','bold')
text(28,12.8,'v5.2 / v6 有相同模块副本；不等于跨目录共享包。GVHMR 只共用对照输入和时间映射，尚未接入实时应用。',10)
text(6,8,'验证边界',11,'#13273d','bold')
text(28,8,'本轮真实执行 MediaPipe / GVHMR 离线对照；v4 / v5.2 浏览器链与 v6 沿用历史证据。无 3D 真值，不声明精度提升。',10)
fig.savefig(report/'architecture.png',dpi=160,facecolor=fig.get_facecolor());fig.savefig(report/'architecture.svg',facecolor=fig.get_facecolor());plt.close(fig)
repo=pathlib.Path(os.environ.get('POSE_REPOSITORY',ROOT/'repo-review'))
pairs=[]
for relative in ['public/joint-policy.js','public/joint-policy-v4.js','public/frame-queue.js','public/seamless-source.js','public/pose-worker.js']:
    a=repo/'baselines/v5.2/pose-v52'/relative;b=repo/'experiments/pose-ik-v6/live-app/pose-v52'/relative
    aa=hashlib.sha256(a.read_bytes()).hexdigest();bb=hashlib.sha256(b.read_bytes()).hexdigest()
    pairs.append({'baseline_path':str(a.relative_to(repo)).replace('\\','/'),'v6_path':str(b.relative_to(repo)).replace('\\','/'),'baseline_sha256':aa,'v6_sha256':bb,'identical_bytes':aa==bb,'relationship':'independent copied files; not shared cross-directory imports'})
v4=repo/'baselines/pose-live-v4/public/joint-policy.js';copy=repo/'baselines/v5.2/pose-v52/public/joint-policy-v4.js'
pairs.append({'v4_policy_to_v52_copy_identical':v4.read_bytes()==copy.read_bytes()})
evidence={'baseline_commit':'e9d7eb38f24f901d7935fde0e3da4907b9a562a9','new_branch':'research/gvhmr-expanded-2026-10-18','initial_local_and_remote_branches':['main','origin/main'],'historical_directories_are_not_git_branches':True,'module_copy_comparisons':pairs,'upstream_gvhmr_commit':'ee960bb6e2ea2d381aa97f08e9b71ef320b624b1','diagram_generated_from':'draw_architecture.py; manually traced actual entry points; not inferred from version labels'}
(report/'architecture-code-evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
print(json.dumps({'outputs':['architecture.svg','architecture.png'],'copy_comparisons':pairs}),flush=True)
