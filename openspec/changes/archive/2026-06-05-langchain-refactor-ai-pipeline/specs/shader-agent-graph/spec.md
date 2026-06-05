## ADDED Requirements

### Requirement: LangGraph Agent Graph
系统 SHALL 使用 LangGraph `StateGraph` + `ToolNode` 构建单 Agent，Agent 节点绑定全部 18 个 tool，LLM 自主决策调用顺序。

#### Scenario: Agent invokes tools in sequence
- **WHEN** `agent.invoke({"messages": [SystemMessage(system_prompt), HumanMessage(user_prompt)]})`
- **THEN** Agent SHALL 自主决策 tool 调用（如先 `summarize_audio`、后 `get_skill_template`），tool 结果返回后继续推理

#### Scenario: Agent finishes without tool call
- **WHEN** Agent 认为任务完成（已生成并保存 GLSL）
- **THEN** Agent SHALL 返回最终消息，图执行结束（进入 END 节点）

#### Scenario: Agent self-corrects after validation failure
- **WHEN** Agent 调用 `validate_glsl_keywords` 返回错误列表
- **THEN** Agent SHALL 根据错误信息修正 GLSL 代码，并再次调用 `validate_glsl_keywords` 验证

### Requirement: Tool-Calling Loop
LangGraph 图 SHALL 实现标准 ReAct 循环：START → agent → [有 tool_calls → tools → agent 循环] → [无 tool_calls → END]。

#### Scenario: Single tool call
- **WHEN** Agent 输出包含 tool_calls
- **THEN** 图 SHALL 路由到 ToolNode 执行 tool，结果返回 agent 节点继续推理

#### Scenario: Consecutive tool calls
- **WHEN** agent 在一次推理中需要调用多个 tool
- **THEN** 图 SHALL 在 agent 和 tools 节点间循环，直到 agent 产出不含 tool_calls 的最终消息

### Requirement: System Prompt Integration
系统 SHALL 提供合并的 `system_prompt.md`，融合 `audio_understanding.md` 和 `coding_agent.md` 的 SOP 内容，并包含全部 18 个 tool 的使用指南。

#### Scenario: System prompt guides tool usage
- **WHEN** Agent 接收 system_prompt
- **THEN** prompt SHALL 包含所有 tool 名称、用途、典型调用时机和推荐调用顺序

#### Scenario: System prompt includes SOP constraints
- **WHEN** Agent 接收 system_prompt
- **THEN** prompt SHALL 包含原 `coding_agent.md` 的全部约束（必须 `mainImage`/`iResolution`/`iTime`，禁止 `gl_FragColor`，输出 fenced code block）

### Requirement: Stream Support
系统 SHALL 支持 Agent 流式输出。通过 `agent.stream()` API 逐步产出消息 token 和 tool 调用事件。

#### Scenario: Stream agent execution
- **WHEN** 调用 `for event in agent.stream(input, stream_mode="values")`
- **THEN** 系统 SHALL 每步产出中间状态（agent 消息、tool 调用、tool 结果）

#### Scenario: Non-stream fallback
- **WHEN** provider 为 mock
- **THEN** `stream()` SHALL 降级为一次性返回并模拟分块
