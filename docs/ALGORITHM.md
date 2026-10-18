# 算法地图与边界

本说明只解释归档源码，不是新的性能或准确度验证。

## v5.2：保留基线

1. `public/seamless-source.js` 用 fMP4 / MediaSource 延续源媒体时间轴；以固定首播基准与片段周期映射 loop、原始 PTS、unwrapped PTS。转身片的固定容器偏移单独扣除。
2. `public/frame-queue.js` 管理最多 2 张等待快照；同一时间只有 1 次推理在途，只提交已到计划释放时刻的帧，过期帧可跳过。不能把显示刷新率等同新推理 Hz。
3. `public/pose-worker.js` 接收当前捕获位图。Python 路径将同一幅 512 px 最长边图像送为 RGBA8；前后端校验 frame_id、epoch 和 source_pts_ms。原位图和对应结果一起显示。
4. `pose-v52-python/server_epoch_modes.py` 调用 MediaPipe Pose Landmarker。`epoch_clock.py` 区分真实源 PTS 和模型要求的递增毫秒时钟。warm 模式保留模型内部 tracking/ROI，cold 模式重建；模型时间不能与浏览器墙钟直接相减求延迟。
5. `public/joint-policy.js` 用每关节 visibility/presence 较小值、分组进入/退出门槛、有限性/跳变/骨长检查，将输出分为 measured、uncertain、lost。v5.2 保留 uncertain 坐标用于明确标记的不确定展示，lost 为 null。measured 只说明通过当前策略，不是 3D 真值认证。
6. 进入门槛为躯干 0.60、肘膝 0.65、腕踝和细节点 0.70；退出门槛分别为 0.50/0.50/0.55/0.55。低于 0.35 为 lost。warm 跨上下文首帧须重新标记 uncertain。
7. 因果预览最多使用过去两次 measured 数据，窗口不超过 150 ms；3D 速度上限 6 m/s、归一化速度 3/s。预测单独标记，不计新检测。
8. `joint-policy-v4.js` 保留短缺口回放修复逻辑：同片段/epoch、两端 measured、间隔不超过 350 ms。它需要未来端点，只适用于离线回放，不能用作实时检测证据。

主入口：`baselines/v5.2/pose-v52/public/app.js`。原始 33 点坐标、置信度与派生输出分别保留。单目髋相对 world landmarks 不提供已标定的绝对世界平移或独立的 3D 准确度保证。

## v4：历史策略

`baselines/pose-live-v4/public/joint-policy.js` 使用统一的 0.65/0.50 进入/退出门槛和 2 次合格恢复。uncertain/lost 观测坐标均隐藏。v5.2 的语义与 v4 不完全相同，不能直接混用有效 FPS 指标。v4 的 app、策略、Worker 和独立审计测试均按源包原样保留。

## v6：未成功的固定 DOF 候选

`experiments/pose-ik-v6/src/opensim_ik.py` 用 OpenSim 4.6 实现自建简化 25 DOF 模型：自由根 6、躯干 3、两侧肩/髋各 3、肘/膝各 1。以 12 个主要关节中心拟合，不包含肌肉、足底接触或个人临床标定。

前 30 个实际输出用于骨长中位数校准；不足 5 个合格样本时使用显式默认值，校准质量单独记录。measured 权重为 confidence²，uncertain 为 0.1 × confidence²，lost/非有限/显式缺失为 0。除根以外的坐标有 clamped 范围；没有额外速度裁切或时间平滑。上帧仅作求解初值。

`live-app/pose-v52-python/live_ik.py` 强制拟合最近一次真实推理的精确身份，同一个输入不能重复拟合；拟合坐标和未观测几何推断不升级为 measured。全失时保持无姿态。

归档报告明确结论为负：固定简化模型没有稳定减少速度尾部，部分动作幅度被压缩，转身残差偏大。该结论不否定整个人体先验/OpenSim 路线，但不支持用本候选替换 v5.2。合成同模型测试只验证求解器自洽，不能证明人体建模或真实 3D 精度。
