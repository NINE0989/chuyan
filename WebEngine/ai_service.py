"""Web 端 AI 服务：接入 ai_pipeline 多 Agent 生成链路。"""
from __future__ import annotations

import hashlib
import json
import os
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

        # provider 策略：有 OPENAI_API_KEY 则默认 openai，否则 mock
        self.provider = os.getenv("AI_PROVIDER", "").strip().lower()
        if self.provider not in {"openai", "mock"}:
            self.provider = "openai" if os.getenv("OPENAI_API_KEY") else "mock"

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

    def _extract_code(self, text: str) -> str:
        import re

        m = re.search(r"(?is)```\s*(?:glsl)?\s*\n?(.*?)\n?```", text)
        return m.group(1).strip() if m else text.strip()

    def generate(self, prompt: str, adjust: bool = False, temperature: float = 0.7, top_p: float = 0.9) -> str:
        del temperature, top_p  # 当前由 ai_pipeline 内部策略控制

        if not adjust:
            # 新会话：重置 session，避免串话
            self._session_seed = hashlib.md5(str(time.time()).encode("utf-8")).hexdigest()[:10]
            self.session_id = f"web_{self._session_seed}"
            self.history.clear()

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
        )

        code = self._extract_code(result.glsl_code)
        self.history.append({"role": "user", "content": prompt})
        self.history.append({"role": "assistant", "content": code})
        return code

    def stream_generate(self, prompt: str, adjust: bool = False, temperature: float = 0.7, top_p: float = 0.9) -> Iterator[str]:
        full = self.generate(prompt, adjust=adjust, temperature=temperature, top_p=top_p)
        chunk_size = max(64, len(full) // 10)
        for i in range(0, len(full), chunk_size):
            yield full[i : i + chunk_size]


__all__ = ["AIService"]
