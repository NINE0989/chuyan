"""验证类工具：GLSL 关键词检查、完整质量检查、badcase 加载。"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from langchain_core.tools import tool


@tool
def validate_glsl_keywords(glsl_code: str = "") -> str:
    """验证 GLSL 代码是否包含必需符号且不含禁用符号。

    必需：mainImage, iResolution, iTime
    禁止：gl_FragColor

    Args:
        glsl_code: GLSL 源码字符串

    Returns:
        问题描述字符串。无问题时返回 "OK"
    """
    if not glsl_code:
        return "空代码"

    issues = []
    for token in ["mainImage", "iResolution", "iTime"]:
        if token not in glsl_code:
            issues.append(f"缺少关键符号: {token}")

    if re.search(r"\bgl_FragColor\b", glsl_code):
        issues.append("使用了过时变量 gl_FragColor，请使用 out vec4")

    return "\n".join(issues) if issues else "OK"


@tool
def run_full_quality_check(glsl_code: str = "") -> str:
    """以子进程方式运行完整 AI 管线质量检查。

    将代码写入临时文件后运行 `python -m ai_pipeline.hooks.quality_check`。

    Args:
        glsl_code: GLSL 源码字符串

    Returns:
        JSON 字符串，含 returncode/stdout/stderr
    """
    if not glsl_code:
        return json.dumps({"returncode": 1, "stdout": "", "stderr": "空代码"})

    root = Path(__file__).resolve().parent.parent.parent
    temp_dir = root / "shaders" / "generated"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / "ai_generated_latest.glsl"
    temp_path.write_text(glsl_code, encoding="utf-8")

    cmd = [
        sys.executable, "-m", "ai_pipeline.hooks.quality_check",
        "--root", str(root),
        "--target-glsl", str(temp_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=root)

    return json.dumps(
        {"returncode": result.returncode, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()},
        ensure_ascii=False,
    )


@tool
def load_known_badcases() -> str:
    """加载已知的着色器生成失败模式（badcase）。

    从 cases/badcase/cases.json 读取。

    Returns:
        JSON 字符串，含已知失败模式列表
    """
    root = Path(__file__).resolve().parent.parent.parent
    path = root / "ai_pipeline" / "cases" / "badcase" / "cases.json"
    if not path.is_file():
        return json.dumps([])
    return path.read_text(encoding="utf-8-sig")
