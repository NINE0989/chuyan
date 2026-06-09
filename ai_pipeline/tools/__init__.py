"""AI 管线工具集：18 个 @tool 函数 + 2 个编译检查工具，分 7 类。

通过 get_all_tools() 获取全部 tool，供 LangGraph Agent 绑定使用。
"""
from __future__ import annotations

from pathlib import Path

from .audio_tools import find_music_by_name, list_music_files, load_audio_from_file, summarize_audio
from .compile_check import compile_check_glsl, compile_check_glsl_file
from .session_tools import load_conversation, save_conversation
from .shader_tools import ensure_glsl_version, extract_glsl_code, inject_shader_header, save_shader_to_file
from .skill_tools import build_skill_prompt, get_skill_template, list_available_skills
from .utility_tools import infer_shader_style, load_audio_array, normalize_audio_analysis, run_py_syntax_check
from .validation_tools import load_known_badcases, run_full_quality_check, validate_glsl_keywords


def get_all_tools() -> list:
    """返回全部 20 个 @tool 函数列表，供 Agent 绑定。"""
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
        # 编译检查类 (2)
        compile_check_glsl,
        compile_check_glsl_file,
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


def get_build_tools() -> list:
    """返回生成阶段专用 tool 列表（排除音频/音乐和分析辅助工具）。"""
    return [
        # Shader 编写类 (4)
        extract_glsl_code,
        save_shader_to_file,
        inject_shader_header,
        ensure_glsl_version,
        # 验证类 (3)
        validate_glsl_keywords,
        run_full_quality_check,
        load_known_badcases,
        # 编译检查类 (2)
        compile_check_glsl,
        compile_check_glsl_file,
        # 技能类 (3)
        get_skill_template,
        list_available_skills,
        build_skill_prompt,
        # 会话类 (2)
        load_conversation,
        save_conversation,
        # 辅助类 (2)
        infer_shader_style,
        load_audio_array,
    ]


__all__ = [
    "get_all_tools",
    "get_build_tools",
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
    "compile_check_glsl",
    "compile_check_glsl_file",
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
