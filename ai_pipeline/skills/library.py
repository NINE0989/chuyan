"""可组合的技能模板与加载器。模板内容从 skills/*.md 文件读取。"""
from __future__ import annotations

from pathlib import Path

from ai_pipeline.types import SkillSpec


def _load_skill_md(name: str) -> str:
    """从 skills/{name}.md 加载模板内容。"""
    path = Path(__file__).resolve().parent / f"{name}.md"
    if path.is_file():
        return path.read_text(encoding="utf-8-sig").strip()
    return ""


SKILL_LIBRARY: dict[str, SkillSpec] = {
    "geometry_sdf": SkillSpec(
        name="geometry_sdf",
        inputs=["geometry_targets"],
        template=_load_skill_md("geometry_sdf"),
        post_rules=["必须保留可编译 mainImage 入口"],
    ),
    "audio_visualization": SkillSpec(
        name="audio_visualization",
        inputs=["audio_profile"],
        template=_load_skill_md("audio_visualization"),
        post_rules=["必须引用 iChannel0"],
    ),
    "style_specialization": SkillSpec(
        name="style_specialization",
        inputs=["style_profile"],
        template=_load_skill_md("style_specialization"),
        post_rules=["不可删除核心 ShaderToy uniform"],
    ),
    "badcase_guard": SkillSpec(
        name="badcase_guard",
        inputs=["constraints"],
        template=_load_skill_md("badcase_guard"),
        post_rules=["输出 diagnostics 说明潜在风险"],
    ),
    "audio_analysis": SkillSpec(
        name="audio_analysis",
        inputs=["audio_array"],
        template=_load_skill_md("audio_analysis"),
        post_rules=["无法加载音频时必须停止，不得输出风格推荐"],
    ),
    "shader_coding": SkillSpec(
        name="shader_coding",
        inputs=["style_profile", "analysis_context"],
        template=_load_skill_md("shader_coding"),
        post_rules=["必须编译通过后才能保存"],
    ),
}


def build_skill_prompt(skill_names: list[str]) -> str:
    """根据技能名称拼接提示模板。"""
    chunks: list[str] = []
    for name in skill_names:
        spec = SKILL_LIBRARY.get(name)
        if spec is None:
            continue
        chunks.append(f"[{spec.name}] {spec.template}")
    return "\n".join(chunks)
