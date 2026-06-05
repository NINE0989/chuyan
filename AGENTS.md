# 仓库规范

## 项目概述
MusicShader —— Python + OpenGL 的 ShaderToy 风格运行时，包含 AI 着色器生成链路。三层架构：
- `shadertoy/`：OpenGL 渲染、音频 FFT、手势识别、uniform 管理
- `ai_pipeline/`：AI 生成管线（多 Agent、技能注入、质量检查）
- `WebEngine/`：PyQt5 前端（聊天 UI、代码编辑、OpenGL 预览）

## 启动方式
```powershell
# 渲染运行时（默认加载 shaders/ink_wash.glsl）
python -m shadertoy

# 指定着色器
python -m shadertoy shaders/audio_viz.glsl

# 完整前端（AI 对话 + 预览 + 着色器库）
python WebEngine/app.py

# AI 生成 CLI
python -m ai_pipeline.generate_cli --prompt "宇宙星空效果" --provider mock
```

## AI 管线架构（LangChain 重构目标）

### 当前实现（纯自建，零第三方 AI 框架）
核心入口：`ai_pipeline/generate_cli.py::generate()`，接收 `GenerateRequest` 返回 `GenerateResult`。

两阶段 Agent 编排（`ai_pipeline/orchestrator.py::MultiAgentOrchestrator`）：
1. **音频理解 Agent**（SOP: `ai_pipeline/audio_understanding.md`）→ 输出 JSON
2. **编码 Agent**（SOP: `ai_pipeline/coding_agent.md`）→ 输出 GLSL

LLM 调用层（`ai_pipeline/mcp/protocol.py`）：
- 「MCP」是本项目自定义的适配器抽象，**不是** Anthropic MCP 协议
- 使用标准库 `urllib.request` 直调 OpenAI 兼容 API，无 OpenAI SDK 依赖
- 通过环境变量 `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` 配置
- `MockMcpAdapter` 返回硬编码示例，用于离线降级
- `_extract_glsl()` 在 `protocol.py`、`generate_cli.py`、`tools/get_fenced_code_block.py` 三处重复

技能注入（`ai_pipeline/skills/library.py`）：
- 4 个 SkillSpec：`geometry_sdf`、`audio_visualization`、`style_specialization`、`badcase_guard`
- 模板文本拼接到用户 prompt 末尾

钩子与质量检查（`ai_pipeline/hooks/`）：
- `GenerationHookEngine.inject_header()`：生成前注入元信息注释
- `GenerationHookEngine.run_hooks()`：生成后检查关键字（mainImage/iResolution/iTime 必须存在，gl_FragColor 禁止）
- 子进程完整质量检查：`python -m ai_pipeline.hooks.quality_check`

Web 端集成（`WebEngine/ai_service.py::AIService`）：
- `generate()` 方法封装 `ai_pipeline.generate_cli.generate()`
- 自动判断 provider：有 `OPENAI_API_KEY` → openai，否则 mock
- `adjust=False` 重置 session，`adjust=True` 保持上下文微调
- `_infer_style()` 从 prompt 关键词推断风格（neon/ink/glitch/minimal）

会话持久化（`ai_pipeline/conversations.json`）：
- 以 session_id 为 key，存储消息数组；编码 Agent 携带最近 8 轮历史

### LangChain 重构要点
- 替换目标：`ai_pipeline/mcp/protocol.py`（适配器层）、`ai_pipeline/orchestrator.py`（编排层）
- 保留不动：`ai_pipeline/skills/`、`ai_pipeline/hooks/`、`ai_pipeline/types.py`、`ai_pipeline/prompts/`
- 外部接口不变：`generate_cli.py::generate()` 的签名不能变（WebEngine 依赖它）
- `requirements.txt` 当前无 langchain 依赖，需新增
- 模型配置改用 LangChain 的 `ChatOpenAI`，保留 mock 降级能力

## 关键约定与陷阱

### ShaderCommon.glsl 缺失
`shaders/ink_wash.glsl` 第 9 行 `#include "ShaderCommon.glsl"`，但该文件在仓库中不存在。默认启动会因 include 解析失败而报 `FileNotFoundError`。其他着色器也可能引用它。需要创建该文件或从各着色器中移除该 include。

### 音频通道语义
- `iChannel0` = 时域波形（R 通道为原始音频采样，512x1）
- `iChannel1` = FFT 频谱（R 通道为归一化频谱，512x1）
- README 标注此规范尚未完全统一到所有 Shader，仍在推进中

### 音频采集降级
音频 loopback 不可用时，应用仍可渲染，仅输出日志。所有组件（音频、手势）都有独立 try/except 降级。

### 手势识别
- 支持 native（本地摄像头+MediaPipe）和 remote（命名管道订阅）两种模式
- 本地模型路径：`shadertoy/assets/hand_landmarker.task`
- 命名管道名通过 `SHADERTOY_GESTURE_PIPE` 环境变量覆盖

### 弃用文件
- `WebEngine/app_old.py`：旧版单文件实现，已不再使用
- `shader_old/`：旧版着色器备份
- `WebEngine/frontend.py`：已被 `ui/` 包替代
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
| `AI_AUDIO_ARRAY_FILE` | 音频数组文件路径（Web 端使用） | — |

## 语言与注释要求
- 回复、说明、注释、文档默认必须使用中文
- 专有名词、库名、协议名、命令行参数可保留原文
- 代码标识符遵循既有命名约定，不强制翻译

## 代码风格
- Python：PEP 8，4 空格缩进，优先补充类型标注
- 模块/文件名：`snake_case.py`；类名：`PascalCase`；函数/变量：`snake_case`
- GLSL 文件名：小写加下划线，`#include` 路径相对于着色器文件所在目录

## 测试与验证
无自动化测试套件。提交前执行手工冒烟：
1. `python -m shadertoy` 确认窗口创建（如果 ShaderCommon.glsl 未修复，先用其他着色器如 `shaders/white.glsl`）
2. `python WebEngine/app.py` 确认前端启动
3. `python -m ai_pipeline.generate_cli --prompt "测试" --provider mock` 确认 AI 管线正常
4. 控制台无着色器编译/链接错误

## 提交规范
- 格式：祈使语态、带范围摘要（如 `audio: smooth FFT normalization`）
- 每次提交聚焦单一主题
- 不要提交 `conversations.json`（会话数据）
