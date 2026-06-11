# AI 音频 Shader 生成框架（ai_pipeline）

本模块提供与 Git 解耦的 AI 生成流程，包含：
- `mcp` 协议适配层（真实 OpenAI 兼容后端 + mock）
- 多 Agent 对话编排（音频理解 Agent + 编码 Agent）
- `hooks` 生成时注入与质量检查
- `cases`（goodcase / badcase / styles）

## 快速使用

```powershell
python -m ai_pipeline.generate_cli --prompt "生成一个随低频脉冲扩张的径向图形" --style neon --provider openai --session-id s1 --audio-array-file .\audio_samples.json
```

## 说明
- 会话历史保存在 `ai_pipeline/conversations.json`，用于持续传递上下文。
- `audio_understanding_agent.md` 负责音频风格总结与可视化方向建议。
- `coding_agent.md` 负责按分析结果落地可编译 GLSL。
- hooks 在生成阶段自动注入，不依赖 `.git/hooks`。
