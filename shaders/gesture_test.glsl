// gesture_focus.glsl
// 最小可用示例：读取 iHandPos 和 iHandAction
#version 330 core

#ifdef GL_ES
precision mediump float;
#endif

uniform vec3 iResolution; // x,y = 分辨率, z unused
uniform float iTime;
uniform vec3 iHandPos;    // normalized 手势坐标 (0..1): x, y, z
uniform float iHandAction; // 手势强度 (0..1)，捏合越紧越接近 1.0

out vec4 fragColor;

// 简单伽马校正
vec3 tone(vec3 c){ return pow(clamp(c,0.0,1.0), vec3(0.8)); }

void mainImage(out vec4 o, in vec2 fragCoord){
    vec2 uv = fragCoord.xy / iResolution.xy;

    // 手势位置在 iHandPos.xy（0..1），y 在 tracker 中已做 1.0 - y 处理
    vec2 hand_uv = clamp(iHandPos.xy, 0.0, 1.0);

    // 根据捏合强度缩放半径（捏合越紧，焦点越集中）
    float minR = 0.022;
    float maxR = 0.22;
    float radius = mix(maxR, minR, iHandAction);

    // 发光强度随捏合强度增强
    float glow = mix(0.8, 4.0, iHandAction);

    float d = distance(uv, hand_uv);

    // 更强的中心光斑，适合快速判断是否捕捉到了手
    float core = exp(-pow(d / max(radius * 0.42, 0.0001), 2.0) * 2.4);

    // 外围柔和光晕
    float halo = exp(-pow(d / max(radius, 0.0001), 2.0) * 0.7);

    // 双层高亮环，强调位置变化和捏合强度
    float ring1 = smoothstep(radius * 1.08, radius * 0.98, d) - smoothstep(radius * 1.24, radius * 1.10, d);
    float ring2 = smoothstep(radius * 0.82, radius * 0.72, d) - smoothstep(radius * 0.95, radius * 0.85, d);
    float rings = ring1 * 1.2 + ring2 * 0.75;

    // 方向性十字，帮助肉眼看出手势中心点
    vec2 q = abs(uv - hand_uv);
    float cross = exp(-q.x * 130.0) * exp(-q.y * 5.0) + exp(-q.y * 130.0) * exp(-q.x * 5.0);
    cross *= 0.22 + 0.6 * iHandAction;

    // 动态色相随时间与手势强度微动
    float hue = fract(0.08 * iTime + iHandAction * 0.25);
    vec3 base_col = vec3(0.5 + 0.5 * sin(hue * 6.2831 + vec3(0.0, 2.0, 4.0)));
    vec3 accent = mix(vec3(0.18, 0.72, 1.0), vec3(1.0, 0.35, 0.18), iHandAction);

    vec3 col = base_col * (halo * glow * 0.55 + core * 2.2) + accent * (rings + cross);

    // 更明显的背景渐变和暗角
    vec2 p = uv * 2.0 - 1.0;
    float vignette = smoothstep(1.25, 0.15, dot(p, p));
    vec3 bg = mix(vec3(0.015, 0.015, 0.02), vec3(0.03, 0.045, 0.06), uv.y);
    bg *= 0.55 + 0.45 * vignette;

    o = vec4(tone(bg + col), 1.0);
}

void main(){
    mainImage(fragColor, gl_FragCoord.xy);
}
