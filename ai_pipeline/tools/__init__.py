"""AI 管线工具集：18 个 @tool 函数，分 6 类。

通过 get_all_tools() 获取全部 tool，供 LangGraph Agent 绑定使用。
"""
from __future__ import annotations

from pathlib import Path

from .audio_tools import find_music_by_name, list_music_files, load_audio_from_file, summarize_audio
from .session_tools import load_conversation, save_conversation
from .shader_tools import ensure_glsl_version, extract_glsl_code, inject_shader_header, save_shader_to_file
from .skill_tools import build_skill_prompt, get_skill_template, list_available_skills
from .utility_tools import infer_shader_style, load_audio_array, normalize_audio_analysis, run_py_syntax_check
from .validation_tools import load_known_badcases, run_full_quality_check, validate_glsl_keywords


def get_all_tools() -> list:
    """返回全部 18 个 @tool 函数列表，供 Agent 绑定。"""
    return [
        # 音频类 (4)
        summarize_audio,
        load_audio_from_file,
        list_music_files,
        find_music_by_name,
        # Shader 编写类 (4)
        extract_glsl_code,
        save_shader_to_file,
        inject_shader_header,
        ensure_glsl_version,
        # 验证类 (3)
        validate_glsl_keywords,
        run_full_quality_check,
        load_known_badcases,
        # 技能类 (3)
        get_skill_template,
        list_available_skills,
        build_skill_prompt,
        # 会话类 (2)
        load_conversation,
        save_conversation,
        # 辅助类 (4)
        infer_shader_style,
        normalize_audio_analysis,
        load_audio_array,
        run_py_syntax_check,
    ]


__all__ = [
    "get_all_tools",
    "summarize_audio",
    "load_audio_from_file",
    "list_music_files",
    "find_music_by_name",
    "extract_glsl_code",
    "save_shader_to_file",
    "inject_shader_header",
    "ensure_glsl_version",
    "validate_glsl_keywords",
    "run_full_quality_check",
    "load_known_badcases",
    "get_skill_template",
    "list_available_skills",
    "build_skill_prompt",
    "load_conversation",
    "save_conversation",
    "infer_shader_style",
    "normalize_audio_analysis",
    "load_audio_array",
    "run_py_syntax_check",
]
