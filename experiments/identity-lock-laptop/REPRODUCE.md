# 复现和文件约定

本次使用 Python 3.10.22、Windows、独立 `.venv`。完整安装版本见 `requirements-lock-final.txt`；它是实测环境清单，不是可跨平台使用的带 wheel 哈希锁文件。关键包为 Ultralytics 8.4.182、torch 2.3.0+cu121、torchvision 0.18.0+cu121、numpy 1.26.4、opencv-python 4.10.0.84、onnxruntime 1.19.2、lap 0.5.12、av 13.0.0、scipy 1.14.1、onnx 1.19.0。torch 的 CUDA wheel 来自官方 PyTorch cu121 索引，其余来自 PyPI；不自动安装任何新依赖。

`POSE_COMPARISON_BASE` 指向已有 `gvhmr-comparison-laptop` 素材目录，含 `outputs/<clip>/input_30fps.mp4`、`frame-map.csv`、`input-manifest.json` 和旧 bbox/MediaPipe 结果。`POSE_IDENTITY_ROOT` 指向新实验数据目录。两个环境变量均可覆盖，脚本默认值只适用于这次 laptop。`isolation.py` 在导入第三方库前设置本实验的缓存、临时目录和离线选项。

已有权重不在 Git 或附件内。YOLOv8x 使用已有文件；唯一新增 ReID 来自 [Ultralytics 官方 assets v8.4.0](https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n-reid.onnx)。完整字节数与 SHA256 见 `asset-provenance.json`。`fetch_assets.py` 是显式下载入口，不在检查或缓存重放时运行。原视频素材与变换、作者、许可、SHA256 见 `metrics/inputs/<clip>/input-manifest.json`。

## 仅运行门控单元测试

在 `scripts` 目录，用已准备好的实验 Python 运行：

```powershell
& $identityPython -B -m unittest test_target_policy test_target_policy_v2 -v
```

13 项测试覆盖相同 ID 的外观切换拒绝、模糊候选、有限无效预测、恢复确认、模板保护和图库策略；它们不证明真实视频身份准确率。最终实际输出的完整性检查见 `metrics/final-audit.json`。

## 不重跑检测或 ReID 的缓存复现

解压诊断附件的 `experiment-data/` 到一个**新的** `POSE_IDENTITY_ROOT`。其中包含冻结检测 JSONL、ReID NPZ、每次决策和失败记录；不要覆盖这次原始输出。`run_cached_guard.py` 可使用新 attempt 名：

```powershell
& $identityPython -B scripts/run_cached_guard.py --source basketball-botsort-v1-model448 --attempt replay-v3-check --policy policy-v3.json
```

预期 83 个有效帧、48 次模板更新、5 次恢复。输出必须对照 `metrics/visual-evaluation/evaluation-summary.json` 判断身份，而非仅看 valid 数。此步骤无需输入视频，不执行模型推理。原 224 的失败结果和特征仍保留，但当前 `run_tracking.py` 已按模型元数据使用 448。

`compare_cached_trackers.py` 对同一 448 冻结检测和真实 ReID 特征运行 BoT-SORT 与一次 Deep OC-SORT，还需要原篮球输入视频用于相同 GMC。它将输出到固定的 `basketball-deepocsort-gallery-v3` 新目录，因此重跑应使用一个只有 448 源缓存的新实验根目录；已有目录会拒绝覆盖。预期 BoT 重放零不一致，Deep 裸初始 ID 在 F88/F90 错跟，v3 仍只接受 83 帧。

## 如需从头重新推理

另建环境/实验目录，核对素材及权重哈希，再显式执行：

```powershell
& $identityPython -B scripts/run_tracking.py --clip r2_occlusion_basketball --attempt basketball-botsort-v1-model448
& $identityPython -B scripts/run_cached_guard.py --attempt basketball-botsort-gallery-v2 --policy policy-v2.json
& $identityPython -B scripts/run_cached_guard.py --attempt basketball-botsort-gallery-v3 --policy policy-v3.json
& $identityPython -B scripts/compare_cached_trackers.py
```

六段 `holdout-*.json` 使用预先目视确认的首帧框，`run_holdout_batch.py` 顺序执行。不得用回归结果重新调参后仍把它们称为未见过的测试集。

可视化脚本从真实输入帧读取。`render_detection_annotation.py`、`render_annotation_supplement.py` 仅生成待检查候选图；`evaluate_visual_annotations.py` 固化本次助手的目视判断，因此不是自动生成独立真值的程序。`render_final_evidence.py` 和 `render_holdout_review.py` 生成实际帧回放；创建已有输出目录时会拒绝覆盖。

诊断附件 `baseline-reference/` 仅带原框、MediaPipe 篮球输出、输入清单和时间映射等小文件，不含原视频和权重。重新渲染依赖已有合法素材，不能把附件称作无需素材的完整独立运行包。附件和 Git 提交都不包含凭据。
