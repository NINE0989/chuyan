## 1. Backend: Analyze 端点

- [x] 1.1 `ai_service.py`: 新增 `analyze()` 方法 — 调用 LLM（不带 tool）进行需求分析，返回分析文本
- [x] 1.2 `api.py`: 新增 `POST /api/chat/analyze` 端点 — SSE 流式返回分析结果，`type: "chat"`
- [x] 1.3 `api.py`: 修改 `POST /api/chat` — Build 模式返回错误提示，引导至 analyze→build 两阶段

## 2. Backend: Build 端点改造

- [x] 2.1 `ai_service.py`: `_build_shader()` 新增 `analysis_context` 参数，注入到 Agent 的 user_content
- [x] 2.2 `api.py`: 新增 `POST /api/chat/build` 端点 — 接收 `analysis_context`，SSE 流式返回 GLSL
- [x] 2.3 `ai_pipeline/generate_cli.py`: `generate()` 的 user_content 增加可选的 `analysis_context` 注入

## 3. Agent 适配

- [x] 3.1 `ai_pipeline/system_prompt.md`: 移除需求分析和风格推断指引，只保留编码约束和 tool 使用指南
- [x] 3.2 `ai_pipeline/agent.py`: `build_shader_agent()` 的 system_prompt 确保不包含分析阶段职责

## 4. Frontend: 两阶段 UI

- [x] 4.1 `index.html`: Build 模式发送 prompt → 调用 `/api/chat/analyze` → SSE 流渲染到消息气泡
- [x] 4.2 `index.html`: 分析结束后在气泡下方渲染「确认生成」和「修改描述」按钮
- [x] 4.3 `index.html` CSS: 分析报告卡片样式 — 左侧彩色边框、按钮组布局
- [x] 4.4 `index.html`: 点击「确认生成」→ 调用 `/api/chat/build` → GLSL 填入编辑器 + 启动预览
- [x] 4.5 `index.html`: 点击「修改描述」→ 原始 prompt 回填输入框

## 5. 验证

- [ ] 5.1 测试 Plan 模式：输入"你好" → 正常对话（未受影响）
- [ ] 5.2 测试 Build 模式：输入"星空效果" → 先展示分析 → 确认 → 生成 GLSL → 预览
- [ ] 5.3 测试修改流程：分析后点击修改 → 调整 prompt → 重新分析
- [ ] 5.4 验证 Git 合并：仅修改指定文件，无新文件
