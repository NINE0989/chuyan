// 音频频谱动态线条 | 高对比RGB色差 | 兼容Shadertoy/WebGL
#ifdef GL_ES
precision mediump float;
#endif

// 强制统一采样宏：兼容不同GLSL版本的纹理采样
#ifndef TEX
#ifdef GL_ES
#define TEX(s, uv) texture2D(s, uv)
#else
#define TEX(s, uv) texture(s, uv)
#endif
#endif

// SAFE_MARGIN=0.05 FIT_MODE=INSIDE
#define SAFE_MARGIN 0.05
#define FIT_MODE_INSIDE 1

// AUDIO_ATTACK=0.08 AUDIO_DECAY=0.30 - 攻击0.08s/衰减0.30s（平滑音频响应）
#define AUDIO_ATTACK 0.08
#define AUDIO_DECAY  0.30
#define AUDIO_SMOOTH_K 0.85

// 视觉配置参数（可直接修改调整效果）
#define LINE_COUNT 64
#define BASE_THICKNESS 0.002
#define MAX_THICKNESS 0.012
#define RGB_SHIFT_AMOUNT 0.003
#define GLOW_INTENSITY 1.8
#define MAX_LINE_EXTENT 0.9

// 运行时Uniforms（必须声明）
uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;

// 顶层out变量（仅桌面GL使用，GL_ES下禁用）
#ifndef GL_ES
out vec4 fragColor;
#endif

// 2D哈希函数（用于颜色随机变化）
float hash12(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453123);
}

// 2D旋转函数（用于线条动画）
vec2 rotate2D(vec2 v, float a) {
    float c = cos(a);
    float s = sin(a);
    return vec2(v.x * c - v.y * s, v.x * s + v.y * c);
}

// 线条掩码函数（硬边+可控抗锯齿）
float lineMask(vec2 localPos, float length, float thickness) {
    float dist = abs(localPos.y);
    float along = abs(localPos.x);
    float lengthSmooth = smoothstep(length, length - 0.015, along);
    float thickSmooth = smoothstep(thickness, thickness - 0.0015, dist);
    return lengthSmooth * thickSmooth;
}

// 频谱采样+局部平均（抑制单帧尖峰）
float sampleBand(float u) {
    const int sampleCount = 5;
    float sum = 0.0;
    float step = 0.0035;
    
    for(int i = -sampleCount/2; i <= sampleCount/2; i++) {
        float uu = clamp(u + float(i) * step, 0.0, 1.0);
        sum += TEX(iChannel0, vec2(uu, 0.0)).r;
    }
    
    return sum / float(sampleCount + 1);
}

// 无状态音频平滑策略（兼容无反馈缓冲环境）
float smoothAudioEnergy(float u) {
    float bandEnergy = sampleBand(u);
    float compressed = pow(bandEnergy, 0.65); // 压缩映射减少突变
    
    // 邻域频率近似前一状态，模拟衰减效果
    float prevApprox = (sampleBand(max(u - 0.012, 0.0)) + sampleBand(min(u + 0.012, 1.0))) * 0.5;
    float rateLimit = clamp(1.0 - AUDIO_SMOOTH_K, 0.01, 0.5);
    
    return mix(compressed, prevApprox, rateLimit);
}

// RGB色差分离（增强视觉层次）
vec3 rgbShift(vec3 color, vec2 uv, float mask) {
    float shift = RGB_SHIFT_AMOUNT * mask;
    vec2 dir = normalize(uv) * shift;
    return vec3(
        color.r * smoothstep(length(dir), 0.0, mask),
        color.g * smoothstep(length(dir) * 0.8, 0.0, mask),
        color.b * smoothstep(length(dir) * 1.2, 0.0, mask)
    );
}

// 屏幕辉光效果（近似屏幕混合）
vec3 addGlow(vec3 color, float mask, float energy) {
    float glow = pow(mask, 0.2) * energy * GLOW_INTENSITY;
    return clamp(color + color * glow, 0.0, 1.0);
}

