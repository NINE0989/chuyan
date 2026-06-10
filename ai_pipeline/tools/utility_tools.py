"""辅助类工具：风格推断、音频分析规范化、语法检查。"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from langchain_core.tools import tool


@tool
def infer_shader_style(prompt: str = "") -> str:
    """根据用户提示词推断着色器风格。

    Args:
        prompt: 用户输入描述

    Returns:
        风格标签：neon / ink / glitch / minimal
    """
    if not prompt:
        return "minimal"
    low = prompt.lower()
    if "neon" in low or "霓虹" in prompt:
        return "neon"
    if "ink" in low or "水墨" in prompt:
        return "ink"
    if "glitch" in low or "故障" in prompt:
        return "glitch"
    return "minimal"


@tool
def normalize_audio_analysis(raw_json: str = "") -> str:
    """规范化音频理解 JSON 输出，填充缺失字段的兜底值。

    Args:
        raw_json: 原始 JSON 字符串（可能不完整）

    Returns:
        规范化后的 JSON 字符串，含 9 个必要字段
    """
    try:
        data = json.loads(raw_json)
    except Exception:
        data = {}

    normalized = {
        "music_style": str(data.get("music_style", "unknown")),
        "energy_curve": str(data.get("energy_curve", "unknown")),
        "band_mapping": data.get("band_mapping", {"low": "低频控制主形体", "mid": "中频控制纹理", "high": "高频控制高光"}),
        "visual_directions": data.get("visual_directions", ["径向频谱环", "频带脉冲"]),
        "shader_plan": data.get("shader_plan", ["低频控制半径", "中频控制扰动", "高频控制闪烁"]),
        "goodcase_checks": data.get("goodcase_checks", ["包含 mainImage", "包含 iChannel0 采样"]),
        "badcase_risks": data.get("badcase_risks", ["uniform 缺失", "采样越界"]),
        "hook_hints": data.get("hook_hints", ["避免 gl_FragColor", "保证 iTime/iResolution 存在"]),
        "confidence": float(data.get("confidence", 0.5)),
    }

    if not isinstance(normalized["band_mapping"], dict):
        normalized["band_mapping"] = {"low": "低频控制主形体", "mid": "中频控制纹理", "high": "高频控制高光"}
    for k in ("low", "mid", "high"):
        normalized["band_mapping"].setdefault(k, "待补充")

    for key in ("visual_directions", "shader_plan", "goodcase_checks", "badcase_risks", "hook_hints"):
        if not isinstance(normalized[key], list) or len(normalized[key]) == 0:
            normalized[key] = ["待补充"]

    return json.dumps(normalized, ensure_ascii=False)


@tool
def load_audio_array(path: str = "") -> str:
    """从文件加载音频采样数组。

    Args:
        path: JSON 或 CSV 文件路径

    Returns:
        JSON 字符串，含 audio_array 字段
    """
    if not path:
        return json.dumps({"audio_array": []})
    p = Path(path)
    if not p.is_file():
        # 尝试在 MusicLib/ 中查找
        try:
            from ai_pipeline.tools.audio_tools import _get_music_dir
            music_dir = _get_music_dir()
            for c in music_dir.rglob(p.name):
                if c.is_file():
                    p = c
                    break
            else:
                return json.dumps({"audio_array": []})
        except Exception:
            return json.dumps({"audio_array": []})

    text = p.read_text(encoding="utf-8-sig", errors="ignore").strip()
    data = []

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            data = [float(x) for x in parsed]
    except Exception:
        for token in text.replace("\n", ",").split(","):
            t = token.strip()
            if not t:
                continue
            try:
                data.append(float(t))
            except Exception:
                continue

    return json.dumps({"audio_array": data})


@tool
def run_py_syntax_check(root_dir: str = "") -> str:
    """对 ai_pipeline/ 下所有 Python 文件做语法检查。

    Args:
        root_dir: 项目根目录路径

    Returns:
        问题列表文本。无问题时返回 "OK"
    """
    if not root_dir:
        return "空路径"
    root = Path(root_dir)
    py_files = list((root / "ai_pipeline").rglob("*.py"))
    issues = []
    for py_file in py_files:
        try:
            source = py_file.read_text(encoding="utf-8-sig")
            ast.parse(source, filename=str(py_file))
        except SyntaxError as e:
            issues.append(f"语法错误: {py_file}:{e.lineno} {e.msg}")
        except Exception as e:
            issues.append(f"读取失败: {py_file} {e}")
    return "\n".join(issues) if issues else "OK"
