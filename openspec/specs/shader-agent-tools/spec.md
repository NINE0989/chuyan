## ADDED Requirements

### Requirement: Audio Tools
系统 SHALL 提供音频类工具，供 Agent 分析音频数据。

#### Scenario: Summarize audio array
- **WHEN** Agent 调用 `summarize_audio(array: list[float])` 传入音频采样数组
- **THEN** SHALL 返回含 `length`、`mean`、`max`、`min`、`samples` 字段的 dict

#### Scenario: Load audio from file
- **WHEN** Agent 调用 `load_audio_from_file(path: str)` 传入 JSON/CSV 文件路径
- **THEN** SHALL 解析文件内容并返回 `list[float]`，解析失败返回空列表

### Requirement: Shader Tools
系统 SHALL 提供 Shader 编写类工具。

#### Scenario: Save shader to file
- **WHEN** Agent 调用 `save_shader_to_file(code: str, out_dir: str, name: str)`
- **THEN** SHALL 将 GLSL 写入 `{out_dir}/{name}.glsl` 并返回文件路径

#### Scenario: Inject shader header
- **WHEN** Agent 调用 `inject_shader_header(code: str, style: str)`
- **THEN** SHALL 在 GLSL 头部注入 `// AI_PIPELINE_HOOK` 和 style_profile 注释

#### Scenario: Extract GLSL from fenced code block
- **WHEN** Agent 调用 `extract_glsl_code(text: str)` 传入含 ```` ```glsl ```` 的文本
- **THEN** SHALL 返回代码块内纯 GLSL，无 fenced block 时返回原文本

#### Scenario: Ensure GLSL version directive
- **WHEN** Agent 调用 `ensure_glsl_version(code: str)` 发现 GLSL 缺少 `#version`
- **THEN** SHALL 自动在顶部添加 `#version 330 core`

### Requirement: Validation Tools
系统 SHALL 提供 Shader 验证类工具。

#### Scenario: Validate GLSL keywords
- **WHEN** Agent 调用 `validate_glsl_keywords(glsl_code: str)`
- **THEN** SHALL 检查 `mainImage`/`iResolution`/`iTime` 存在且 `gl_FragColor` 不存在，返回问题列表

#### Scenario: Run full quality check as subprocess
- **WHEN** Agent 调用 `run_full_quality_check(code: str)`
- **THEN** SHALL 子进程运行 `quality_check` 返回 `{"returncode": int, "stdout": str, "stderr": str}`

#### Scenario: Load known badcases
- **WHEN** Agent 调用 `load_known_badcases()`
- **THEN** SHALL 从 `cases/badcase/cases.json` 加载并返回已知失败模式列表

### Requirement: Skill Tools
系统 SHALL 提供技能模板查询类工具。

#### Scenario: Get skill template by name
- **WHEN** Agent 调用 `get_skill_template(name: str)` 传入 `geometry_sdf`
- **THEN** SHALL 返回对应 `SkillSpec` 的 dict，包含 template 和 post_rules

#### Scenario: List all available skills
- **WHEN** Agent 调用 `list_available_skills()`
- **THEN** SHALL 返回 `SKILL_LIBRARY` 中所有技能名称列表

#### Scenario: Build combined skill prompt
- **WHEN** Agent 调用 `build_skill_prompt(names: list[str])`
- **THEN** SHALL 拼接指定技能模板文本并返回

### Requirement: Session Tools
系统 SHALL 提供会话管理类工具。

#### Scenario: Load conversation from JSON
- **WHEN** Agent 调用 `load_conversation(session_id: str)`
- **THEN** SHALL 从 `conversations.json` 读取该 session 的消息列表

#### Scenario: Save conversation to JSON
- **WHEN** Agent 调用 `save_conversation(session_id: str, messages: list[dict])`
- **THEN** SHALL 将消息追加写入 `conversations.json`

### Requirement: Utility Tools
系统 SHALL 提供辅助类工具。

#### Scenario: Infer shader style from prompt
- **WHEN** Agent 调用 `infer_shader_style(prompt: str)` 传入含"霓虹"的用户输入
- **THEN** SHALL 返回 `"neon"`，未匹配返回 `"minimal"`

#### Scenario: Normalize audio analysis JSON
- **WHEN** Agent 调用 `normalize_audio_analysis(raw_json: str)` 传入解析失败的文本
- **THEN** SHALL 返回含 9 个兜底字段的规范化 dict

#### Scenario: Load audio array from file
- **WHEN** Agent 调用 `load_audio_array(path: str)` 传入 JSON 文件路径
- **THEN** SHALL 解析并返回 `list[float]`，解析失败返回空列表

#### Scenario: Check Python syntax
- **WHEN** Agent 调用 `run_py_syntax_check(root: str)`
- **THEN** SHALL AST 解析 `ai_pipeline/` 下所有 `.py` 文件，返回语法错误列表
