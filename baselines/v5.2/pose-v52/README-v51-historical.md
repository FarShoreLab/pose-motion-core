# POSE LIVE v5：真实因果推理，显式保留不确定观测

## 推荐快捷启动：v5.1三个真实运动输入

源码包解压后，pose-v5 与 pose-v5-python 必须保持同级。将 pose-live-v5.1-primary-inputs.zip 解压到同一根目录，保留 pose-v5/assets/videos/ 的目录层级。该视频包含三份获许可的派生视频、署名与许可链接、原始/派生SHA、逐帧PTS映射CSV。它们分别为慢深蹲25fps、快速开合跳/波比跳29.97fps、芭蕾转身25fps；不是旧Pexels的24/25/30fps三片。快动作原素材只有640×480，未上采样为720p，也不是篮球。另两片为1280×720。

这是本次云Linux实际使用的配置。源码包含固定模型和浏览器依赖，Python虚拟环境不随包分发。新的干净机器安装尚未完整重测，详见 ../pose-v5-python/INSTALL.md。首次安装官方固定Python依赖：

    sh pose-v5-python/install-linux.sh

停止占用8766的旧进程后，从两个目录的共同父目录启动推荐配置：

    sh pose-v5-python/start-epoch-modes.sh --port 8766 --epoch-policy warm

依次打开以下完整地址，不要遗漏backend参数；每个65秒窗口源视频自然1×循环、现场重新推理：

    http://127.0.0.1:8766/?run=commons-overhead25&seconds=65&name=my-slow-run-001&backend=python
    http://127.0.0.1:8766/?run=commons-jumping2997&seconds=65&name=my-fast-run-001&backend=python
    http://127.0.0.1:8766/?run=commons-pirouettes25&seconds=65&name=my-turn-run-001&backend=python

不要同时开两个实时推理标签页或运行API测试。每次换name以保留旧结果。自动测试结束会暂停原视频并保持末帧；保存失败也进入结束态，仍可“导出原始记录”。源码不包含所有可选菜单素材，因此请用上方完整URL选择已打包的输入，不能依赖首页默认旧slow素材。

cold对照仍保留，需先停warm服务器再启动：

    sh pose-v5-python/start-epoch-modes.sh --port 8766 --epoch-policy cold

warm保留模型内部ROI跟踪历史，使用跨epoch单调模型时间戳。它不缓存骨架输出，每个当前PNG仍真实推理。应用关节历史在loop/seek清空，跨epoch第一结果标为不确定。它减少cold重建空窗，但不等于跨不同场景的相同跟踪状态或相同精度；契约见 ../pose-v5-python/EPOCH-MODES.md。

v5.1仅新增输入选择、来源元数据与版本信息。推理worker、关节策略、队列、预测和绘制逻辑与已保留v5工作版相同；差异见 v5-to-v5.1-inputs.diff。此前v3/v4/v5源码和记录均保留，不覆盖旧包。真实结果、原始JSON/CSV、审计和录像在独立证据包，不伪装为干净安装或准确率认证。

## 启动与测试

以下为原JS/WASM诊断入口，固定模型和依赖已打包，无需在线模型下载。当前云浏览器缺少Worker WebGL时，此入口会明确失败；推荐使用上面的Python配置。运行：

    python3 server.py 8767

原始三份视频可用时（本次未完整恢复，不可把此URL当已可用输入）：

    http://127.0.0.1:8767/?run=slow&seconds=65&name=slow-v5&suite=1

会依次对 slow / fast / challenge 现场重新推理各65秒，源视频自然1×循环，自动测试结束后暂停并标为保持末帧，无未来帧输入、无离线姿态输入。源视频不是随源码原本提供的文件；必须核对 assets/videos/ 中实际恢复的视频与相应来源说明。三片原视频不可用时，不得把其他素材命名成原文件冒充恢复。

冒烟入口（仅5fps，不能证明24/25/30fps性能）：

    http://127.0.0.1:8767/?run=smoke&seconds=15&name=smoke-v5

JSON 自动写 results/<name>.json。页面“导出原始记录”亦可导出。window.poseDemo 提供只读状态、exportLog()、save(name) 和素材切换。npm test 执行语法、10项关节策略、worker时钟/bitmap协议、HTTP Range检查。以上单测不代替真实浏览器测量。

## 本次改动

