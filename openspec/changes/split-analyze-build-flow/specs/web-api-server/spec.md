## ADDED Requirements

### Requirement: Analyze and Build API
服务 SHALL 提供两阶段生成 API，分离分析和编码步骤。

#### Scenario: POST /api/chat/analyze
- **WHEN** 收到 `POST /api/chat/analyze` `{"prompt":"宇宙星空","mode":"build"}`
- **THEN** 服务 SHALL 调用 LLM 进行需求分析，以 SSE 流返回分析文本

#### Scenario: POST /api/chat/build
- **WHEN** 收到 `POST /api/chat/build` `{"prompt":"宇宙星空","analysis_context":"风格: neon...","mode":"build"}`
- **THEN** 服务 SHALL 调用 `AIService._build_shader()`，传入 analysis_context 到 Agent，以 SSE 流返回 GLSL

## MODIFIED Requirements

### Requirement: Chat API
服务 SHALL 提供 AI 生成 API。Build 模式下引导使用两阶段 API。

#### Scenario: POST /api/chat in build mode
- **WHEN** 收到 `POST /api/chat` `{"prompt":"宇宙星空","mode":"build"}`
- **THEN** 服务 SHALL 返回 `{"success":false,"error":"请先调用 /api/chat/analyze 进行分析，确认后再调用 /api/chat/build 生成代码"}`

#### Scenario: POST /api/chat in plan mode
- **WHEN** 收到 `POST /api/chat` `{"prompt":"你好","mode":"plan"}`
- **THEN** 服务 SHALL 正常对话，流式返回文本

#### Scenario: Adjust mode
- **WHEN** 请求 `adjust:true` 且之前已生成过
- **THEN** 服务 SHALL 保持会话上下文，在已有代码基础上微调
