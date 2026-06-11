#version 330

// ============================================================
// Blue Danube — Minimal Audio Visualization
// 风格: minimal / 极简
// 概念: 蓝色河流上的音符律动
// 频段: 低频(弦乐铺垫) → 主波形幅度
//       中频(主旋律)   → 波纹细节密度
//       高频(泛音点缀) → 辉光闪烁
// ============================================================

uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;

out vec4 FragColor;

// ---- 工具函数 ----

// 安全音频采样（带clamp）
float sampleAudio(float t) {
    return texture(iChannel0, vec2(clamp(t, 0.0, 1.0), 0.0)).r;
}

// 平滑阶梯
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
    // 1. 音频分带采样（带时间微移，丰富动态）
    // ============================================================
    float bass   = sampleAudio(0.05 + 0.01 * sin(iTime * 0.13));
    float mid    = sampleAudio(0.38 + 0.01 * sin(iTime * 0.21));
    float treble = sampleAudio(0.78 + 0.01 * sin(iTime * 0.29));

    // 峰值保持近似（用慢速采样模拟）
    float bassPeak = max(bass, sampleAudio(0.05 + 0.005 * sin(iTime * 0.07)));

    // 综合能量
    float energy = bass * 0.50 + mid * 0.35 + treble * 0.15;

    // ============================================================
    // 2. 背景 — 深蓝灰垂直渐变（Minimal 干净背景）
    // ============================================================
    vec3 bgTop    = vec3(0.020, 0.022, 0.045);
    vec3 bgBottom = vec3(0.045, 0.055, 0.090);
    vec3 bg = mix(bgBottom, bgTop, uv.y);
    vec3 color = bg;

    // ============================================================
    // 3. 主波形 — 横跨屏幕的优雅波浪（"多瑙河河面"）
    // ============================================================
    vec3 waveColor = vec3(0.35, 0.65, 1.00); // 淡蓝
    float xPos = uv.x * 2.0 - 1.0; // [-1, 1]

    // 多层波形叠加
    for (int i = 0; i < 4; i++) {
        float fi = float(i);

        // 频率逐层递增
        float freq = 2.5 + fi * 1.8;
        // 幅度由低频控制
        float amp = (0.06 + 0.10 * bassPeak) * (1.0 - fi * 0.12);
        // 相位偏移
        float phase = fi * 1.57;

        // 基波 + 谐波（中频调制细节）
        float wave = sin(xPos * freq * 3.14159 + iTime * 0.60 + phase);
        wave += sin(xPos * freq * 2.0 * 3.14159 + iTime * 0.90 + phase * 1.5) * (0.15 + 0.25 * mid);
        wave *= amp;

        // 波形在屏幕中的垂直位置
        float yPos = 0.0 + wave;

        // 到波形的距离
        float dist = abs(p.y - yPos);
        float lineWidth = 0.0025 + 0.0030 * treble;

        // --- 线条主体 ---
        float line = 1.0 - smoothStep(0.0, lineWidth, dist);
        vec3 lineCol = waveColor * (1.0 + treble * 0.6);
        color = mix(color, lineCol, line * 0.85);

        // --- 柔和辉光 ---
        float glow = exp(-dist * 60.0) * (0.15 + 0.20 * bass);
        color += waveColor * glow * 0.35;
    }

    // ============================================================
    // 4. 径向脉冲环 — 从中心扩散的节奏感
    // ============================================================
    float radius = length(p);
    // 环的位置由低频推动
    float ringRadius = 0.15 + 0.20 * bass + 0.05 * sin(iTime * 1.2);

    // 多环
    for (int i = 0; i < 3; i++) {
        float fi = float(i);
        float r = ringRadius * (1.0 + fi * 0.6) + fi * 0.05;
        float ringWidth = 0.004 + 0.006 * (1.0 - fi * 0.2);

        float ringDist = abs(radius - r);
        float ring = 1.0 - smoothStep(0.0, ringWidth, ringDist);
        ring *= smoothStep(r * 0.8, r * 1.2, radius); // 外淡内浓

        vec3 ringColor = mix(vec3(0.20, 0.50, 0.90), vec3(0.50, 0.80, 1.00), fi / 3.0);
        color = mix(color, ringColor, ring * 0.25 * (0.50 + 0.50 * bass));
    }

    // ============================================================
    // 5. 底部频谱条 — 极简低调的频谱显示
    // ============================================================
    {
        // 仅在底部 8% 区域显示
        float barRegion = smoothStep(0.08, 0.0, abs(p.y + 0.42));
        if (barRegion > 0.0) {
            // 15段频谱
            float barCount = 15.0;
            float barIdx = floor((xPos + 1.0) * 0.5 * barCount);
            float barPos = (barIdx + 0.5) / barCount * 2.0 - 1.0;
            float barCenter = abs(xPos - barPos);

            // 每段对应不同频率
            float freqT = barIdx / barCount;
            float ampVal = sampleAudio(0.02 + freqT * 0.96);

            // 峰值保持衰减
            float ampPeak = max(ampVal, sampleAudio(0.02 + freqT * 0.96 - 0.005));

            float barHeight = ampPeak * 0.06;
            float inBar = 1.0 - smoothStep(0.0, 0.015, barCenter);
            float inHeight = 1.0 - smoothStep(0.0, barHeight, abs(p.y + 0.42));

            float barMask = inBar * inHeight * barRegion;

            vec3 barColor = mix(
                vec3(0.15, 0.35, 0.70),
                vec3(0.40, 0.70, 1.00),
                freqT
            );
            color = mix(color, barColor, barMask * 0.35);
        }
    }

    // ============================================================
    // 6. 高频星点 — 泛音点缀
    // ============================================================
    {
        // 在波峰位置生成光点
        vec2 gridId = floor(p * 30.0);
        vec2 gridPos = fract(p * 30.0) - 0.5;
        float pointDist = length(gridPos);

        float hash = sin(dot(gridId, vec2(12.9898, 78.233))) * 43758.5453;
        hash = fract(hash);

        float brightness = smoothStep(0.05, 0.0, pointDist);
        float twinkle = sin(hash * 100.0 + iTime * (2.0 + hash * 3.0)) * 0.5 + 0.5;
        brightness *= twinkle * treble * 0.6;
        brightness *= smoothStep(0.4, 0.0, abs(p.y)); // 仅在中部区域

        color += vec3(0.60, 0.80, 1.00) * brightness * 0.30;
    }

    // ============================================================
    // 7. 中心柔光 — 整体氛围
    // ============================================================
    float centerGlow = exp(-radius * 3.5) * energy * 0.30;
    color += vec3(0.20, 0.45, 0.80) * centerGlow;

    // ============================================================
    // 8. 最终色调映射（Minimal 风格：低饱和、干净）
    // ============================================================
    // 轻微暗角
    float vignette = 1.0 - 0.25 * radius * radius;
    color *= vignette;

    // 防溢出
    color = clamp(color, 0.0, 1.0);

    fragColor = vec4(color, 1.0);
}

// ---- 双入口兼容 ----
void main() {
    mainImage(FragColor, gl_FragCoord.xy);
}
