## MODIFIED Requirements

### Requirement: System Prompt Integration
系统 SHALL 提供合并的 `system_prompt.md`，包含全部 20 个 tool 的使用指南。Agent 的职责专注于根据已有分析结果生成 GLSL，不包含需求分析、风格推断、音频分析步骤。

#### Scenario: System prompt guides code generation only
- **WHEN** Agent 接收 system_prompt
- **THEN** prompt SHALL 假设需求分析已完成，指导直接进入编码阶段
- **AND** prompt SHALL 包含所有 tool 名称、用途、典型调用时机

#### Scenario: System prompt includes coding constraints
- **WHEN** Agent 接收 system_prompt
- **THEN** prompt SHALL 包含 `mainImage`/`iResolution`/`iTime` 必须存在，`gl_FragColor` 禁止，输出 fenced code block

### Requirement: LangGraph Agent Graph
系统 SHALL 使用 LangGraph `StateGraph` + `ToolNode` 构建单 Agent，Agent 节点绑定全部 20 个 tool，LLM 自主决策调用顺序。Agent 接收分析上下文作为输入，直接进入编码阶段。

#### Scenario: Agent receives analysis context
- **WHEN** `agent.invoke` 的 user_content 包含 `analysis_context` 字段
- **THEN** Agent SHALL 基于该上下文直接生成 GLSL，跳过需求分析步骤

#### Scenario: Agent invokes tools in sequence
- **WHEN** Agent 执行编码任务
- **THEN** Agent SHALL 自主决策 tool 调用（如 `get_skill_template`、`compile_check_glsl`、`save_shader_to_file`），tool 结果返回后继续推理

#### Scenario: Agent finishes without tool call
- **WHEN** Agent 认为任务完成（已生成并保存 GLSL）
- **THEN** Agent SHALL 返回最终消息，图执行结束（进入 END 节点）

#### Scenario: Agent self-corrects after compilation failure
- **WHEN** Agent 调用 `compile_check_glsl` 返回错误
- **THEN** Agent SHALL 根据 `fix_hints` 修正 GLSL 代码，并再次验证
