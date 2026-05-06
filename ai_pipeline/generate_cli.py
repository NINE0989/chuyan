"""AI Shader 生成 CLI：支持多 Agent 持续对话流程。"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from ai_pipeline.hooks.engine import GenerationHookEngine
from ai_pipeline.mcp import build_mcp_adapter
from ai_pipeline.orchestrator import MultiAgentOrchestrator
from ai_pipeline.skills.library import build_skill_prompt
from ai_pipeline.types import GenerateRequest, GenerateResult


def save_shader(code: str, out_dir: Path, name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{name}.glsl"
    out_path.write_text(code, encoding="utf-8")
    return out_path


def run_quality(root: Path, target_glsl: Path) -> dict[str, str | int]:
    cmd = [
        sys.executable,
        "-m",
        "ai_pipeline.hooks.quality_check",
        "--root",
        str(root),
        "--target-glsl",
        str(target_glsl),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return {
        "returncode": result.returncode,
        "stdout": result.stdout.strip() if result.stdout else "",
        "stderr": result.stderr.strip() if result.stderr else "",
    }


def _extract_glsl(text: str) -> str:
    import re

    m = re.search(r"(?is)```\s*(?:glsl)?\s*\n?(.*?)\n?```", text)
    return m.group(1).strip() if m else text.strip()


def generate(
    req: GenerateRequest,
    root: Path,
    provider: str = "openai",
    session_id: str = "default",
    audio_array: list[float] | None = None,
) -> GenerateResult:
    prompt_ctx = build_skill_prompt(
        ["geometry_sdf", "audio_visualization", "style_specialization", "badcase_guard"]
    )

    adapter = build_mcp_adapter(provider)
    orchestrator = MultiAgentOrchestrator(root, adapter)

    merged_prompt = req.prompt + "\n" + prompt_ctx
    raw_output, multi_diag = orchestrator.run(
        session_id=session_id,
        user_prompt=merged_prompt,
        audio_array=audio_array or [],
        style_profile=req.style_profile,
    )

    code = _extract_glsl(raw_output)

    hook_engine = GenerationHookEngine(root)
    code = hook_engine.inject_header(code, req.style_profile)
    out_path = save_shader(code, root / "shaders" / "generated", "ai_generated_latest")

    hook_results = hook_engine.run_hooks(out_path)
    quality = run_quality(root, out_path)

    diagnostics = list(multi_diag)
    diagnostics.append(f"生成文件: {out_path}")
    diagnostics.extend([f"hook:{r.name}:{'ok' if r.ok else 'fail'}" for r in hook_results])

    tags = ["goodcase:baseline", f"style:{req.style_profile}", f"session:{session_id}"]
    return GenerateResult(
        glsl_code=code,
        includes=[],
        diagnostics=diagnostics,
        case_tags=tags,
        quality_report=quality,
    )


def _load_audio_array(audio_path: str | None) -> list[float]:
    if not audio_path:
        return []
    p = Path(audio_path)
    if not p.is_file():
        return []
    text = p.read_text(encoding="utf-8-sig").strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [float(x) for x in data]
    except Exception:
        pass
    values: list[float] = []
    for token in text.replace("\n", ",").split(","):
        t = token.strip()
        if not t:
            continue
        try:
            values.append(float(t))
        except Exception:
            continue
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description="AI 音频 Shader 生成工具")
    parser.add_argument("--prompt", required=True, help="生成提示")
    parser.add_argument("--audio-profile", default="balanced")
    parser.add_argument("--style", default="minimal")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--provider", default="openai", choices=["openai", "mock"])
    parser.add_argument("--session-id", default="default")
    parser.add_argument("--audio-array-file", default=None, help="numpy音频数组导出的json/csv文本文件")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    req = GenerateRequest(
        prompt=args.prompt,
        audio_profile=args.audio_profile,
        geometry_targets=["circle", "line", "polygon"],
        style_profile=args.style,
        constraints={"target_glsl": "330"},
        seed=args.seed,
    )
    audio_array = _load_audio_array(args.audio_array_file)
    result = generate(
        req,
        root,
        provider=args.provider,
        session_id=args.session_id,
        audio_array=audio_array,
    )
    print(
        json.dumps(
            {
                "diagnostics": result.diagnostics,
                "case_tags": result.case_tags,
                "quality_report": result.quality_report,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
