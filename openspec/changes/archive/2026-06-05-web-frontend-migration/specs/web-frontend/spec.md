## ADDED Requirements

### Requirement: Chat Interface
Web 前端 SHALL 提供聊天界面，支持文本输入和 AI 生成。

#### Scenario: Send user prompt
- **WHEN** 用户在输入框输入文本并按回车或点击发送
- **THEN** 前端 SHALL 调用 `POST /api/chat` 发送 prompt，显示加载中状态，收到 GLSL 后渲染到代码面板

#### Scenario: Display generation result
- **WHEN** `POST /api/chat` 返回 GLSL 代码
- **THEN** 前端 SHALL 在代码编辑器区域展示 GLSL，应用按钮 SHALL 变为可用

### Requirement: Shader Library
Web 前端 SHALL 提供 Shader 库浏览功能。

#### Scenario: List shaders
- **WHEN** 用户切换到 Shader 库 Tab
- **THEN** 前端 SHALL 调用 `GET /api/shaders` 获取所有 .glsl 文件列表并渲染为卡片网格

#### Scenario: Load shader
- **WHEN** 用户点击 Shader 库中的某个卡片
- **THEN** 前端 SHALL 调用 `GET /api/shader?path=...` 加载代码到编辑器并切换到 Chat Tab

### Requirement: Apply / Launch OpenGL Window
Web 前端 SHALL 支持启动独立 OpenGL 窗口。

#### Scenario: Launch borderless window
- **WHEN** 用户点击「应用」按钮
- **THEN** 前端 SHALL 调用 `POST /api/launch` 传入当前 GLSL 代码，服务端调用 `launch.py` 启动独立 OpenGL 窗口

### Requirement: Settings Page
Web 前端 SHALL 在设置 Tab 中直接展示设置表单（复用已有 settings.html 的设计）。

### Requirement: Responsive Layout
Web 前端 SHALL 支持窗口缩放自适应。

#### Scenario: Narrow viewport
- **WHEN** 浏览器窗口宽度 < 768px
- **THEN** 聊天区和代码区 SHALL 垂直堆叠（而非左右分栏）
