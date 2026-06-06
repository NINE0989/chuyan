# 仓库规范

## 项目概述
MusicShader —— Python + OpenGL 的 ShaderToy 风格运行时，含 AI 着色器生成链路。三层架构：
- `shadertoy/`：OpenGL 渲染、音频 FFT、手势识别、uniform 管理
- `ai_pipeline/`：AI 生成管线（LangGraph Agent + 20 个 tool + skills + hooks）
- `WebEngine/`：HTTP 服务 + 浏览器前端（对话 UI、代码编辑、shader 应用与预览）

## 启动方式
```powershell
# 渲染运行时（默认加载 shaders/ink_wash.glsl）
python -m shadertoy

# 指定着色器
python -m shadertoy shaders/stars.glsl

# 完整前端（HTTP 服务 + 浏览器打开）
python WebEngine/app.py

# AI 生成 CLI
python -m ai_pipeline.generate_cli --prompt "宇宙星空效果" --provider mock
```

## AI 管线架构（LangGraph Agent）

核心入口：`ai_pipeline/generate_cli.py::generate()` — 签名不变，接收 `GenerateRequest` 返回 `GenerateResult`。

LangGraph Agent 取代了旧自建编排器：
- `ai_pipeline/agent.py`：构建 LangGraph StateGraph，agent ↔ tools 循环（`build_shader_agent`）
- `ai_pipeline/llm/adapter.py`：LLM 实例化 — `ChatOpenAI` 或 mock `RunnableLambda`（读 env/settings.json）
- `ai_pipeline/tools/`：20 个 `@tool` 函数，分 7 类（audio/shader/validation/compile_check/skill/session/utility），由 `get_all_tools()` 聚合
- `ai_pipeline/system_prompt.md`：Agent 的 system prompt，由 `agent.py` 加载

**关键点**：`ai_pipeline/mcp/` 目录已空（仅 `__pycache__/`），旧 MCP 适配层已被 `llm/adapter.py` 完全替代。不要引用 `mcp/protocol.py`。

模型配置优先级：`settings.json` API key > 环境变量 `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` > 默认值。mock 降级在无 key 时自动启用。

### 技能注入与质检（保留不动）
- `ai_pipeline/skills/library.py`：4 个 SkillSpec（geometry_sdf / audio_visualization / style_specialization / badcase_guard）
- `ai_pipeline/hooks/engine.py`：`inject_header()` + `run_hooks()`（检测 mainImage/iResolution/iTime 必须存在，gl_FragColor 禁止）
- 子进程质量检查：`python -m ai_pipeline.hooks.quality_check`

### Web 端集成
- `WebEngine/ai_service.py::AIService`：封装 `generate_cli.generate()`，暴露 `generate()` 和 `stream_generate()`
- `adjust=False` 重置 session，`adjust=True` 保持上下文
- `_infer_style()` 按关键词推断风格（neon/ink/glitch/minimal）
- 音频输入通过 `AI_AUDIO_ARRAY_FILE` 环境变量指向 JSON/CSV 文件

### 其他 Web 模块
- `WebEngine/server.py`：本地 HTTP 服务（端口 18090-18099）
- `WebEngine/launch.py`：在子进程中启动 borderless shader 窗口（gesture_mode="remote"）
- `WebEngine/speech_service.py`：语音录制 + OpenAI Whisper API 转录（需要 `import pyaudio`，当前仅 `pyaudiowpatch` 在 requirements.txt 中）
- `WebEngine/settings.py`：`Settings` 单例，环境变量 > `settings.json` > 默认值的三层配置

## 关键约定与陷阱

### ShaderCommon.glsl
`shaders/ShaderCommon.glsl` 已从 `shader_old/` 同步到 `shaders/` 目录，`ink_wash.glsl` 的 `#include` 可以正常解析。注意：该文件仅提供 uniform 声明，不可单独编译（无 main 入口）。

### #version 指令规范
所有着色器统一使用 `#version 330`（**不带 `core` 关键字**）：
- `shadertoy/shader.py` 顶点着色器：`#version 330`
- `ai_pipeline/tools/shader_tools.py::ensure_glsl_version`：注入 `#version 330`
- `ai_pipeline/llm/adapter.py` 的 mock 响应模板：`#version 330`
- `ai_pipeline/system_prompt.md` 要求：`#version 330`
- `WebEngine/launch.py::_ensure_version`：补全 `#version 330`

**原因**：GLFW 在某些系统上可能回退到 OpenGL ES 上下文，ES 不接受 `core` 关键字。`shadertoy/shader.py` 已添加 `CLIENT_API=OPENGL_API` + `CONTEXT_CREATION_API=NATIVE_CONTEXT_API` 窗口提示以强制桌面 GL。若仍回退到 ES，`load_shader()` 会**自动**将 `#version 330` 改写为 `#version 300 es` 并注入 `precision mediump float;`。

