'''多轮对话，路径矫正'''
import os
import json
import logging
import sys
import re
from pathlib import Path
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.hunyuan.v20230901 import hunyuan_client, models

# 配置日志
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class GLSLGenerator:
    def __init__(self):
        """初始化GLSL生成器"""
        self.secret_id = os.getenv("TENCENTCLOUD_SECRET_ID")
        self.secret_key = os.getenv("TENCENTCLOUD_SECRET_KEY")
        
        if not self.secret_id or not self.secret_key:
            raise ValueError("请确保已配置TENCENTCLOUD_SECRET_ID和TENCENTCLOUD_SECRET_KEY环境变量")
        
        self.client = self._init_client()
        # 纠正保存路径：
        # 1. 程序所在目录 = shadertoy文件夹（假设程序放在shadertoy文件夹内）
        self.program_dir = Path(__file__).parent  # 即 shadertoy 文件夹路径
        # 2. 同级目录 = shadertoy文件夹的上一级目录
        self.sibling_dir = self.program_dir.parent  
        # 3. 目标路径 = 同级目录/shaders/AI_shaders
        self.output_dir = self.sibling_dir / "shaders" / "AI_shaders"
        self.output_dir.mkdir(exist_ok=True, parents=True)  # 自动创建shaders和AI_shaders目录
        
        self.default_style = "简洁"
        self.default_version = "330 core"
        self.conversation_history = []  # 存储多轮对话历史

    def _init_client(self):
        """初始化腾讯云混元模型客户端"""
        try:
            http_profile = HttpProfile()
            http_profile.endpoint = "hunyuan.tencentcloudapi.com"
            http_profile.reqTimeout = 120
            
            client_profile = ClientProfile()
            client_profile.httpProfile = http_profile
            
            return hunyuan_client.HunyuanClient(
                credential.Credential(self.secret_id, self.secret_key),
                "ap-guangzhou",
                client_profile
            )
        except Exception as e:
            logger.error(f"初始化客户端失败: {str(e)}")
            raise

    def _extract_config(self, prompt):
        """提取提示词中的自定义配置"""
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

    def generate_or_adjust_glsl(self, prompt, is_adjust=False, temperature=0.7):
        """生成或调整GLSL代码（支持多轮对话上下文）"""
        try:
            action = "调整" if is_adjust else "生成"
            logger.info(f"开始{action}GLSL代码，提示词: {prompt}")
            
            # 首次生成时初始化系统提示和对话历史
            if not is_adjust:
                style, version = self._extract_config(prompt)
                system_prompt = (
    f"你是一位精通 GLSL 与 Shadertoy 的图形程序员，为 Python Shadertoy 运行环境生成可直接编译运行的音频响应式片元着色器（GLSL），严格遵循以下规范（优先级：格式要求 > 兼容性 > 功能逻辑 > 视觉风格）："
    # 1. 输出格式要求（必须，优先级最高）
    f"\n### 1. 输出格式要求"
    f"仅输出纯 GLSL 源码，无任何 Markdown 标记（```、`）、说明文字或元数据，直接可写入 .glsl 文件编译；"
    f"源码中禁止包含反引号，注释仅用 // 且无 Markdown 标记；"
    f"代码自包含，不使用 #include 或外部依赖，无网络请求/文件读写/不兼容扩展；"
    f"必须同时实现：Shadertoy 入口 void mainImage(out vec4 fragColor, in vec2 fragCoord)（主逻辑）、桌面/GL ES 适配入口 void main()（调用 mainImage，传入 gl_FragCoord.xy）。"
    # 2. 兼容性规范（必须）
    f"\n### 2. 兼容性规范"
    f"强制使用 #version 330（兼容桌面 GL3.3 与 Shadertoy）；"
    f"必须包含兼容宏：\n// Compatibility boilerplate\n#ifdef GL_ES\nprecision mediump float;\n#endif\n#ifndef TEX\n#ifdef GL_ES\n#define TEX(s, uv) texture2D(s, uv)\n#else\n#define TEX(s, uv) texture(s, uv)\n#endif\n#endif"
    f"main() 适配器需严格区分环境：\nvoid main() {{\n    #ifdef GL_ES\n    vec4 fragColor;\n    mainImage(fragColor, gl_FragCoord.xy);\n    gl_FragColor = fragColor;\n    #else\n    out vec4 fragColor;\n    mainImage(fragColor, gl_FragCoord.xy);\n    #endif\n}}"
    # 3. 运行时与采样规则（必须）
    f"\n### 3. 运行时与采样规则"
    f"顶部显式声明 Uniforms：uniform vec3 iResolution; uniform float iTime; uniform sampler2D iChannel0;"
    f"iChannel0 为 512x2 音频频谱纹理，仅采样 y=0.0 行，用 TEX 宏，u∈[0.0,1.0] 对应频率（低→高）；"
    f"减少 hot-loop 中 iChannel0 采样次数，优先在循环外缓存 bass、mid、treble、volume 等采样结果。"
    # 4. 视觉与掩码要求（必须）
    f"\n### 4. 视觉与掩码要求"
    f"背景严格为纯黑（vec3(0.0)），无噪点/杂色/抖动；"
    f"必须实现显式掩码函数（如 float shapeMask(vec2 p)、float edgeMask(float v, float thresh)），主体颜色仅在 mask>threshold 区域绘制，mask≤threshold 像素输出纯黑；"
    f"边缘抗锯齿用 smoothstep（宽度≤0.02），不依赖随机扰动；"
    f"glow/bloom 仅作用于主体区域，不泄漏到背景（用 screenGlow 函数且乘以 mask）。"
    # 5. 音频-视觉映射（必须）
    f"\n### 5. 音频-视觉映射"
    f"频率分区：bass（u<0.20）→ 主体尺寸缩放/核心亮度/缓慢旋转（≤0.1rad/s）；mid（0.20≤u≤0.50）→ 主体内细节密度/纹理抖动幅度（受掩码限制）；treble（u>0.50）→ 粒子生成率/运动速度/边缘锐度；"
    f"总体音量（(bass+mid+treble)/3.0）→ glow/bloom 强度（screenGlow 入参）。"
    # 6. 内置函数与性能（必须）
    f"\n### 6. 内置函数与性能"
    f"必须实现轻量函数：\n- float hash12(vec2 p)  // 伪随机数生成\n- vec2 rotate2D(vec2 uv, float a)  // 二维旋转\n- float noise2D(vec2 p)  // 二维噪声\n- float fbm(vec2 p, int octaves)  // 分形布朗运动\n- float guardedTexelFetch(sampler2D s, int idx, int width)  // 安全频谱采样\n- vec3 rgbShift(vec3 col, float amount)  // RGB 色差\n- vec3 screenGlow(vec3 col, float intensity)  // 屏幕空间辉光"
    f"粒子系统用固定数组，#define 暴露参数：\n#define MAX_PARTICLES 128\n#define PARTICLE_ITERATIONS 32\n#define NEBULA_OCTAVES 3\n#define GLOW_INTENSITY 0.8"
    f"避免深度 raymarch 或大量步进的 3D marching，循环用固定迭代上限（如 PARTICLE_ITERATIONS）。"
    # 7. 视觉风格偏好（推荐）
    f"\n### 7. 视觉风格偏好"
    f"优先实现：RGB 色差分离（subtle rgb-shift，幅度≤0.01）、径向/环形/低多边形（lowpoly）风格；"
    f"用户描述映射：{prompt} 作为视觉风格关键词（如“赛博朋克”对应蓝紫色调+强 rgb-shift，“复古”对应暖色调+低多边形），直接体现在代码参数中，无需文字解释，可加一行短注释标注风格标签（如 // Style: Cyberpunk RGB-Shift）。"
    # 8. 最终要求（必须）
    f"\n### 8. 最终要求"
    f"代码最顶端保留1行短注释（如 // Audio-Responsive RGB Rings — AI Generated | mainImage + main adapter）；"
    f"辅助函数全部内置，对除法/指数操作做护栏（如 clamp(x, 0.0, 1.0)、max(abs(x), 1e-6)）；"
    f"不使用高级扩展或 compute shader 特性，确保编译无语法错误。"
    f"\n### 特别强调：类型与语法规范"
    f"严格避免`vec3`到`float`的隐式类型转换，所有类型转换必须显式声明（如`float(val)`）；"
    f"`fragColor`的声明与使用需完全遵循GLSL 330规范：\n"
    f"  - 在`mainImage`中，`fragColor`作为`out vec4`参数传递；\n"
    f"  - 在`main`函数中，GL ES环境下使用`gl_FragColor`，桌面环境下使用`out vec4 fragColor`声明，且**禁止在`main`函数内对`fragColor`使用`in`/`out`修饰符**；\n"
    f"  - 参考正确的`main`函数实现：\n"
    f'    void main() {{\n'
    f'        #ifdef GL_ES\n'
    f'        vec4 fragColor;\n'
    f'        mainImage(fragColor, gl_FragCoord.xy);\n'
    f'        gl_FragColor = fragColor;\n'
    f'        #else\n'
    f'        out vec4 fragColor;\n'
    f'        mainImage(fragColor, gl_FragCoord.xy);\n'
    f'        #endif\n'
    f'    }}'
    f"\n### 语法与变量强制约束"
    f"1. 严格保证语法完整性：所有符号（括号、引号、分号）必须正确闭合，无任何非法或未定义符号（如`$undefined`类的无效标记）；\n"
    f"2. 强制显式声明Uniform变量：必须在代码顶部明确声明`uniform vec3 iResolution; uniform float iTime; uniform sampler2D iChannel0;`，确保变量可访问；\n"
    f"3. `fragColor`使用规范：\n"
    f"   - 在`mainImage`中，`fragColor`作为`out vec4`参数传递；\n"
    f"   - 在`main`函数中，严格按照以下模板实现，禁止对`fragColor`使用`in`/`out`修饰符：\n"
    f'    void main() {{\n'
    f'        #ifdef GL_ES\n'
    f'        vec4 fragColor;\n'
    f'        mainImage(fragColor, gl_FragCoord.xy);\n'
    f'        gl_FragColor = fragColor;\n'
    f'        #else\n'
    f'        out vec4 fragColor;\n'
    f'        mainImage(fragColor, gl_FragCoord.xy);\n'
    f'        #endif\n'
    f'    }}'

    f"\n### 输出前自我检查清单（必须执行）\n"
    f"1. 检查是否存在`vec3`转`float`的隐式转换，所有类型转换必须显式（如`float(val)`）；\n"
    f"2. 验证`iResolution`、`iTime`、`iChannel0`是否已显式声明为uniform；\n"
    f"3. 确认`main`函数中`fragColor`的使用完全符合适配模板，无`in`/`out`修饰符冲突；\n"
    f"4. 确保工具函数（如screenGlow）已实现且被正确调用；\n"
    f"5. 检查语法完整性，无非法符号、未闭合结构；\n"
)
                self.conversation_history = [
                    {"Role": "system", "Content": system_prompt},
                    {"Role": "user", "Content": f"生成以下效果的GLSL代码：{prompt}"}
                ]
            else:
                # 调整时添加用户的微调需求到对话历史
                self.conversation_history.append({"Role": "user", "Content": f"调整要求：{prompt}"})
            
            # 确保对话以user角色结束
            if self.conversation_history[-1]["Role"] != "user":
                raise ValueError("对话消息必须以 'user' 角色结束")
            
            req = models.ChatCompletionsRequest()
            params = {
                "Model": "hunyuan-pro",
                "Messages": self.conversation_history,
                "Temperature": temperature,
                "TopP": 0.9
            }
            
            req.from_json_string(json.dumps(params))
            resp = self.client.ChatCompletions(req)
            result = json.loads(resp.to_json_string())
            
            if "Choices" in result and len(result["Choices"]) > 0:
                glsl_code = result["Choices"][0]["Message"]["Content"].strip()
                # 将AI的回复添加到对话历史，用于下一轮调整
                self.conversation_history.append({"Role": "assistant", "Content": glsl_code})
                logger.info(f"GLSL代码{action}成功")
                return glsl_code
            else:
                logger.error(f"{action}结果不包含有效代码")
                return None
                
        except TencentCloudSDKException as e:
            logger.error(f"腾讯云API错误: {e.get_code()} - {e.get_message()}")
            raise
        except Exception as e:
            logger.error(f"{action}GLSL代码失败: {str(e)}")
            raise

    #def save_glsl_file(self, glsl_code, filename=None):
        """保存GLSL代码到文件（保持原清理逻辑）"""
        if not glsl_code:
            raise ValueError("GLSL代码不能为空")
        
        # 阶段1: 基础清理
        cleaned_code = glsl_code.strip()
        
        # 阶段2: 多模式清理
        patterns = [
            (r'^\s*\'\'\'\s*', r'\s*\'\'\'\s*$'),
            (r'^\s*\"\"\"\s*', r'\s*\"\"\"\s*$'),
            (r'^\s*```glsl\s*', r'\s*```\s*$'),
            (r'^\s*```\s*', r'\s*```\s*$'),
            (r'^\s*\'\s*', r'\s*\'\s*$'),
            (r'^\s*\"\s*', r'\s*\"\s*$')
        ]
        
        # 阶段3: 多轮清理
        max_attempts = 5
        attempts = 0
        while attempts < max_attempts:
            original = cleaned_code
            for start_pat, end_pat in patterns:
                if re.match(start_pat, cleaned_code) and re.search(end_pat, cleaned_code):
                    cleaned_code = re.sub(start_pat, '', cleaned_code, count=1)
                    cleaned_code = re.sub(end_pat, '', cleaned_code, count=1)
                    cleaned_code = cleaned_code.strip()
                    logger.debug(f"第{attempts+1}轮清理: 移除了匹配标记")
                    break
            if cleaned_code == original:
                break
            attempts += 1
        
        # 阶段4: 暴力清理三重引号
        cleaned_code = cleaned_code.replace("'''", "").replace('"""', "")
        
        # 阶段5: 结构校验与补充
        '''if not cleaned_code.startswith("void mainImage"):
            logger.warning("生成的代码未以mainImage函数开头，可能存在格式问题")'''
        
        # 版本声明处理
        version = self.default_version
        for msg in self.conversation_history:
            if msg["Role"] == "system":
                version_match = re.search(r'OpenGL\s*([\d]+(?:\s+core)?)', msg["Content"])
                if version_match:
                    version = version_match.group(1).strip()
                    break
        if f"#version {version}" not in cleaned_code:
            cleaned_code = f"#version {version}\n" + cleaned_code
        
        # 添加main函数
        if "void main()" not in cleaned_code:
            main_function = """
void main() {
    mainImage(fragColor, gl_FragCoord.xy);
}
"""
            cleaned_code += main_function
        
        # 文件名处理
        if not filename:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"shader_{timestamp}.glsl"
        if not filename.endswith(".glsl"):
            filename += ".glsl"
        
        # 保存到纠正后的目标路径
        file_path = self.output_dir / filename
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(cleaned_code)
            logger.info(f"GLSL代码已保存到: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"保存文件失败: {str(e)}")
            raise

    def save_glsl_file(self, glsl_code, filename=None):
        """保存GLSL代码到文件（移除所有清理逻辑）"""
        if not glsl_code:
            raise ValueError("GLSL代码不能为空")
    
        # 版本声明处理
        version = self.default_version
        for msg in self.conversation_history:
            if msg["Role"] == "system":
                version_match = re.search(r'OpenGL\s*([\d]+(?:\s+core)?)', msg["Content"])
                if version_match:
                    version = version_match.group(1).strip()
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
    
        # 保存到文件
        file_path = self.output_dir / filename
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(glsl_code)
            logger.info(f"GLSL代码已保存到: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"保存文件失败: {str(e)}")
            raise

# 在LLM2.py中修改main函数
def main():
    try:
        generator = GLSLGenerator()
        
        print("=" * 60)
        print("欢迎使用GLSL代码生成器")
        print(f"默认配置：代码风格=简洁，GLSL版本=330 core")
        print(f"保存路径：{generator.output_dir}")
        print("提示：如需自定义基础配置，可在效果描述中添加（例：粒子效果，代码风格：详细，GLSL版本：450 core）")
        print("=" * 60)
        
        # 首次生成 - 获取用户输入并保存
        prompt = input("\n请输入所需的效果描述: ")
        # 存储原始提示词用于返回
        original_prompt = prompt  # 新增：保存原始提示词
        
        glsl_code = generator.generate_or_adjust_glsl(prompt=prompt, is_adjust=False)
        
        if not glsl_code:
            print("生成失败，未获取到有效GLSL代码")
            sys.exit(1)
        
        # 展示生成结果（保持不变）
        print("\n生成的GLSL代码:")
        print("-" * 50)
        print(glsl_code)
        print("-" * 50)
        
        # 多轮微调逻辑（保持不变）
        while True:
            adjust_choice = input("\n是否需要调整代码？（输入y/Y进行调整，其他键直接保存）: ").strip().lower()
            if adjust_choice != "y":
                break
            
            adjust_prompt = input("请输入你的微调需求（例：增加颜色饱和度、优化动画流畅度）: ")
            # 更新提示词为微调需求（用于后续可能的多轮传递）
            original_prompt = adjust_prompt  # 新增：更新提示词为最新调整需求
            glsl_code = generator.generate_or_adjust_glsl(prompt=adjust_prompt, is_adjust=True)
            
            if not glsl_code:
                print("调整失败，保留上一版代码")
                continue
            
            print("\n调整后的GLSL代码:")
            print("-" * 50)
            print(glsl_code)
            print("-" * 50)
        
        # 保存最终代码（保持不变）
        filename = input("\n请输入保存的文件名（不输入则自动生成）: ").strip()
        file_path = generator.save_glsl_file(glsl_code, filename if filename else None)
        print(f"\n✅ 代码已成功保存到: {file_path}")
        
        # 新增：返回最终的提示词（可能是原始输入或最后一次调整需求）
        return original_prompt
        
    except Exception as e:
        print(f"\n❌ 发生错误: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()