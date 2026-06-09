"""AI Shader 生成 CLI：使用 LangGraph Agent + tools 替代自建编排器。"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from langchain_core.messages import HumanMessage

from ai_pipeline.agent import build_shader_agent
from ai_pipeline.hooks.engine import GenerationHookEngine
from ai_pipeline.llm.adapter import build_llm
from ai_pipeline.tools import get_build_tools
from ai_pipeline.tools.shader_tools import extract_glsl_code
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
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=root)
    return {
        "returncode": result.returncode,
        "stdout": result.stdout.strip() if result.stdout else "",
        "stderr": result.stderr.strip() if result.stderr else "",
    }


def generate(
    req: GenerateRequest,
    root: Path,
    provider: str = "openai",
    session_id: str = "default",
    audio_array: list[float] | None = None,
    analysis_context: str = "",
) -> GenerateResult:
    # 构建 LLM + tools + agent
    llm = build_llm(provider)
    tools = get_build_tools()
    agent = build_shader_agent(llm, tools)

    # 构建用户消息
    audio_summary = ""
    if audio_array:
        from ai_pipeline.tools.audio_tools import summarize_audio

        audio_summary = summarize_audio.invoke({"audio_array": audio_array})

    user_content = (
        f"用户需求: {req.prompt}\n"
        f"style_profile: {req.style_profile}\n"
        f"音频摘要: {audio_summary}\n"
        + (f"分析上下文:\n{analysis_context}\n" if analysis_context else "")
        + "音频分析已在上一阶段完成。请根据分析上下文生成 GLSL 着色器。"
    )

    # 运行 Agent
    result = agent.invoke(
        {"messages": [HumanMessage(content=user_content)]},
        config={"recursion_limit": 50},
    )

    # 从 agent 最终消息提取 GLSL
    messages = result.get("messages", [])
    raw_output = ""
    for msg in reversed(messages):
        if hasattr(msg, "content") and msg.content:
            raw_output = str(msg.content)
            break

    code = extract_glsl_code.invoke({"text": raw_output})

    # 后处理：hooks + 保存 + 质量检查（保持与旧版一致）
    hook_engine = GenerationHookEngine(root)
    code = hook_engine.inject_header(code, req.style_profile)
    out_path = save_shader(code, root / "shaders" / "generated", "ai_generated_latest")

    hook_results = hook_engine.run_hooks(out_path)
    quality = run_quality(root, out_path)

    diagnostics = [
        f"session={session_id}",
        f"style={req.style_profile}",
        f"provider={provider}",
        f"agent_has_tool_calls={str(any(hasattr(m, 'tool_calls') and m.tool_calls for m in messages if hasattr(m, 'tool_calls')))}",
        f"生成文件: {out_path}",
    ]
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
    try:
        rc = main()
    except Exception as e:
        print(f"[generate_cli] 异常: {e}")
        import traceback
        traceback.print_exc()
        rc = 1
    os._exit(rc)
