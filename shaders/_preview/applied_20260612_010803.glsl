#version 330
// AI_PIPELINE_HOOK
// style_profile: minimal
// generated_with: langgraph_agent

// ============================================================
// Blue Danube — Amplitude-Driven Wave Visualization
// 核心逻辑:
//   音频力度(绝对值) → 直接控制波的振幅(幅度)
//   音频力度 → 仅轻微调制频率(±10%)
//   不再用音频驱动抖动，而是让波的大小随音乐起伏
// ============================================================

uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;

out vec4 FragColor;

// ---- 音频采样（独立于 x 位置） ----
float sampleAudio(float t) {
    return texture(iChannel0, vec2(clamp(t, 0.0, 1.0), 0.0)).r;
}

// ---- 平滑阶梯 ----
float smoothStep(float edge0, float edge1, float x) {
    float t = clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0);
    return t * t * (3.0 - 2.0 * t);
}

// ---- 主入口 ----
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    float aspect = iResolution.x / iResolution.y;
    vec2 p = (uv - 0.5) * vec2(aspect, 1.0);

    // ============================================================
    // 1. 音频采样 — 全局力度提取
    // ============================================================
    // 当前时刻的音频幅度（绝对值），用于控制波的振幅
    float ampNow = abs(sampleAudio(0.10));
    float ampMid = abs(sampleAudio(0.35));
    float ampLow = abs(sampleAudio(0.60));

    // 综合力度：音频核心能量
    float energy = ampNow * 0.5 + ampMid * 0.3 + ampLow * 0.2;

    // 平滑力度（防止采样点突变导致画面闪烁）
    float smoothEnergy = energy;
    // 用多次采样平均做简单平滑
    smoothEnergy = (energy 
        + abs(sampleAudio(0.08)) * 0.5 
        + abs(sampleAudio(0.12)) * 0.5) / 2.0;

    // 峰值保持（让波幅衰减更自然）
    float peakEnergy = max(smoothEnergy, 
        abs(sampleAudio(0.10 - 0.02)) * 0.7);

    // ============================================================
    // 2. 背景
    // ============================================================
    vec3 bgTop    = vec3(0.012, 0.015, 0.035);
    vec3 bgBottom = vec3(0.035, 0.045, 0.075);
    vec3 bg = mix(bgBottom, bgTop, uv.y);
    vec3 color = bg;

    // ============================================================
    // 3. 主波形 — 音频力度控制振幅，频率仅受轻微影响
    // ============================================================
    float xPos = uv.x * 2.0 - 1.0; // [-1, 1]

    // --- 3a. 主波形（粗线）---
    {
        // 固定基频（几乎不变），只受能量轻微调制（±8%）
        float baseFreq = 3.5;
        float freqMod = 1.0 + (smoothEnergy - 0.5) * 0.08; // ±4% 变化
        float freq = baseFreq * freqMod;

        // 振幅完全由音频力度控制 —— 这才是核心修改
        // 力度大 → 波幅大，力度小 → 波幅小
        float amplitude = 0.05 + 0.35 * peakEnergy; // 最大振幅 0.40

        // 波形计算：频率基本固定，振幅随音频起伏
        float waveY = sin(xPos * 3.14159 * freq + iTime * 0.5) * amplitude;
        
        // 水平位置微移（极小，仅增加流动感）
        float waveX = cos(xPos * 2.5 * 3.14159 + iTime * 0.15) * 0.01;

        float yPos = waveY;
        vec2 wavePoint = vec2(xPos + waveX, yPos);

        float dist = abs(p.y - yPos);
        float lineWidth = 0.003 + 0.006 * peakEnergy;

        float line = 1.0 - smoothStep(0.0, lineWidth, dist);
        vec3 lineCol = vec3(0.30, 0.60, 1.00) * (0.8 + 0.4 * peakEnergy);
        color = mix(color, lineCol, line * 0.85);

        // 辉光（随音频力度变化）
        float glow = exp(-dist * 45.0) * (0.08 + 0.25 * peakEnergy);
        color += vec3(0.25, 0.55, 0.95) * glow;
    }

    // --- 3b. 辅波形 × 3 层（中高频细节）---
    for (int i = 0; i < 3; i++) {
        float fi = float(i);

        // 不同层的基频
        float baseFreq = 5.5 + fi * 2.0;
        // 频率微调：随音频能量轻微变化（±5%）
        float freqMod = 1.0 + (ampMid - 0.5) * 0.05;
        float freq = baseFreq * freqMod;

        // 振幅由音频力度控制，逐层递减
        float layerEnergy = (i == 0) ? peakEnergy : 
                            (i == 1) ? ampMid * 0.8 : ampLow * 0.6;
        float amplitude = (0.02 + 0.12 * layerEnergy) * (1.0 - fi * 0.15);

        // 相位偏移产生错落感
        float phase = fi * 1.05;

        float waveY = sin(xPos * 3.14159 * freq + iTime * (0.35 + fi * 0.08) + phase) * amplitude;
        float yPos = waveY;

        float dist = abs(p.y - yPos);
        float lineWidth = 0.002 + 0.003 * (1.0 - fi * 0.15);

        float line = 1.0 - smoothStep(0.0, lineWidth, dist);
        vec3 col = mix(vec3(0.20, 0.45, 0.85), vec3(0.45, 0.70, 1.00), fi / 3.0);
        float alpha = 0.35 * (0.5 + 0.5 * layerEnergy);
        color = mix(color, col, line * alpha);

        float glow = exp(-dist * 35.0) * 0.06;
        color += col * glow;
    }

    // ============================================================
    // 4. 径向波纹 — 音频力度控制半径和可见度
    // ============================================================
    {
        float radius = length(p);
        float angle = atan(p.y, p.x);

        // 半径由音频力度控制（力度大 → 波纹扩散更远）
        float radiusScale = 0.15 + 0.25 * peakEnergy;

        // 频率几乎固定
        float ringFreq = 20.0;
        float density = sin(radius * ringFreq * radiusScale - angle * 2.0 + iTime * 0.4) * 0.5 + 0.5;
        density *= 0.5 + 0.5 * sin(radius * 15.0 + angle * 3.0 + iTime * 0.6);

        float ringVisibility = 0.06 + 0.22 * peakEnergy;
        float radiusMask = exp(-radius * 2.8);
        float ring = density * radiusMask * ringVisibility;

        vec3 ringColor = mix(vec3(0.12, 0.35, 0.75), vec3(0.35, 0.65, 1.00), peakEnergy);
        color += ringColor * ring;
    }

    // ============================================================
    // 5. 底部频谱条 — 高度由音频力度控制
    // ============================================================
    {
        float barRegion = smoothStep(0.08, 0.0, abs(p.y + 0.42));
        if (barRegion > 0.0) {
            float barCount = 16.0;
            float barIdx = floor((xPos + 1.0) * 0.5 * barCount);
            float barPos = (barIdx + 0.5) / barCount * 2.0 - 1.0;
            float barCenter = abs(xPos - barPos);

            float freqT = barIdx / barCount;
            float ampVal = abs(sampleAudio(0.02 + freqT * 0.96));
            
            // 高度完全由音频幅度控制
            float barHeight = ampVal * 0.08;

            float inBar = 1.0 - smoothStep(0.0, 0.012, barCenter);
            float inHeight = 1.0 - smoothStep(0.0, barHeight, abs(p.y + 0.42));
            float barMask = inBar * inHeight * barRegion;

            vec3 barColor = mix(
                vec3(0.10, 0.25, 0.60),
                vec3(0.30, 0.60, 1.00),
                freqT
            );
            color = mix(color, barColor, barMask * 0.45);
        }
    }

    // ============================================================
    // 6. 高频星点 — 亮度和数量由高频能量控制
    // ============================================================
    {
        vec2 gridId = floor(p * 22.0);
        vec2 gridPos = fract(p * 22.0) - 0.5;
        float pointDist = length(gridPos);

        float hash = sin(dot(gridId, vec2(12.9898, 78.233))) * 43758.5453;
        hash = fract(hash);

        float hiFreq = abs(sampleAudio(0.72));
        float brightness = smoothStep(0.04, 0.0, pointDist);
        float twinkle = sin(hash * 100.0 + iTime * (2.0 + hiFreq * 3.0)) * 0.5 + 0.5;
        brightness *= twinkle * hiFreq * 0.6;
        brightness *= smoothStep(0.35, 0.0, abs(p.y));

        color += vec3(0.50, 0.70, 1.00) * brightness * 0.30;
    }

    // ============================================================
    // 7. 中心柔光 + 暗角
    // ============================================================
    float radius = length(p);
    float centerGlow = exp(-radius * 3.5) * smoothEnergy * 0.30;
    color += vec3(0.12, 0.35, 0.70) * centerGlow;

    float vignette = 1.0 - 0.22 * radius * radius;
    color *= vignette;
    color = clamp(color, 0.0, 1.0);

    fragColor = vec4(color, 1.0);
}

// ---- 双入口兼容 ----
void main() {
    mainImage(FragColor, gl_FragCoord.xy);
}
