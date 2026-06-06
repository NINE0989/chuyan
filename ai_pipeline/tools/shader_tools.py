"""Shader 编写类工具：代码提取、保存、头注入、版本检测。"""
from __future__ import annotations

import re
from pathlib import Path

from langchain_core.tools import tool


@tool
def extract_glsl_code(text: str = "") -> str:
    """从文本中提取 GLSL 代码。

    优先提取 ```glsl 代码块；若无，则找到 #version 行开始截取到文本末尾。

    Args:
        text: 可能包含 GLSL 代码块的文本

    Returns:
        纯 GLSL 代码字符串
    """
    if not text:
        return ""
    m = re.search(r"(?is)```\s*(?:glsl)?\s*\n?(.*?)\n?```", text)
    if m:
        return m.group(1).strip()
    # 无 fence：找到 #version 行截取
    vm = re.search(r"(^|\n)(#version\s+\d+.*)", text)
    if vm:
        return text[vm.start(2):].strip()
    return text.strip()


@tool
def save_shader_to_file(code: str = "", out_dir: str = "", name: str = "ai_generated") -> str:
    """将 GLSL 代码保存到 .glsl 文件。

    Args:
        code: GLSL 源码
        out_dir: 输出目录路径
        name: 文件名（不含 .glsl 后缀）

    Returns:
        保存后的文件路径
    """
    if not code or not out_dir:
        return "错误: code 和 out_dir 不能为空"
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)
    out_path = p / f"{name}.glsl"
    out_path.write_text(code, encoding="utf-8")
    return str(out_path)


@tool
def inject_shader_header(code: str = "", style: str = "minimal") -> str:
    """在 GLSL 代码头部注入 AI 管线元信息注释。

    Args:
        code: GLSL 源码
        style: 风格标签（neon/ink/glitch/minimal）

    Returns:
        带头部注释的 GLSL 代码
    """
    header = (
        "// AI_PIPELINE_HOOK\n"
        f"// style_profile: {style}\n"
        "// generated_with: langgraph_agent\n"
    )
    return header + code


@tool
def ensure_glsl_version(code: str = "") -> str:
    """确保 GLSL 代码以 #version 指令开头。

    如果代码不以 #version 开头，自动添加 `#version 330`。

    Args:
        code: GLSL 源码

    Returns:
        带版本指令的 GLSL 代码
    """
    if not code.strip():
        return "#version 330\n"
    stripped = code.lstrip()
    if stripped.startswith("#version"):
        return code
    return "#version 330\n" + code
