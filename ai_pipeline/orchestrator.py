"""多 Agent 对话编排：音频理解 Agent + 编码 Agent。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ai_pipeline.mcp import McpAdapter


@dataclass(slots=True)
class ConversationState:
    session_id: str
    messages: list[dict[str, str]] = field(default_factory=list)


class ConversationStore:
    """会话持久化，保证持续传递信息。"""

    def __init__(self, root: Path):
        self.path = root / "ai_pipeline" / "conversations.json"

    def load(self, session_id: str) -> ConversationState:
        if not self.path.is_file():
            return ConversationState(session_id=session_id)
        data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        messages = data.get(session_id, [])
        return ConversationState(session_id=session_id, messages=messages)

    def save(self, state: ConversationState) -> None:
        if self.path.is_file():
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        else:
            data = {}
        data[state.session_id] = state.messages
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class MultiAgentOrchestrator:
    """两阶段编排：先音频理解，再编码落地。"""

    def __init__(self, root: Path, adapter: McpAdapter):
        self.root = root
        self.adapter = adapter
        self.store = ConversationStore(root)
        self.audio_agent_prompt = (root / "ai_pipeline" / "audio_understanding.md").read_text(encoding="utf-8-sig")
        self.coding_agent_prompt = (root / "ai_pipeline" / "coding_agent.md").read_text(encoding="utf-8-sig")

    def _summarize_audio(self, audio_array: list[float]) -> dict[str, Any]:
        if not audio_array:
            return {"length": 0, "mean": 0.0, "max": 0.0, "min": 0.0, "samples": []}
        length = len(audio_array)
        mean = float(sum(audio_array) / length)
        max_v = float(max(audio_array))
        min_v = float(min(audio_array))
        step = max(1, length // 32)
        samples = [float(audio_array[i]) for i in range(0, length, step)][:32]
        return {"length": length, "mean": mean, "max": max_v, "min": min_v, "samples": samples}

    def _normalize_audio_analysis(self, raw_text: str) -> dict[str, Any]:
        try:
            data = json.loads(raw_text)
        except Exception:  # noqa: BLE001
            data = {}

        normalized = {
            "music_style": str(data.get("music_style", "unknown")),
            "energy_curve": str(data.get("energy_curve", "unknown")),
            "band_mapping": data.get(
                "band_mapping",
                {"low": "低频控制主形体", "mid": "中频控制纹理", "high": "高频控制高光"},
            ),
            "visual_directions": data.get("visual_directions", ["径向频谱环", "频带脉冲"]),
            "shader_plan": data.get("shader_plan", ["低频控制半径", "中频控制扰动", "高频控制闪烁"]),
            "goodcase_checks": data.get("goodcase_checks", ["包含 mainImage", "包含 iChannel0 采样"]),
            "badcase_risks": data.get("badcase_risks", ["uniform 缺失", "采样越界"]),
            "hook_hints": data.get("hook_hints", ["避免 gl_FragColor", "保证 iTime/iResolution 存在"]),
            "confidence": float(data.get("confidence", 0.5)),
        }

        # 基本兜底约束
        if not isinstance(normalized["band_mapping"], dict):
            normalized["band_mapping"] = {"low": "低频控制主形体", "mid": "中频控制纹理", "high": "高频控制高光"}
        for k in ("low", "mid", "high"):
            normalized["band_mapping"].setdefault(k, "待补充")

        for key in ("visual_directions", "shader_plan", "goodcase_checks", "badcase_risks", "hook_hints"):
            if not isinstance(normalized[key], list) or len(normalized[key]) == 0:
                normalized[key] = ["待补充"]

        return normalized

    def run(
        self,
        session_id: str,
        user_prompt: str,
        audio_array: list[float],
        style_profile: str,
    ) -> tuple[str, list[str]]:
        state = self.store.load(session_id)
        audio_summary = self._summarize_audio(audio_array)

        audio_messages = [
            {"role": "system", "content": self.audio_agent_prompt},
            {
                "role": "user",
                "content": (
                    f"用户目标: {user_prompt}\n"
                    f"style_profile: {style_profile}\n"
                    f"numpy音频数组摘要: {json.dumps(audio_summary, ensure_ascii=False)}\n"
                    "请严格按SOP输出 JSON。"
                ),
            },
        ]
        audio_analysis_text = self.adapter.chat_completion(audio_messages, temperature=0.3)
        audio_analysis = self._normalize_audio_analysis(audio_analysis_text)

        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in state.messages[-8:]])
        coding_messages = [
            {"role": "system", "content": self.coding_agent_prompt},
            {
                "role": "user",
                "content": (
                    f"用户需求: {user_prompt}\n"
                    f"style_profile: {style_profile}\n"
                    f"音频理解结果: {json.dumps(audio_analysis, ensure_ascii=False)}\n"
                    f"历史上下文:\n{history_text}\n"
                    "请严格按SOP输出最终 GLSL。"
                ),
            },
        ]
        shader_output = self.adapter.chat_completion(coding_messages, temperature=0.45)

        state.messages.append({"role": "user", "content": user_prompt})
        state.messages.append({"role": "assistant", "content": json.dumps(audio_analysis, ensure_ascii=False)})
        state.messages.append({"role": "assistant", "content": shader_output[:1500]})
        self.store.save(state)

        diagnostics = [
            f"session={session_id}",
            f"music_style={audio_analysis.get('music_style', 'unknown')}",
            f"energy_curve={audio_analysis.get('energy_curve', 'unknown')}",
            f"confidence={audio_analysis.get('confidence', 0.0)}",
            "multi_agent_pipeline=audio_understanding->coding",
        ]
        return shader_output, diagnostics
