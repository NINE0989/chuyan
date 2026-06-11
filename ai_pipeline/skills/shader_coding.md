# Shader Coding Skill

根据分析上下文生成可编译、可运行的 GLSL 着色器。

## 铁律

1. `compile_check_glsl` 验证 → 失败则根据 `fix_hints` 修正 → 重新验证，最多 3 轮
2. 3 轮仍未通过 → 输出「❌ 编译未能通过：[最后一次错误信息]」→ 停止，不保存
3. 不得输出未经验证的代码给用户

## 编码规范

### 基础约束
- `#version 330`
- 声明 uniform：`iResolution` (vec3)、`iTime` (float)、`iChannel0` (sampler2D)
- 双入口：`void mainImage(out vec4 fragColor, in vec2 fragCoord)` + `void main()`
- 用 `out vec4 FragColor;` 输出，**禁止使用** `gl_FragColor`
- 至少一处 `texture(iChannel0, ...)` 音频采样

### 频段映射
- 低频 → 主形体尺度、位移、节奏
- 中频 → 纹理扰动、细节密度、几何复杂度
- 高频 → 高光、闪烁、辉光、边缘增强

## 工作流

1. 调用 `get_skill_template` 取对应风格的 skill（如 geometry_sdf、style_specialization）
2. 根据分析上下文 + 风格 skill 生成 GLSL 代码
3. 调用 `compile_check_glsl` 编译验证
4. 通过 → 调用 `save_shader_to_file` 保存
5. 失败 → 根据 `fix_hints` 修正 → 回到步骤 3
