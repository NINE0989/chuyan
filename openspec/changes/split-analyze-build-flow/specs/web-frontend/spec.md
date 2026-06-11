## ADDED Requirements

### Requirement: Two-Phase Build Flow
Build 模式下，前端 SHALL 执行两阶段流程：分析→确认→生成。

#### Scenario: User sends prompt in Build mode
- **WHEN** 用户在 Build 模式下发送 prompt
- **THEN** 前端 SHALL 先调用 `POST /api/chat/analyze`（SSE 流），在消息气泡中流式展示分析结果

#### Scenario: Analyze stream ends with confirm button
- **WHEN** Analyze SSE 流返回 `[DONE]`
- **THEN** 消息气泡下方 SHALL 显示「确认生成」和「修改描述」两个按钮

#### Scenario: User confirms analysis
- **WHEN** 用户点击「确认生成」
- **THEN** 前端 SHALL 调用 `POST /api/chat/build`（SSE 流），传入原始 prompt 和完整分析文本作为 `analysis_context`
- **AND** 生成结束后，GLSL 代码 SHALL 填入编辑器并启动预览

#### Scenario: User modifies after analysis
- **WHEN** 用户点击「修改描述」
- **THEN** 原始 prompt SHALL 回填到输入框，用户可修改后重新发送

### Requirement: Analysis Report Display
分析结果 SHALL 以结构化卡片形式展示，区别于普通聊天消息。

#### Scenario: Analysis card styling
- **WHEN** Analyze 阶段返回分析文本
- **THEN** 卡片 SHALL 使用左侧彩色边框区分普通消息，包含「确认生成」主按钮和「修改」次按钮

## MODIFIED Requirements

### Requirement: Apply / Launch OpenGL Window
Web 前端 SHALL 支持启动独立 OpenGL 窗口。

#### Scenario: Launch borderless window
- **WHEN** 用户点击「部署」按钮
- **THEN** 前端 SHALL 调用 `POST /api/launch` 传入当前 GLSL 代码，服务端调用 `launch.py` 启动独立 OpenGL 窗口

### Requirement: Chat Interface
Web 前端 SHALL 提供聊天界面，支持文本输入和 AI 交互。Build 模式使用两阶段流程。

#### Scenario: Send user prompt
- **WHEN** 用户在输入框输入文本并按 Enter 或点击发送
- **THEN** 根据当前模式：Plan → 对话；Build → 进入分析阶段
- **AND** 前端 SHALL 显示加载状态
