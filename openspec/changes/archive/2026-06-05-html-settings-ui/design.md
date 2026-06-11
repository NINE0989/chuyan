## Context

当前设置界面 `WebEngine/ui/settings_dialog.py` 是 PyQt5 `QDialog`（480×380 固定大小），控件靠手动布局，样式通过 QSS 字符串定义。已接入 DeepSeek + 语音识别，设置功能完整但 UI 体验差。

项目已依赖 `PyQtWebEngine`，理论上可嵌入 Web 页面，但本次选择独立浏览器方案：
- 不需要修改现有 PyQt5 窗口结构
- 用户可在任意浏览器访问设置
- Python 标准库 `http.server` + `webbrowser` 零额外依赖

## Goals / Non-Goals

**Goals:**
- 用 HTML/CSS 重建设置界面，暗色主题，响应式布局，卡片式预设选择
- 用 Python 标准库 `http.server` 提供本地 HTTP 服务
- 保持与现有 `Settings` 配置管理器兼容（读写同一个 `settings.json`）
- 服务器随应用启动/退出自动管理生命周期

**Non-Goals:**
- 不引入 Flask/FastAPI 等第三方框架
- 不改动现有 PyQt5 主界面（main_page.py 只改 ⚙ 按钮行为）
- 不添加用户认证（本地 localhost 服务）

## Decisions

### 决策 1：用 `http.server` 而非 Flask

**选择**：Python 标准库 `http.server.ThreadingHTTPServer`

**原因**：
- 零额外依赖，`requirements.txt` 不变
- 设置接口仅 2 个端点（GET/POST `/api/settings`），不需要路由框架
- 后台线程运行，不阻塞 PyQt5 主线程

**备选方案**：Flask — 功能更完善但增加依赖，对 2 个端点的简单场景过度

### 决策 2：独立浏览器页面而非 QWebEngineView

**选择**：`webbrowser.open()` 打开系统默认浏览器

**原因**：
- 设置操作频率低（一次配置长期使用），不需要嵌入主窗口
- 浏览器独立窗口自然支持缩放、响应式布局
- 不影响现有 PyQt5 布局结构
- 可随时在浏览器 `localhost:18090/settings.html` 访问

**备选方案**：QWebEngineView 嵌入 — 集成度更高但需要 QWebChannel 桥接，增加复杂度

### 决策 3：端口自动递增

**选择**：18090 起，端口冲突时自动 +1 直到 18099

**原因**：
- 避免多实例端口冲突
- 返回实际端口给调用方，浏览器打开正确 URL

### 决策 4：单例服务器

**选择**：模块级单例 `_server_instance`，重复调用返回已有实例

**原因**：
- 多次点击 ⚙ 不会启动多个服务器
- 已运行时直接打开浏览器

### 决策 5：HTML 内联 CSS/JS（无外部依赖）

**选择**：所有 CSS/JS 写在一个 HTML 文件中

**原因**：
- 不需要静态文件服务路由
- 单个文件易于维护
- 无 CDN 依赖（本地服务也可能离线）

## Data Flow

```
用户点击 ⚙
  │
  ▼
start_settings_server(18090)
  │
  ├─ 已有实例？→ 不重复启动
  ├─ 端口占用？→ 递增重试
  └─ 启动 ThreadingHTTPServer
  │
  ▼
webbrowser.open(f"http://127.0.0.1:{port}/settings.html")
  │
  ▼
浏览器加载 HTML → GET /api/settings → 返回 settings.json
  │
  用户编辑 → 点击保存 → POST /api/settings → 写入 settings.json
  │
  ▼
成功提示 + 关闭浏览器

应用退出 → shutdown_server()
```

## Risks / Trade-offs

| 风险 | 缓解 |
|---|---|
| 浏览器未安装 / 无法打开 | `webbrowser.open()` 在 headless 环境会静默失败，不影响主功能 |
| localhost 端口被防火墙拦截 | 使用 `127.0.0.1` 而非 `0.0.0.0`，仅本机访问 |
| 多用户同时写入 settings.json | 使用 `threading.Lock` 保护文件写入 |
