#version 330

// ============================================================
// 主包络 + 距离衰减平滑振幅
// 核心:
//   1. 双边滑动平均滤波 — 消除突兀跳变
//   2. 中心主包络 = 滤波后音频能量，控制全局振幅
//   3. 辅波形振幅按距中心距离平滑衰减
//   4. 频率仅受包络极轻微影响（<3%）
// ============================================================

uniform vec3  iResolution;
uniform float iTime;
uniform sampler2D iChannel0;

out vec4 FragColor;

// ---- 安全音频采样 ----
float sampleAudio(float t) {
    return texture(iChannel0, vec2(clamp(t, 0.0, 1.0), 0.0)).r;
}

float absSample(float t) {
    return abs(sampleAudio(t));
}

// ---- 双边滑动平均滤波（5点三角权重） ----
float smoothAudio(float t) {
    float sum = 0.0;
    float weights = 0.0;
    for (int i = -2; i <= 2; i++) {
        float fi = float(i);
        float w = 1.0 - abs(fi) * 0.2;
        sum += absSample(t + fi * 0.005) * w;
        weights += w;
    }
    return sum / weights;
}

// ---- 主入口 ----
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    float aspect = iResolution.x / iResolution.y;
    vec2 p = (uv - 0.5) * vec2(aspect, 1.0);
    float xPos = p.x;
    float radius = length(p);

    // ============================================================
    // 1. 音频包络提取
    // ============================================================
    // 主包络 — 中心位置的平滑音频值，控制全局波幅
    float mainEnv = smoothAudio(0.50);
    
    // 侧边包络 — 左右两侧，用于距离衰减
    float leftEnv  = smoothAudio(0.25);
    float rightEnv = smoothAudio(0.75);
    float bassEnv  = smoothAudio(0.05);
    float highEnv  = smoothAudio(0.85);

    // 全局能量（背景氛围用）
    float energy = 0.0;
    for (int i = 0; i < 8; i++) {
        energy += smoothAudio(float(i) / 8.0);
    }
    energy /= 8.0;
    energy = clamp(energy, 0.0, 1.0);

    // ============================================================
    // 2. 背景 — minimal 深色渐变
    // ============================================================
    vec3 bgTop    = vec3(0.008, 0.010, 0.025);
    vec3 bgBottom = vec3(0.025, 0.035, 0.060);
    vec3 bg = mix(bgBottom, bgTop, uv.y);
    vec3 color = bg;

    // ============================================================
    // 3. 主波形 — 主包络驱动振幅，频率固定 + 极小调制
    // ============================================================
    vec3 mainWaveCol = vec3(0.22, 0.55, 1.00);
    
    {
        // 振幅由主包络控制（平滑后的音频力度）
        float amplitude = 0.20 * mainEnv;
        
        // 频率基本固定，仅受 < 2% 的包络影响
        float freq = 4.0 * (1.0 + 0.02 * mainEnv);
        float phase = 0.01 * bassEnv * sin(iTime * 0.15);
        
        // 波形高度 = 振幅 × 正弦波
        float wave = sin(xPos * freq * 3.14159 + iTime * 0.45 + phase);
        float yPos = amplitude * wave;
        
        // 描边
        float dist = abs(p.y - yPos);
        float lineWidth = 0.004 + 0.006 * mainEnv;
        float line = 1.0 - smoothstep(0.0, lineWidth, dist);
        vec3 lineCol = mainWaveCol * (0.8 + 0.6 * mainEnv);
        color = mix(color, lineCol, line * 0.80);
        
        // 发光
        float glow = exp(-dist * 50.0) * (0.05 + 0.20 * mainEnv);
        color += mainWaveCol * glow * 0.30;
    }

    // ============================================================
    // 4. 辅波形 × 3 层 — 按距中心距离平滑衰减振幅
    // ============================================================
    for (int i = 0; i < 3; i++) {
        float fi = float(i);
        
        // 距离因子：越远离中心，衰减越明显
        float distFactor = 1.0 - fi * 0.30;
        distFactor = max(distFactor, 0.05);
        
        // 包络混合：近层用主包络，远层混合侧边包络
        float envMix = 1.0 - fi * 0.25;
        float layerEnv = mix(leftEnv * rightEnv, mainEnv, envMix);
        
        // 振幅 = 包络 × 距离衰减
        float amplitude = (0.04 + 0.08 * layerEnv) * distFactor;
        
        // 频率
        float baseFreq = 5.0 + fi * 2.5;
        float freq = baseFreq * (1.0 + 0.02 * layerEnv);
        float phase = fi * 1.10 + 0.01 * highEnv * sin(iTime * (0.4 + fi * 0.2));
        
        float wave = sin(xPos * freq * 3.14159 + iTime * (0.55 + fi * 0.15) + phase);
        float yPos = amplitude * wave;
        
        float dist = abs(p.y - yPos);
        float lineWidth = 0.002 + 0.003 * distFactor;
        float line = 1.0 - smoothstep(0.0, lineWidth, dist);
        
        vec3 col = mix(vec3(0.15, 0.40, 0.80), vec3(0.35, 0.65, 1.00), fi / 3.0);
        float alpha = 0.35 * distFactor * (0.5 + 0.5 * layerEnv);
        color = mix(color, col, line * alpha);
        
        float glow = exp(-dist * 40.0) * 0.04 * distFactor;
        color += col * glow;
    }

    // ============================================================
    // 5. 径向环 — 包络控制密度
    // ============================================================
    {
        float angle = atan(p.y, p.x);
        
        // 环密度由主包络控制，距离中心衰减
        float ringFreq = 20.0 + 4.0 * bassEnv;
        float density = sin(radius * ringFreq + angle * 3.0 + iTime * 0.30) * 0.5 + 0.5;
        density *= sin(radius * 14.0 - angle * 2.0 + iTime * 0.45) * 0.5 + 0.5;
        
        float radiusFalloff = exp(-radius * 2.5) * (1.0 - radius * 0.3);
        float ringAlpha = density * radiusFalloff * (0.08 + 0.20 * mainEnv);
        
        vec3 ringCol = mix(vec3(0.08, 0.25, 0.65), vec3(0.25, 0.55, 1.00), mainEnv);
        color += ringCol * ringAlpha;
    }

    // ============================================================
    // 6. 底部频谱条
    // ============================================================
    {
        float barRegion = smoothstep(0.05, 0.0, abs(p.y + 0.42));
        if (barRegion > 0.0) {
            float barCount = 16.0;
            float barIdx = floor((xPos + 1.0) * 0.5 * barCount);
            float barPos = (barIdx + 0.5) / barCount * 2.0 - 1.0;
            float barCenter = abs(xPos - barPos);
            
            float freqT = barIdx / barCount;
            float ampVal = smoothAudio(0.02 + freqT * 0.96);
            
            float barHeight = ampVal * 0.06;
            
            float inBar = 1.0 - smoothstep(0.0, 0.008, barCenter);
            float inHeight = 1.0 - smoothstep(0.0, barHeight, abs(p.y + 0.42));
            float barMask = inBar * inHeight * barRegion;
            
            vec3 barCol = mix(vec3(0.06, 0.18, 0.50), vec3(0.22, 0.52, 1.00), freqT);
            color = mix(color, barCol, barMask * 0.35);
        }
    }

    // ============================================================
    // 7. 星点 — 高频驱动微弱闪烁
    // ============================================================
    {
        vec2 gridId = floor(p * 24.0);
        vec2 gridPos = fract(p * 24.0) - 0.5;
        float pointDist = length(gridPos);
        
        float hash = fract(sin(dot(gridId, vec2(12.9898, 78.233))) * 43758.5453);
        
        float brightness = smoothstep(0.04, 0.0, pointDist);
        float twinkle = sin(hash * 100.0 + iTime * (1.5 + highEnv * 3.0)) * 0.5 + 0.5;
        brightness *= twinkle * highEnv * 0.4;
        brightness *= smoothstep(0.30, 0.0, abs(p.y));
        
        color += vec3(0.40, 0.65, 1.00) * brightness * 0.20;
    }

    // ============================================================
    // 8. 中心柔光 + 暗角
    // ============================================================
    float centerGlow = exp(-radius * 3.5) * energy * 0.18;
    color += vec3(0.08, 0.28, 0.60) * centerGlow;
    
    float vignette = 1.0 - 0.18 * radius * radius;
    color *= vignette;
    color = clamp(color, 0.0, 1.0);
    
    fragColor = vec4(color, 1.0);
}

// ---- 双入口兼容 ----
void main() {
    mainImage(FragColor, gl_FragCoord.xy);
}
