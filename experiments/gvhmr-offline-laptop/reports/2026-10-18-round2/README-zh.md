# 七段离线对照实测：MediaPipe 与 GVHMR

日期：2026-10-18 UTC。设备：Windows laptop，RTX 4060 Laptop 8GB。MediaPipe 1.1.0 / Python 3.13.1 / CPU；GVHMR / Python 3.10.22 / PyTorch 2.3.0+cu121。

**七段、六个源文件、共 54.7 秒／1,641 帧已真实执行并校验。此次证明流水线能运行、暴露具体失败；没有 3D 真值，不能据此宣称 GVHMR 更准确或可以替换实时基线。** 七段各运行一次；模型/文件缓存可能已热，不是冷启动统计或重复试验置信区间。两段芭蕾来自同一视频的不重叠区间，篮球两片来自同一场地；不能视为七个独立受试者。

## 完整墙钟耗时与缺失

每种方法使用同一 MP4 字节、同一逐帧 PTS。表中 GVHMR 时间包含 YOLO、ViTPose、HMR2、需要时的 SimpleVO、主网络原始输出、第二次官方后处理 forward、FK 导出和序列化。每阶段单独进程以控制内存，因此含重复 Python 导入与模型加载成本。MediaPipe 包含一个进程从启动到保存退出。准备视频和渲染另计，完整工作流时间也在逐片 JSON 中保留。

|片段|时长/帧|MP 完整秒|GVHMR 完整秒|MP 无姿态帧|MP 低置信帧¹|选中 bbox 补全帧²|相机条件|
|---|---:|---:|---:|---:|---:|---:|---|
|慢：过顶深蹲|8s / 240|6.74|61.32|0|0|0 (0.0%)|static 假设|
|慢：侧向单腿深蹲|7s / 210|4.64|49.84|0|210|0 (0.0%)|static 假设|
|快：开合跳／波比跳|10s / 300|6.26|59.12|0|76|70 (23.3%)|static 假设|
|快：篮球投篮|6.8s / 204|5.38|51.59|8|164|0 (0.0%)|SimpleVO 完成|
|转身：芭蕾 A|8s / 240|5.09|56.19|0|29|2 (0.8%)|VO 失败→static|
|转身：芭蕾 B|8s / 240|5.07|54.68|0|11|16 (6.7%)|VO 失败→static|
|额外：篮球多人遮挡|6.9s / 207|4.54|53.58|9|194|20 (9.7%)|SimpleVO 完成|

¹ 至少一个公共主要关节的 min(visibility,presence)<0.5；排除无姿态帧，比例分母仍为全部输入帧。它不是 v5.2 完整状态门控，也不是“整个姿态错误”。侧向单腿深蹲虽然每帧都有姿态，但全部帧都有至少一处低置信主要关节。
² 以实际被选中的 YOLO 轨迹为准；区间内线性插值与首尾保持分开记录。波比跳为 70 帧内部插值；芭蕾 B 为 15 帧内部插值、1 帧端点保持。GVHMR 因插值和时序先验每帧都有输出，不等于每帧均有观测。

样本中 MediaPipe 进程树 RSS 峰值约 225.0 MiB；GVHMR 最大约 5.63 GiB。PyTorch 分配显存最大 1.35 GiB、保留显存最大 1.48 GiB。整卡 nvidia-smi 数字包含桌面和其他进程，不可归因全部属于本实验。采样峰值是下界，详见资源样本。

## 跳变与动作幅度

公共 12 点先按左右髋中点平移对齐；不做旋转/尺度拟合。相邻 30fps 输入帧的欧氏位移 >0.2m（相当于 6m/s）或髋轴投影方向变化 >45° 只用于定位审阅。真实快动作、低置信、身份变化、初始化均可能触发；它不是验证过的错误检测器。缺失点不补成 MP 观测，跨缺失区间不算连续步长。

|片段|最大公共点步长 MP / GV raw (m)|>0.2m 的帧 MP / GV raw|髋轴 >45° MP / GV raw|
|---|---:|---:|---:|
|慢：过顶深蹲|0.064 / 0.011|0 / 0|0 / 0|
|慢：侧向单腿深蹲|0.393 / 0.044|6 / 0|0 / 0|
|快：开合跳／波比跳|0.787 / 0.178|27 / 0|0 / 0|
|快：篮球投篮|0.958 / 0.405|47 / 3|10 / 0|
|转身：芭蕾 A|1.185 / 0.602|46 / 16|5 / 1|
|转身：芭蕾 B|1.120 / 0.315|56 / 12|6 / 0|
|额外：篮球多人遮挡|0.848 / 0.638|56 / 6|5 / 1|

官方后处理在本轮多数片段上没有消除这些大跳变。过顶深蹲左膝原始 GVHMR 峰值 130.44°、官方后处理 119.81°；最大—最小范围 117.70°→107.03°。这说明后处理会改变动作幅度，不能只凭更平滑评价改进。逐片左/右膝与肘的几何屈曲范围、P05–P95 范围、逐关节 XYZ 幅度保存在 metrics-full.json / frame-diagnostics.csv；这些是模型关节点几何角，不是临床关节角。

## 具体审阅位置

所有事件都在 review-events.csv 中保留 input_frame、input_seconds、source_frame 和实际 source_seconds；不是只给整段平均数。以下是代表性位置：