// 静默状态颜色（低强度基础效果）
vec3 idleColor(vec2 uv, float time) {
    float angle = atan(uv.y, uv.x);
    float lineIdx = floor(angle / (6.283 / float(LINE_COUNT))) / float(LINE_COUNT);
    float hue = fract(lineIdx * 1.0 + time * 0.05);
    vec3 hsv = vec3(hue, 0.7, 0.15);
    
    vec4 K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
    vec3 p = abs(fract(hsv.xxx + K.xyz) * 6.0 - K.www);
    return hsv.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), hsv.y);
}

// 音频驱动颜色（随频谱动态变化）
vec3 audioColor(vec2 uv, float time, float lineIdx, float energy) {
    float hue = fract(lineIdx * 1.3 + time * 0.2 + hash12(vec2(lineIdx, time * 0.1)) * 0.4);
    vec3 hsv = vec3(hue, 0.9, 0.95 * energy);
    
    vec4 K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
    vec3 p = abs(fract(hsv.xxx + K.xyz) * 6.0 - K.www);
    return hsv.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), hsv.y);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // 中心化+短边归一化坐标（保证不同宽高比兼容）
    vec2 center = 0.5 * iResolution.xy;
    float scale = min(iResolution.x, iResolution.y);
    vec2 uv = (fragCoord - center) / scale;
    float maxSafeRadius = 1.0 - SAFE_MARGIN;
    
    vec3 finalColor = vec3(0.0);
    float masterEnergy = smoothAudioEnergy(0.5); // 整体能量（中频段参考）
    float activity = smoothstep(0.0, 0.02, masterEnergy); // 静默→激活过渡因子
    
    // 循环绘制频谱驱动线条
    for(int i = 0; i < LINE_COUNT; i++) {
        float lineIdx = float(i) / float(LINE_COUNT);
        float freq = lineIdx; // 线条索引映射到频率[0,1]
        
        // 采样对应频段的平滑能量
        float bandEnergy = smoothAudioEnergy(freq);
        float smoothE = mix(0.03, bandEnergy * 2.2, activity); // 平滑能量映射
        
        // 线条参数（随音频和频段动态调整）
        float angle = lineIdx * 6.28318 + iTime * 0.12;
        float lineLength = clamp(smoothE * MAX_LINE_EXTENT * maxSafeRadius, 0.05, maxSafeRadius);
        float thickness = mix(BASE_THICKNESS, MAX_THICKNESS, smoothE * (freq * 0.6 + 0.4));
        
        // 旋转坐标以匹配线条角度
        vec2 rotatedUV = rotate2D(uv, -angle);
        
        // 计算线条掩码（硬边+抗锯齿）
        float mask = lineMask(rotatedUV, lineLength, thickness);
        if(mask < 0.01) continue; // 跳过微弱像素，优化性能
        
        // 混合静默/音频状态颜色
        vec3 idleCol = idleColor(rotatedUV, iTime);
        vec3 audioCol = audioColor(rotatedUV, iTime, lineIdx, smoothE);
        vec3 lineColor = mix(idleCol, audioCol, activity);
        
        // 应用RGB色差和辉光
        lineColor = rgbShift(lineColor, rotatedUV, mask);
        lineColor = addGlow(lineColor, mask, smoothE);
        
        // 累积线条颜色（避免过曝）
        finalColor = clamp(finalColor + lineColor * mask, 0.0, 1.0);
    }
    
    // 安全区域外强制纯黑（严格遵守布局保护）
    float safeMask = step(length(uv), maxSafeRadius + 0.01);
    finalColor *= safeMask;
    
    fragColor = vec4(finalColor, 1.0);
}

// 适配器函数（兼容GL_ES和桌面GL）
void main() {
#ifdef GL_ES
    vec4 result;
    mainImage(result, gl_FragCoord.xy);
    gl_FragColor = result;
#else
    mainImage(fragColor, gl_FragCoord.xy);
#endif
}