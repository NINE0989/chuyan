"""LangChain LLM 适配器：ChatOpenAI 工厂 + mock 降级。"""
from __future__ import annotations

import json
import os
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI


def _mock_chat(messages: list[dict], **kwargs: Any) -> AIMessage:
    """保留旧 MockMcpAdapter 的关键词判断逻辑。"""
    last_content = ""
    for m in reversed(messages):
        if isinstance(m, dict):
            last_content = str(m.get("content", ""))
        elif hasattr(m, "content"):
            last_content = str(getattr(m, "content", ""))
        if last_content:
            break

    if "JSON" in last_content or "音乐风格" in last_content:
        return AIMessage(content=json.dumps(
            {
                "music_style": "电子/节奏驱动",
                "energy_curve": "中高能量，间歇性峰值",
                "visual_directions": ["径向脉冲环", "频带驱动粒子", "高频闪烁边缘"],
                "shader_plan": ["低频控制尺度", "中频控制纹理扰动", "高频控制辉光与闪烁"],
                "goodcase_checks": ["包含 mainImage", "包含 iChannel0 采样"],
                "badcase_risks": ["uniform 缺失", "采样越界"],
                "hook_hints": ["避免 gl_FragColor", "保证 iTime/iResolution 存在"],
                "confidence": 0.8,
            },
            ensure_ascii=False,
        ))

    return AIMessage(content="""
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
""".strip())


def _mock_tool_calling(messages: list[dict], **kwargs: Any) -> AIMessage:
    """Mock 含 tool_calls 的响应，模拟 Agent tool-calling 流程。

    对 agent 的初次请求，mock 返回一个「虚拟」的 tool_calls 列表，
    让 LangGraph 的 ToolNode 能够执行实际的 tool 函数。
    对 tool 结果返回后的 follow-up，输出最终 GLSL。
    """
    last_content = ""
    for m in reversed(messages):
        if isinstance(m, dict):
            last_content = str(m.get("content", ""))
        elif hasattr(m, "content"):
            last_content = str(getattr(m, "content", ""))
        if last_content:
            break

    # 如果消息中已包含 tool 结果（ToolMessage），说明已经执行过 tool，
    # 此时 mock 返回最终 GLSL
    if any(
        (isinstance(m, dict) and m.get("role") == "tool") or
        (hasattr(m, "type") and getattr(m, "type", "") == "tool")
        for m in messages
    ):
        return AIMessage(content="""
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
""".strip())

    # 模拟 tool_calls：让 LangGraph ToolNode 执行 extract_glsl_code
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "extract_glsl_code",
                "args": {"text": last_content or "mock"},
                "id": "mock_tool_call_1",
            }
        ],
    )


def _get_settings():
    """延迟导入避免循环依赖。"""
    try:
        from WebEngine.settings import get_settings
        return get_settings()
    except Exception:
        return None


def build_llm(provider: str = "openai") -> BaseChatModel | RunnableLambda:
    """构建 LLM 实例。

    - provider == "openai" → ChatOpenAI（读环境变量 > settings.json > 默认值）
    - 其他 → mock RunnableLambda
    """
    s = _get_settings()
    api_key = (s and s.api_key) or os.getenv("OPENAI_API_KEY", "").strip()
    base_url = (s and s.base_url) or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = (s and s.model) or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    if provider == "openai" and api_key:
        return ChatOpenAI(
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=0.45,
            timeout=90,
            max_retries=2,
        )

    return RunnableLambda(_mock_chat)
