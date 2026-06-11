## Context

当前 `ai_pipeline/` 是纯自建 AI 框架，约 500 行代码实现：
- **LLM 调用层** (`mcp/protocol.py`)：`urllib.request` 直调 OpenAI `/chat/completions`，无重试/stream/structured output
- **编排层** (`orchestrator.py`)：自建 `MultiAgentOrchestrator` 串联音频理解→编码两阶段，会话持久化到 JSON
- **技能层** (`skills/library.py`)：4 个 `SkillSpec` 模板文本拼接到 prompt 末尾

本次重构将 LLM 调用和编排替换为 LangChain + LangGraph Agent 模式，将所有内嵌功能拆分为独立的 `@tool` 函数。

约束：
- `generate_cli.py::generate()` 签名不能变（WebEngine 依赖）
- `conversations.json` 格式保持可读（旧 session 数据不丢失）
- 回归测试 `regression_badcase.py` 无需修改
- mock 降级能力必须保留

## Goals / Non-Goals

**Goals:**
- 将 18 个现有功能函数拆分为 6 类 `@tool`，Agent 可自主调用
- 用 LangGraph `StateGraph` + `ToolNode` 构建单 Agent 图替代硬编码 pipeline
- 实现「生成→自检→修正→保存」的 Agent 自主循环
- 统一 `_extract_glsl()` 为单一 `@tool`，消除三处重复
- 新增真实流式输出支持
- 合并两个 SOP 为 `system_prompt.md`，含 tool 使用指南

**Non-Goals:**
- 不改动 `skills/` 数据定义（`SKILL_LIBRARY`）、`hooks/`、`types.py`
- 不改动 Web 端 UI（`ui/` 包）
- 不引入 LangSmith / LangServe
- 不修改 `conversations.json` 数据格式

## Decisions

### 决策 1：LangGraph StateGraph + ToolNode（而非 LCEL chain）

**选择**：LangGraph `StateGraph` + `ToolNode`

**原因**：
- 用户明确要求"将已有功能整理为 API 供调用方使用"，即 tool-calling 模式
- 单 Agent 拥有全部 18 个 tool，LLM 自主决策调用顺序，支持「生成→自检→修正」循环
- LCEL `RunnableSequence` 只能实现固定顺序链，无法支持条件分支和循环
- LangGraph 图结构：`START → agent ⇄ tools → END`，天然支持 ReAct tool-calling

**备选方案**：`create_tool_calling_agent` + `AgentExecutor` — 更简洁但不如 LangGraph 可扩展。选择 LangGraph 为后续复杂流程（多步自修正、条件验证门禁）预留空间。

### 决策 2：单一 Agent 拥有全部 tool（而非多 Agent 各自 tool 集）

**选择**：单一 Agent

**原因**：
- 用户明确选择"单一全能 Agent"
- 简化架构：一个 system prompt 包含全部 SOP + tool 指南
- 避免多 Agent 间消息传递和数据序列化开销
- 当前 18 个 tool 数量适中，单一 Agent 上下文可容纳

### 决策 3：Tool 粒度——每个独立功能函数一个 `@tool`

**选择**：18 个 `@tool`，分 6 类

**原因**：
- 每个 tool 对应一个现有的纯函数，输入输出明确
- LangChain `@tool` 装饰器自动生成 schema（名称、描述、参数类型），LLM 可根据描述选择合适的 tool
- 排除需要 OpenGL 上下文的函数（`_compile_shader`、`_link_program`、`launch_borderless_process`）
- 每个 tool 可独立测试，不依赖 Agent

### 决策 4：System Prompt 合并策略

**选择**：合并 `audio_understanding.md` + `coding_agent.md` 为一个 `system_prompt.md`，追加 tool 使用指南

**原因**：
- 单一 Agent 需要知道全部 SOP 约束
- tool 使用指南告诉 Agent：何时用 `summarize_audio`、何时用 `validate_glsl_keywords`、推荐调用顺序
- 保留两份原始 SOP 文件不动（作为参考文档），`system_prompt.md` 从它们派生

### 决策 5：Mock 降级用 `ChatOpenAI` 的 mock 模式 + 条件 `RunnableLambda`

**选择**：`provider=="openai"` → `ChatOpenAI(...).bind_tools(tools)`，`provider=="mock"` → `RunnableLambda` 包装旧 mock 逻辑

