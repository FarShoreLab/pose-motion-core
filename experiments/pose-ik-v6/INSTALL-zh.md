# 安装、复现与入口

这是独立v6实验目录。请勿将其覆盖原来的v5.2目录。

## 验证范围

已验证Linux x86_64 / Python3.12 / 官方OpenSim4.6与MediaPipe1.1.0。Windows、macOS、ARM未测试。当前环境使用独立venv并可见基础科学Python包，已执行pip check；requirements-environment.txt记录实测完整版本，minimal requirements只列主依赖，未声称全新跨平台安装通过。

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --index-url https://pypi.org/simple --only-binary=:all: -r requirements-minimal.txt
.venv/bin/python -m pip check
sh live-app/start-live.sh
```

默认只监听127.0.0.1:8770。浏览器打开：

- 慢动作：http://127.0.0.1:8770/?run=commons-overhead25&seconds=65&name=my-slow&capture=1
- 快动作：http://127.0.0.1:8770/?run=commons-jumping2997&seconds=65&name=my-fast&capture=1
- 转身：http://127.0.0.1:8770/?run=commons-pirouettes25&seconds=65&name=my-turn&capture=1

一次只开一个运行页。网页将在原速播放65秒后停止，自动保存JSON到live-app/pose-v52/results，并出现“下载本次现场对比录屏”链接。浏览器不同可能不支持WebM录制；不加capture=1可关闭录屏并重新测量，但结果应与录屏组分开。

Linux动态库通常需要libEGL、libGLESv2、libGL、GLib。live-app/pose-v52-python/fetch-debian-libgles.sh提供可选的工作目录局部库下载，严格来自官方Debian并核验hash，仅适用于相容环境。首选由机器管理员安装发行版官方运行库，不需要改浏览器安全选项。

本次命令沙箱内MediaPipe模型创建遇到tcmalloc读取CPU信息失败；正式提升执行路径也因工具环境初始化失败而不能启动。最终用受支持的dot云桌面程序启动器运行同一工作目录脚本，正常读取实际CPU信息后成功。没有伪造sysfs、修改权限或浏览器安全设置。若某环境不暴露必要CPU运行时信息，应使用该环境正式支持的运行入口或报告未测，不要修改系统安全设置来伪造成功。

## 离线同源复现

先将指标包的metric-reference目录放在本目录；原始输入是既有真实在线记录，不是重新跑推理。

```sh
.venv/bin/python src/run_offline.py metric-reference/raw/v52-fast-release.json --out output/retest-fast
.venv/bin/python src/run_offline.py metric-reference/raw/v52-slow-release.json --out output/retest-slow
.venv/bin/python src/run_offline.py metric-reference/raw/v52-turn-release.json --out output/retest-turn
.venv/bin/python audit/run_independent_audit.py
.venv/bin/python audit/run_boundary_audit.py
```

audit脚本加载audit/snapshot/opensim_ik.py，保证测试的是被记录hash的实现；它不会自动改用新的src。修改实现后应建立新的测试快照和记录，不能用旧结果证明新版本。

现场JSON汇总：

```sh
.venv/bin/python src/summarize_live.py live-app/pose-v52/results/my-fast.json
```

## 源码检查

```sh
cd live-app/pose-v52
npm test
cd ..
../.venv/bin/python -m unittest discover -s pose-v52-python -p "test_live_ik.py" -v
../.venv/bin/python pose-v52-python/test_epoch_clock.py
../.venv/bin/python pose-v52-python/test_epoch_backend.py
```

完整说明参阅live-app/README-live-comparison.md及README-zh.md。旧v5.2附带安装说明是历史文档；v6运行入口以本文件为准。
