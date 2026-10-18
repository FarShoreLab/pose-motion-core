# POSE LIVE v4：同帧观测、逐关节缺失、因果预览与回放修复

本版在独立目录实现并重新运行。原 final-v3 源码、日志和视频没有改动。新版录像来自云 Linux 桌面的真实 Chromium 在线推理，没有预计算骨架、插帧、变速或伪造检测。

## 打开运行

已带运行依赖、模型时：

```sh
python3 scripts/download_assets.py  # 下载并校验测试视频；已有正确文件不重下
python3 server.py 8767
# 浏览器打开 http://127.0.0.1:8767/
```

若没有依赖，先执行 `npm ci --ignore-scripts`。锁定 MediaPipe Tasks Vision 1.1.0、Three.js 0.180.0、官方 Pose Landmarker lite float16 revision 1。服务器是支持 byte-Range 的 Python 版本，监听 0.0.0.0，仅用于可信本地环境，不要直接暴露公网。

本次使用我们自己的云电脑，Chromium 154、CPU/WASM、没有硬件 GPU。已有原浏览器用软件 GL 启动：

```sh
chromium --user-data-dir=/tmp/pose-cloud-chrome \
  --use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader \
  --no-first-run --autoplay-policy=no-user-gesture-required \
  http://127.0.0.1:8767/
```

在本云环境，必须通过本机图形终端启动服务器与浏览器；隔离 shell 的 socket 不能直接接通桌面。普通启用 GPU 的电脑不必照搬软件图形参数。没有使用用户电脑。

### 可重复地址

- `/`：交互演示，默认深蹲，点“播放”
- `/a.html`：深蹲、投篮、转身各 22 秒的真实在线测试，保存 `results/*-v4.json`
- `/?run=challenge&seconds=22&name=my-challenge-v4`：单段测试
- `/r.html`：先运行 18 秒深蹲并明确注入少量受控关节缺失，再回放 18 秒；自动展示修复开启、原始观测、再开启，保存 `repair-demo-v4.json` 和 `repair-demo-v4-replay.json`
- `?horizon=100`：可缩短预测窗口，最大允许 150 ms

同名运行会覆盖同名日志。保留交付证据后再重跑。`seconds` 是测量观察窗，不包含首次模型初始化；中途循环的模型重置与空窗保留在指标里。

## 界面怎样解释

1. 左栏和中栏是严格同帧观测：视频 bitmap、2D 和 3D 使用完全相同的 frame_id、epoch 和源 PTS，在同一次绘制任务提交。
2. 未返回新推理时，保持整张同帧观测画面。源视频仍按原时间线释放并适当跳帧。因此这是稀疏观测更新，不是完整 24/25/30 fps 源视频逐帧显示。零帧差不等于零延迟。
3. 每个关节独立判定 measured / uncertain / lost。只有 measured 有观测坐标、绘点与连线；一端不可靠就不画该骨段。不再用整体平均分掩盖某只手臂的缺失。
4. 右栏是可关闭的独立因果预测预览，琥珀色、虚线，只使用过去两次 measured 数据。目标是实时源时刻，距离每个关节最近有效源时刻超过 150 ms 就隐藏。它不计入推理、有效观测或同帧统计。本机延迟常超过该窗口，所以空白预测栏是正常且诚实的超时表现。
5. “回放已记录”使用本次会话已保存的观测和同一帧快照，不再调用模型。紫色是短缺口修复，仅在前后有效观测端点的间隔不超过 350 ms 时插值；需要未来端点，因此只适用于回放。取消勾选可看原始过滤后观测。
6. 受控缺失仅在 `fault=1` 或 `/r.html` 启用，页面明确显示“受控缺失注入 · 非真实模型漏检”。自然三段基准没有注入。原始模型输出和置信度从不修改。

“measured”只表示通过当前模型置信度与启发式检查的观测，不表示真实测量或已验证准确。visibility/presence 不一定识别全部遮挡；单目模型仍可能高置信地给错位置。

## 策略和边界

