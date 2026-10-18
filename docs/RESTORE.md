# 恢复指南与已知缺口

## 1. 核验，不覆盖历史基线

```sh
python3 scripts/verify_backup.py
python3 scripts/run_checks.py
```

`baseline-sources.json` 中所有保留文件均应匹配来源 ZIP 的 SHA-256。导入 Git 的时间是本次备份时间，不能伪装为历史提交。后续修改请在单独工作副本/分支中进行。

## 2. 依赖锁定

- 每个前端保留 `package.json` 和 `package-lock.json`。固定主版本为 MediaPipe Tasks Vision 1.1.0、Three.js 0.180.0、esbuild 0.25.12。进入相应前端目录运行 `npm ci --ignore-scripts`；不要用 `npm update` 替代恢复。
- v5.2：`baselines/v5.2/pose-v52-python/requirements-lock.txt` 固定 Python 依赖；原始 `install-linux.sh` 面向 Linux x86_64 / Python 3.12 创建 `.venv`。原注释明确说锁文件从观察版本导出、没有清洁安装重测，本备份也没有重测安装。
- v6：`requirements-minimal.txt` 固定 OpenSim 4.6、MediaPipe 1.1.0、OpenCV contrib 5.0.0.93、aiohttp 3.14.4、NumPy 2.3.5、SciPy 1.17.0。原 `requirements-environment.txt` 含不便携且与核心算法无关的本机环境路径，已从公开备份排除；顶层最小依赖版本照原样保留。不要误用 v6 内旧前端附带的 v5.2 Python 锁来替代 v6 的顶层安装说明。
- Python 锁文件没有 wheel 哈希，OS 图形动态库也没有统一跨平台锁。当前 Git 备份不是完整可重复的系统镜像。

这些都是归档时原值，没有联网确认今天仍可下载安装，也没有升级。安装/模型运行须在合适平台和获授权的环境进行。

原 v5.2 `INSTALL.md` 的开头与后文对“清洁安装已验证”有矛盾；以未在此次备份重新验证为准。原文保持不动以保护历史。

## 3. 单独恢复模型

`assets/model-manifest.json` 保留官方来源、revision 1、5,777,746 字节及 SHA-256：

`59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a`

示例（这是显式联网下载步骤，本次备份没有执行）：

```sh
python3 scripts/restore_model.py --frontend baselines/v5.2/pose-v52
```

脚本只按现有模型清单下载并校验；不会下载视频或加载模型。每个前端目录需要自己的模型文件。原 `download_assets.py` 同时下载历史视频，可能涉及失效来源，不建议为了取模型直接运行它。

## 4. 视频与完整演示

此包没有视频。保留的 `assets/videos/manifest.json`、`active-candidates.json`、`COMMONS-SOURCES.md` 和 `seamless/*.json` 是公开来源/署名/版本/哈希/时间映射信息，不是运行日志。

- v4 历史 Pexels 素材：原文件 URL 和哈希保留。归档说明记录过访问失败；不能用任意同名视频冒充原素材。
- v5.2 / v6：需要独立的连续输入包，或精确恢复 Commons 派生 MP4 后用 `scripts/build_seamless_assets.py` 重封装。三个派生源 MP4 的期望哈希在 `active-candidates.json`；最终 fMP4 哈希在 `seamless/*.json`。
- 原说明提到的完整 `commons-input-manifest.json`、原始源视频、精确转码命令及全部媒体证据未在这三份源码包中完整提供。因此本备份不能保证从公开原片一键复建为完全相同的派生字节。不同转码/ffmpeg 版本可能改变哈希，必须如实另记。
- 找回输入包时先按保存的哈希核对。模型/视频/依赖恢复后再运行相应 `verify_layout.py` 和原安装说明。

本次未运行 API/native/inference/browser/performance 测试。默认轻量检查通过不能证明实时表现或正确恢复了视频。

v6 的 `audit/audit_live.py` 还依赖未提供的 `baseline-v5.2/` 树；`audit/run_wrapper_audit.py` 需要未提供的 `metric-reference/raw`。它们保留为历史审计源码，不能在无数据时冒充复现完成。v6 内的 `public/source-manifest.json` 和 `package.json` 沿用了 v5.2 身份；前者的 app/worker/index/style 哈希已与 v6 实际代码不同。以根目录新建的 `manifests/baseline-sources.json` 核验归档字节，旧清单只作为历史记录。

## 5. 启动路径和安全

v5.2 原入口：在 `baselines/v5.2/` 中执行 `sh pose-v52/start.sh 8768`；需要已装好的 Python 环境、JS 依赖、模型和连续输入。v6 原入口：在 `experiments/pose-ik-v6/` 阅读 `INSTALL-zh.md`，用其顶层 `.venv` 与 `live-app/start-live.sh`，只用于复查实验。

v4 静态服务器监听 0.0.0.0，不能直接暴露公网。源码中未增加认证；不要把原始姿态日志、录屏、访问密钥或个人视频提交到 Git。

## 6. Git bundle

如交付 ZIP 根部附带 `pose-motion-core.bundle`：

```sh
git clone pose-motion-core.bundle restored-pose-motion-core
cd restored-pose-motion-core
git log --oneline
python3 scripts/verify_backup.py
```

只有本次新建的一个归档提交，不含原始开发历史。GitHub 仓库创建、可见性、上传与远程提交核验由单独步骤处理；本地 bundle 本身不代表已在 GitHub 备份。
