## 1. API 服务层

- [x] 1.1 创建 `WebEngine/api.py`：`APIHandler` 类，整合 settings_api 功能，新增 chat/shaders/launch 路由
- [x] 1.2 创建 `WebEngine/server.py`：`start_server(port=18090)`、`stop_server()`，使用 `APIHandler`，整合 settings_server 功能
- [x] 1.3 修改 `WebEngine/app.py`：启动 server → 打开浏览器 → `input("按 Enter 退出")` 等待

## 2. HTML 前端 SPA

- [x] 2.1 创建 `WebEngine/html/index.html`：暗色主题 SPA，3 个 Tab（Chat / Shader库 / 设置）
- [x] 2.2 Chat Tab：输入框 + 发送按钮 + 聊天气泡（用户/AI 消息）+ 加载动画
- [x] 2.3 Code 面板：`<textarea>` 等宽字体 + 「应用」按钮 + 状态提示
- [x] 2.4 Shader库 Tab：卡片网格，从 `GET /api/shaders` 加载，点击加载到编辑器
- [x] 2.5 设置 Tab：`<iframe>` 内嵌已有 `settings.html`
- [x] 2.6 JS 逻辑：API 调用封装、Tab 切换、会话状态管理（adjust 模式）

## 3. 后端 API 实现

- [x] 3.1 `POST /api/chat`：调用 `AIService.generate()`，返回 GLSL + diagnostics
- [x] 3.2 `GET /api/shaders`：扫描 `shaders/` 目录返回文件列表 JSON
- [x] 3.3 `GET /api/shader?path=...`：读取指定文件返回 code
- [x] 3.4 `POST /api/shader`：保存 GLSL 到文件
- [x] 3.5 `POST /api/launch`：调用 `launch_borderless_process()` 启动 OpenGL 窗口
- [x] 3.6 `GET /api/settings` / `POST /api/settings`：复用已有逻辑

## 4. 清理旧 PyQt5 UI

- [x] 4.1 删除 `WebEngine/ui/main_page.py`
- [x] 4.2 删除 `WebEngine/ui/shader_page.py`
- [x] 4.3 删除 `WebEngine/ui/window.py`
- [x] 4.4 删除 `WebEngine/visualizer.py`（PyQt5 OpenGL widget 不再需要）
- [x] 4.5 删除 `WebEngine/settings_server.py`（合并到 server.py）
- [x] 4.6 删除 `WebEngine/settings_api.py`（合并到 api.py）

## 5. 验证

- [x] 5.1 启动 `python WebEngine/app.py` → 浏览器打开 → Chat/Shader库/设置 Tab 可用
- [x] 5.2 输入 prompt 发送 → AI 生成返回 → 代码展示在面板
- [x] 5.3 点击「应用」→ OpenGL 独立窗口启动
- [x] 5.4 Shader 库加载文件列表 → 点击加载到编辑器
- [x] 5.5 设置保存后生效
- [x] 5.6 `python -m ai_pipeline.generate_cli --provider mock` 不受影响

