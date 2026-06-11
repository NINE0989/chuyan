"""质量检查入口：以 AI 生成链路为核心。"""
from __future__ import annotations

import argparse
import ast
import re
import os
import sys
from pathlib import Path


def run_py_syntax(paths: list[Path]) -> list[str]:
    issues: list[str] = []
    for path in paths:
        try:
            source = path.read_text(encoding="utf-8-sig")
            ast.parse(source, filename=str(path))
        except SyntaxError as e:
            issues.append(f"Python 语法错误: {path}:{e.lineno}:{e.offset} {e.msg}")
        except Exception as e:  # noqa: BLE001
            issues.append(f"Python 读取失败: {path} {e}")
    return issues


def run_glsl_checks(paths: list[Path]) -> list[str]:
    issues: list[str] = []
    required = ["mainImage", "iResolution", "iTime"]
    for path in paths:
        if not path.is_file():
            issues.append(f"GLSL 文件不存在: {path}")
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in required:
            if token not in text:
                issues.append(f"GLSL 缺少关键符号 {token}: {path}")
        if re.search(r"\bgl_FragColor\b", text):
            issues.append(f"GLSL 使用过时变量 gl_FragColor: {path}")
    return issues


def collect_py_files(root: Path) -> list[Path]:
    return [p for p in (root / "ai_pipeline").rglob("*.py")]


def collect_glsl_files(root: Path, target: str | None) -> list[Path]:
    if target:
        return [Path(target).resolve()]
    default_target = root / "shaders" / "generated" / "ai_generated_latest.glsl"
    return [default_target] if default_target.is_file() else []


def main() -> int:
    parser = argparse.ArgumentParser(description="AI 管线质量检查工具")
    parser.add_argument("--root", default=".", help="项目根目录")
    parser.add_argument("--target-glsl", default=None, help="仅检查指定生成文件")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    py_files = collect_py_files(root)
    glsl_files = collect_glsl_files(root, args.target_glsl)

    issues = []
    issues.extend(run_py_syntax(py_files))
    issues.extend(run_glsl_checks(glsl_files))

    if issues:
        print("[ai-hooks] 检查失败:")
        for item in issues:
            print(f"- {item}")
        return 1

    print("[ai-hooks] 检查通过")
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    except Exception as e:
        print(f"[ai-hooks] 质量检查异常: {e}")
        import traceback
        traceback.print_exc()
        rc = 1
    os._exit(rc)
