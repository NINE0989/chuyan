## Why

当前 Build 模式的 Agent 流程是一步到位的：LLM 分析需求→调工具→写 GLSL→编译检查→保存，整个链路在一个 LangGraph invoke 中完成。这导致 DeepSeek 等模型经常输出被截断，模型的推理+编码 token 超出上下文窗口，用户看到的不是完整 shader 而是半截代码或 token 截断错误。同时，用户对生成结果没有中间确认环节，无法在编码前调整方案。

## What Changes

- **两阶段分离**：Analyze 阶段（纯 LLM 分析，不含 tool calls）和 Build 阶段（走 LangGraph Agent 编码），中间通过用户确认衔接
- Analyze 阶段：输入 prompt → LLM 输出分析报告（风格建议、参数规划、频段映射）→ 显示给用户
- 用户确认分析结果后，触发 Build 阶段：分析结果 + 原始 prompt → LangGraph Agent → GLSL → 保存 + 预览
- 前端新增「分析报告」展示区域，Build 模式发送 prompt 后先展示分析，用户点击「确认生成」后才进入编码
- 后端 `ai_service` 新增 `analyze()` 方法替代原有一步生成的 `_build_shader` 开头部分
- Agent 不再负责分析阶段（减少 tool 调用轮次，降低截断风险）

## Capabilities

### New Capabilities
- `shader-analyze-phase`: Analyze 阶段 API 和前端交互——发送 prompt → LLM 返回结构化分析 → 前端展示 → 用户确认

### Modified Capabilities
- `shader-agent-graph`: Agent 的 system prompt 和工作流去掉分析阶段的职责，专注于编码+自检+保存
- `web-api-server`: 新增 `/api/chat/analyze` 端点，`/api/chat/build` 端点分离
- `web-frontend`: Build 模式下新增分析报告卡片、确认按钮，与现有流式输出整合

## Impact

- `ai_pipeline/generate_cli.py`：入口参数增加 `analysis_context` 可选字段
- `ai_pipeline/agent.py`：system prompt 简化
- `ai_pipeline/system_prompt.md`：去掉分析指导，专注编码
- `WebEngine/ai_service.py`：新增 `analyze()` 方法
- `WebEngine/api.py`：新增两个端点
- `WebEngine/html/index.html`：新增分析报告 UI、确认按钮、两步调用逻辑
