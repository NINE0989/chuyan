#version 330
// AI_PIPELINE_HOOK
// style_profile: minimal
// generated_with: langgraph_agent

uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;  // 音频纹理
uniform sampler2D iChannel1;  // 手势交互纹理（预留）

out vec4 FragColor;

// ---- 工具函数 ----
float hash21(vec2 p) {
    p = fract(p * vec2(234.34, 435.345));
    p += dot(p, p + 19.19);
    return fract(p.x * p.y);
}

// 2D 旋转矩阵
mat2 rot(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, -s, s, c);
}

// 圆 SDF
float sdCircle(vec2 p, float r) {
    return length(p) - r;
}

// 菱形 SDF
float sdDiamond(vec2 p, float s) {
    return abs(p.x) + abs(p.y) - s;
}

// 星形 SDF (简化版)
float sdStar(vec2 p, float r, float spikes) {
    float a = atan(p.y, p.x);
    float n = spikes;
    float d = cos(floor(0.5 + a * n / 6.2832) * 6.2832 / n - a) * r;
    return length(p) - d * 0.5;
}

// 方形 SDF
float sdBox(vec2 p, vec2 b) {
    vec2 d = abs(p) - b;
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
}

// 获取音频采样（低频/中频/高频）
void getAudioSamples(out float bass, out float mid, out float treble) {
    float sumBass = 0.0, sumMid = 0.0, sumTreble = 0.0;
    int bassSteps = 8, midSteps = 16, trebleSteps = 16;
    
    for (int i = 0; i < 32; i++) {
        float t = float(i) / 32.0;
        vec4 s = texture(iChannel0, vec2(t, 0.0));
        float v = (s.x + s.y + s.z + s.w) * 0.25;
        if (i < bassSteps) sumBass += v;
        else if (i < bassSteps + midSteps) sumMid += v;
        else sumTreble += v;
    }
    
    bass = sumBass / float(bassSteps);
    mid = sumMid / float(midSteps);
    treble = sumTreble / float(trebleSteps);
}

// 手势交互层 - 从 iChannel1 读取
vec2 getGesture(vec2 uv) {
    vec4 g = texture(iChannel1, uv);
    // 返回手势位置偏移和强度
    return vec2(g.x * 2.0 - 1.0, g.y * 2.0 - 1.0) * g.z;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / min(iResolution.x, iResolution.y);
    
    // 获取音频
    float bass, mid, treble;
    getAudioSamples(bass, mid, treble);
    
    // 圆舞曲 3/4 拍节奏 - 使用时间产生旋转
    float waltzBeat = sin(iTime * 1.5 * 3.14159 * 2.0) * 0.5 + 0.5;
    float waltzPhase = iTime * 0.8;
    
    // 手势交互偏移（预留层）
    vec2 gestureOffset = getGesture(uv);
    // 手势影响轻微偏移
    uv += gestureOffset * 0.05;
    
    // ---- 构建网格小元素 ----
    float gridSize = 6.0 + mid * 2.0;  // 中频影响网格密度
    vec2 gv = uv * gridSize;
    vec2 id = floor(gv);
    vec2 p = fract(gv) - 0.5;
    
    // 每个格子随机旋转
    float rotAngle = hash21(id) * 6.2832 + waltzPhase * 0.2;
    p *= rot(rotAngle);
    
    // 每个格子的随机元素类型
    float type = hash21(id + 0.5);
    // 每个格子的随机颜色
    vec3 colorBase = 0.5 + 0.5 * sin(hash21(id + 1.0) * 6.2832 + vec3(0.0, 2.0, 4.0));
    
    // 元素大小 - 受低频（bass）和圆舞曲节奏影响
    float sizeBase = 0.25 + 0.15 * sin(iTime * 1.5 + hash21(id) * 6.2832);
    float size = sizeBase + bass * 0.2 + waltzBeat * 0.1;
    size = clamp(size, 0.05, 0.45);
    
    // 元素形状随中频变化
    float shapeBlend = mid * 0.8 + 0.1 * sin(iTime * 2.0 + id.x * 3.0);
    shapeBlend = clamp(shapeBlend, 0.0, 1.0);
    
    // 计算各形状 SDF
    float dCircle = sdCircle(p, size);
    float dDiamond = sdDiamond(p, size);
    float dBox = sdBox(p, vec2(size * 0.8));
    float dStar = sdStar(p, size, 5.0 + treble * 4.0);
    
    // 形状随时间渐变 - 在圆形和其他形状之间混合
    float morphFactor = 0.5 + 0.5 * sin(iTime * 0.5 + id.x * 2.0 + id.y * 3.0);
    float d;
    if (type < 0.5) {
        d = mix(dCircle, dDiamond, morphFactor * shapeBlend);
    } else {
        d = mix(dBox, dStar, morphFactor * shapeBlend);
    }
    
    // 元素发光/辉光效果
    float glow = exp(-abs(d) * 4.0) * (0.5 + treble * 0.5);
    
    // 元素颜色 - 受音频影响
    vec3 col = colorBase;
    // 低频影响亮度
    col *= 0.8 + bass * 0.4;
    // 中频影响色相偏移
    col += vec3(0.1, 0.05, 0.15) * mid;
    // 高频增加高光
    col += vec3(0.3, 0.2, 0.1) * treble * glow;
    
    // 元素主体
    float mask = 1.0 - smoothstep(0.0, 0.02, d);
    vec3 elementColor = col * mask;
    
    // 辉光叠加
    vec3 glowColor = col * 1.5 * glow * (1.0 - mask);
    
    // ---- 背景 ----
    // 径向渐变背景，带轻微的圆舞曲旋转感
    float bgAngle = atan(uv.y, uv.x) + waltzPhase * 0.1;
    float bgRadial = length(uv);
    vec3 bgColor = vec3(0.95, 0.97, 1.0) - bgRadial * 0.3;
    bgColor += vec3(0.05, 0.02, 0.08) * (0.5 + 0.5 * sin(bgAngle * 3.0 + iTime * 0.3));
    
    // 背景上淡淡的音频波纹
    float wave = sin(length(uv) * 20.0 - iTime * 3.0 + bass * 5.0) * 0.03;
    bgColor += wave * (0.5 + 0.5 * bass);
    
    // ---- 合成 ----
    vec3 finalColor = bgColor;
    // 叠加元素
    finalColor = mix(finalColor, elementColor, mask);
    // 叠加辉光
    finalColor += glowColor * 0.6;
    
    // 手势交互层可视化（半透明提示层 - 仅在手势有输入时显示）
    float gestureStrength = length(gestureOffset);
    if (gestureStrength > 0.01) {
        // 手势位置显示一个小光点
        float gd = length(uv - gestureOffset * 0.5);
        float gGlow = exp(-gd * 10.0) * 0.3;
        finalColor += vec3(0.2, 0.5, 0.8) * gGlow;
    }
    
    // 轻微晕影
    float vignette = 1.0 - length(uv) * 0.3;
    finalColor *= vignette;
    
    fragColor = vec4(finalColor, 1.0);
}

void main() {
    vec4 color;
    mainImage(color, gl_FragCoord.xy);
    FragColor = color;
}