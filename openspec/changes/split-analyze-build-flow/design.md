## Context

当前 Build 模式的 `AIService._build_shader()` → `pipeline_generate()` → LangGraph Agent 在一个 `agent.invoke()` 中完成分析+编码+校验。DeepSeek 等模型在此流程中经常超出 token 窗口导致输出截断。前端只在完整 GLSL 产生后才能看到结果。

## Goals / Non-Goals

**Goals:**
- 将单步 Agent 调用拆为两个阶段，减少单次 LLM 调用的 token 压力
- 用户可在编码前审查分析结果，确认后再投入编码阶段
- 前端流式展示分析结果，确认交互自然融入现有 UI

**Non-Goals:**
- 不修改 LangGraph Agent 的核心工具链（tools/skills/hooks 保持不变）
- 不改变 Plan 模式的对话行为
- 不引入新的持久化层或会话存储

## Decisions

### 1. 两阶段通过 API 端点分离，而非 Agent 内部状态机

**选择**：前端发出两次独立 HTTP 请求 — `POST /api/chat/analyze` 和 `POST /api/chat/build`

**替代方案**：Agent 内部状态机（先分析→暂停→用户确认→继续编码）。放弃原因：LangGraph 的 `interrupt` 机制需要 checkpointer 和复杂的状态恢复，增加维护成本，且对 SSE 流式输出不友好。

**实现**：
- Analyze 端点：`AIService._plan_chat()` 变体，带 "分析着色器需求" 前缀的系统提示词 → LLM 直接返回分析文本，不走 Agent
- Build 端点：`AIService._build_shader()` 原逻辑，但 `GenerateRequest` 新增 `analysis_context` 字段，传入上一步的分析文本，注入到 Agent 的 user_content 中

### 2. 前端确认交互相对于流式输出的位置

**选择**：Analyze 阶段的 SSE 流结束后，在消息气泡下方渲染确认按钮（而非替换气泡内容）

**理由**：流式输出给用户即时反馈，确认按钮在流结束后出现，用户可以选择修改 prompt 重分析或点击「确认生成」进入 Build 阶段。

**UI 布局**：
```
[用户: 做一个星空效果]
[AI: 分析中...] ← SSE 流式填充
  ┌─ 分析报告 ─────────────────────┐
  │ 风格建议: neon                 │
  │ 频段映射: 低频→缩放, 高频→辉光  │
  │ 参数建议: ...                  │
  │ [✏ 修改]  [🔨 确认生成]       │
  └────────────────────────────────┘
         ↓ 点击确认后
[AI: 生成中...]
  → 代码填入编辑器 + 预览
```

### 3. Agent 的 system prompt 简化

**选择**：移除系统提示词中「分析音频、判断风格、推荐方案」等内容，只保留编码相关约束

**理由**：分析职责移到 Analyze 阶段，Agent 不应再花 token 做重复分析。Agent 现在只负责：根据 `analysis_context` 生成 GLSL → 编译检查 → 修正 → 保存。

## Risks / Trade-offs

- [风险] 两次 LLM 调用增加延迟 → 缓解：Analyze 阶段使用轻量 prompt（不走 tool），响应快；Build 阶段分析信息已固定，减少 Agent 的 tool 调用轮次
- [风险] Analyze 和 Build 的上下文断裂 → 缓解：`analysis_context` 作为字符串注入 Build 阶段
- [风险] 用户可能跳过分析直接点确认 → 缓解：分析结果默认展开显示，确认按钮在流结束后才出现
