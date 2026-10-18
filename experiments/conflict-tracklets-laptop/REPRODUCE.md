# 复核与复现

本轮已经在 laptop 的既有隔离 Python 3.10.22 环境运行。没有安装依赖、替换模型、修改系统配置或执行新的 3D 推理。`requirements-lock-final.txt` 仅记录此前环境，不是本轮安装动作。

在一个新的本地目录解压诊断包与输入视频包，保持相对目录结构：

```text
base/
  identity-lock-2026-10-18/
    outputs/basketball-botsort-v1-model448/{frame-decisions.jsonl,detection-embeddings.npz,...}
    outputs/holdout-<clip>-v3/{frame-decisions.jsonl,detection-embeddings.npz,...}
    diagnostics/visual-evaluation/{per-frame-visual-annotations.json,per-attempt-identity-decisions.json,...}
  outputs/<clip>/{input_30fps.mp4,input-manifest.json,frame-map.csv}
  conflict-tracklets-2026-10-18/   # 保存的本轮结果与视觉证据
  scripts/                       # 本轮源码
```

将进程环境变量 `POSE_COMPARISON_BASE` 指向上面的 base，将 `POSE_CONFLICT_ROOT` 指向一个**新的空结果目录**。脚本把模型配置、缓存及临时文件环境变量限制到该实验结果目录；不会修改全局环境。调用已经准备好的隔离 Python，不要把下面命令当成依赖安装说明。

```powershell
$env:POSE_COMPARISON_BASE = 'D:\review\base'
$env:POSE_CONFLICT_ROOT = 'D:\review\new-attempt'
& '<isolated-python.exe>' -B -X utf8 .\scripts\test_association.py
& '<isolated-python.exe>' -B -X utf8 .\scripts\run_oracle.py --attempt oracle-v1-pair-certainty
& '<isolated-python.exe>' -B -X utf8 .\scripts\run_experiments.py --clip r2_occlusion_basketball --attempt v1
```

同一 `run_experiments.py` 分别传入其余六个 clip：`r2_fast_basketball`、`r2_fast_burpees`、`r2_slow_overhead`、`r2_slow_singleleg`、`r2_turn_ballet_a`、`r2_turn_ballet_b`。每次运行会拒绝覆盖同名结果目录，并保存代码/配置/输入哈希，检查缓存未变及因果前缀一致性。运行的是缓存关联，不会下载权重或重新做模型推理。

`score_and_preview.py` 生成第一篮球新选择审查，`evaluate_results.py` 读取明确的 AI 标签并评分；`review_fast_basketball.py` 输出第二篮球全部帧，`finalize_assessment.py` 将已完成的 AI 目视结论展开成逐帧标签，**它不是自动真值标注器**。`render_deliverables.py` 生成视频。最终发布脚本只复制、打包、验证已有结果。

复现将使用当前 `association.py` 的逐边排除间隔。早期整组 oracle 输出已另行保存在 `oracle-v1`，没有尝试伪装成当前源码生成的另一次结果。各自动实验的算法代码哈希与政策哈希一致，后加入的视觉审查/发布脚本不改变算法输出。

报告视频时长与原输入不同：第一篮球预演使用全部 207 个真实帧以 15fps 回放，时长 13.8 秒；原输入仍是 30fps、6.9 秒。六段回归视频按 30fps 拼接，共 1434 帧、47.8 秒。没有新插帧或补动作。

身份状态与几何状态是两条独立字段。临时身份的真实候选框可以显示，不能供下游当成已确认目标；缺失框和关节不作插值。离线输出必须连同 `evidence_last_frame` 及 `future_frames_used` 使用，不能混入实时指标。
