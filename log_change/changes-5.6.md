# changes-5.6

## 本次变更概述

本次主要围绕“手势交互共享”和“本地资源固定化”做了收敛，目标是让主窗口和 borderless 窗口共享同一份手势结果，同时避免重复打开摄像头与自动联网下载模型。

## 具体变更

### 1. 手势数据源共享
- 新增并重构 `shadertoy/gesture.py`，将手势采集与数据分发集中到 `GestureTracker`。
- 主窗口侧作为采集发布者，borderless 子进程作为订阅者，保证两个窗口读取同一份 `iHandPos` / `iHandAction`。
- 传输层由 UDP 改为 Windows Named Pipe，避免占用网络端口。

### 2. 本地模型固定化
- 将 `hand_landmarker.task` 固定到仓库路径 `shadertoy/assets/hand_landmarker.task`。
- 代码改为强制使用本地模型，不再执行自动下载逻辑。
- 保留通过 `SHADERTOY_HAND_LANDMARKER_MODEL` 指定本地模型路径的能力，便于团队内统一部署。

### 3. 运行时接入
- `WebEngine/visualizer.py`：内嵌预览窗口接入手势采集，并作为发布者使用。
- `shadertoy/__main__.py`：增加 `gesture_mode` 控制，支持 native / remote 两种模式。
- `WebEngine/launch.py`：borderless 窗口使用 remote 模式，避免重复打开摄像头。
- `shadertoy/shader.py` 与 `shadertoy/uniforms.py`：补充 `iHandPos`、`iHandAction` 两个 uniform 的传递。

### 4. 文档同步
- 更新 `README.md`，补充手势交互、命名管道、本地模型路径与验证方式说明。

## 验证结果
- 已执行 Python 语法编译检查，相关修改文件通过编译。
- 仍建议在本机实际启动主窗口与 borderless 窗口做一次联调确认。

## 备注
- 当前模型文件体积约 7.9 MB，已放在仓库内，后续如需团队共享，可直接随仓库提交。
- 如果未来需要跨平台复用，建议再抽象一层 IPC 适配，替换 Windows Named Pipe 的实现细节。