### .glsl 文件编码陷阱
- 所有 `.glsl` 文件必须是 UTF-8 无 BOM
- **行尾统一为 `\n`（LF）**，不要用 `\r\n`（CRLF）
- Python `write_text(data, encoding='utf-8')` 在 Windows 上会将 `\n` 转为 `\r\n`，需使用 `write_text(data, encoding='utf-8', newline='')` 禁用此行为
- 若行尾出现 `\r\r\n`，GLSL 编译器会将 `\r` 视为 `#version` 指令后的非法字符，从而忽略整条 version 指令，回退到默认 GLSL ES 1.00

### 编译检查 tool（AI 管线新增）
- `ai_pipeline/tools/compile_check.py`：`compile_check_glsl`（编译 GLSL 代码字符串）和 `compile_check_glsl_file`（从文件路径编译）
- 使用 headless GLFW 窗口创建真实 GL 上下文进行编译验证
- 失败时自动分类错误（version/out/texture/swizzle/index 等 9 类）并生成修复建议
- CLI 入口：`python -m ai_pipeline.tools.compile_check [shader_path]`
- PyOpenGL 版本差异：`glGetShaderInfoLog`/`glGetProgramInfoLog` 在不同 PyOpenGL 版本中可能返回 `str` 或 `bytes`，需用 `isinstance(log, bytes)` 判断后 decode

### 音频通道语义
- `iChannel0` = 时域波形（R 通道为原始音频采样，chunk_size×1 纹理）
- `iChannel1` = FFT 频谱（R 通道为归一化频谱，fft_size×1 纹理）
- 代码实现（`shadertoy/__main__.py::setup_audio_channel`）与 Shader 用法需保持一致

### 音频采集降级
音频 loopback 不可用时应用仍可渲染，仅输出日志。所有组件（音频、手势）都有独立 try/except 降级。

### 手势识别
- native 模式：本地摄像头 + MediaPipe（模型路径 `shadertoy/assets/hand_landmarker.task`，通过 `SHADERTOY_HAND_LANDMARKER_MODEL` 覆盖）
- remote 模式：命名管道订阅（管道名通过 `SHADERTOY_GESTURE_PIPE` 覆盖）
- borderless 窗口（`launch.py`）固定使用 `remote`，避免多进程抢占摄像头
- 额外 uniform：`iHandPos`、`iHandAction`、`iHandDepthRef`、`iPinchEnabled`

### 弃用文件
- `WebEngine/app_old.py`：旧版单文件实现
- `shader_old/`：旧版着色器备份（ShaderCommon.glsl 仅存在于此目录）
- `WebEngine/frontend.py`：已被 `ui/` 包替代
- `ai_pipeline/mcp/`：已被 `ai_pipeline/llm/` 替代
- 修改代码时不要碰这些文件

### 环境变量速查
| 变量 | 用途 | 默认值 |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API 密钥 | — |
| `OPENAI_BASE_URL` | API 地址 | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | 模型名 | `gpt-4.1-mini` |
| `AI_PROVIDER` | 强制 provider（覆盖自动检测） | — |
| `SHADERTOY_HAND_LANDMARKER_MODEL` | 手势模型路径 | `shadertoy/assets/hand_landmarker.task` |
| `SHADERTOY_GESTURE_PIPE` | 命名管道名 | `shadertoy_gesture` |
| `SHADER_MONITOR_INDEX` | 渲染目标显示器 | — |
| `SHADER_BORDERLESS_MONITOR` | borderless 窗口目标显示器（`launch.py` 使用） | `0` |
| `AI_AUDIO_ARRAY_FILE` | 音频数组文件路径（Web 端使用） | — |

## 语言与注释要求
- 回复、说明、注释、文档默认使用中文
- 专有名词、库名、协议名、命令行参数可保留原文
- 代码标识符遵循既有命名约定

## 代码风格
- Python：PEP 8，4 空格缩进，优先补充类型标注
- 模块/文件名：`snake_case.py`；类名：`PascalCase`；函数/变量：`snake_case`
- GLSL 文件名：小写加下划线，`#include` 路径相对于着色器文件所在目录

## 测试与验证
无自动化测试套件。提交前手工冒烟：
1. `python -m shadertoy` 确认窗口创建
2. `python WebEngine/app.py` 确认 HTTP 服务启动且浏览器打开
3. `python -m ai_pipeline.generate_cli --prompt "测试" --provider mock` 确认 LangGraph Agent 管线正常
4. 控制台无着色器编译/链接错误

## 提交规范
- 格式：祈使语态、带范围摘要（如 `audio: smooth FFT normalization`）
- 每次提交聚焦单一主题
- 不要提交 `conversations.json`（会话数据）
