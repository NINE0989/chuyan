'''多轮对话，路径矫正'''
import os
import json
import logging
import sys
import re
from pathlib import Path
import requests  # 使用requests库直接发送HTTP请求，适配腾讯云混元API格式

# 配置日志
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class GLSLGenerator:
    def __init__(self):
        """初始化GLSL生成器（适配腾讯云混元OpenAI兼容接口）"""
        # 从环境变量获取腾讯云混元API密钥（HUNYUAN_API_KEY）
        self.api_key = os.getenv("HUNYUAN_API_KEY")
        if not self.api_key:
            raise ValueError("请确保已配置HUNYUAN_API_KEY环境变量（腾讯云混元API密钥）")
        
        # 腾讯云混元API接口地址（与curl中的地址一致）
        self.api_url = "https://api.hunyuan.cloud.tencent.com/v1/chat/completions"
        
        # 路径配置（保持原功能）
        self.program_dir = Path(__file__).parent  # shadertoy文件夹路径
        self.sibling_dir = self.program_dir.parent  # shadertoy同级目录
        self.output_dir = self.sibling_dir / "shaders" / "AI_shaders"
        self.output_dir.mkdir(exist_ok=True, parents=True)  # 自动创建目录
        
        # 内置默认配置
        self.default_style = "简洁"
        self.default_version = "330 core"
        self.default_temperature = 0.7  # 内置默认温度
        self.conversation_history = []  # 多轮对话历史存储
        self.model = "hunyuan-turbos-latest"  # 模型名称（与curl中的一致）

    def _extract_config(self, prompt):
        """提取提示词中的自定义配置（代码风格、GLSL版本）"""
        style = self.default_style
        version = self.default_version
        
        if "代码风格：" in prompt or "代码风格:" in prompt:
            style_match = re.search(r'代码风格[:：]\s*([^，,。；;]+)', prompt)
            if style_match:
                style = style_match.group(1).strip()
        if "GLSL版本：" in prompt or "GLSL版本:" in prompt:
            version_match = re.search(r'GLSL版本[:：]\s*([^，,。；;]+)', prompt)
            if version_match:
                version = version_match.group(1).strip()
        return style, version

    def generate_or_adjust_glsl(self, prompt, is_adjust=False):
        """生成或调整GLSL代码（使用腾讯云混元OpenAI兼容接口）"""
        try:
            action = "调整" if is_adjust else "生成"
            temperature = self.default_temperature
            logger.info(f"开始{action}GLSL代码，提示词: {prompt}，使用温度: {temperature}")
            
            # 首次生成：初始化系统提示和对话历史
            if not is_adjust:
                style, version = self._extract_config(prompt)
                system_prompt = (
    f"你是一位精通 GLSL 与 Shadertoy 的图形程序员，为 Python Shadertoy 运行环境生成可直接编译运行的音频响应式片元着色器（GLSL），严格遵循以下规范（优先级：格式要求 > 兼容性 > 功能逻辑 > 视觉风格）："
    # 1. 输出格式要求（必须）
    f"\n### 1. 输出格式要求"
    f"仅输出纯 GLSL 源码，无任何 Markdown 标记（```、`）、说明文字或元数据，直接可写入 .glsl 文件编译；"
    f"源码中禁止包含反引号，注释仅用 // 且无 Markdown 标记；"
    f"代码自包含，不使用 #include 或外部依赖，无网络请求/文件读写/不兼容扩展；"
    f"必须同时实现：Shadertoy 入口 void mainImage(out vec4 fragColor, in vec2 fragCoord)、桌面/GL ES 适配入口 void main()。"
    # 2. 兼容性规范（必须）
    f"\n### 2. 兼容性规范"
    f"强制使用 #version 330（兼容桌面 GL3.3 与 Shadertoy）；"
    f"必须包含兼容宏：\n// Compatibility boilerplate\n#ifdef GL_ES\nprecision mediump float;\n#endif\n#ifndef TEX\n#ifdef GL_ES\n#define TEX(s, uv) texture2D(s, uv)\n#else\n#define TEX(s, uv) texture(s, uv)\n#endif\n#endif"
    f"main() 适配器需严格区分环境：\nvoid main() {{\n    #ifdef GL_ES\n    vec4 fragColor;\n    mainImage(fragColor, gl_FragCoord.xy);\n    gl_FragColor = fragColor;\n    #else\n    out vec4 fragColor;\n    mainImage(fragColor, gl_FragCoord.xy);\n    #endif\n}}"
    # 3. 运行时与采样规则（必须）
    f"\n### 3. 运行时与采样规则"
    f"顶部显式声明 Uniforms：uniform vec3 iResolution; uniform float iTime; uniform sampler2D iChannel0;"
    f"iChannel0 为 512x2 音频频谱纹理，仅采样 y=0.0 行，用 TEX 宏，u∈[0.0,1.0] 对应频率（低→高）；"
    f"减少 hot-loop 中 iChannel0 采样次数，优先在循环外缓存 bass、mid、treble、volume 等结果。"
    # 4. 视觉与掩码要求（必须）
    f"\n### 4. 视觉与掩码要求"
    f"背景严格为纯黑（vec3(0.0)），无噪点/杂色/抖动；"
    f"必须实现显式掩码函数（如 float shapeMask(vec2 p)），主体颜色仅在 mask>threshold 区域绘制，mask≤threshold 输出纯黑；"
    f"边缘抗锯齿用 smoothstep（宽度≤0.02），glow/bloom 仅作用于主体区域（乘以 mask）。"
    # 5. 音频-视觉映射（必须）
    f"\n### 5. 音频-视觉映射"
    f"频率分区：bass（u<0.20）→ 主体尺寸/亮度/旋转；mid（0.20≤u≤0.50）→ 细节密度/纹理抖动；treble（u>0.50）→ 粒子生成率/运动速度；"
    f"总体音量 → glow/bloom 强度（screenGlow 入参）。"
    # 6. 内置函数与性能（必须）
    f"\n### 6. 内置函数与性能"
    f"必须实现轻量函数：hash12、rotate2D、noise2D、fbm、guardedTexelFetch、rgbShift、screenGlow；"
    f"粒子系统用固定数组，#define 暴露参数：MAX_PARTICLES 128、PARTICLE_ITERATIONS 32 等；"
    f"避免深度 raymarch，循环用固定迭代上限。"
    # 7. 视觉风格与语法规范（必须）
    f"\n### 7. 视觉风格与语法规范"
    f"用户描述映射：{prompt} 作为视觉风格关键词，直接体现在代码参数中；"
    f"严格避免 vec3 到 float 隐式转换，所有类型转换必须显式（如 float(val)）；"
    f"代码最顶端保留1行短注释，辅助函数全部内置，确保编译无语法错误。"
    )
                self.conversation_history = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"生成以下效果的GLSL代码：{prompt}"}
                ]
            else:
                # 调整时添加微调需求到对话历史
                self.conversation_history.append({"role": "user", "content": f"调整要求：{prompt}"})
            
            # 构造API请求参数（与curl中的格式完全一致）
            payload = {
                "model": self.model,
                "messages": self.conversation_history,
                "temperature": temperature,
                "top_p": 0.9,
                "enable_enhancement": True  # 启用增强模式（与curl中的参数一致）
            }
            
            # 构造请求头（使用Bearer Token认证）
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"  # 与curl中的认证方式一致
            }
            
            # 发送POST请求到腾讯云混元API
            response = requests.post(
                url=self.api_url,
                headers=headers,
                json=payload,
                timeout=120
            )
            
            # 检查请求是否成功
            if response.status_code != 200:
                raise Exception(f"API请求失败，状态码: {response.status_code}，响应: {response.text}")
            
            # 解析响应结果
            result = response.json()
            
            # 提取并返回GLSL代码
            if "choices" in result and len(result["choices"]) > 0:
                glsl_code = result["choices"][0]["message"]["content"].strip()
                self.conversation_history.append({"role": "assistant", "content": glsl_code})
                logger.info(f"GLSL代码{action}成功")
                return glsl_code
            else:
                logger.error(f"{action}结果不包含有效代码，响应: {result}")
                return None
                
        except Exception as e:
            logger.error(f"{action}GLSL代码失败: {str(e)}")
            raise

    def save_glsl_file(self, glsl_code, filename=None):
        """保存GLSL代码到文件（与原功能一致）"""
        if not glsl_code:
            raise ValueError("GLSL代码不能为空")
        
        # 版本声明处理
        version = self.default_version
        for msg in self.conversation_history:
            if msg["role"] == "system" and "version 330" in msg["content"]:
                version = "330"
                break
        if f"#version {version}" not in glsl_code:
            glsl_code = f"#version {version}\n" + glsl_code
        
        # 文件名处理
        if not filename:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"shader_{timestamp}.glsl"
        if not filename.endswith(".glsl"):
            filename += ".glsl"
        
        # 保存文件
        file_path = self.output_dir / filename
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(glsl_code)
            logger.info(f"GLSL代码已保存到: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"保存文件失败: {str(e)}")
            raise

def main():
    try:
        generator = GLSLGenerator()
        
        # 欢迎信息
        print("=" * 60)
        print("欢迎使用GLSL代码生成器（腾讯云混元OpenAI兼容接口版）")
        print(f"默认配置：代码风格={generator.default_style}，GLSL版本={generator.default_version}")
        print(f"内置模型温度={generator.default_temperature}，模型={generator.model}")
        print(f"API地址：{generator.api_url}")
        print(f"保存路径：{generator.output_dir}")
        print("=" * 60)
        
        # 首次生成
        prompt = input("\n请输入所需的效果描述: ")
        original_prompt = prompt
        glsl_code = generator.generate_or_adjust_glsl(prompt=prompt, is_adjust=False)
        
        if not glsl_code:
            print("生成失败，未获取到有效GLSL代码")
            sys.exit(1)
        
        # 展示生成结果
        print("\n生成的GLSL代码:")
        print("-" * 50)
        print(glsl_code)
        print("-" * 50)
        
        # 多轮微调
        while True:
            adjust_choice = input("\n是否需要调整代码？（输入y/Y进行调整，其他键直接保存）: ").strip().lower()
            if adjust_choice != "y":
                break
            
            adjust_prompt = input("请输入你的微调需求（例：增加颜色饱和度、优化动画流畅度）: ")
            original_prompt = adjust_prompt
            glsl_code = generator.generate_or_adjust_glsl(prompt=adjust_prompt, is_adjust=True)
            
            if not glsl_code:
                print("调整失败，保留上一版代码")
                continue
            
            print("\n调整后的GLSL代码:")
            print("-" * 50)
            print(glsl_code)
            print("-" * 50)
        
        # 保存最终代码
        filename = input("\n请输入保存的文件名（不输入则自动生成）: ").strip()
        file_path = generator.save_glsl_file(glsl_code, filename if filename else None)
        print(f"\n✅ 代码已成功保存到: {file_path}")
        return original_prompt
        
    except Exception as e:
        print(f"\n❌ 发生错误: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()