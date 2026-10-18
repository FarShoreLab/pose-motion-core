# Pose Motion Core：核心算法备份

这是从 3 份已保存源码包恢复的轻量备份。基线源文件逐字节保留，没有改算法，没有重新运行模型，也没有把旧实验改称成功版本。

## 版本选择

- **当前保留基线：v5.2**，位于 `baselines/v5.2/`。浏览器前端和 Python CPU 后端仍是相邻目录。
- **历史版本：v4**，位于 `baselines/pose-live-v4/`。
- **失败实验：v6 固定 25 自由度 OpenSim IK**，位于 `experiments/pose-ik-v6/`。保留实现、模型定义 XML、测试和原报告，供复查负结果；不得替换 v5.2。
- v5 / v5.1 只有 v5.2 包内的历史说明、策略文件和差异文件，不能视为完整独立版本。
- 最初版本 / final-v3 源码未在这 3 份包中找到，**没有假装恢复**。

## 备份包含什么

源码、锁定依赖文件、原始安装说明、关节策略、帧队列、时间映射、Worker 契约、后端时钟、OpenSim 求解器、审计/测试脚本，以及来源与 SHA-256 清单。

**不包含**模型权重、视频、node_modules、虚拟环境、录屏、逐帧结果、私有运行日志或凭据。`simplified_human.osim` 是可读的人体模型定义 XML，属于核心实现，保留；它不是模型权重二进制。

原目录中的 README 是历史原文；其中“已包含依赖/模型”、性能结果、运行路径和报告链接描述原交付，不代表这个精简备份已包含它们或本次重测通过。以本 README 和 `docs/RESTORE.md` 为当前备份说明。

## 先验证源码

在本目录运行：

```sh
python3 scripts/verify_backup.py
python3 scripts/run_checks.py
```

只需 Python 3 和 Node.js；默认测试不安装包、不访问互联网、不加载 MediaPipe/OpenSim、不执行姿态推理。HTTP Range 测试会短暂启动本地静态测试服务器。测试范围和本次结果见 `docs/VALIDATION.md`。

## 恢复和继续开发

1. 先阅读 `docs/RESTORE.md`，按所选版本恢复依赖与外部资源。
2. 在新分支或新目录做后续算法，不修改这次归档基线。
3. `manifests/baseline-sources.json` 记录每个来源 ZIP、归档版本、SHA-256，以及 170 个原样保留文件的来源路径和哈希。
4. Git 快照只记录这次真实备份；没有原 Git 历史。若附带 bundle，可用 `git clone pose-motion-core.bundle restored-pose-motion-core` 恢复。ZIP 的源码目录不含 `.git`，bundle 另保留该次提交。

算法边界见 `docs/ALGORITHM.md`，依赖与权利边界见 `docs/THIRD_PARTY.md`。本次未选择或授予新的开源许可证。
