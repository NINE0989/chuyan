"""技能类工具：从 SKILL_LIBRARY 查询、列出、组合技能模板。"""
from __future__ import annotations

import json

from langchain_core.tools import tool

from ai_pipeline.skills.library import SKILL_LIBRARY, build_skill_prompt as _build_skill_prompt


@tool
def get_skill_template(name: str = "") -> str:
    """查询指定名称的技能模板详情。

    Args:
        name: 技能名称（如 geometry_sdf, audio_visualization）

    Returns:
        JSON 字符串，含 name/template/post_rules/fallbacks
    """
    spec = SKILL_LIBRARY.get(name)
    if spec is None:
        return json.dumps({"name": name, "error": "未找到该技能"})
    return json.dumps(
        {
            "name": spec.name,
            "template": spec.template,
            "post_rules": spec.post_rules,
            "fallbacks": spec.fallbacks,
        },
        ensure_ascii=False,
    )


@tool
def list_available_skills() -> str:
    """列出所有可用的技能名称。

    Returns:
        JSON 字符串，含技能名称列表
    """
    return json.dumps({"skills": list(SKILL_LIBRARY.keys())})


@tool
def build_skill_prompt(skill_names: list[str] | None = None) -> str:
    """组合指定技能模板为一段完整提示词。

    Args:
        skill_names: 技能名称列表（如 ["geometry_sdf", "audio_visualization"]）

    Returns:
        拼接后的技能提示文本
    """
    if not skill_names:
        skill_names = list(SKILL_LIBRARY.keys())
    return _build_skill_prompt(skill_names)