**原因**：
- `ChatOpenAI` 天然支持 `.bind_tools(tools)` 填入 tool schema
- mock 场景下 LLM 不会真正调用 API，用 `RunnableLambda` 返回硬编码消息（模拟 tool_calls 响应）
- 旧 `MockMcpAdapter` 的关键词判断逻辑保留

### 决策 6：环境变量配置保持不变

**选择**：继续使用 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL` 环境变量

**原因**：
- `ChatOpenAI` 构造函数天然支持这些参数
- 与现有 `tools/openAI_env.py` 配置工具兼容
- 工厂函数 `build_llm(provider)` 签名一致

## Module Layout After Refactoring

```
ai_pipeline/
├── llm/
│   └── adapter.py              # build_llm(provider) → ChatOpenAI | RunnableLambda
├── tools/                      # NEW: 18 @tool functions in 6 categories
│   ├── __init__.py             # get_all_tools() — aggregates all tools for agent
│   ├── audio_tools.py          # summarize_audio, load_audio_from_file
│   ├── shader_tools.py         # save_shader_to_file, inject_shader_header, extract_glsl_code, ensure_glsl_version
│   ├── validation_tools.py     # validate_glsl_keywords, run_full_quality_check, load_known_badcases
│   ├── skill_tools.py          # get_skill_template, list_available_skills, build_skill_prompt
│   ├── session_tools.py        # load_conversation, save_conversation
│   └── utility_tools.py        # infer_shader_style, normalize_audio_analysis, load_audio_array, run_py_syntax_check
├── agent.py                    # NEW: build_shader_agent(llm, tools) → LangGraph StateGraph
├── system_prompt.md            # NEW: merged SOP + tool usage guide
├── generate_cli.py             # MODIFIED: agent.invoke() + hooks/quality post-processing
├── orchestrator.py             # REMOVED
├── mcp/                        # REMOVED
├── skills/                     # UNCHANGED (SKILL_LIBRARY data only)
├── hooks/                      # UNCHANGED
├── types.py                    # UNCHANGED
├── audio_understanding.md      # UNCHANGED (reference)
├── coding_agent.md             # UNCHANGED (reference)
└── regression_badcase.py       # UNCHANGED
```

### Data Flow After Refactoring

```
generate_cli.py::generate()
    │
    ├─ build_llm(provider) → ChatOpenAI.bind_tools(tools)
    │    or RunnableLambda (mock)
    │
    ├─ tools = get_all_tools(root)
    │    → list of 18 @tool functions
    │
    ├─ agent = build_shader_agent(llm, tools)
    │    → LangGraph StateGraph: agent ⇄ tools
    │       ├─ agent node: LLM + system_prompt → decide next action
    │       └─ tools node: ToolNode → execute tool → return result to agent
    │
    ├─ result = agent.invoke({"messages": [
    │       SystemMessage(system_prompt),
    │       HumanMessage(f"用户需求: {req.prompt}\nstyle: {req.style_profile}\n音频: {audio_summary}")
    │   ]})
    │
    ▼
    extract GLSL from final agent message
    │
    ├─ GenerationHookEngine.inject_header()   ← UNCHANGED
    ├─ save_shader()                           ← UNCHANGED
    ├─ GenerationHookEngine.run_hooks()        ← UNCHANGED
    ├─ run_quality()                           ← UNCHANGED
    │
    ▼
    GenerateResult(glsl_code, diagnostics, quality_report)
```

## Risks / Trade-offs

| 风险 | 缓解措施 |
|---|---|
| **LangGraph 版本兼容**：API 更新频繁 | 锁定 `langgraph>=0.2.0,<1.0` |
| **Tool 数量过多**：18 个 tool 可能导致 prompt 过长或 LLM 选择困难 | 每个 tool 描述精简为 1-2 句，system prompt 给出推荐调用顺序 |
| **Agent 幻觉调用**：LLM 可能调用不存在的 tool 或传错参数 | LangGraph ToolNode 在执行前验证 tool_calls 有效性，无效调用返回错误消息 |
| **Mock 降级路径** | 用 `RunnableLambda` 包装，保留旧 mock 的关键词检测和条件返回 |
| **无限循环**：Agent 可能在 validate→fix→validate 间无限循环 | 在 `agent.py` 中设置 `max_iterations` 上限（默认 15） |
| **conversations.json 兼容** | `session_tools` 的 `load_conversation` / `save_conversation` 保持旧格式 |