|片段|输入时间|实际源帧时间|观察／诊断|
|---|---:|---:|---|
|慢：侧向单腿深蹲|0.033s|0.040s|mediapipe_raw / left_ankle 单步 0.393m，需看片审阅|
|快：开合跳／波比跳|3.100s|11.114s|mediapipe_raw / left_ankle 单步 0.787m，需看片审阅|
|快：篮球投篮|4.967s|4.975s|mediapipe_raw / left_ankle 单步 0.958m，需看片审阅|
|转身：芭蕾 A|1.267s|1.360s|mediapipe_raw / right_ankle 单步 1.185m，需看片审阅|
|转身：芭蕾 B|2.367s|10.440s|mediapipe_raw / right_ankle 单步 1.120m，需看片审阅|
|额外：篮球多人遮挡|4.967s|4.954s|mediapipe_raw / right_wrist 单步 0.848m，需看片审阅|
|篮球多人遮挡|2.300s|2.317s|已看图确认：MediaPipe 取蓝衣球员，GVHMR 取红衣球员，不能逐点比较|

多人遮挡片段中，179 帧可计算 MP 髋中点与选中 YOLO bbox 的代理检查，75 帧落在该 bbox（加 5% 边距）之外。代理检查不是身份真值，但上面的具体画面确认了至少一处人物不一致。篮球投篮片段该代理未报警，也不能替代完整身份标注。

相机估计失败：芭蕾 A 在输入帧对 16→24（0.533→0.800s，实际源 0.600→0.880s）失败；芭蕾 B 在 0→8（0→0.267s，源 8.080→8.360s）失败。官方 pycolmap 路径返回空变换，触发 AttributeError；没有伪造成功轨迹。两个片段随后明确采用 static 假设，失败耗时包含在完整流水线时间内。篮球两片 SimpleVO 成功完成，但无相机真值，成功不等于旋转准确。

## 来源与取样

所有源均来自 Wikimedia Commons，作者、许可证、准确下载 URL、原始/派生文件 SHA-256、源 PTS、取样范围和编码输入哈希保存在 sources-and-sampling.json 与逐片 input-manifest.json。最近邻 PTS 采样到 30fps，平局取较早帧；不做光流插帧或改变播放速度。保留各片原尺寸；最终对照画面等比例留边。

|片段|原始 FPS / 本地载体 FPS|源归一化区间|来源与许可|
|---|---|---|---|
|慢：过顶深蹲|25.000|[6, 14)s|[Cavemantraining (Taco Fleur)](https://commons.wikimedia.org/wiki/File:Overhead_Kettlebell_Squat.webm) · [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)|
|慢：侧向单腿深蹲|30.000|[0, 7)s|[RickyBennison](https://commons.wikimedia.org/wiki/File:Basic_single_leg_squat.webm) · [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)|
|快：开合跳／波比跳|29.970|[8, 18)s|[Taco fleur (Cavemantraining)](https://commons.wikimedia.org/wiki/File:Jumping_jacks_and_burpees.webm) · [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)|
|快：篮球投篮|30.151|[0, 6.8)s|[Azorbli](https://commons.wikimedia.org/wiki/File:Basketball_(1).ogv) · [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)|
|转身：芭蕾 A|25.000|[0, 8)s|[Fanny Schertzer](https://commons.wikimedia.org/wiki/File:Grands_battements_et_pirouettes.ogv) · [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)|
|转身：芭蕾 B|25.000|[8, 16)s|[Fanny Schertzer](https://commons.wikimedia.org/wiki/File:Grands_battements_et_pirouettes.ogv) · [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)|
|额外：篮球多人遮挡|25.028|[0, 6.9)s|[Azorbli](https://commons.wikimedia.org/wiki/File:Basketball_(4).ogv) · [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)|

篮球投篮原片约 6.865s、遮挡原片约 6.992s，因此实际使用 6.8s / 6.9s（约 7 秒），未补静帧凑长。芭蕾用先前已核验的 720p 派生文件，源原片为 1080p/25fps；434 帧全部保留，本地 fMP4 首 PTS 为 0.08s，取样已计入该偏移。芭蕾 A/B 同源、互不重叠。

## 可复核产物与边界

最终七个视频均为三栏：MediaPipe 原始、GVHMR 原始、GVHMR 官方后处理；标注每一帧实际选中的源 PTS。完整证据包包含共同编码输入、frame-map、原始 MediaPipe NPZ/JSONL、GVHMR 原始与处理后参数/关节 NPZ、VO 轨迹/失败帧对、YOLO 原始轨迹、逐帧诊断、阶段日志、资源样本、图表和脚本。预训练权重、SMPL-X、虚拟环境、原视频全集不打包。

Git 分支只放可复现脚本、经过校验的兼容补丁、版本锁、公开来源清单、小型指标和架构图文；完整数据与视频交付 Library。原始 pilot 的 smoke/squat6s/turn3s 输出保持不变。

本轮进程在任何第三方 import 前设置实验目录内的 YOLO、Matplotlib、Torch、HuggingFace、CUDA、临时文件等配置路径；没有恢复或猜测此前未知全局设置。此前诊断造成的 Ultralytics 全局配置重置仍在旧记录中披露，本轮开始和结束哈希必须相同，见 environment-isolation-verification.json。

当前判断：GVHMR 可继续作为离线重建研究路线，前处理和模型启动占主要墙钟成本；多人身份选择、VO 失败、转身跳变和后处理改变动作幅度均需要后续解决。当前数据不支持替换 v5.2 实时基线，也不足以比较绝对世界平移或脚滑精度。
