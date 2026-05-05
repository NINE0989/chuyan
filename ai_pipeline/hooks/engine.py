"""AI 管线 hooks：生成阶段注入与执行。"""
from __future__ import annotations

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
        """在生成内容头部注入元信息注释。"""
        header = (
            "// AI_PIPELINE_HOOK\n"
            f"// style_profile: {style_profile}\n"
            "// generated_with: mock_mcp_adapter\n"
        )
        return header + glsl_code

    def run_hooks(self, shader_path: Path) -> list[HookResult]:
        """执行生成后 hooks。"""
        issues = run_glsl_checks([shader_path])
        if issues:
            return [HookResult(name="glsl_quality", ok=False, messages=issues)]
        return [HookResult(name="glsl_quality", ok=True, messages=["GLSL 检查通过"]) ]
