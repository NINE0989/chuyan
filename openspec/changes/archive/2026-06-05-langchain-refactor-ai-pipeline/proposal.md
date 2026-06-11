## Why

当前 AI 管线 (`ai_pipeline/`) 是纯自建框架（约 500 行 Python），用 `urllib.request` 直调 OpenAI API，自建两阶段 Agent 编排。存在以下痛点：

1. **代码重复严重**：`_extract_glsl()` 在 `protocol.py`、`generate_cli.py`、`tools/get_fenced_code_block.py` 三处重复，`_load_audio_array()` 在 `generate_cli.py` 和 `ai_service.py` 重复
2. **无流式输出**：`AIService.stream_generate()` 是假流式（完整生成后分块），编排层完全不支持 stream
3. **JSON 解析脆弱**：`_normalize_audio_analysis()` 靠 try/except 兜底，无结构化输出保证
4. **无重试/退避**：API 调用失败直接抛异常，90 秒超时无中间策略
5. **硬编码管线**：固定「音频理解→编码」两步，LLM 无法自主选择调用哪些工具、无法自修正
6. **工具不可见**：所有功能埋在两阶段黑盒中（save_shader、validate_glsl、get_skill 等），Agent 无法按需调用

引入 LangChain `ChatOpenAI` + LangGraph `StateGraph` + `@tool` 函数，构建单一全能 Agent：
- **Tool 化**：将现有 18 个功能函数拆分为 6 类 `@tool`，Agent 自主决策调用
- **LangGraph 编排**：`agent → tools → agent` 循环替代硬编码 pipeline，LLM 可调用 validate tool 自检后修正
- **外部接口不变**：`generate_cli.py::generate()` 签名保持

## What Changes

- **BREAKING 移除** `ai_pipeline/mcp/` 整个目录（`McpAdapter`、`McpEnvelope`、`McpError`、`OpenAIMcpAdapter`、`MockMcpAdapter`、`build_mcp_adapter`）
- **BREAKING 移除** `ai_pipeline/orchestrator.py`（`MultiAgentOrchestrator`、`ConversationStore`）
- **BREAKING 移除** `tools/get_fenced_code_block.py`（功能合并到 `ai_pipeline/tools/shader_tools.py`）
- **新增** `ai_pipeline/tools/` 目录：18 个 `@tool` 函数，分 6 类
  - `audio_tools.py`（2 tools）：`summarize_audio`、`load_audio_from_file`
  - `shader_tools.py`（4 tools）：`save_shader_to_file`、`inject_shader_header`、`extract_glsl_code`、`ensure_glsl_version`
  - `validation_tools.py`（3 tools）：`validate_glsl_keywords`、`run_full_quality_check`、`load_known_badcases`
  - `skill_tools.py`（3 tools）：`get_skill_template`、`list_available_skills`、`build_skill_prompt`
  - `session_tools.py`（2 tools）：`load_conversation`、`save_conversation`
  - `utility_tools.py`（4 tools）：`infer_shader_style`、`normalize_audio_analysis`、`load_audio_array`、`run_py_syntax_check`
- **新增** `ai_pipeline/agent.py`：LangGraph `StateGraph` + `ToolNode` 构建单 Agent 图
- **新增** `ai_pipeline/system_prompt.md`：合并 `audio_understanding.md` + `coding_agent.md` 的综合 prompt，含 tool 使用指南
- **新增** `ai_pipeline/llm/adapter.py`：`ChatOpenAI` 工厂函数 + mock 降级（保留关键词判断逻辑）
- **修改** `ai_pipeline/generate_cli.py`：用 `agent.invoke()` 替换 orchestrator，保持 `generate()` 签名不变
- **修改** `WebEngine/ai_service.py`：适配 Agent 接口，使用真实流式 Agent
- **修改** `requirements.txt`：新增 `langchain>=0.3.0,<1.0`、`langchain-openai>=0.2.0,<1.0`、`langgraph>=0.2.0,<1.0`
- **保留不动**：`ai_pipeline/types.py`、`ai_pipeline/skills/`（`SKILL_LIBRARY` 数据定义）、`ai_pipeline/hooks/`、`ai_pipeline/prompts/`、`ai_pipeline/cases/`、`ai_pipeline/regression_badcase.py`

### 重构前后关键函数对照