1. 原始模型输出不修改。中等置信度有限点不再一律隐藏：琥珀空心点与虚线表示不确定原始观测，绿色实心表示通过确定性门槛。丢失点隐藏。顶栏“原始33点”显示额外灰色原始二维点，含被门控隐藏但有限的坐标。
2. 确定观测采用关节分组：躯干 enter .60 / exit .50；肘膝 .65 / .50；腕踝及细节 .70 / .55。恢复由两次强观测改为一次，减少缺口但可能增加短暂错误恢复。低于 .35 的 visibility/presence 最小值仍隐藏；阈值是未用独立真值标定的工程值；硬有限/坐标边界检查和速度/骨长检查保留。速度/骨长异常降为可见不确定，不计确定有效。
3. 单帧同步512px canvas快照锁定 rVFC 对应视频帧，ImageBitmap直接传入worker，同一个bitmap在同步 detectForVideo 完成后返回主线程。删除全分辨率捕获与第二次resize-clone。显示分辨率现在也为max-edge512，较v4全分辨率保留图降低显示细节，必须与性能收益一起披露。
4. 最多1个在途推理 + 1个最新待释放快照。新已释放快照替换旧待处理快照时明确记录跳过源帧；未来帧不能挤掉较近的待释放帧而造成饥饿；源视频继续1×播放。严格配对主屏只在新结果到达时更新，并不等于源视频24–30fps。返回消息直接完成配对绘制，减少等下一次rAF的额外等待。
5. 循环/seek不重新加载模型。MediaPipe内部推理时间戳跨epoch严格递增；关节跟踪和预测历史每epoch清空。warm模型可能保留上一段ROI，因此第一新周期结果只能不确定显示，随后按置信度重新获取。这减少初始化空白，但无法保证所有突然切换都正确跟踪，需实际录像检查。
6. Three.js仅作真实world-XYZ透视投影，绘制为Canvas2D。观测3D按新结果/旋转变化重画；预测最多15Hz，预测本身仍只取过去两次确定观测，最长150ms，当前不确定的关节也不预测。预测不计新观测或有效姿态。
7. 回放帧缓存默认关闭，避免为验证实时性能引入额外每帧copy。需要原有离线回放功能时加retain=1；未来端点修复只用于明确标注的离线回放。

## 日志与不能混淆的口径

- frames：每次真实rVFC callback，source PTS、frame_id、epoch、loop、scheduled release、捕获/dispatch、跳过原因。
- inferences：每次真实模型运行，统一performance时钟上的start/end/result、原始33点、visibility/presence、exact bitmap对应ID、joint states/reasons/transitions。
- valid：保留v4旧模型全局口径（12主要关节的平均vis/pres >=.5且world33点有限）。
- v4_filtered_valid：冻结v4策略在同一份raw输入上复算，策略文件同字节保留。
- filtered_valid：新策略12主要关节全部measured。不确定可见、预测和回放修复都不算。
- renders：只有新结果的配对绘制。总延迟为软件源release→draw提交，包含capture/copy/worker/model/回传/draw，不能当物理显示光子延迟。
- sync_error_ms：本次显示位图PTS与本次姿态PTS之差。匹配同一帧可为0，但不能说明图像新鲜或低延迟。
- source_lead_ms / frame_age_ms：原速视频领先配对图像的时差以及配对画面年龄，独立记录。
- render_ticks：每rAF记录留存画面，new_observation始终false；不能用它作为新姿态Hz。
- 当前模型没有地面真值，因此“measured”意为通过质量门槛，不是准确性保证；三维精度未校准。

旧v4源码包未覆盖。public/joint-policy-v4.js、public/app-v4-reference.js为本次对照；legacy-v4-docs与audit_v4仅供历史参考，不是本次v5结果。新源码SHA在public/source-manifest.json。

## 云浏览器无WebGL时的独立Python CPU配置

本次云浏览器普通网页API确认Worker无可用WebGL。即便delegate=CPU，固定MediaPipe JS图像输入也依赖GL纹理上传，因此该JS配置会明确显示失败并停机，不伪装为成功。

独立目录 ../pose-v5-python 提供官方 MediaPipe Python 1.1.0 CPU/XNNPACK 后端（同一lite.task SHA）。按该目录README/启动脚本运行服务器后，用同源地址加 backend=python，例如：

    http://127.0.0.1:8766/?run=worker&seconds=65&name=worker-python-v5&backend=python

worker/aisle是原始59.94fps的Intel真人替代输入，不是恢复的原24/25/30fps片段；具体许可与来源见assets/videos/ALTERNATIVE-SOURCES.md、alternative-input-manifest.json。smoke为原始5fps，仅可作流程检查。不得升采样后冒充高帧率输入。

Python配置仍由浏览器rVFC现场截取当前帧；同一个512px bitmap用PNG无损编码后POST到同源infer端点，后端仅推理这一请求，不读取源视频、不缓存轨迹。返回结果必须echo匹配frame_id、sessionUUID:epoch与source PTS，才能与保留原bitmap绘制。该后端首次播放前调用不含图像、不会推理的prepare（暖机在开始计时前，另有明确记录）；之后每epoch新建VIDEO tracker，循环时源视频不暂停，close+create与首次推理总耗时包含在本次请求内；这与JS warm-loop策略不同。

所有browser release/capture/dispatch/HTTP bracket/result/draw时间来自统一performance时钟。worker_processing_total_ms包含PNG编码与整个HTTP往返；inference_ms是后端自己的monotonic时钟测得的纯模型耗时，不能将两者混为同一时段或跨时钟相减。backend_stages_ms分列嵌套时长，不重复累加。完整端到端以总release→draw提交为准。新后端不同runtime/configuration，因此它的速度变化不能单独归因于v5前端优化，也不是原v4 JS栈达到目标的证据。
