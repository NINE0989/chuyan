## Context

当前 PyQt5 前端（`main_page.py` 659 行 + `shader_page.py` 84 行 + `window.py` 48 行）维护成本高，样式受限于 QSS。设置页面已成功 HTML 化（`html-settings-ui` change），验证了 `http.server` + 浏览器方案的可行性。

## Goals / Non-Goals

**Goals:**
- 用单个 HTML SPA 替代 PyQt5 `MainPage` + `ShaderPage` + `MainWindow`
- 扩展 HTTP 服务，统一提供前端页面 + API 端点
- 聊天、代码编辑、Shader 库浏览、设置、一键应用启动
- 暗色主题，响应式布局
- 零新增依赖

**Non-Goals:**
- 不改动 OpenGL 窗口（`launch.py` 独立进程不变）
- 不改动 AI 管线（`ai_pipeline/`、`ai_service.py` 不变）
- 不引入 React/Vue 等框架（纯 vanilla JS）
- 不引入 Flask/FastAPI（扩展 `http.server`）

## Decisions

### 决策 1：扩展 http.server 而非引入 Web 框架

**选择**：在现有 `threadingHTTPServer` + `BaseHTTPRequestHandler` 上添加路由

**原因**：
- 零新依赖，`requirements.txt` 不变
- 已完成 settings 服务的模式可直接复用
- 端点数量有限（~6 个），不需要路由框架

### 决策 2：SPA 单页应用 + Tab 导航

**选择**：单个 `index.html`，3 个 Tab（Chat / Shader库 / 设置）

**原因**：
- 简单：无页面跳转，无前端路由
- 所有功能在一个 HTML 文件中，`http.server` 只需 serve 一个文件
- Tab 切换由 JS 控制显示/隐藏 div

### 决策 3：聊天支持"附加代码"和 adjust 模式

**选择**：前端维护 `hasGeneratedOnce` 标志，首次 → `adjust:false`，后续 → `adjust:true`

**原因**：保持与 PyQt5 版相同的行为逻辑

### 决策 4：代码编辑器用 `<textarea>` + 等宽字体

**选择**：纯 `<textarea>` without CodeMirror/Monaco

**原因**：
- 零外部依赖
- GLSL 代码通常较短（<300 行），不需要高级编辑功能
- 暗色背景 + 等宽字体足够

## Module Layout

```
WebEngine/
├── app.py              # 入口：启动 HTTP 服务 → 打开浏览器
├── server.py           # 统一 HTTP 服务（ThreadingHTTPServer + 路由）
├── api.py              # API handler：chat/shaders/launch/settings
├── settings.py         # 不变：配置管理器
├── ai_service.py       # 不变：AI 服务封装
├── speech_service.py   # 不变：语音服务
├── launch.py           # 不变：OpenGL 窗口启动
├── html/
│   ├── index.html      # 新：主 SPA 页面
│   └── settings.html   # 已有（设置页面，可在 SPA Tab 中 iframe 引用）
├── settings_server.py  # 合并到 server.py，保留为兼容层
├── settings_api.py     # 合并到 api.py
└── ui/                 # 删除 main_page.py, shader_page.py, window.py
```

## Data Flow

```
python WebEngine/app.py
  │
  ├─ start_server(18090)
  ├─ webbrowser.open("http://127.0.0.1:18090")
  │
  ▼
浏览器加载 index.html
  │
  ├─ [Chat Tab] 输入 prompt → POST /api/chat → AI 生成 → 展示代码
  ├─ [Shader库 Tab] GET /api/shaders → 渲染卡片 → 点击加载
  ├─ [设置 Tab] iframe settings.html → 保存配置
  │
  ├─ 点击「应用」→ POST /api/launch → launch.py → OpenGL 独立窗口
  │
  ▼
Ctrl+C → stop_server() → 退出
```

## Risks

| 风险 | 缓解 |
|---|---|
| 浏览器未安装 | `webbrowser.open()` 失败时打印 URL 到控制台，用户可手动粘贴 |
| JS fetch 跨域 | 服务端所有 API 添加 `Access-Control-Allow-Origin: *` |
| 长生成阻塞 UI | 后端 AIService.generate() 是同步的，前端显示加载动画足够 |
| 旧 PyQt5 代码残留 | 全部删除 `ui/` 包中的主页面文件 |
