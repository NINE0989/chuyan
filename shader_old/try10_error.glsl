// 横向频谱起伏线 | 高对比彩色 | Target: generic | Estimated texture samples per pixel: ~1
#ifdef GL_ES
precision mediump float;
#endif

// 强制统一采样宏：兼容不同GLSL版本
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

// 性能与视觉参数（保守默认值，保证实时性）
#define LINE_COUNT 32          // 横向线条数量
#define DEFAULT_BANDS 32       // 频谱预采样频段数
#define SAMPLE_COUNT 3         // 每个频段邻域采样数
#define BASE_THICKNESS 0.003   // 线条基础厚度
#define MAX_THICKNESS 0.015    // 线条最大厚度
#define RGB_SHIFT 0.002        // RGB色差偏移量
#define GLOW_INTENSITY 1.2     // 辉光强度
#define MAX_LINE_HEIGHT 0.4    // 线条最大起伏高度

// 运行时Uniforms
uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;

// 顶层out变量（仅桌面GL使用）
#ifndef GL_ES
out vec4 fragColor;
#endif

// 2D哈希函数（用于颜色随机变化）
float hash12(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453123);
}

// 线条掩码函数（硬边+可控抗锯齿）
float lineMask(vec2 uv, float lineY, float halfHeight, float thickness) {
    float yDist = abs(uv.y - lineY);
    float thickMask = smoothstep(thickness, thickness - 0.001, yDist);
    float xMask = smoothstep(halfHeight, halfHeight - 0.01, abs(uv.x));
    return thickMask * xMask;
}

// 采样频段中心（邻域平均，抑制尖峰）
float sampleBandCenter(int bandIdx, int totalBands) {
    float u = float(bandIdx) / float(totalBands);
    float sum = 0.0;
    float step = 0.002;
    
    for(int i = -SAMPLE_COUNT/2; i <= SAMPLE_COUNT/2; i++) {
        float uu = clamp(u + float(i) * step, 0.0, 1.0);
        sum += TEX(iChannel0, vec2(uu, 0.0)).r;
    }
    
    return sum / float(SAMPLE_COUNT);
}

// 无状态音频平滑策略（兼容无反馈缓冲）
float smoothAudioEnergy(float target, float prevApprox) {
    float compressed = pow(target, 0.65);
    float rateLimit = clamp(1.0 - AUDIO_SMOOTH_K, 0.01, 0.5);
    return mix(compressed, prevApprox, rateLimit);
}

// RGB色差分离（增强视觉层次）
vec3 rgbShift(vec3 color, vec2 uv, float mask) {
    float shift = RGB_SHIFT * mask;
    return vec3(
        color.r * smoothstep(shift, 0.0, mask),
        color.g * smoothstep(shift * 0.8, 0.0, mask),
        color.b * smoothstep(shift * 1.2, 0.0, mask)
    );
}

// 辉光效果（低开销近似）
vec3 addGlow(vec3 color, float mask, float energy) {
    float glow = pow(mask, 0.3) * energy * GLOW_INTENSITY;
    return clamp(color + color * glow, 0.0, 1.0);
}

// 静默状态颜色（低强度基础效果）
vec3 idleColor(float lineIdx, float time) {
    float hue = fract(lineIdx * 0.8 + time * 0.05);
    vec3 hsv = vec3(hue, 0.6, 0.1);
    
    vec4 K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
    vec3 p = abs(fract(hsv.xxx + K.xyz) * 6.0 - K.www);
    return hsv.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), hsv.y);
}

// 音频驱动颜色（随频谱动态变化）
vec3 audioColor(float lineIdx, float energy, float time) {
    float hue = fract(lineIdx * 1.1 + time * 0.2 + hash12(vec2(lineIdx, time * 0.1)) * 0.5);
    vec3 hsv = vec3(hue, 0.9, 0.9 * energy);
    
    vec4 K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
    vec3 p = abs(fract(hsv.xxx + K.xyz) * 6.0 - K.www);
    return hsv.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), hsv.y);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // 中心化+短边归一化坐标（兼容任意宽高比）
    vec2 center = 0.5 * iResolution.xy;
    float scale = min(iResolution.x, iResolution.y);
    vec2 uv = (fragCoord - center) / scale;
    float maxSafe = 1.0 - SAFE_MARGIN;
    
    // 频谱预采样（一次性采样所有频段，减少纹理访问）
    float bands[DEFAULT_BANDS];
    float prevBands[DEFAULT_BANDS];
    for(int i = 0; i < DEFAULT_BANDS; i++) {
        bands[i] = sampleBandCenter(i, DEFAULT_BANDS);
        // 邻域近似前一频段能量，用于平滑
        prevBands[i] = (i > 0) ? bands[i-1] : bands[0];
    }
    
    vec3 finalColor = vec3(0.0);
    float masterEnergy = smoothAudioEnergy(bands[DEFAULT_BANDS/2], prevBands[DEFAULT_BANDS/2]);
    float activity = smoothstep(0.0, 0.02, masterEnergy); // 静默→激活过渡
    
    // 早期剔除：只处理当前像素附近的3条线（优化性能）
    float lineSpacing = (maxSafe * 1.8) / float(LINE_COUNT - 1);
    float lineYBase = -maxSafe * 0.9;
    int closestLine = int((uv.y - lineYBase) / lineSpacing + 0.5);
    closestLine = clamp(closestLine, 0, LINE_COUNT - 1);
    
    // 处理当前线及上下各1条线，共3条（减少循环次数）
    for(int offset = -1; offset <= 1; offset++) {
        int lineIdx = closestLine + offset;
        if(lineIdx < 0 || lineIdx >= LINE_COUNT) continue;
        
        float lineNorm = float(lineIdx) / float(LINE_COUNT - 1);
        int bandIdx = clamp(lineIdx * DEFAULT_BANDS / LINE_COUNT, 0, DEFAULT_BANDS - 1);
        
        // 平滑频段能量
        float bandEnergy = bands[bandIdx];
        float prevEnergy = prevBands[bandIdx];
        float smoothE = smoothAudioEnergy(bandEnergy, prevEnergy);
        smoothE = mix(0.05, smoothE * 1.8, activity);
        
        // 线条参数（横向从左到右，y位置固定，高度随能量变化）
        float lineY = lineYBase + lineIdx * lineSpacing;
        float lineHalfHeight = maxSafe * 0.9; // 横向全长（左到右）
        float lineThickness = mix(BASE_THICKNESS, MAX_THICKNESS, smoothE * (lineNorm * 0.5 + 0.5));
        
        // 早期几何剔除：距离线条过远直接跳过
        float yDist = abs(uv.y - lineY);
        if(yDist > lineThickness + 0.002) continue;
        
        // 计算线条掩码
        float mask = lineMask(uv, lineY, lineHalfHeight, lineThickness);
        if(mask < 0.01) continue;
        
        // 混合静默/音频颜色
        vec3 idleCol = idleColor(lineNorm, iTime);
        vec3 audioCol = audioColor(lineNorm, smoothE, iTime);
        vec3 lineColor = mix(idleCol, audioCol, activity);
        
        // 应用RGB色差和辉光
        lineColor = rgbShift(lineColor, uv, mask);
        lineColor = addGlow(lineColor, mask, smoothE);
        
        // 累积颜色（避免过曝）
        finalColor = clamp(finalColor + lineColor * mask, 0.0, 1.0);
    }
    
    // 安全区域外强制纯黑
    float safeMask = step(length(uv), maxSafe + 0.01);
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