## ADDED Requirements

### Requirement: HTML Settings Page
系统 SHALL 提供基于 HTML/CSS 的设置页面，通过本地 HTTP 服务访问。

#### Scenario: Open settings in browser
- **WHEN** 用户点击 ⚙ 按钮
- **THEN** 系统 SHALL 启动本地 HTTP 服务（端口 18090）并在默认浏览器打开 `http://localhost:18090/settings.html`

#### Scenario: Display current configuration
- **WHEN** 页面加载
- **THEN** 页面 SHALL 通过 `GET /api/settings` 获取当前配置并填充表单字段

#### Scenario: Save configuration
- **WHEN** 用户填写 API Key/Base URL/Model 并点击保存
- **THEN** 页面 SHALL 通过 `POST /api/settings` 提交 JSON 数据，服务端写入 `settings.json`，页面显示成功提示

### Requirement: Local HTTP Server
系统 SHALL 提供基于 Python `http.server` 的本地 HTTP 服务。

#### Scenario: Server starts on designated port
- **WHEN** 调用 `start_settings_server(port=18090)`
- **THEN** 服务 SHALL 在后台线程启动，监听 `127.0.0.1:18090`

#### Scenario: Port already in use
- **WHEN** 18090 端口被占用
- **THEN** 系统 SHALL 自动尝试 18091-18099，找到第一个可用端口

#### Scenario: GET /api/settings
- **WHEN** 收到 `GET /api/settings` 请求
- **THEN** 服务 SHALL 返回当前 `settings.json` 内容的 JSON（含 api_key/base_url/model）

#### Scenario: POST /api/settings
- **WHEN** 收到 `POST /api/settings` 请求体 `{"api_key":"sk-...","base_url":"...","model":"..."}`
- **THEN** 服务 SHALL 写入 `settings.json` 并返回 `{"ok":true}`

### Requirement: Modern UI Design
HTML 页面 SHALL 采用现代化设计。

#### Scenario: Dark theme
- **WHEN** 页面渲染
- **THEN** 背景色 SHALL 为深色系（#1a1a2e 或类似），文字为浅色，卡片为暗色半透明

#### Scenario: Preset quick switch
- **WHEN** 用户点击 "DeepSeek" 预设卡片
- **THEN** base_url SHALL 自动填充 `https://api.deepseek.com/v1`，model SHALL 自动填充 `deepseek-chat`

#### Scenario: API key visibility toggle
- **WHEN** 用户点击密码输入框旁的眼睛图标
- **THEN** API Key SHALL 在明文和密文之间切换

#### Scenario: Responsive layout
- **WHEN** 浏览器窗口宽度变化
- **THEN** 表单卡片 SHALL 自适应居中，最小宽度 400px，最大宽度 640px

### Requirement: Server Lifecycle
服务 SHALL 随应用退出自动关闭。

#### Scenario: Server shuts down with app
- **WHEN** 应用退出（MainPage.closeEvent）
- **THEN** HTTP 服务 SHALL 调用 `shutdown()` 停止后台线程