- 有限 XYZ 且每关节 visibility/presence 的较小值达到进入门限 0.65；恢复需连续两次合格。已 measured 的关节可在 0.5 退出门限以上保持状态。低于 0.35 或没有有限数据记 lost，中间区域或不合理跳变记 uncertain。uncertain/lost 的过滤观测坐标均为 null。
- 额外做保守跳变/骨长检查，使用过去可信骨长，不做身体尺寸或真实深度校准。阈值见 `public/joint-policy.js`，不是遮挡检测准确率保证。
- 预测采用限速线性外推：三维速度最多 6 m/s、归一化坐标速度最多 3/s；历史间隔过长或不足两次观测时不预测。没有未来观测输入。
- 回放修复不跨 clip、epoch、循环、暂停/重置。缺口没有两端有效数据、超过 350 ms 或位于开头/结尾时保持缺失。修复对象是已有观测帧中的缺失关节，不是把跳过的所有源视频帧恢复出来。
- 33 点原始 world_landmarks、归一化 landmarks、visibility/presence、模型旧版全身 validity 均保留。过滤观测、预测和回放修复单独记录。
- 3D 来自 MediaPipe World XYZ，Three.js 相机做透视投影，Canvas 绘制。不是平面 2D 假 3D。坐标是模型估计的髋相对米制量，无标定、无独立 3D 真值，不保证绝对位置、身体真实尺寸或地面轨迹。

## 时序与资源上限

源释放时刻为 `wall_anchor + source_pts - source_anchor`。只分发已经释放的帧；一个推理 in-flight，最多 12 个捕获帧，选择最新已释放帧，旧帧跳过。推理的原 bitmap 独立保留，不受捕获缓冲驱逐；结果按 frame_id、epoch、PTS 验证后才能画。待画结果最多一个，更新结果可明确取代较旧结果。

完整延迟从源名义释放到视频 + 2D + 3D 原子绘制提交，包含捕获、缩放、传输、推理、消息与绘制等待。阶段差允许负的释放到捕获值（解码器预先提供帧）；阶段和仍等于总延迟。不是物理运动到屏幕光子的测量。

快照以最长边 512 px 保存，最多 240 张，超过丢掉最早快照。每张 RGB(A) 缓冲上界 512×512×4 字节，因此快照像素部分上界约 240 MiB，实际纵横比下更少；不含浏览器对象开销、日志、解码器和模型。原始日志会随会话增长，需要长时服务时应另做滚动持久化。

新版把“新有效”定义收紧为 12 个主要关节全部 measured；旧版是 12 点平均置信度合格。不能直接把两者有效 FPS 当成同一个指标比较。审计同时报告 raw-valid FPS（旧标准）和 strict-valid FPS（新标准）。画面年龄和重置空窗单独统计，防止同帧画面停留时被新更新延迟掩盖。

## 验证

```sh
npm test
python3 audit_v4/audit_raw.py results/slow-v4.json --out results/slow-v4.audit.json
python3 audit_v4/audit_raw.py results/fast-v4.json --out results/fast-v4.audit.json
python3 audit_v4/audit_raw.py results/challenge-v4.json --out results/challenge-v4.audit.json
python3 audit_v4/audit_raw.py results/repair-demo-v4-replay.json --out results/repair-demo-v4-replay.audit.json
```

测试包含 14 个独立关节策略测试、14 个独立审计统计/故障注入测试、三项 JS 语法检查，以及 byte/suffix/open-ended Range 校验。合成单元测试只验证策略逻辑，不是模型准确率或吞吐证据。运行记录另做独立复算。

- `results/source-snapshot/`：实际录屏运行前的源码与 SHA-256
- `results/new-live-v4.mp4`：完整 100 秒真实桌面录像
- `deliverables/new-live-v4-71s.mp4`：裁去桌面边框的连续 71 秒摘录，含三段自然输入；无变速、插帧
- `results/replay-v4.mp4`：受控缺失与回放开关实际桌面录像
- `results/*-v4.json`：完整原始推理、源时序、同帧记录、预测来源和回放修复记录
- `audit_v4/`：独立审核脚本、测试、复算结果

模型和依赖许可证保留在资源/依赖目录。测试视频来源、作者、原文件 SHA-256、Pexels 使用边界在 `assets/videos/manifest.json` 和 `SOURCES.md`；运行包通过脚本单独下载，不把库存素材独立再分发。没有训练模型或识别人物身份。
