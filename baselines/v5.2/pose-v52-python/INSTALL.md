# v5.2 安装说明

本轮已在新建Python3.12虚拟环境实际安装requirements-lock.txt，pip check通过，并在云Linux原生运行环境完成CPU推理和65秒实测。推荐入口为前端README-zh.md的start-epoch-modes.sh --epoch-policy warm。下文保留动态库与平台注意事项；Windows/macOS/ARM仍未测试。

# 可分发安装与启动说明

## 支持范围与目录

当前实际验证环境是 Linux x86_64、Python 3.12.14、MediaPipe 1.1.0。这是 CPU 后端。Windows、macOS、ARM、其他 Python 版本及干净机器上的重新安装尚未验证；不能把本文中的 Linux 脚本当作跨平台安装器。

请保留同级目录，不要把 Python 后端塞入前端目录：

```text
source-root/
  pose-v52/
    public/
    assets/pose_landmarker_lite.task
    assets/videos/
    package.json
    package-lock.json
  pose-v52-python/
    server.py
    start.sh
    install-linux.sh
    fetch-debian-libgles.sh
    verify_layout.py
    requirements-lock.txt
    requirements-observed.txt
```

源码 ZIP 不应包含 `.venv/`、`__pycache__/`、`.cache/`、`.mplconfig/` 或 `system-libs/`。这些是环境产物，应在目标环境安装或重建。前端 `node_modules/` 可不打包，由锁文件安装；如果已包含，仍需校验实际文件。保留现有输入来源、许可证、哈希和不可用原始素材说明。

## 1. 安装 Python 依赖

先在目标 Linux x86_64 上准备 Python 3.12、venv 和 pip，再执行：

```sh
cd source-root
sh pose-v52-python/install-linux.sh
```

脚本只在当前源码目录新建 `.venv`，从官方 `https://pypi.org/simple` 安装固定版本 wheel，不启动服务器或推理，也不修改已有 `.venv`。如果找不到对应 wheel，脚本停止，不会静默编译或从其他来源安装。

等价主要命令：

```sh
python3.12 -m venv pose-v52-python/.venv
pose-v52-python/.venv/bin/python -m pip install --index-url https://pypi.org/simple --only-binary=:all: pip==25.0.1
pose-v52-python/.venv/bin/python -m pip install --index-url https://pypi.org/simple --only-binary=:all: -r pose-v52-python/requirements-lock.txt
pose-v52-python/.venv/bin/python -m pip check
```

`requirements-observed.txt` 是测试时实际环境的原始固定版本清单。初次测试环境同时安装了 `opencv-python-headless` 和 `opencv-contrib-python`，它们共享 `cv2` 命名空间；官方文档建议只装一种。分发用 `requirements-lock.txt` 仅移除冗余 headless 包，保留 MediaPipe 声明依赖的 `opencv-contrib-python==5.0.0.93` 及其他原版本。这份干净安装清单尚未重新安装验证，不能声称逐包环境与旧测试完全一致。不要把两个清单连续安装进同一个 venv。

## 2. Linux 系统动态库

本轮 MediaPipe Python wheel 即使使用 CPU，也需要动态链接 `libEGL.so.1` 和 `libGLESv2.so.2`。它不因此要求可用的浏览器 WebGL/GPU。原测试机器已有 EGL/GLdispatch，缺少 GLES；仅在工作目录解包官方 Debian `libgles2` 后启动成功。

优先由目标机器的管理员通过发行版官方包管理器安装所缺库。Debian 13 示例（仅在该目标机器适用且你允许系统安装时执行）：

```sh
sudo apt-get update
sudo apt-get install libegl1 libgles2 libgl1 libglib2.0-0t64 libportaudio2
```

实际包名依发行版而定；旧版Ubuntu/Debian的GLib包可能名为libglib2.0-0。`libGL`/GLib 是当前 full OpenCV wheel 可能需要的运行依赖；PortAudio 与 MediaPipe 的 sounddevice 依赖相关，后端不会打开麦克风、采集音频或调用声音设备。不要为了通过安装检查改变浏览器安全参数。

如果目标 Linux 已有 EGL、GLdispatch 等，只缺 GLES，且与 Debian amd64 包兼容，可选择局部解包方式：

```sh
sh pose-v52-python/fetch-debian-libgles.sh
```

