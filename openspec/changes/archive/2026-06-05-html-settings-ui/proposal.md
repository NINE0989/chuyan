## Why

当前设置界面 `WebEngine/ui/settings_dialog.py` 基于 PyQt5 `QDialog`，窗口固定 480×380，PyQt 原生控件样式简陋，无法实现现代化设计。用户期望：
1. 窗口可缩放、布局响应式
2. 使用 HTML/CSS 实现现代化 UI（预设卡片、视觉层级、暗色主题）
3. 通过本地 HTTP 服务提供 HTML 页面，支持浏览器访问

**时机**：DeepSeek + 语音输入刚接入，设置界面是用户第一个接触的入口，体验影响第一印象。

## What Changes

- **新增** `WebEngine/html/settings.html`：响应式 HTML 设置页面，现代化 CSS 设计（暗色主题、卡片布局、预设选择、状态提示）
- **新增** `WebEngine/settings_server.py`：基于 `http.server` 的本地 HTTP 服务，端口 18090，提供 `/settings.html` 页面和 `/api/settings` GET/POST 接口
- **新增** `WebEngine/settings_api.py`：设置 API 处理层，处理 JSON 请求/响应，读写 `settings.json`
- **修改** `WebEngine/ui/main_page.py`：⚙ 按钮调用 `start_settings_server()` + `webbrowser.open()` 在浏览器打开设置页，替代 PyQt5 对话框
- **移除** `WebEngine/ui/settings_dialog.py`：不再需要 PyQt5 设置对话框
- **移除** `WebEngine/ui/settings_dialog.py` 的 import

## Capabilities

### New Capabilities
- `html-settings-page`：基于 HTML/CSS 的现代化设置界面，通过本地 HTTP 服务提供。包括暗色主题设计、DeepSeek/OpenAI 预设一键切换、API Key 可视化输入（显示/隐藏）、保存状态实时反馈、响应式布局

### Modified Capabilities
（无现有 spec，无需修改）

## Impact

- **新增文件**：`WebEngine/html/settings.html`、`WebEngine/settings_server.py`、`WebEngine/settings_api.py`
- **修改文件**：`WebEngine/ui/main_page.py`（⚙ 按钮行为变更）
- **删除文件**：`WebEngine/ui/settings_dialog.py`
- **新增依赖**：无（`http.server`、`webbrowser` 均为 Python 标准库）
- **端口占用**：本地 `18090` 端口，启动时检查可用性
