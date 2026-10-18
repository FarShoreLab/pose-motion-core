# v6 OpenSim 现场人体约束对照

这是独立实验分支。`baseline-v5.2/` 未修改，前端 `joint-policy.js`、`joint-policy-v4.js`、`frame-queue.js`、`seamless-source.js` 和后端 `epoch_clock.py` 与 v5.2 原件一致。

## 启动

在本工程根目录运行 `live-app/start-live.sh`。它使用父目录 `.venv`、`src/opensim_ik.py`，监听 `127.0.0.1:8770`，采用原 v5.2 的 warm tracker epoch 策略。

- 深蹲：`http://127.0.0.1:8770/?run=commons-overhead25&seconds=65&name=v6-live-slow`
- 快速动作：`http://127.0.0.1:8770/?run=commons-jumping2997&seconds=65&name=v6-live-fast`
- 转身：`http://127.0.0.1:8770/?run=commons-pirouettes25&seconds=65&name=v6-live-turn`

只开启一个运行页面。一个完成后再切换下一段，避免 CPU 争用和后端并发身份冲突。

若本环境的隔离 shell 无法提供 MediaPipe/tcmalloc 所需的正常 CPU 信息，进程会在初始化时退出。这不是模型推理结果。不要伪造系统 CPU 信息或降低系统安全设置；应通过获准的原生云电脑终端运行同一启动命令。

## 真实数据路径

1. MSE 原始速度 1× 连续播放；保留 2 个待发快照 + 1 个在途帧，使用原有最新可用帧队列。
2. `requestVideoFrameCallback` 同步截取最大边 512 px 的原始帧；同一 ImageBitmap 保留用于严格配对显示。RGBA8 输入经过 `/infer` 逐帧运行 MediaPipe Python CPU。
3. Worker 加载原件 `JointTracker`，用相同的阈值、关节组、速度和骨长跳变规则生成观察状态。未放宽 v5.2 有效性门槛。
4. `/fit-ik` 只接受与服务器刚刚完成的真实推理完全匹配的 frame_id、epoch、source_pts_ms。客户端不提交替代坐标；OpenSim 只读取服务器保存的该帧原始输出。
5. 第 1–30 次现场输出用于校准；此阶段第三屏保持空白。第 30 次锁定骨长；第 31 次开始拟合。循环保持骨长，跨源变更重新校准；无预读视频、离线姿态缓存或平滑。
6. 三屏一次性显示同一帧：原视频/2D、v5.2 原始过滤观测、OpenSim 约束拟合。两侧 3D 视角联动。

## 标签和失败状态

- 原始测得/不确定/丢失统计完全保留。
- 蓝色为 fitted，珊瑚虚线为 inferred_unobserved；两者均不是新观测，均不计入严格有效姿态率。
- 原始观测丢失仍在 UI 和日志中显示，不被拟合补点抵消。
- no_pose、no_observation、solver_error 隐藏拟合，不显示旧解。
- 仅实现 12 个主关节的简化 25-DoF 模型；头、手、足部细节点不建模。骨长和角限一致不代表真实三维准确，也不代表抖动改善。
- 骨长校准使用默认值的项数在 UI 中明示，样本数、默认值情况、长度及坐标限位均保存在校准记录。

## 记录

`pose-v52/results/<name>.json` 保存完整浏览器时钟、队列、跳帧、原始全 33 点及其置信度、v5.2 状态、拟合/推断状态、精确帧身份、拟合残差、坐标、solver_ms、IK HTTP 时间以及端到端延迟。

`pose-v52/results/immutable-live-*.jsonl` 是服务器只追加审计：每次原始输出在拟合前完整记录，后接独立的派生 IK 输出。不会覆盖原始点。浏览器记录避免再次复制一整份 backend 坐标数组，校准元数据只在锁定时记录一次。

`inference_ms` 仍是 MediaPipe 原生推理时间；`ik_solver_ms` 是新增 OpenSim 原生求解时间；`ik_http_ms` 是附加 IK 往返；`worker_processing_total_ms` 和 `total_delay_ms` 包括完整串行链路。校准的模型创建时间单独记录，不误计为求解时间。

## 已通过的代码验证

- `cd live-app/pose-v52 && npm test`
- `cd live-app/pose-v52-python && ../../.venv/bin/python -m unittest test_live_ik test_epoch_clock test_epoch_backend -v`

`test_live_ik` 使用合成真值，只验证软件契约、30 次校准、只读原始数据、帧身份校验、循环固定骨长和无观测隐藏；不能用于声称真实视频的性能或准确率。

保存接口上限调整为128MiB，以容纳65秒30fps的原始全量+IK审计；单帧输入上限仍为2MiB，单帧RGBA最大512px未改变。