它仅下载官方 Debian 文件并核验 SHA-256，不执行 sudo、不安装系统包。文件：libgles2 1.7.0-1+b2，17256 字节；SHA-256：e12c18aa77939d122ee1dea520ba0440b97dc19200b7396e03dff03a3ece74c1。`start.sh` 自动将局部库目录加入本进程的 `LD_LIBRARY_PATH`。此替代方式仅补一个库，不保证适用于其他 Linux 发行版或缺少更多动态库的机器。

## 3. 前端依赖与路径校验

```sh
cd source-root/pose-v52
npm ci --registry=https://registry.npmjs.org
cd ..
python3.12 pose-v52-python/verify_layout.py
```

路径校验只读取文件、验证模型哈希，不加载模型、不执行推理。需要检查的模型 SHA-256 是 59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a。脚本会列出实际存在的测试视频；它不会补造缺失的原始三段视频。

## 4. 单服务器启动

```sh
cd source-root
sh pose-v52-python/start.sh --port 8766
```

等终端出现 `ready: true` 后，在这台机器的浏览器打开：

- 流程检查：http://127.0.0.1:8766/?backend=python&run=smoke
- 已提供的真人替代输入：http://127.0.0.1:8766/?backend=python&run=worker

Python 服务器同时提供前端、静态视频 Range、模型和推理 API，全部同源。不要再同时启动前端旧 `server.py` 或 `npm start` 并误用另一个端口。需要使用8765时应先停止占用该端口的旧服务器，并明确传 `--port 8765`。默认仅监听127.0.0.1；不要为了方便随意暴露到公网。

当前前端使用播放前 `/prepare` 初始化 tracker，该请求不传图像、不推理。初始准备时间单独记录；播放后的 loop/epoch 重建仍真实计入该帧延迟，并未通过暂停视频隐藏。

运行机器必须有 MediaPipe 本地运行时所需的普通 CPU 系统信息访问。本轮受限命令执行器缺失 sysfs CPU 信息，tcmalloc 初始化会中止；相同程序在云机原生运行环境已成功。不提供伪造系统信息或绕过沙箱限制的补丁。

## 5. 可选功能检查与正式测量分开

服务器独占时才执行以下测试，避免与浏览器基准争抢同一个推理后端：

```sh
pose-v52-python/.venv/bin/python pose-v52-python/test_api.py http://127.0.0.1:8766
```

此测试发送少量选定图像，验证协议、身份、哈希、33点、忙拒绝等；不是实时性能证据。正式测量必须在浏览器中以原始1×速度播放，用同一浏览器时钟测量原帧释放到显示提交的完整延迟。Python推理耗时、网络RTT与E2E不能互相替代。不要一边跑API测试一边测浏览器。

## 验证状态

- 本轮现有Linux环境安装、原生CPU少量帧推理及初版HTTP契约测试已通过。
- 分发安装脚本仅做shell语法检查；未实际执行干净安装。
- `verify_layout.py` 在当前源码布局通过，只说明文件齐全与模型hash匹配。
- Windows/macOS/ARM、无网络安装、其他Python版本、其他机器性能均未验证。
- 新版服务的正式浏览器运行结果请以随源码提供的最终测试报告为准，不要用旧功能probe代替。

## 官方资料

- [MediaPipe Python安装与平台要求](https://developers.google.com/edge/mediapipe/solutions/setup_python)
- [MediaPipe Pose Landmarker Python接口](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/python)
- [OpenCV wheel安装：cv2包只选一种](https://pypi.org/project/opencv-python/)
- [Debian libgles2包说明](https://packages.debian.org/trixie/libgles2)
- [官方Debian下载与校验和](https://packages.debian.org/trixie/amd64/libgles2/download)

## 本轮环境记录

原生记录为 AMD EPYC 9V74 的虚拟机，9个可见逻辑CPU，内存总计9967 MiB（采集瞬间可用7582 MiB），Linux 6.18.44 x86_64；浏览器为Chrome154、hardwareConcurrency=9。CPU型号中的80-Core不表示本任务获得80核。nvidia-smi不可用不等于无GPU；可验证的是浏览器WebGL不可用、姿态后端明确采用CPU/XNNPACK。详见 `environment-evidence.json` 及其引用的原始日志。这些是测量环境说明，不是保证性能或最低配置。
