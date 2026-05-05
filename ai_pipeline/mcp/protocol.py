"""MCP 协议适配层：支持真实模型后端与 mock。"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class McpError:
    code: str
    message: str


@dataclass(slots=True)
class McpEnvelope:
    version: str
    capability: str
    payload: dict[str, Any]
    error: McpError | None = None


class McpAdapter:
    def chat_completion(self, messages: list[dict[str, str]], temperature: float = 0.4) -> str:
        raise NotImplementedError

    def generate_shader(self, request_payload: dict[str, Any]) -> McpEnvelope:
        raise NotImplementedError


class OpenAIMcpAdapter(McpAdapter):
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    def _post_chat(self, body: dict[str, Any]) -> tuple[str | None, McpError | None]:
        if not self.api_key:
            return None, McpError(code="missing_api_key", message="缺少 OPENAI_API_KEY 环境变量")

        req = urllib.request.Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", errors="ignore")
            return None, McpError(code=f"http_{e.code}", message=msg[:800])
        except Exception as e:  # noqa: BLE001
            return None, McpError(code="network_error", message=str(e))

        try:
            parsed = json.loads(raw)
            content = parsed["choices"][0]["message"]["content"]
            return content, None
        except Exception:  # noqa: BLE001
            return None, McpError(code="invalid_response", message=raw[:800])

    def chat_completion(self, messages: list[dict[str, str]], temperature: float = 0.4) -> str:
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        content, err = self._post_chat(body)
        if err is not None:
            raise RuntimeError(f"mcp chat失败: {err.code} {err.message}")
        return content or ""

    def _extract_glsl(self, text: str) -> str:
        import re

        m = re.search(r"(?is)```\s*(?:glsl)?\s*\n?(.*?)\n?```", text)
        return m.group(1).strip() if m else text.strip()

    def generate_shader(self, request_payload: dict[str, Any]) -> McpEnvelope:
        prompt = request_payload.get("prompt", "")
        messages = [
            {"role": "system", "content": "你只返回 GLSL fenced code block，不要额外解释。"},
            {"role": "user", "content": prompt},
        ]
        content, err = self._post_chat({"model": self.model, "messages": messages, "temperature": 0.4})
        if err is not None:
            return McpEnvelope(version="1.0", capability="shader.generate", payload={}, error=err)

        glsl_code = self._extract_glsl(content or "")
        return McpEnvelope(
            version="1.0",
            capability="shader.generate",
            payload={
                "glsl_code": glsl_code,
                "diagnostics": [f"real mcp 调用成功，model={self.model}", f"响应长度={len(content or '')}"],
            },
            error=None,
        )


class MockMcpAdapter(McpAdapter):
    def chat_completion(self, messages: list[dict[str, str]], temperature: float = 0.4) -> str:
        last = messages[-1]["content"] if messages else ""
        if "JSON" in last or "音乐风格" in last:
            return json.dumps(
                {
                    "music_style": "电子/节奏驱动",
                    "energy_curve": "中高能量，间歇性峰值",
                    "visual_directions": ["径向脉冲环", "频带驱动粒子", "高频闪烁边缘"],
                    "shader_plan": ["低频控制尺度", "中频控制纹理扰动", "高频控制辉光与闪烁"],
                },
                ensure_ascii=False,
            )
        return """
```glsl
#version 330 core
uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;
out vec4 FragColor;
void mainImage(out vec4 fragColor, in vec2 fragCoord){
vec2 uv = fragCoord.xy / iResolution.xy;
vec2 p = (uv - 0.5) * vec2(iResolution.x / iResolution.y, 1.0);
float bass = texture(iChannel0, vec2(0.05, 0.25)).r;
float mid = texture(iChannel0, vec2(0.25, 0.25)).r;
float tre = texture(iChannel0, vec2(0.75, 0.25)).r;
float r = length(p);
float ring = smoothstep(0.03, 0.0, abs(r - (0.25 + bass * 0.2 + 0.03*sin(iTime))));
vec3 col = vec3(0.02, 0.02, 0.03);
col += ring * vec3(0.2 + bass, 0.5 + mid, 0.8 + tre);
fragColor = vec4(col, 1.0);
}
void main(){ mainImage(FragColor, gl_FragCoord.xy); }
```
""".strip()

    def generate_shader(self, request_payload: dict[str, Any]) -> McpEnvelope:
        content = self.chat_completion([{"role": "user", "content": request_payload.get("prompt", "")}])
        glsl_code = content.replace("```glsl", "").replace("```", "").strip()
        return McpEnvelope(
            version="1.0",
            capability="shader.generate",
            payload={"glsl_code": glsl_code, "diagnostics": ["mock mcp 已生成样例"]},
            error=None,
        )


def build_mcp_adapter(provider: str) -> McpAdapter:
    if provider == "openai":
        return OpenAIMcpAdapter()
    return MockMcpAdapter()
