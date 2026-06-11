## ADDED Requirements

### Requirement: Chat API
服务 SHALL 提供 AI 生成 API。

#### Scenario: POST /api/chat
- **WHEN** 收到 `POST /api/chat` 请求体 `{"prompt":"宇宙星空","adjust":false}`
- **THEN** 服务 SHALL 调用 `AIService.generate()` 并返回 `{"success":true,"code":"...","diagnostics":[...]}`

#### Scenario: Adjust mode
- **WHEN** 请求 `adjust:true` 且之前已生成过
- **THEN** 服务 SHALL 保持会话上下文，在已有代码基础上微调

### Requirement: Shader API
服务 SHALL 提供 Shader 文件管理 API。

#### Scenario: GET /api/shaders
- **WHEN** 收到 `GET /api/shaders`
- **THEN** 服务 SHALL 扫描 `shaders/` 目录并返回文件列表 JSON：`[{"name":"...","path":"...","size":...,"modified":"..."}]`

#### Scenario: GET /api/shader
- **WHEN** 收到 `GET /api/shader?path=shaders/ink_wash.glsl`
- **THEN** 服务 SHALL 返回文件内容 `{"code":"..."}`

#### Scenario: POST /api/shader
- **WHEN** 收到 `POST /api/shader` `{"code":"...","name":"my_shader"}`
- **THEN** 服务 SHALL 保存到 `shaders/my_shader.glsl` 并返回 `{"ok":true,"path":"..."}`

### Requirement: Launch API
服务 SHALL 提供 OpenGL 窗口启动 API。

#### Scenario: POST /api/launch
- **WHEN** 收到 `POST /api/launch` `{"code":"...","path":"optional/source/path"}`
- **THEN** 服务 SHALL 调用 `WebEngine.launch.launch_borderless_process()` 启动独立 OpenGL 窗口

### Requirement: Server Lifecycle
服务 SHALL 随 `app.py` 启动/退出。

#### Scenario: App starts server
- **WHEN** `python WebEngine/app.py` 执行
- **THEN** HTTP 服务 SHALL 在后台启动，主线程打开浏览器等待 KeyboardInterrupt 或窗口关闭
