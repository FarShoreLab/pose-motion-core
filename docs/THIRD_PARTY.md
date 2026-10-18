# 第三方来源与许可边界

没有为整个备份新加 MIT、Apache 或其他总括许可证，也没有断言用户拥有全部第三方素材的再许可权。

- MediaPipe、Three.js、OpenSim、NumPy、SciPy、OpenCV 等各自遵循其原许可证。固定版本和软件包完整性信息按原 lock / requirements 保存；依赖正文及 vendored binaries 不在本备份中。恢复时检查对应精确版本的包内 LICENSE/NOTICE。
- 人体定义 `src/simplified_human.osim` 是该实验包提供的可读 XML，与 OpenSim 引擎本身分开；保留它不构成对其他模型的许可声明。
- 原视频来源、作者、许可链接和修改说明保留在各 `assets/videos/*SOURCES.md` 与清单中。该信息为历史文档，媒体本身未随本备份再分发。
- Commons 素材说明区分 CC BY-SA 4.0 / 3.0、作者与转码改动；历史 Pexels 与 Intel 来源仍有各自条款。程序许可不会替代媒体许可。已有 `intel-LICENSE` 原文一并保留以避免丢失来源条件，并不意味着本包包含 Intel 视频。
- 原始 README 中关于许可证或第三方的文字按归档保存；新的发布、重分发或商业使用需根据实际包含的内容重新检查。

若后续要公开仓库，先确认代码的许可选择与所有新增文件的可公开性。私有备份也不应提交密钥、个人视频或私有运行日志。
