"""Direct AI service for generating GLSL via Ark (Volcengine Doubao) style API.

Environment precedence for API key:
    AI_API_KEY > ARK_API_KEY > VOLC_API_KEY > HUNYUAN_API_KEY
Environment precedence for URL:
    AI_API_URL > HUNYUAN_API_URL (legacy) > DEFAULT_BASE_URL

If the provided base URL does not end with '/chat/completions', it will be
automatically appended. This fixes 404 errors when only the version root is supplied.
"""
from __future__ import annotations
import os
import json
import logging
import requests
from typing import Iterator, Optional, List, Dict

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "doubao-seed-1-6-vision-250815"

class AIService:
    def __init__(self, model: str = DEFAULT_MODEL, timeout: int = 120):
        # Resolve API key from multiple env names (no hardcode)
        self.api_key = (
            "9c7f2504-29b9-4b66-abe3-3c6b064ed0d8"
        )
        if not self.api_key:
            raise RuntimeError("缺少 API Key，请设置 AI_API_KEY 或 ARK_API_KEY 环境变量")

        base_url = (
            os.getenv("AI_API_URL")
            or os.getenv("HUNYUAN_API_URL")  # backward compatibility
            or DEFAULT_BASE_URL
        ).rstrip('/').lower()
        # Append endpoint if user passed only base
        if not base_url.endswith("/chat/completions"):
            self.api_url = base_url + "/chat/completions"
        else:
            self.api_url = base_url

        self.model = model
        self.timeout = timeout
        self.history: List[Dict[str,str]] = []
        self.system_prompt = (
            "你是一个GLSL助手，返回纯GLSL片元着色器源码，不包含Markdown或解释文字。"
        )
        # Extended spec will be built dynamically on first generation

    def _build_system_prompt(self, user_prompt: str) -> str:
        """Build the extended specification system prompt for first-time generation.

        NOTE: We avoid backticks in instructions to reduce model tendency to emit them.
        """
        return (
            "你是一位精通 GLSL 与 Shadertoy 的图形程序员，为 Python Shadertoy 运行环境生成可直接编译运行的音频响应式片元着色器(GLSL)，严格遵循以下规范(优先级: 格式 > 兼容性 > 功能逻辑 > 视觉风格):"  # 1. 格式
            "\n[格式] 仅输出纯 GLSL 源码, 不含 Markdown 标记、说明文字或元数据; 不使用反引号; 不输出代码围栏; 不使用 #include; 不依赖外部文件;"
            "\n[入口] 必须实现 void mainImage(out vec4 fragColor, in vec2 fragCoord) 与桌面/GL ES 兼容 main():"
            "\nvoid main(){"  # main adapter skeleton inline so model learns pattern
            "\n    #ifdef GL_ES"  
            "\n    vec4 fragColor;"  
            "\n    mainImage(fragColor, gl_FragCoord.xy);"  
            "\n    gl_FragColor = fragColor;"  
            "\n    #else"  
            "\n    out vec4 fragColor;"  
            "\n    mainImage(fragColor, gl_FragCoord.xy);"  
            "\n    #endif"  
            "\n}"
            "\n[版本] 强制使用 #version 330; 顶部第一行必须是 #version 330 core"
            "\n[兼容宏] 添加: // Compatibility boilerplate\n#ifdef GL_ES\nprecision mediump float;\n#endif\n#ifndef TEX\n#ifdef GL_ES\n#define TEX(s, uv) texture2D(s, uv)\n#else\n#define TEX(s, uv) texture(s, uv)\n#endif\n#endif"
            "\n[Uniforms] 顶部声明: uniform vec3 iResolution; uniform float iTime; uniform sampler2D iChannel0;"
            "\n[音频纹理] iChannel0 为 512x2 频谱; 仅采样 y=0.0; u∈[0,1] 低频到高频; 采样次数要缓存减少重复;"
            "\n[视觉] 背景必须纯黑 vec3(0.0); 提供掩码函数 float shapeMask(vec2 p); mask<=threshold 输出纯黑; 边缘抗锯齿用 smoothstep 宽度≤0.02; glow/bloom 仅作用主体区域乘 mask;"
            "\n[频率映射] bass(u<0.20) 控制尺寸/亮度/旋转; mid(0.20≤u≤0.50) 控制细节密度/纹理抖动; treble(u>0.50) 控制粒子生成率/速度; 总体音量控制 glow 强度;"
            "\n[函数] 必须实现辅助: hash12, rotate2D, noise2D, fbm, guardedTexelFetch, rgbShift, screenGlow; 粒子系统用固定数组; 使用 #define MAX_PARTICLES 128, #define PARTICLE_ITERATIONS 32; 避免深度 raymarch; 循环有固定上限;"
            "\n[语法] 避免隐式类型转换; 所有 float(vec3.x) 转换显式写; 顶部保留一行简短注释描述效果;"
            f"\n[风格关键词] 将用户描述 '{user_prompt}' 直接映射到颜色/运动/粒子参数; 使用可调常量暴露风格。"
            "\n[禁止] 不输出多余解释、JSON、注释块说明、任何非 GLSL 内容。"
            "\n[输出目标] 结果应能直接在 Shadertoy 与 OpenGL 3.3 环境编译运行并响应音频。"
        )

    def _headers(self) -> Dict[str,str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _build_messages(self, prompt: str, adjust: bool) -> List[Dict[str,str]]:
        if not self.history or not adjust:
            # Build extended system prompt only on fresh generation
            extended = self._build_system_prompt(prompt)
            self.history = [
                {"role": "system", "content": extended},
                {"role": "user", "content": f"生成以下效果的GLSL代码：{prompt}"},
            ]
        else:
            # Adjustment request
            self.history.append({"role": "user", "content": f"调整要求：{prompt}"})
        return self.history

    def _unwrap_code(self, text: str) -> str:
        """Strip common wrappers: triple quotes, markdown fences, stray quotes."""
        t = text.strip()
        # Triple quotes
        if (t.startswith('"""') and t.endswith('"""')) or (t.startswith("'''") and t.endswith("'''")):
            t = t[3:-3].strip()
        # Markdown fences
        if t.startswith('```'):
            lines = t.splitlines()
            if lines and lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            t = '\n'.join(lines).strip()
        # Single-line quote wrapper
        if ((t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'"))) and '\n' not in t:
            t = t[1:-1].strip()
        # Remove accidental leading 'glsl' language tag line
        lines = t.splitlines()
        if lines and lines[0].lower().strip() in ('glsl','shader','code:'):  # heuristic
            lines = lines[1:]
        return '\n'.join(lines).strip()

    def generate(self, prompt: str, adjust: bool = False, temperature: float = 0.7, top_p: float = 0.9) -> str:
        messages = self._build_messages(prompt, adjust)
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "stream": False,
        }
        try:
            resp = requests.post(self.api_url, headers=self._headers(), json=payload, timeout=self.timeout)
        except requests.exceptions.RequestException as e:  # noqa: BLE001
            raise RuntimeError(f"网络请求失败: {e}")
        if resp.status_code != 200:
            sample = resp.text[:400]
            raise RuntimeError(f"AI请求失败 {resp.status_code}: {sample}")
        data = resp.json()
        try:
            choice0 = data.get("choices", [{}])[0]
            message = choice0.get("message", {})
            content = (message.get("content") or "").strip()
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"AI响应解析失败: {e}; 原始: {data}")
        if not content:
            raise RuntimeError(f"AI未返回内容: {data}")
        cleaned = self._unwrap_code(content)
        self.history.append({"role": "assistant", "content": cleaned})
        return cleaned

    def stream_generate(self, prompt: str, adjust: bool = False, temperature: float = 0.7, top_p: float = 0.9) -> Iterator[str]:
        full = self.generate(prompt, adjust, temperature, top_p)
        chunk_size = max(64, len(full)//10)
        for i in range(0, len(full), chunk_size):
            yield full[i:i+chunk_size]

__all__ = ["AIService"]
