"""Web 端 AI 服务：Plan 模式（对话）和 Build 模式（Shader 生成）。"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, Iterator, List

from ai_pipeline.generate_cli import generate as pipeline_generate
from ai_pipeline.types import GenerateRequest


class AIService:
    """兼容旧接口的 AI 服务封装。"""

    def __init__(self, model: str = "", timeout: int = 120):
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.timeout = timeout
        self.history: List[Dict[str, str]] = []

        # provider 策略：有 API key（环境变量或 settings.json）则 openai，否则 mock
        self.provider = os.getenv("AI_PROVIDER", "").strip().lower()
        if self.provider not in {"openai", "mock"}:
            try:
                from WebEngine.settings import Settings
                s = Settings()
                has_key = bool(s.api_key)
            except Exception:
                has_key = bool(os.getenv("OPENAI_API_KEY"))
            self.provider = "openai" if has_key else "mock"

        self._session_seed = hashlib.md5(str(time.time()).encode("utf-8")).hexdigest()[:10]
        self.session_id = f"web_{self._session_seed}"

        # 可选音频数组输入文件（json/csv）
        self.audio_array_file = os.getenv("AI_AUDIO_ARRAY_FILE", "").strip()

    def _load_audio_array(self) -> list[float]:
        if not self.audio_array_file:
            return []
        p = Path(self.audio_array_file)
        if not p.is_file():
            return []
        text = p.read_text(encoding="utf-8-sig", errors="ignore").strip()
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

    def _infer_style(self, prompt: str) -> str:
        low = prompt.lower()
        if "neon" in low or "霓虹" in prompt:
            return "neon"
        if "ink" in low or "水墨" in prompt:
            return "ink"
        if "glitch" in low or "故障" in prompt:
            return "glitch"
        return "minimal"

    def generate(self, prompt: str, adjust: bool = False, temperature: float = 0.7, top_p: float = 0.9, mode: str = "plan") -> str:
        """根据 mode 分发：plan → 对话，build → Shader Agent 生成。"""
        del temperature, top_p

        if not adjust:
            self._session_seed = hashlib.md5(str(time.time()).encode("utf-8")).hexdigest()[:10]
            self.session_id = f"web_{self._session_seed}"
            self.history.clear()

        if mode == "build":
            return "Build 模式已升级为两阶段流程。请先调用 analyze 端点进行需求分析，确认后再调用 build 端点生成代码。"

        return self._plan_chat(prompt)

    def _find_music_files(self, prompt: str) -> list[Path]:
        """从 prompt 中提取引用的音乐文件路径。"""
        root = Path(__file__).resolve().parent.parent
        music_dir = root / "MusicLib"
        found: list[Path] = []
        # 匹配 /文件名.后缀 或 MusicLib/文件名.后缀
        for m in re.finditer(r'(?:/|MusicLib[/\\])?([\w\u4e00-\u9fff\s_-]+\.(?:mp3|wav|flac|ogg|aac|m4a|wma|json|csv|txt))', prompt, re.IGNORECASE):
            name = m.group(1).strip()
            for f in music_dir.rglob(name):
                if f.is_file():
                    found.append(f)
                    break
            else:
                # try MusicLib root
                f = music_dir / name
                if f.is_file():
                    found.append(f)
        return found

    def _load_audio_summary(self, filepath: Path) -> str:
        """加载音频文件并返回摘要信息。"""
        try:
            ext = filepath.suffix.lower()
            if ext in (".json", ".csv", ".txt"):
                text = filepath.read_text(encoding="utf-8-sig", errors="ignore").strip()
                try:
                    data = json.loads(text)
                    if isinstance(data, list):
                        values = [float(x) for x in data]
                except Exception:
                    values = []
                    for token in text.replace("\n", ",").split(","):
                        try: values.append(float(token.strip()))
                        except ValueError: continue
                if values:
                    import numpy as np
                    arr = np.array(values, dtype=np.float32)
                    peak = float(np.max(np.abs(arr)))
                    return (
                        f"音频文件: {filepath.name}\n"
                        f"采样点数: {len(values)}, 峰值: {peak:.3f}\n"
                        f"数据可用于 iChannel0（时域）和 iChannel1（FFT 频谱）"
                    )
                return f"音频文件: {filepath.name}（无法解析采样数据）"
            elif ext in (".wav", ".mp3", ".flac", ".ogg"):
                return f"音频文件: {filepath.name}（二进制音频，运行时由 PyAudio 实时采集到 iChannel0/1）"
            return f"音频文件: {filepath.name}"
        except Exception:
            return f"音频文件: {filepath.name}（加载失败）"

    def analyze(self, prompt: str) -> str:
        """Analyze 阶段：调用 LangGraph Agent（仅音频+技能 tool）分析音频并输出结构化报告。

        自动检测 prompt 中的音乐文件引用。
        """
        music_files = self._find_music_files(prompt)
        audio_array: list[float] = []
        for mf in music_files[:2]:
            arr = self._load_audio_array_from_file(mf)
            if arr:
                audio_array.extend(arr)
        if audio_array:
            os.environ["AI_AUDIO_ARRAY_FILE"] = str(music_files[0].resolve()) if music_files else ""

        try:
            from ai_pipeline.agent import build_shader_agent
            from ai_pipeline.llm.adapter import build_llm
            from ai_pipeline.tools.audio_tools import summarize_audio, load_audio_from_file, list_music_files, find_music_by_name
            from ai_pipeline.tools.skill_tools import get_skill_template
            from ai_pipeline.tools.utility_tools import infer_shader_style
            from langchain_core.messages import HumanMessage

            analyze_tools = [
                summarize_audio, load_audio_from_file, list_music_files, find_music_by_name,
                infer_shader_style, get_skill_template,
            ]
            analyze_sys_prompt = "必须调用 get_skill_template 加载分析流程。有音频数据时必须调用 summarize_audio。"
            llm = build_llm(self.provider)

            # 预加载 skill template 注入 user_content，确保即使 tool calling 失败也有完整指令
            from ai_pipeline.skills.library import SKILL_LIBRARY
            skill_spec = SKILL_LIBRARY.get("audio_analysis")
            skill_text = skill_spec.template if skill_spec else ""

            analyze_agent = build_shader_agent(llm, analyze_tools, system_prompt=analyze_sys_prompt, max_iterations=6)

            file_refs = "\n".join(f"- {f.name}" for f in music_files) if music_files else ""
            user_content = (
                f"用户需求: {prompt}"
                + (f"\n\n音频文件: {file_refs}" if file_refs else "\n\n未引用音频文件，请告知用户从音乐库选择文件。")
                + (f"\n\n## 分析流程（必须遵循）\n\n{skill_text}" if skill_text else "")
            )

            result = analyze_agent.invoke(
                {"messages": [HumanMessage(content=user_content)]},
                config={"recursion_limit": 10},
            )
            messages = result.get("messages", [])
            for msg in reversed(messages):
                if hasattr(msg, "content") and msg.content:
                    return str(msg.content)
            return "分析未能完成，请重试。"
        except Exception:
            return self._analyze_fallback(prompt, music_files)

    def _analyze_fallback(self, prompt: str, music_files: list[Path]) -> str:
        """分析降级方案：使用 skill 模板 + 纯 LLM。"""
        audio_summary = ""
        for mf in music_files:
            info = self._load_audio_summary(mf)
            if info:
                audio_summary += info + "\n"
        audio_block = f"\n\n音频数据:\n{audio_summary}" if audio_summary else ""

        from ai_pipeline.skills.library import SKILL_LIBRARY
        skill_spec = SKILL_LIBRARY.get("audio_analysis")
        skill_text = skill_spec.template if skill_spec else "请先输出音频元数据（时长、峰值、RMS、节奏型、BPM），再推荐风格。"

        try:
            from ai_pipeline.llm.adapter import build_llm
            from langchain_core.messages import HumanMessage
            llm = build_llm(self.provider)
            msg = HumanMessage(content=(
                f"用户需求: {prompt}{audio_block}\n\n"
                f"## 分析流程（必须严格遵循）\n\n{skill_text}"
            ))
            resp = llm.invoke([msg])
            return str(resp.content) if hasattr(resp, "content") else str(resp)
        except Exception:
            return f"分析失败，请重试。"

    def _load_audio_array_from_file(self, filepath: Path) -> list[float]:
        """从文件加载音频采样数组（复用 audio_tool 逻辑）。"""
        try:
            from ai_pipeline.tools.audio_tools import load_audio_from_file
            result = json.loads(load_audio_from_file.invoke({"path": str(filepath)}))
            return result.get("audio_array", [])
        except Exception:
            return []

    def _build_shader(self, prompt: str, adjust: bool, analysis_context: str = "") -> str:
        """Build 阶段：走 LangGraph Agent 生成 GLSL，可选传入分析上下文。"""
        req = GenerateRequest(
            prompt=prompt,
            audio_profile="balanced",
            geometry_targets=["circle", "line", "polygon"],
            style_profile=self._infer_style(prompt),
            constraints={"target_glsl": "330", "source": "web_ai_service"},
            seed=None,
        )

        root = Path(__file__).resolve().parent.parent
        result = pipeline_generate(
            req=req,
            root=root,
            provider=self.provider,
            session_id=self.session_id,
            audio_array=self._load_audio_array(),
            analysis_context=analysis_context,
        )

        code = result.glsl_code
        self.history.append({"role": "user", "content": prompt})
        self.history.append({"role": "assistant", "content": code})
        return code

    def _plan_chat(self, prompt: str) -> str:
        """Plan 模式：检测音频引用 → 分析；否则纯对话。"""
        # 检测音频引用 → 在 Plan 模式也走分析
        music_files = self._find_music_files(prompt)
        if music_files:
            return self.analyze(prompt)

        try:
            from ai_pipeline.llm.adapter import build_llm
            from langchain_core.messages import HumanMessage
            llm = build_llm(self.provider)
            msg = HumanMessage(content=(
                "你是 MusicShader AI 助手，Plan 模式。简短回复（2-4 句），不生成代码。\n\n"
                f"用户: {prompt}"
            ))
            resp = llm.invoke([msg])
            return str(resp.content) if hasattr(resp, "content") else str(resp)
        except Exception:
            return f"收到: '{prompt}'\n\n需要生成 Shader？按 Shift+Tab 切换到 Build 模式。"

    def stream_generate(self, prompt: str, adjust: bool = False, temperature: float = 0.7, top_p: float = 0.9) -> Iterator[str]:
        full = self.generate(prompt, adjust=adjust, temperature=temperature, top_p=top_p)
        chunk_size = max(64, len(full) // 10)
        for i in range(0, len(full), chunk_size):
            yield full[i : i + chunk_size]


__all__ = ["AIService"]
