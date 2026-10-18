# POSE LIVE v5.2：有界等待队列与连续循环

## 本轮改动

- 固定 MediaPipe Python 1.1.0、Lite float16 模型、CPU/XNNPACK、512px最长边输入，以及 v5.1 的全部关节置信度/合理性门槛。worldLandmarks 保留。绿色实测、琥珀不确定、隐藏丢失、紫色≤150ms因果预测仍分开，预测不计检测结果。
- 浏览器 MediaSource 追加同一段原始压缩帧的 fMP4 重封装，形成连续媒体时间轴。源视频正常1×；不在每圈执行原生 seek。最多约2.25个源周期在前方，最多约2个周期在后方，旧缓冲定期清理。预缓冲的是压缩视频，推理只接收当下 rVFC 回调锁定的位图。
- 固定首个 play 时钟基准，之后每圈仅加原片的精确周期。日志仍记录固定理想源释放→软件绘制提交的总延迟，不通过每圈重设计时掩盖延迟。转身片因B帧重封装具有80ms容器起点：仅在开始计时前定位到0.08s；整个运行把媒体时刻减同一80ms，映回原始帧PTS。
- 队列上限明确变为2张待释放/待处理快照加1张推理在途。只有到固定释放时刻的帧可以进入模型；多个已到期帧保留最新一张，不无限堆积。若容量不足，跳帧及原因写入日志。v5.1为1张等待，候选单槽版本发生的吞吐退步也保留在实验记录中。
- 本机 HTTP 帧传输改为同一512px位图的无损RGBA8，省去PNG编解码；仍等待实际模型结果后，用原位图与其结果同时绘制。像素验证把同一真实视频帧的RGBA和PNG交给OpenCV解码比较，589824个RGB通道字节全部相同。HTTP请求体更大，远程网络未验证。

## 解压与启动（已验证云Linux x86_64 / Python3.12）

将源码包和 v5.2 连续输入包解压到同一目录，形成：

    pose-v52/
    pose-v52-python/

模型、Three.js和浏览器依赖已包含。Python环境不随包分发；在新的目录安装官方固定依赖：

    sh pose-v52-python/install-linux.sh

CPU后端仍需系统EGL/GLES动态库。如果系统只缺libGLESv2，安装说明中的官方Debian局部解包脚本可用：

    sh pose-v52-python/fetch-debian-libgles.sh

验证布局，然后启动：

    python3 pose-v52-python/verify_layout.py
    bash pose-v52/start.sh 8768

浏览器打开以下三个地址（同一时刻只运行一个）：

    http://127.0.0.1:8768/?run=commons-overhead25&seconds=65&name=my-slow-001
    http://127.0.0.1:8768/?run=commons-jumping2997&seconds=65&name=my-fast-001
    http://127.0.0.1:8768/?run=commons-pirouettes25&seconds=65&name=my-turn-001

每次换name保留原始结果。默认后端是Python，默认播放模式是连续源，默认2张等待快照。可以不带参数打开首页、手动选择三片输入。运行结束会暂停源视频并明确显示保持末帧。PNG对照加transport=png；单等待槽诊断加pending=1。原生循环对照加playback=native，但需要v5.1原输入复制到pose-v52/assets/videos/candidates-commons（见原输入包，不能拿fMP4改名冒充原片）。

默认只监听127.0.0.1。没有新增认证、凭据、远程服务或浏览器不安全参数。Windows、macOS、ARM、外部网络延迟、移动浏览器和其他机器性能均未验证。浏览器必须支持相应H264 MSE codec；不支持时会明确报错，不自动改成预计算。

## 测试与结果

    cd pose-v52 && npm test

包括语法、原关节策略、单槽和双槽队列、Worker身份/时间、HTTP Range，以及三片共1,418,000个源帧在1000周期内的时间映射测试。独立审计还对80,111个位图生命周期做随机队列压力测试，检查容量、无提前分发、无饥饿和一次释放。

正式性能仅以交付的65秒现场实测、桌面录屏和逐帧/逐推理JSON/CSV为准，不能用单元测试、12秒冒烟或离线重放替代。所有新旧对照均使用同一云机器、CPU模型、输入帧，正式运行前重新启动模型服务，录像时保持相同桌面采集设置。

数据口径：
- new_paired：新的真实推理结果完成精确同帧绘制的次数/观测窗口。
- rawvalid_paired：沿用v5.1原始33点有限且12关节平均vis/pres≥0.5的口径。
- strict12：12主关节全部为measured；不确定和预测不算。
- render_ticks：rAF刷新，包含重复展示同一结果，不能当作新姿态Hz。
- total_delay_ms：固定理想源释放→软件绘制提交；不等于物理显示光子延迟。
- sync_error_ms：同帧图像PTS减姿态PTS，零差不代表没有处理延迟。
- 回失/恢复统计没有3D真值，只描述门槛下的观察状态；更多检测次数不等于模型更准确。

源码源文件hash、原始逐帧PTS和压缩包样本hash、80ms容器偏移、实测机器与依赖版本均随交付保存。模型权重、关节策略和各阶段原始输出保留可复核。v3/v4/v5.1原交付不覆盖；本版本为独立副本。

## 素材与许可

输入与v5.1相同：壶铃深蹲25fps720p、开合跳/波比跳29.97fps原480p、芭蕾转身25fps720p。快片不是篮球、不是720p，未上采样。v5.2重封装没有重新编码或增删源帧；转身容器PTS统一增加80ms，并在映射中明确扣除。

完整作者/来源/CC BY-SA许可及此前转码说明见assets/videos/COMMONS-SOURCES.md与输入包ATTRIBUTION.txt。录屏中叠加了2D/3D骨架与性能UI，保留相同署名与适用ShareAlike许可。
