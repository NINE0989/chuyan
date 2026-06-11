"""AI 管线 hooks：生成阶段注入与执行。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .quality_check import run_glsl_checks


@dataclass(slots=True)
class HookResult:
    name: str
    ok: bool
    messages: list[str]


class GenerationHookEngine:
    """在 AI 生成层执行的 hooks 引擎，与 Git 无关。"""

    def __init__(self, root: Path):
        self.root = root

    def inject_header(self, glsl_code: str, style_profile: str) -> str:
        """在生成内容中注入元信息注释。

        若已有 #version 指令，注释插在其后；否则插在最前（但 GLSL 要求 #version 必须在首行）。
        """
        header = (
            "// AI_PIPELINE_HOOK\n"
            f"// style_profile: {style_profile}\n"
            "// generated_with: langgraph_agent\n"
        )
        # 若存在 #version，将 header 插在 #version 行之后
        m = re.search(r'^(#version[^\n]*\n)', glsl_code, re.MULTILINE)
        if m:
            return m.group(1) + header + glsl_code[m.end():]
        return header + glsl_code

    def run_hooks(self, shader_path: Path) -> list[HookResult]:
        """执行生成后 hooks。"""
        issues = run_glsl_checks([shader_path])
        if issues:
            return [HookResult(name="glsl_quality", ok=False, messages=issues)]
        return [HookResult(name="glsl_quality", ok=True, messages=["GLSL 检查通过"]) ]
