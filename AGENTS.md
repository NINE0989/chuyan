# 仓库规范

## 项目结构与模块组织
本仓库包含一个基于 Python 的 ShaderToy 风格运行时，以及 GLSL 着色器资源。

- `shadertoy/`：应用代码。
  - `__main__.py`：可执行入口（`python -m shadertoy`）。
  - `shader.py`：OpenGL 窗口、着色器编译/链接、uniform 上传。
  - `audio.py`、`audioUtils.py`：回环采集与 FFT 处理。
  - `uniforms.py`：兼容 ShaderToy 的 uniform 数据模型。
- `shaders/`：片段着色器（`*.glsl`）与共享 include（例如 `ShaderCommon.glsl`）。
- `requirements.txt`：运行时依赖。

请将 Python 运行时逻辑放在 `shadertoy/`，将着色器实验放在 `shaders/`。

## 语言与注释要求
- 回复、说明、注释、文档默认必须使用中文。
- 仅在专有名词、库名、协议名、标准名、命令行参数等不可自然翻译或翻译会引发歧义时，允许保留原文。
- 代码标识符遵循既有命名约定，不强制翻译。

## 构建、测试与开发命令
- `python -m pip install -r requirements.txt`  
  安装项目依赖。
- `python -m shadertoy`  
  使用默认着色器运行（`shaders/ink_wash.glsl`）。
- `python -m shadertoy shaders/audio_viz.glsl`  
  运行指定着色器文件。

如果音频回环不可用，请确认应用仍可渲染并输出降级行为日志。

## 代码风格与命名约定
- Python：遵循 PEP 8，使用 4 空格缩进。
- 新增或修改的公共方法优先补充类型标注。
- 模块/文件名：`snake_case.py`；类名：`PascalCase`；函数/变量：`snake_case`。
- GLSL 文件名：小写加下划线，例如 `new_effect.glsl`。
- 着色器 include 文件应保留在 `shaders/` 内，并通过 `#include "File.glsl"` 引用。

## 测试指南
当前尚无正式自动化测试套件。提交改动时，请执行手工冒烟测试：
1. 启动 `python -m shadertoy` 并确认窗口成功创建。
2. 显式加载至少一个着色器路径。
3. 确认控制台日志中没有着色器编译/链接错误。

涉及音频改动时，请验证 FFT 纹理更新，并确认失败时可平稳降级。

## 提交与 Pull Request 规范
近期历史中同时存在中文短摘要与 merge commit。后续新改动建议：
- Commit 格式：使用祈使语态、带范围的摘要（例如：`audio: smooth FFT normalization`）。
- 每次提交聚焦单一主题（运行时、着色器资源或文档）。

PR 应包含：
- 改了什么，以及原因。
- 本地运行与验证方式。
- 若涉及视觉效果，附截图或短视频。
- 关联 issue/任务（如适用）。
