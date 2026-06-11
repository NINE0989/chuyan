## 1. 基础设施

- [x] 1.1 修改 `requirements.txt`：新增 `langchain>=0.3.0,<1.0`、`langchain-openai>=0.2.0,<1.0`、`langgraph>=0.2.0,<1.0`
- [x] 1.2 运行 `pip install -r requirements.txt` 确认依赖安装成功
- [x] 1.3 创建 `ai_pipeline/llm/` 目录，含 `__init__.py` 和 `adapter.py` 空文件
- [x] 1.4 创建 `ai_pipeline/tools/` 目录，含 `__init__.py` 和 6 个分类文件空壳

## 2. LLM 适配器（`ai_pipeline/llm/adapter.py`）

- [x] 2.1 实现 `build_llm(provider: str)` 工厂函数：`provider=="openai"` 返回 `ChatOpenAI`（读取 `OPENAI_API_KEY`/`OPENAI_BASE_URL`/`OPENAI_MODEL`），否则返回 mock `RunnableLambda`
- [x] 2.2 实现 mock `RunnableLambda`：保留旧 `MockMcpAdapter` 的关键词判断逻辑（检测 "JSON"/"音乐风格"→返回硬编码 JSON，否则返回硬编码 GLSL），包装为 LangChain 消息格式
- [x] 2.3 验证：`python -c "from ai_pipeline.llm.adapter import build_llm; llm=build_llm('mock'); print(llm.invoke([HumanMessage(content='JSON 测试')]).content)"`

## 3. Tool 实现 — 音频类（`tools/audio_tools.py`）

- [x] 3.1 实现 `@tool summarize_audio(array: list[float]) -> dict`：迁移自 `orchestrator._summarize_audio()` 逻辑（length/mean/max/min/samples 抽样）
- [x] 3.2 实现 `@tool load_audio_from_file(path: str) -> list[float]`：迁移自 `generate_cli._load_audio_array()` 逻辑
- [x] 3.3 验证：`python -c "from ai_pipeline.tools.audio_tools import summarize_audio; print(summarize_audio.invoke({'array':[0.1,0.2,0.3]}))"`

## 4. Tool 实现 — Shader 类（`tools/shader_tools.py`）

- [x] 4.1 实现 `@tool extract_glsl_code(text: str) -> str`：迁移自 `tools/get_fenced_code_block.py` 正则，统一三处重复
- [x] 4.2 实现 `@tool save_shader_to_file(code: str, out_dir: str, name: str) -> str`：迁移自 `generate_cli.save_shader()`
- [x] 4.3 实现 `@tool inject_shader_header(code: str, style: str) -> str`：迁移自 `hooks.engine.GenerationHookEngine.inject_header()`
- [x] 4.4 实现 `@tool ensure_glsl_version(code: str) -> str`：迁移自 `WebEngine.launch._ensure_version()`

## 5. Tool 实现 — 验证类（`tools/validation_tools.py`）

- [x] 5.1 实现 `@tool validate_glsl_keywords(glsl_code: str) -> str`：迁移自 `hooks.quality_check.run_glsl_checks()`，检查 mainImage/iResolution/iTime 存在、gl_FragColor 禁止，返回问题描述字符串
- [x] 5.2 实现 `@tool run_full_quality_check(code: str) -> str`：迁移自 `generate_cli.run_quality()`，子进程运行完整检查，返回 JSON 结果字符串
- [x] 5.3 实现 `@tool load_known_badcases() -> str`：迁移自 `regression_badcase.load_badcases()`，返回 JSON 格式已知失败模式

## 6. Tool 实现 — 技能类 + 会话类 + 辅助类

- [x] 6.1 实现 `tools/skill_tools.py`：`@tool get_skill_template(name)`、`@tool list_available_skills()`、`@tool build_skill_prompt(names)`（基于 SKILL_LIBRARY）
- [x] 6.2 实现 `tools/session_tools.py`：`@tool load_conversation(session_id)`、`@tool save_conversation(session_id, messages)`（基于 conversations.json）
- [x] 6.3 实现 `tools/utility_tools.py`：`@tool infer_shader_style(prompt)`、`@tool normalize_audio_analysis(raw_json)`、`@tool load_audio_array(path)`、`@tool run_py_syntax_check(root)`
- [x] 6.4 实现 `tools/__init__.py::get_all_tools(root: Path) -> list`：聚合全部 18 个 tool

## 7. System Prompt + LangGraph Agent（`agent.py`）

- [x] 7.1 创建 `ai_pipeline/system_prompt.md`：合并 `audio_understanding.md` + `coding_agent.md` 的核心约束，追加 18 个 tool 的名称、用途和推荐调用顺序
- [x] 7.2 实现 `agent.py::build_shader_agent(llm, tools, system_prompt)`：构建 LangGraph `StateGraph`
  - `agent` 节点：`llm.bind_tools(tools)` 调用，注入 `SystemMessage(system_prompt)`
  - `tools` 节点：`ToolNode(tools)`
  - `START → agent → tools → agent → END` 条件路由图，`max_iterations=15`
- [x] 7.3 验证：用 mock LLM 运行 agent，确认 tool 调用循环正常

## 8. CLI 入口适配（`generate_cli.py`）

- [x] 8.1 修改 `generate()`：用 `build_llm()` + `get_all_tools()` + `build_shader_agent()` + `agent.invoke()` 替换 `build_mcp_adapter()` + `MultiAgentOrchestrator().run()`
- [x] 8.2 删除 `generate_cli.py` 中的 `_extract_glsl()`（改用 `tools/shader_tools.py`）
- [x] 8.3 确保 `generate()` 返回值 `GenerateResult` 结构不变（从 agent 结果提取 GLSL → hooks → quality → return）
- [x] 8.4 验证：`python -m ai_pipeline.generate_cli --prompt "测试" --provider mock` 成功输出

## 9. Web 端适配（`WebEngine/ai_service.py`）

- [x] 9.1 修改 `AIService.generate()`：适配 `pipeline_generate()` 返回结构（如有微调）
- [x] 9.2 删除 `AIService._extract_code()`（改用 `ai_pipeline.tools.shader_tools.extract_glsl_code`）
- [x] 9.3 修改 `AIService.stream_generate()`：使用 `agent.stream()` 实现真实流式输出
- [x] 9.4 验证：`python WebEngine/app.py` 启动前端，确认 AI 生成功能正常

## 10. 回归测试 + 清理旧代码

- [x] 10.1 运行 `python -m ai_pipeline.regression_badcase --provider mock` 确认通过
- [x] 10.2 运行 `python -m ai_pipeline.hooks.quality_check` 确认无回归
- [x] 10.3 删除 `ai_pipeline/mcp/` 整个目录
- [x] 10.4 删除 `ai_pipeline/orchestrator.py`
- [x] 10.5 删除 `tools/get_fenced_code_block.py`
- [x] 10.6 更新 `ai_pipeline/__init__.py`：移除 mcp/orchestrator 相关 re-export
- [x] 10.7 全局搜索 `from ai_pipeline.mcp`、`from ai_pipeline.orchestrator`、`from tools.get_fenced_code_block` 确认无残留引用

