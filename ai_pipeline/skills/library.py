"""可组合的技能模板与加载器。"""
from __future__ import annotations

from ai_pipeline.types import SkillSpec


SKILL_LIBRARY: dict[str, SkillSpec] = {
    "geometry_sdf": SkillSpec(
        name="geometry_sdf",
        inputs=["geometry_targets"],
        template=(
            "几何构建建议：使用 SDF 基元（circle/box/segment/polygon）、"
            "smooth min 布尔融合、极坐标重复与旋转变换。"
        ),
        post_rules=["必须保留可编译 mainImage 入口"],
    ),
    "audio_visualization": SkillSpec(
        name="audio_visualization",
        inputs=["audio_profile"],
        template=(
            "音频可视化建议：分带采样低中高频，叠加频谱柱状、径向脉冲、"
            "波形描边，加入峰值保持与时间衰减。"
        ),
        post_rules=["必须引用 iChannel0"],
    ),
    "style_specialization": SkillSpec(
        name="style_specialization",
        inputs=["style_profile"],
        template="风格特化建议：依据 style_profile 调整配色、噪声纹理、光晕与运动节奏。",
        post_rules=["不可删除核心 ShaderToy uniform"],
    ),
    "badcase_guard": SkillSpec(
        name="badcase_guard",
        inputs=["constraints"],
        template=(
            "坏例规避建议：避免未声明 uniform、避免数组越界、避免 NaN 传播，"
            "保证纹理采样坐标在[0,1]范围。"
        ),
        post_rules=["输出 diagnostics 说明潜在风险"],
    ),
}


def build_skill_prompt(skill_names: list[str]) -> str:
    """根据技能名称拼接提示模板。"""
    chunks: list[str] = []
    for name in skill_names:
        spec = SKILL_LIBRARY.get(name)
        if spec is None:
            continue
        chunks.append(f"[{spec.name}] {spec.template}")
    return "\n".join(chunks)
