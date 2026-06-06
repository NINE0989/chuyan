## ADDED Requirements

### Requirement: Analyze Endpoint
服务 SHALL 提供 `POST /api/chat/analyze` 端点，调用 LLM 分析着色器需求并返回结构化分析文本。

#### Scenario: Analyze with SSE stream
- **WHEN** 收到 `POST /api/chat/analyze` `{"prompt":"星空效果", "mode":"build"}`
- **THEN** 服务 SHALL 调用 LLM（不带 tool），以 SSE 流返回分析文本，系统提示词指导输出风格建议、频段映射、参数规划
- **AND** 流结束后 SHALL 发送 `[DONE]` 标记

#### Scenario: Analyze falls back on LLM error
- **WHEN** LLM 调用失败
- **THEN** 服务 SHALL 返回本地生成的基础分析模板

### Requirement: Build Endpoint with Analysis Context
服务 SHALL 提供 `POST /api/chat/build` 端点，接收分析结果作为上下文，走 LangGraph Agent 生成 GLSL。

#### Scenario: Build with analysis context
- **WHEN** 收到 `POST /api/chat/build` `{"prompt":"星空效果", "analysis_context":"风格建议: neon...", "mode":"build"}`
- **THEN** Agent 的 user_content SHALL 包含分析上下文，Agent SHALL 基于上下文直接编码，不再做需求分析
- **AND** 返回 SSE 流含 GLSL 代码（type: "shader"）

#### Scenario: Build without analysis context
- **WHEN** 收到 `POST /api/chat/build` 且 `analysis_context` 为空
- **THEN** Agent SHALL 使用默认上下文（minimal 风格）生成

### Requirement: Mode-Aware Routing
`/api/chat` SHALL 保持兼容，根据 mode 参数自动路由：mode="plan" → 对话，mode="build" → 先返回提示请使用 `/api/chat/analyze`。

#### Scenario: Legacy chat endpoint in build mode
- **WHEN** `POST /api/chat` 收到 `{"mode":"build", ...}`
- **THEN** 服务 SHALL 返回错误提示，引导调用 `/api/chat/analyze` 先进行分析
