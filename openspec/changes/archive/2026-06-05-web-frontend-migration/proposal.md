## Why

当前前端基于 PyQt5 原生控件（`QLineEdit`、`QTextEdit`、`QScrollArea` 等），存在以下问题：
1. 样式受限于 QSS，无法实现现代化设计（圆角、渐变、过渡动画）
2. 控件布局固定，不支持响应式缩放
3. 与已完成的 HTML 设置页面风格割裂
4. 维护两套 UI 技术栈（PyQt5 + HTML）增加复杂度

**时机**：设置页面已完成 HTML 化 + DeepSeek/语音接入已就绪，统一为 Web 前端可消除技术栈分裂。

## What Changes

- **新增** `WebEngine/html/index.html`：Web 主页面（聊天 + 代码编辑 + Shader 库 + 设置 的 Tab 导航 SPA）
- **新增** `WebEngine/server.py`：统一 HTTP 服务（整合现有 `settings_server.py`），新增 API 端点
- **新增** `WebEngine/api.py`：API 路由处理（chat/generate/shaders/launch/settings）
- **修改** `WebEngine/app.py`：启动 HTTP 服务 → 打开浏览器 → 等待退出
- **BREAKING 移除** `WebEngine/ui/main_page.py`：PyQt5 主页面 → Web 替代
- **BREAKING 移除** `WebEngine/ui/shader_page.py`：PyQt5 Shader 库 → Web 替代
- **BREAKING 移除** `WebEngine/ui/window.py`：PyQt5 主窗口 → 不再需要
- **移除** `WebEngine/ui/settings_dialog.py`：已在 html-settings-ui 中删除
- **保留** `WebEngine/launch.py`：OpenGL 独立窗口启动（不受影响）
- **保留** `WebEngine/ai_service.py`、`speech_service.py`、`settings.py`：后端服务不变

## Capabilities

### New Capabilities
- `web-frontend`：基于 HTML/CSS/JS 的单页 Web 前端，暗色主题，Tab 导航（Chat / Shader库 / 设置），聊天界面、代码编辑器、一键应用启动
- `web-api-server`：本地 HTTP API 服务，提供 `/api/chat`（AI 生成）、`/api/shaders`（列表+加载+保存）、`/api/launch`（启动 OpenGL 窗口）、`/api/settings`（配置管理）端点

### Modified Capabilities
（无现有 spec，无需修改）

## Impact

- **删除文件**：`WebEngine/ui/main_page.py`、`WebEngine/ui/shader_page.py`、`WebEngine/ui/window.py`
- **新增文件**：`WebEngine/html/index.html`、`WebEngine/server.py`、`WebEngine/api.py`
- **修改文件**：`WebEngine/app.py`（入口改为 HTTP 服务 + 浏览器）、`WebEngine/settings_server.py`（合并到 server.py 或废弃）
- **新增依赖**：无（`http.server`、`json`、`threading` 均为标准库）
- **OpenGL 窗口**：不受影响（`launch.py` 独立进程）