| 重构前函数 | 重构后实现 | 说明 |
|---|---|---|
| `protocol.py::OpenAIMcpAdapter.chat_completion()` | `llm/adapter.py::build_llm()` | `ChatOpenAI` 替代 `urllib.request` |
| `protocol.py::MockMcpAdapter.chat_completion()` | `llm/adapter.py::build_llm(provider="mock")` | `RunnableLambda` 包装 mock 逻辑 |
| `protocol.py::_extract_glsl()` (重复) | `tools/shader_tools.py::extract_glsl_code` | 统一为 `@tool` |
| `orchestrator.py::MultiAgentOrchestrator.run()` | `agent.py::build_shader_agent()` | LangGraph `StateGraph` 替代自建编排 |
| `orchestrator.py::ConversationStore` | `tools/session_tools.py`（`load_conversation` / `save_conversation`） | 拆分为 2 个 `@tool` |
| `orchestrator.py::_normalize_audio_analysis()` | `tools/utility_tools.py::normalize_audio_analysis` | `@tool` |
| `orchestrator.py::_summarize_audio()` | `tools/audio_tools.py::summarize_audio` | `@tool` |
| `skills/library.py::build_skill_prompt()` | `tools/skill_tools.py::build_skill_prompt` | `@tool`，`SKILL_LIBRARY` 数据不动 |
| `hooks/engine.py::GenerationHookEngine.inject_header()` | `tools/shader_tools.py::inject_shader_header` | `@tool` |
| `hooks/engine.py::GenerationHookEngine.run_hooks()` | `tools/validation_tools.py::validate_glsl_keywords` | `@tool` |
| `hooks/quality_check.py::run_glsl_checks()` | `tools/validation_tools.py::validate_glsl_keywords` | `@tool` |
| `hooks/quality_check.py::run_py_syntax()` | `tools/utility_tools.py::run_py_syntax_check` | `@tool` |
| `generate_cli.py::save_shader()` | `tools/shader_tools.py::save_shader_to_file` | `@tool` |
| `generate_cli.py::run_quality()` | `tools/validation_tools.py::run_full_quality_check` | `@tool` |
| `generate_cli.py::_extract_glsl()` (重复) | 删除，用 `tools/shader_tools.py` | 消除重复 |
| `generate_cli.py::_load_audio_array()` (重复) | `tools/utility_tools.py::load_audio_array` | `@tool` |
| `regression_badcase.py::load_badcases()` | `tools/validation_tools.py::load_known_badcases` | `@tool` |
| `AIService._infer_style()` | `tools/utility_tools.py::infer_shader_style` | `@tool` |
| `AIService._extract_code()` (重复) | 删除，用 `tools/shader_tools.py` | 消除重复 |
| `launch.py::_ensure_version()` | `tools/shader_tools.py::ensure_glsl_version` | `@tool` |
| `tools/get_fenced_code_block.py` | 删除 | 合并到 `shader_tools.py` |
| `ai_pipeline/mcp/__init__.py` | 删除 | 整个 mcp 模块移除 |

## Capabilities

### New Capabilities
- `shader-agent-tools`：18 个 `@tool` 函数，分 6 类（audio/shader/validation/skill/session/utility），供 Agent 按需调用。每个 tool 独立定义、独立测试、可被 Agent 自主选择执行
- `shader-agent-graph`：LangGraph `StateGraph` + `ToolNode` 构建的单 Agent 图，LLM 绑定全部 tool，自主决策调用顺序，支持「生成→自检→修正→保存」循环

### Modified Capabilities
（无现有 spec，无需修改）

## Impact

- **受影响模块**：`ai_pipeline/mcp/`（删除）、`ai_pipeline/orchestrator.py`（删除）、`ai_pipeline/generate_cli.py`（修改）、`WebEngine/ai_service.py`（修改）、`tools/get_fenced_code_block.py`（删除）
- **新增模块**：`ai_pipeline/tools/`（6 个分类文件 + `__init__.py`）、`ai_pipeline/agent.py`（LangGraph 图）、`ai_pipeline/system_prompt.md`（合并 SOP）、`ai_pipeline/llm/adapter.py`（ChatOpenAI 工厂）
- **新增依赖**：`langchain`、`langchain-openai`、`langgraph`（追加到 `requirements.txt`）
- **外部接口不变**：`ai_pipeline/generate_cli.py::generate()` 签名保持 `(GenerateRequest, Path, str, str, list[float] | None) -> GenerateResult`
- **向下兼容**：保留 `conversations.json` 会话数据格式，可读取旧 session
- **回归测试**：`regression_badcase.py` 无需修改（它调用 `generate()`，签名不变）
