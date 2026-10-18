# 显式cold / warm epoch对照

`server.py` 保持原cold行为不变。新入口 `server_epoch_modes.py` 提供显式选择，省略选项仍默认cold：

```sh
# 对照：每epoch关闭、重建PoseLandmarker
sh pose-v5-python/start-epoch-modes.sh --port 8766 --epoch-policy cold
# 试验：模型保持，VIDEO时间单调连续
sh pose-v5-python/start-epoch-modes.sh --port 8766 --epoch-policy warm
```

先停止同端口旧服务器。不要和其他API或浏览器推理同时运行。仅允许一个在途推理；服务端不排队。两个模式都逐次处理HTTP请求中当前PNG/JPEG，从未预先解码或推理视频，也不缓存或复用上一帧骨架输出。

## warm保留了什么

warm模式不在epoch变化时关闭MediaPipe实例，因此保留其内部tracking/ROI历史。它不是“全新tracker”，也不能声称与cold的检测状态相同。应用层关节历史仍应在epoch变化时清空；第一份跨epoch结果应明确标注不确定，不能把内部ROI连续性误当成独立的首次检测。跨完全不同视频的跟踪影响必须观察，不能只看延迟。

每帧仍只在该帧释放并被提交后调用一次 `detect_for_video`。服务端没有骨架输出缓存。单个MediaPipe对象+恒定大小的时钟状态，不随loop数量累计旧模型。

## 时间契约

官方Python `detect_for_video` 要求相邻调用的输入毫秒时间单调递增：[API文档](https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/vision/PoseLandmarker#detect_for_video)。这不等于浏览器媒体源PTS必须跨loop连续；本实现区分二者。

- `source_pts_ms`：浏览器发送的实际媒体PTS，原值回传；不修改为模型时间。
- `source_pts_rounded_ms`：round(source_pts_ms)，整数毫秒。
- `model_epoch_offset_ms`：此epoch内部固定偏移。
- `model_timestamp_ms = source_pts_rounded_ms + model_epoch_offset_ms`。
- warm首个epoch偏移为0；后续epoch首帧偏移取使其模型时间至少比上一模型时间大一个四舍五入的名义源帧间隔的最小非负整数。后续帧保持同一偏移。
- cold每epoch新模型，偏移为0，模型时钟随新模型重启。
- `previous_model_timestamp_ms`和`epoch_source_pts_start_ms`回传用于核查映射。
- 同epoch重复或倒退的sourcePTS拒绝。过于接近导致整数模型时间不增长也拒绝；不伪造源PTS或重复上一骨架结果。

所有推理/解码/重置duration仍由Python monotonic差值测量。模型timestamp只满足模型视频时序契约，绝不可与浏览器wall clock相减来计算延迟。

## 日志语义

`/health`报告 `epoch_policy`、启动时读取的 `backend_source_sha256` 和 `epoch_clock_source_sha256`。每个infer响应记录相同哈希与完整时间映射。

- `model_reused_across_context`与`tracker_roi_history_retained`：warm首次跨epoch后，在该epoch内保持true，表示确实继承了模型状态；不是“每帧都切换epoch”。
- `warm_epoch_first_frame`：只有该warm epoch首次成功推理的帧为true，前端应据此标记过渡结果，而不是将整个epoch都降为不确定。
- `epoch_changed`：本次infer内的prepare是否遇到新epoch。若此前显式/prepare已执行，则可能为false；首帧应看 `warm_epoch_first_frame`。
- `tracker_reset`：仅cold确实close+create时true。
- `pose_output_cache_used`：恒为false。
- cold的 `backend_reset_ms`包含完整close+create；warm此项为0，不意味着省略推理或隐瞒请求延迟。

## 保存结果限额

新入口允许 `/save-results` 最大64MiB JSON，避免长测日志被旧入口统一2MiB限额拒绝。`/infer`仍逐块读取且严格限制2MiB，即使没有Content-Length也无法无限读入；原像素尺寸上限继续保留。旧server.py的保存限额未改变。

## 已验证与未验证

14项纯单元测试通过：cold/warm时序、loop/不同源FPS、重复PTS、失败不提交、warm不重建、状态标志、已知/分块请求大小限制。测试不导入模型、不发HTTP、不运行推理。py_compile和shell语法检查通过。

这些检查不等于warm原生推理、65秒浏览器运行或精度验证通过；其结果由随后独立的实际运行报告给出。不得用warm延迟变化直接宣称检测质量改善。
