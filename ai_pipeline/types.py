"""AI 生成管线核心数据类型定义。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class GenerateRequest:
    """描述一次 Shader 生成请求。"""

    prompt: str
    audio_profile: str = "balanced"
    geometry_targets: list[str] = field(default_factory=list)
    style_profile: str = "minimal"
    constraints: dict[str, Any] = field(default_factory=dict)
    seed: int | None = None


@dataclass(slots=True)
class GenerateResult:
    """描述一次 Shader 生成结果。"""

    glsl_code: str
    includes: list[str] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    case_tags: list[str] = field(default_factory=list)
    quality_report: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SkillSpec:
    """技能模板定义。"""

    name: str
    inputs: list[str]
    template: str
    post_rules: list[str] = field(default_factory=list)
    fallbacks: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CaseSpec:
    """案例定义。"""

    id: str
    type: str
    intent: str
    input: dict[str, Any]
    expected_signals: list[str]
    known_risks: list[str] = field(default_factory=list)
