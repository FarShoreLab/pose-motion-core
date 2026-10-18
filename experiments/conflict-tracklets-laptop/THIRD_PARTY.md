# 依赖与素材来源

此次仅在独立实验环境使用官方 PyPI / PyTorch wheel 和官方模型来源。没有点击新的法律接受流程，也不声称拥有企业授权或商业用途许可。

| 项目 | 固定版本 / 来源 | 许可或限制 |
|---|---|---|
| Ultralytics BoT-SORT、Deep OC-SORT 实现 | 8.4.182，PyPI | [Ultralytics AGPL-3.0 / Enterprise 说明](https://www.ultralytics.com/license)；本次没有 Enterprise 授权声明 |
| yolo26n-reid ONNX | [官方 assets v8.4.0](https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n-reid.onnx)，模型元数据为 MSMT17-v1、512 维、448px | 按 Ultralytics 模型许可说明记录为 AGPL-3.0；只测试这一个编码器 |
| YOLOv8x | 复用本地已有权重，SHA256 见 `asset-provenance.json` | Ultralytics 模型许可；未重新分发权重 |
| PyTorch / torchvision | 2.3.0+cu121 / 0.18.0+cu121 | 已安装包元数据及随包许可见 `metrics/dependency-license-metadata.json` |
| ONNX Runtime / ONNX | 1.19.2 / 1.19.0 | 同上；分别为运行时与图结构检查工具 |
| numpy、OpenCV、SciPy、lap、PyAV、Pillow 等 | 完整版本见 `requirements-lock-final.txt` | 保存已安装发行包声明；空或自定义元数据不解释成“无许可限制” |
| GVHMR | 既有基线，仅读取旧结果 | [该版本 LICENSE](https://github.com/zju3dv/GVHMR/blob/ee960bb6e2ea2d381aa97f08e9b71ef320b624b1/LICENSE) 为教育、研究及非营利用途限制；本轮不重新推理，也未给予商业许可判断 |
| MediaPipe | 既有基线，仅读取旧结果 | 项目代码 Apache-2.0；不据此替其他模型或素材授予许可 |

方法参考：[官方跟踪文档](https://docs.ultralytics.com/modes/track/)、[Deep OC-SORT 论文](https://arxiv.org/abs/2302.11813)、[Deep SORT 最近邻图库实现](https://github.com/nwojke/deep_sort/blob/master/deep_sort/tracker.py)。这些来源说明算法与配置背景，不证明本片身份锁定成功。

## 视频与派生画面署名

| 本地片段 | 原作品 / 作者 | 原许可 |
|---|---|---|
| r2_occlusion_basketball | [Basketball (4)](https://commons.wikimedia.org/wiki/File:Basketball_(4).ogv)，Azorbli | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| r2_fast_basketball | [Basketball (1)](https://commons.wikimedia.org/wiki/File:Basketball_(1).ogv)，Azorbli | CC BY-SA 4.0 |
| r2_fast_burpees | [Jumping jacks and burpees](https://commons.wikimedia.org/wiki/File:Jumping_jacks_and_burpees.webm)，Taco fleur (Cavemantraining) | CC BY-SA 4.0 |
| r2_slow_overhead | [Overhead Kettlebell Squat](https://commons.wikimedia.org/wiki/File:Overhead_Kettlebell_Squat.webm)，Cavemantraining (Taco Fleur) | CC BY-SA 4.0 |
| r2_slow_singleleg | [Basic single leg squat](https://commons.wikimedia.org/wiki/File:Basic_single_leg_squat.webm)，RickyBennison | CC BY-SA 4.0 |
| r2_turn_ballet_a / b | [Grands battements et pirouettes](https://commons.wikimedia.org/wiki/File:Grands_battements_et_pirouettes.ogv)，Fanny Schertzer | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) |

本次派生画面的改动：使用之前准备好的片段，静音、最近真实 PTS 采样至 30fps，缩放并排显示，叠加框、标签、时间、方法和来源；不生成插值图像。原始许可信息和裁剪时段完整保存在 `metrics/inputs/`。视频及候选截图沿用各自素材的署名及相同方式共享要求；六段合辑各段保留原许可标识。此次没有替整个源码仓库新设许可证，也没有把第三方权重放入 Git 或交付附件。


本轮 conflict-tracklets 实验仅复用上述输入和缓存，不安装依赖、不推理模型、不分发权重。视频改动为新增框、状态、成本与 AI 审查标签；第一篮球回放为 0.5 倍速。素材对应片段及截图继续按原 CC BY-SA 版本提供，作者/来源/修改记录随包保留。GTA 与 AFLink 只作为方法参考，没有复制或安装其仓库。
