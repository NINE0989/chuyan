#version 330

// ============================================================
// Blue Danube — True Audio Waveform Visualization
// 核心概念:
//   横波（Transverse Wave）: 音频幅度 → 垂直位移
//   纵波（Longitudinal Wave）: 音频幅度 → 相位旋转/密度调制
//   不再使用固定频率抖动，所有波形角度均由实时音频采样驱动
// ============================================================

uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;

out vec4 FragColor;

// ---- 安全音频采样 ----
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
    // 1. 音频采样 — 沿时间轴多点采样，驱动波形角度
    // ============================================================
    float energy = 0.0;
    for (int i = 0; i < 8; i++) {
        float fi = float(i) / 8.0;
        energy += abs(sampleAudio(fi * 0.5 + 0.25));
    }
    energy /= 8.0;

    float bass   = abs(sampleAudio(0.05 + 0.02 * sin(iTime * 0.11)));
    float mid    = abs(sampleAudio(0.35 + 0.02 * sin(iTime * 0.17)));
    float treble = abs(sampleAudio(0.72 + 0.02 * sin(iTime * 0.23)));

    // ============================================================
    // 2. 背景
    // ============================================================
    vec3 bgTop    = vec3(0.015, 0.018, 0.040);
    vec3 bgBottom = vec3(0.040, 0.050, 0.085);
    vec3 bg = mix(bgBottom, bgTop, uv.y);
    vec3 color = bg;

    // ============================================================
    // 3. 横波（Transverse Wave）
    // ============================================================
    vec3 waveColor = vec3(0.30, 0.60, 1.00);
    float xPos = uv.x * 2.0 - 1.0;

    // --- 3a. 主波形 ---
    {
        float audioTime = xPos * 0.5 + 0.5;
        float amp = sampleAudio(audioTime * 0.8 + 0.1);
        float phaseAngle = amp * 6.2832;
        float waveVertical = sin(xPos * 4.0 + phaseAngle + iTime * 0.3) * 0.10;
        float waveHorizontal = cos(xPos * 3.0 + phaseAngle * 0.5 + iTime * 0.2) * 0.03;
        float yPos = amp * 0.25 + waveVertical;
        vec2 wavePoint = vec2(xPos + waveHorizontal, yPos);

        float dist = abs(p.y - wavePoint.y);
        float lineWidth = 0.004 + 0.004 * bass;
        float line = 1.0 - smoothStep(0.0, lineWidth, dist);
        vec3 lineCol = waveColor * (1.0 + treble * 0.5);
        color = mix(color, lineCol, line * 0.80);

        float glow = exp(-dist * 50.0) * (0.10 + 0.20 * bass);
        color += waveColor * glow * 0.30;
    }

    // --- 3b. 辅波形 ---
    for (int i = 0; i < 3; i++) {
        float fi = float(i);
        float audioTime = xPos * 0.5 + 0.5;
        float offset = 0.05 + fi * 0.12;
        float ampDetail = sampleAudio(audioTime * 0.8 + offset);
        float phaseAngle = ampDetail * 6.2832 + fi * 2.094;

        float waveY = sin(xPos * (5.0 + fi * 2.0) + phaseAngle + iTime * (0.4 + fi * 0.1)) * (0.04 + 0.03 * mid);
        float waveX = cos(xPos * (4.0 + fi * 1.5) + phaseAngle * 0.7 + iTime * (0.3 + fi * 0.08)) * 0.02;
        float yPos = ampDetail * 0.15 + waveY;
        vec2 wavePt = vec2(xPos + waveX, yPos);

        float dist = abs(p.y - yPos);
        float lineWidth = 0.002 + 0.002 * (1.0 - fi * 0.2);
        float line = 1.0 - smoothStep(0.0, lineWidth, dist);
        vec3 col = mix(vec3(0.25, 0.50, 0.90), vec3(0.50, 0.75, 1.00), fi / 3.0);
        color = mix(color, col, line * 0.40 * (0.5 + 0.5 * treble));

        float glow = exp(-dist * 40.0) * 0.08;
        color += col * glow;
    }

    // ============================================================
    // 4. 纵波（Longitudinal Wave）
    // ============================================================
    {
        float radius = length(p);
        float angle = atan(p.y, p.x);
        float audioPhase = sampleAudio(radius * 0.3 + 0.2);
        float angleOffset = audioPhase * 6.2832;

        float density = sin(radius * 30.0 - angle * 3.0 + angleOffset + iTime * 0.5) * 0.5 + 0.5;
        density *= sin(radius * 20.0 + angle * 5.0 + angleOffset * 1.3 + iTime * 0.7) * 0.5 + 0.5;

        float ringVisibility = 0.08 + 0.20 * bass;
        float radiusMask = exp(-radius * 2.5);
        float ring = density * radiusMask * ringVisibility;

        vec3 ringColor = mix(vec3(0.15, 0.40, 0.80), vec3(0.40, 0.70, 1.00), mid);
        color += ringColor * ring;
    }

    // ============================================================
    // 5. 底部频谱条
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
            float barHeight = ampVal * 0.07;
            float inBar = 1.0 - smoothStep(0.0, 0.012, barCenter);
            float inHeight = 1.0 - smoothStep(0.0, barHeight, abs(p.y + 0.42));
            float barMask = inBar * inHeight * barRegion;
            vec3 barColor = mix(vec3(0.12, 0.30, 0.65), vec3(0.35, 0.65, 1.00), freqT);
            color = mix(color, barColor, barMask * 0.40);
        }
    }

    // ============================================================
    // 6. 星点
    // ============================================================
    {
        vec2 gridId = floor(p * 25.0);
        vec2 gridPos = fract(p * 25.0) - 0.5;
        float pointDist = length(gridPos);
        float hash = sin(dot(gridId, vec2(12.9898, 78.233))) * 43758.5453;
        hash = fract(hash);
        float brightness = smoothStep(0.04, 0.0, pointDist);
        float twinkle = sin(hash * 100.0 + iTime * (2.0 + treble * 4.0)) * 0.5 + 0.5;
        brightness *= twinkle * treble * 0.5;
        brightness *= smoothStep(0.35, 0.0, abs(p.y));
        color += vec3(0.55, 0.75, 1.00) * brightness * 0.25;
    }

    // ============================================================
    // 7. 中心柔光 + 暗角
    // ============================================================
    float radius = length(p);
    float centerGlow = exp(-radius * 3.0) * energy * 0.25;
    color += vec3(0.15, 0.40, 0.75) * centerGlow;
    float vignette = 1.0 - 0.20 * radius * radius;
    color *= vignette;
    color = clamp(color, 0.0, 1.0);

    fragColor = vec4(color, 1.0);
}

// ---- 双入口兼容 ----
void main() {
    mainImage(FragColor, gl_FragCoord.xy);
}
