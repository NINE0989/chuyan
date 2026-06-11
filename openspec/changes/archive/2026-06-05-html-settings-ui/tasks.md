## 1. HTML 设置页面

- [x] 1.1 创建 `WebEngine/html/` 目录
- [x] 1.2 创建 `WebEngine/html/settings.html`：暗色主题 HTML 页面，含 API Key（密码框+显示切换）、Base URL、Model 输入、DeepSeek/OpenAI/自定义预设卡片、保存按钮、状态提示
- [x] 1.3 CSS 响应式设计：卡片居中、max-width 640px、暗色背景 #1a1a2e、圆角、hover 效果
- [x] 1.4 JS 逻辑：页面加载时 `fetch GET /api/settings` 填充表单，保存时 `fetch POST /api/settings` 提交 JSON

## 2. 本地 HTTP 服务

- [x] 2.1 创建 `WebEngine/settings_api.py`：`SettingsAPIHandler` 类，处理 `GET /api/settings` 返回 settings.json 内容，`POST /api/settings` 写入 settings.json
- [x] 2.2 创建 `WebEngine/settings_server.py`：`start_settings_server(port=18090)` 在后台线程启动 `ThreadingHTTPServer`，端口冲突自动递增，返回实际端口；`stop_server()` 关闭服务；全局单例
- [x] 2.3 验证：`python -c "from WebEngine.settings_server import start_settings_server; port=start_settings_server(); print(port)"`

## 3. 主界面集成

- [x] 3.1 修改 `WebEngine/ui/main_page.py`：⚙ 按钮 `_open_settings` 改为调用 `start_settings_server()` + `webbrowser.open()`
- [x] 3.2 添加 `import webbrowser`
- [x] 3.3 在 `closeEvent` 中调用 `stop_server()` 确保退出时关闭服务
- [x] 3.4 验证：启动 `python WebEngine/app.py`，点击 ⚙，确认浏览器打开设置页面，保存配置后 settings.json 更新

## 4. 清理

- [x] 4.1 删除 `WebEngine/ui/settings_dialog.py`
- [x] 4.2 删除 `main_page.py` 中 `from WebEngine.ui.settings_dialog import SettingsDialog`
- [x] 4.3 删除 `main_page.py` 中 `_open_settings` 的旧 PyQt5 对话框逻辑

