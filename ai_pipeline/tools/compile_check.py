"""GLSL 编译检查工具：创建 headless GL 上下文进行实际编译，返回结构化错误信息。

提供 compile_check_glsl tool，供 AI Agent 在生成着色器后进行编译验证和 reflection 修复。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

# 缓存 import，避免每次 tool 调用都重新加载 OpenGL DLL
_gl_imported = False
_gl_context_cache: dict = {}


def _ensure_gl() -> bool:
    """延迟导入 GL，确保只初始化一次。返回是否可用。"""
    global _gl_imported
    if _gl_imported:
        return True
    try:
        import glfw  # noqa: F811
        from OpenGL import GL as _GL  # noqa: F811
        _gl_imported = True
        return True
    except Exception:
        return False


@dataclass
class GlslCompileResult:
    """GLSL 编译结果。"""
    success: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    gl_version: str = ""
    glsl_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "errors": self.errors,
            "warnings": self.warnings,
            "gl_version": self.gl_version,
            "glsl_version": self.glsl_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def _compile_glsl_onscreen(glsl_code: str) -> GlslCompileResult:
    """使用 headless GLFW 窗口编译 GLSL 代码。

    创建不可见窗口获取 GL 上下文，编译顶点+片段着色器。
    """
    import glfw
    from OpenGL import GL

    if not glfw.init():
        return GlslCompileResult(success=False, errors=["GLFW init 失败"])

    vertex_src = "#version 330\nlayout(location=0) in vec2 aPos;layout(location=1) in vec2 aUV;out vec2 vUV;void main(){vUV=aUV;gl_Position=vec4(aPos,0.0,1.0);}"

    result = GlslCompileResult()

    try:
        # 配置窗口提示，争取桌面 GL
        glfw.window_hint(glfw.CLIENT_API, glfw.OPENGL_API)
        glfw.window_hint(glfw.CONTEXT_CREATION_API, glfw.NATIVE_CONTEXT_API)
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.VISIBLE, glfw.FALSE)

        window = glfw.create_window(64, 64, "glsl-check", None, None)
        if not window:
            result.errors.append("GLFW 窗口创建失败")
            glfw.terminate()
            return result

        glfw.make_context_current(window)

        # 获取版本信息（PyOpenGL 不同版本可能返回 str 或 bytes）
        def _to_str(s) -> str:
            if isinstance(s, bytes):
                return s.decode("utf-8", errors="replace")
            return str(s) if s else ""

        result.gl_version = _to_str(GL.glGetString(GL.GL_VERSION))
        result.glsl_version = _to_str(GL.glGetString(GL.GL_SHADING_LANGUAGE_VERSION))

        # 编译顶点着色器
        vs = GL.glCreateShader(GL.GL_VERTEX_SHADER)
        GL.glShaderSource(vs, vertex_src)
        GL.glCompileShader(vs)
        vs_ok = GL.glGetShaderiv(vs, GL.GL_COMPILE_STATUS)
        vs_log = _to_str(GL.glGetShaderInfoLog(vs)).strip()
        if not vs_ok:
            result.errors.append(f"[顶点着色器] {vs_log}")
        elif vs_log:
            result.warnings.append(f"[顶点着色器] {vs_log}")

        # 编译片段着色器
        fs = GL.glCreateShader(GL.GL_FRAGMENT_SHADER)
        GL.glShaderSource(fs, glsl_code)
        GL.glCompileShader(fs)
        fs_ok = GL.glGetShaderiv(fs, GL.GL_COMPILE_STATUS)
        fs_log = _to_str(GL.glGetShaderInfoLog(fs)).strip()
        if not fs_ok:
            result.errors.append(f"[片段着色器] {fs_log}")
        elif fs_log:
            result.warnings.append(f"[片段着色器] {fs_log}")

        # 尝试链接程序（额外检查）
        if vs_ok and fs_ok:
            prog = GL.glCreateProgram()
            GL.glAttachShader(prog, vs)
            GL.glAttachShader(prog, fs)
            GL.glLinkProgram(prog)
            link_ok = GL.glGetProgramiv(prog, GL.GL_LINK_STATUS)
            link_log = _to_str(GL.glGetProgramInfoLog(prog)).strip()
            if not link_ok:
                result.errors.append(f"[链接阶段] {link_log}")
            elif link_log:
                result.warnings.append(f"[链接阶段] {link_log}")
            GL.glDeleteProgram(prog)

        GL.glDeleteShader(vs)
        GL.glDeleteShader(fs)
        result.success = len(result.errors) == 0

    except Exception as e:
        result.errors.append(f"编译异常: {e}")
    finally:
        try:
            glfw.destroy_window(window)
        except Exception:
            pass
        glfw.terminate()

    return result


def _parse_glsl_errors(error_log: str) -> list[dict[str, Any]]:
    """解析 GLSL 编译错误日志，返回结构化错误列表。

    匹配格式: "ERROR: 0:41: 'out' : storage qualifier supported..."
    返回: [{"line": 41, "message": "...", "full": "..."}]
    """
    structured: list[dict[str, Any]] = []
    # 分割多行日志
    for line in error_log.split("\n"):
        line = line.strip()
        if not line:
            continue
        entry: dict[str, Any] = {"full": line}
        m = re.match(r"ERROR:\s*(\d+):(\d+):\s*(.+)", line)
        if m:
            entry["shader"] = int(m.group(1))
            entry["line"] = int(m.group(2))
            entry["message"] = m.group(3)
        structured.append(entry)
    return structured


def _classify_error(message: str) -> str:
    """将 GLSL 编译错误分类为修复方向。"""
    lower = message.lower()
    if "version" in lower and ("core" in lower or "invalid" in lower or "' '" in lower):
        return "version_directive"
    if "out'" in lower and "storage qualifier" in lower:
        return "out_qualifier_gles"
    if "texture'" in lower and ("overloaded" in lower or "no matching" in lower or "not found" in lower):
        return "texture_function_gles"
    if "field selection" in lower:
        return "swizzle_error"
    if "index expression" in lower and "const" in lower:
        return "non_const_index"
    if "undeclared identifier" in lower:
        return "undeclared_identifier"
    if "syntax error" in lower:
        return "syntax_error"
    if "missing entry point" in lower:
        return "missing_entry_point"
    if "reserved word" in lower:
        return "reserved_word"
    if "not allowed" in lower:
        return "scope_error"
    return "unknown"


def _generate_fix_hints(errors: list[str], code: str) -> str:
    """根据编译错误生成修复建议。"""
    if not errors:
        return "无编译错误"
    hints: list[str] = []
    parsed: list[dict[str, Any]] = []
    for e in errors:
        parsed.extend(_parse_glsl_errors(e))

    classifications: dict[str, list[dict[str, Any]]] = {}
    for p in parsed:
        cat = _classify_error(p.get("message", ""))
        classifications.setdefault(cat, []).append(p)

    for cat, items in classifications.items():
        lines = sorted({item["line"] for item in items if "line" in item})
        line_str = f" 行{lines}" if lines else ""

        if cat == "version_directive":
            hints.append(f"#version 指令无效{line_str}：请使用 `#version 330`（不带 `core`），且 `#` 后不加空格")
        elif cat == "out_qualifier_gles":
            hints.append(f"`out` 限定符不被旧版 GLSL ES 支持{line_str}：请在片元着色器顶部声明 `out vec4 FragColor;`，且确保 #version 不低于 330")
        elif cat == "texture_function_gles":
            hints.append(f"`texture()` 函数不存在{line_str}：旧版 GLSL ES 使用 `texture2D()`。请改用 `texture()` 并确保 #version 330")
        elif cat == "swizzle_error":
            hints.append(f"字段访问错误{line_str}：检查 `.x` 等 swizzle 访问的对象必须是向量类型")
        elif cat == "non_const_index":
            hints.append(f"非 const 索引{line_str}：循环索引必须使用常量或循环变量，请检查数组访问")
        elif cat == "undeclared_identifier":
            hints.append(f"未声明标识符{line_str}：请确认变量/函数名拼写正确，uniform 已声明")
        elif cat == "missing_entry_point":
            hints.append(f"缺少入口函数{line_str}：必须包含 `void mainImage(out vec4 fragColor, in vec2 fragCoord)` 和 `void main()`")
        elif cat == "syntax_error":
            hints.append(f"语法错误{line_str}：检查括号匹配、分号、类型声明")
        else:
            sample = items[0].get("message", "")[:60] if items else ""
            hints.append(f"未知错误{line_str}: {sample}...")

    return "\n".join(f"  {i + 1}. {h}" for i, h in enumerate(hints))


@tool
def compile_check_glsl(glsl_code: str = "") -> str:
    """使用真实 GL 上下文编译 GLSL 着色器，返回结构化编译结果。

    编译失败时会自动分类错误并生成修复建议，方便 Agent 进行 reflection 修复。

    Args:
        glsl_code: GLSL 片段着色器源码

    Returns:
        JSON 字符串：{success, errors[], warnings[], gl_version, glsl_version, fix_hints}
    """
    if not glsl_code.strip():
        return json.dumps({"success": False, "errors": ["空代码"], "fix_hints": "代码为空"}, ensure_ascii=False)

    result = _compile_glsl_onscreen(glsl_code)

    fix_hints = _generate_fix_hints(result.errors, glsl_code) if not result.success else ""

    return json.dumps(
        {
            "success": result.success,
            "errors": result.errors,
            "warnings": result.warnings,
            "gl_version": result.gl_version,
            "glsl_version": result.glsl_version,
            "fix_hints": fix_hints,
        },
        ensure_ascii=False,
        indent=2,
    )


@tool
def compile_check_glsl_file(shader_path: str = "") -> str:
    """从文件路径加载 GLSL 并编译检查。

    Args:
        shader_path: .glsl 文件的路径

    Returns:
        与 compile_check_glsl 相同格式的 JSON
    """
    p = Path(shader_path)
    if not p.is_file():
        return json.dumps({"success": False, "errors": [f"文件不存在: {shader_path}"]}, ensure_ascii=False)
    code = p.read_text(encoding="utf-8", errors="replace")
    return compile_check_glsl.invoke({"glsl_code": code})


# ---- 命令行入口 ----
def main() -> int:
    """CLI: python -m ai_pipeline.tools.compile_check [shader_path]"""
    if len(sys.argv) > 1:
        path = sys.argv[1]
        print(compile_check_glsl_file.invoke({"shader_path": path}))
    else:
        # 检查 stdin
        code = sys.stdin.read() if not sys.stdin.isatty() else ""
        print(compile_check_glsl.invoke({"glsl_code": code}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
