# 在独立目录复现本次离线评测

本目录是离线实验，不修改 v4/v5.2/v6。实际结果见 `reports/2026-10-18-round2/README-zh.md`；实际代码关系见仓库 `docs/ARCHITECTURE-2026-10-18-zh.md`。

## 固定依赖和资源

- Windows 测试环境：Python 3.10.22 + PyTorch 2.3.0+cu121（GVHMR）；Python 3.13.1 + MediaPipe 1.1.0（CPU）。完整已解析版本在 `provenance/*requirements-resolved.txt`。此文件记录实际环境，不是跨平台安装保证。
- 上游 GVHMR：<https://github.com/zju3dv/GVHMR/tree/ee960bb6e2ea2d381aa97f08e9b71ef320b624b1>。将源码放在 `src/GVHMR-ee960bb6e2ea2d381aa97f08e9b71ef320b624b1/`。
- PyTorch3D v0.7.6：<https://github.com/facebookresearch/pytorch3d/tree/v0.7.6>。只使用其官方 Python transforms 源码，放在 `src/pytorch3d-0.7.6/`，本次没有编译原生渲染/KNN 扩展。
- 在干净的固定 GVHMR 源码根运行 `git apply --check <本实验目录>/patches/laptop-adapter.patch`，然后 `git apply <同一路径>`。补丁已在固定源码的新副本上实际应用，并匹配 14 个运行文件的规范化 UTF-8 哈希。源文件应使用 LF；补丁包含正确的无末尾换行标记。
- GVHMR 及其衍生补丁限教育、科研和非营利使用；保留 `patches/GVHMR-LICENSE.txt`。ViTPose/HMR2/YOLO/SMPL-X 各自许可仍单独适用。补丁不授予模型或商业使用许可。
- 权重路径、大小、SHA-256、项目官方演示所用公开镜像见 `provenance/model-assets.json`。SMPL-X 由使用者按其许可自行提供；仓库和证据包均不包含它。不要把权重放入 Git。

实验根布局：

```text
<experiment-root>/
  scripts_v2/                       本目录的脚本副本
  .venv/Scripts/python.exe          GVHMR 环境
  .venv-mediapipe/Scripts/python.exe
  src/GVHMR-ee960bb6e2ea2d381aa97f08e9b71ef320b624b1/
  src/pytorch3d-0.7.6/
  assets/checkpoints/{yolo,vitpose,hmr2,gvhmr}/
  assets/body_models/smplx/SMPLX_NEUTRAL.npz
  assets/pose_landmarker_lite.task
  outputs/<clip>/input_30fps.mp4
  outputs/<clip>/frame-map.csv
  outputs/<clip>/input-manifest.json
  outputs/<clip>/source-pts.json
```

## 精确输入与运行

为了重现本次编码输入的字节，请从完整证据包只复制每片的四个输入/映射文件到新的实验根；不要复制已有 `pipeline-timings.json` 或预测文件。输入 SHA-256 在报告清单中。原始来源可按 clips.json 的公开 URL 获取；重新转码的文件可能因编码器版本而不同，不能悄悄沿用本次输入哈希。芭蕾本轮使用已有 720p 派生源，确切共同输入已随证据包交付。

在 PowerShell 中只对当前进程设置：

```powershell
$env:POSE_MOTION_ROOT = '<experiment-root>'
& '<experiment-root>\.venv-mediapipe\Scripts\python.exe' '<experiment-root>\scripts_v2\run_suite.py' --skip-prepare
& '<experiment-root>\.venv-mediapipe\Scripts\python.exe' '<experiment-root>\scripts_v2\analyze_round2.py'
& '<experiment-root>\.venv-mediapipe\Scripts\python.exe' '<experiment-root>\scripts_v2\render_delivery.py'
```

也可加 `--name r2_fast_burpees` 只运行一片。若已有全部源文件并希望重新编码，省略 `--skip-prepare`，脚本会核查不覆盖旧输入。任何完整输出已存在时会停止，应用新的实验根。`isolate_env.py` 必须先于第三方导入，缓存、YOLO 设置、Matplotlib、Torch、HF、CUDA、临时目录等均限制在当前实验根；不要直接从裸 Python 导入 Ultralytics 做诊断。

## 测量与审阅

完整 E2E 来自父进程连续计时，不能把阶段工作时间相加冒充完整耗时；GPU 每阶段工作计时前后同步。GVHMR 含第二次完整 forward 生成官方后处理，另记 raw tensor 就绪时间。预处理、可视化另计。资源采样记录实际采样时刻；nvidia-smi 查询会延迟 RSS 采样，因此峰值是采样下界，整卡占用还包含其他进程。

MediaPipe 在本测试处理全分辨率离线文件，模型 VIDEO 内部跟踪保留，但没有 v5.2 外部策略、浏览器队列或 v6 IK；因此这不是 v5.2 实时延迟复测。GVHMR 使用未来帧。官方后处理和原始结果分开，预测参数/关节点保存在 NPZ，原始 MP 在 NPZ/JSONL，所有缺失与插值不隐藏。

本轮未修改驱动、网络或系统全局环境；此前 pilot 诊断造成的全局 Ultralytics 设置重置仍作为已知事件保留，没有猜测回滚。本轮全局文件开始/结束哈希相同，见 isolation 记录。源视频作者、许可和派生说明必须随评审视频一起保留；三栏视频也写入 MP4 元数据。
