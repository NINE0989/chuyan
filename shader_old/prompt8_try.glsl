// Horizontal Fourier Spectrum - audio reactive lines, smooth attack/decay, SAFE_MARGIN=0.05 FIT_MODE=INSIDE
#ifdef GL_ES
precision mediump float;
#endif

#ifndef TEX
#ifdef GL_ES
#define TEX(s, uv) texture2D(s, uv)
#else
#define TEX(s, uv) texture(s, uv)
#endif
#endif

// AUDIO_ATTACK=0.08 (rise) AUDIO_DECAY=0.30 (fall) - stateless smooth fallback
#define AUDIO_ATTACK 0.08
#define AUDIO_DECAY  0.30
#define AUDIO_SMOOTH_K 0.85
#define SAFE_MARGIN 0.05
#define FIT_MODE_INSIDE 1
#define MAX_PARTICLES 128
#define PARTICLE_ITERATIONS 32
#define NOISE_OCTAVES 2
#define GLOW_INTENSITY 1.1
#define EDGE_SMOOTH 0.006
#define LINE_COUNT 64
#define BASE_LINE_WIDTH 0.012
#define SPECTRUM_SMOOTH_SAMPLES 5 // 局部平均抑制尖峰

uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453123);
}

float noise2D(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

float guardedTexelFetch(float u) {
    u = clamp(u, 0.0, 1.0);
    return TEX(iChannel0, vec2(u, 0.0)).r;
}

// 局部频谱平均（抑制尖峰）
float sampleSmoothSpectrum(float u) {
    float total = 0.0;
    float step = 1.0 / float(512);
    int halfSamples = SPECTRUM_SMOOTH_SAMPLES / 2;
    
    for (int i = -halfSamples; i <= halfSamples; i++) {
        float uu = u + float(i) * step * 2.0;
        total += guardedTexelFetch(uu);
    }
    
    return total / float(SPECTRUM_SMOOTH_SAMPLES);
}

// 无状态能量平滑（压缩+变化率限制）
float smoothEnergy(float target) {
    float compressed = pow(target, 0.65); // 压缩减少突变
    float rateLimit = clamp(1.0 - AUDIO_SMOOTH_K, 0.01, 0.5);
    
    // 空间近邻估计近似前一状态（无buffer回退）
    float spatialSmooth = noise2D(vec2(iTime * 0.1, 0.0)) * 0.1;
    return mix(compressed, spatialSmooth, rateLimit);
}

float getBass() {
    float energy = 0.0;
    for (int i = 0; i < 8; i++) {
        float u = float(i) / float(LINE_COUNT) * 0.2;
        energy += sampleSmoothSpectrum(u);
    }
    float raw = energy / 8.0;
    return smoothEnergy(clamp(raw, 0.0, 1.0));
}

float getMid() {
    float energy = 0.0;
    for (int i = 0; i < 16; i++) {
        float u = 0.2 + float(i) / float(LINE_COUNT) * 0.3;
        energy += sampleSmoothSpectrum(u);
    }
    float raw = energy / 16.0;
    return smoothEnergy(clamp(raw, 0.0, 1.0));
}

float getTreble() {
    float energy = 0.0;
    for (int i = 0; i < 24; i++) {
        float u = 0.5 + float(i) / float(LINE_COUNT) * 0.5;
        energy += sampleSmoothSpectrum(u);
    }
    float raw = energy / 24.0;
    return smoothEnergy(clamp(raw, 0.0, 1.0));
}

float getOverallVolume() {
    float vol = (getBass() + getMid() + getTreble()) / 3.0;
    return smoothstep(0.0, 0.02, vol); // 软阈值避免噪声触发
}

// 横向线条掩码（左到右分布）
float lineMask(vec2 uv, float xPos, float height, float width) {
    float maxX = 1.0 - SAFE_MARGIN;
    float minX = -maxX;
    float maxY = 1.0 - SAFE_MARGIN;
    
    // X轴掩码（横向分布）
    float xMask = smoothstep(xPos - width, xPos, uv.x) - 
                  smoothstep(xPos, xPos + width, uv.x);
    // Y轴掩码（高度由音频控制）
    float yMask = smoothstep(-height - EDGE_SMOOTH, -height, uv.y) - 
                  smoothstep(height, height + EDGE_SMOOTH, uv.y);
    // 边界保护
    float boundMask = step(uv.x, maxX) * step(minX, uv.x) * step(abs(uv.y), maxY);
    
    return clamp(xMask * yMask * boundMask, 0.0, 1.0);
}

float edgeMask(float v) {
    return smoothstep(0.0, EDGE_SMOOTH, v);
}

// 轻微RGB色差（增强边缘）
vec3 rgbShift(vec3 col, float freq, float amount) {
    amount = clamp(amount, 0.0, 0.01);
    float shift = sin(freq * 6.283 + iTime * 0.5) * amount;
    return vec3(
        col.r * (1.0 + shift * 8.0),
        col.g,
        col.b * (1.0 - shift * 8.0)
    );
}

// 屏幕辉光（仅限掩码区域）
vec3 screenGlow(vec3 col, float intensity, float mask) {
    float bright = dot(col, vec3(0.299, 0.587, 0.114));
    vec3 glow = vec3(pow(bright, 2.0)) * intensity * mask;
    return clamp(col + glow * 0.5, 0.0, 1.8);
}

// 绘制横向频谱线
vec3 drawSpectrumLines(vec2 uv, float bass, float mid, float treble, float volume, out float totalMask) {
    totalMask = 0.0;
    vec3 color = vec3(0.0);
    float maxX = 1.0 - SAFE_MARGIN;
    float minX = -maxX;
    float xStep = (maxX - minX) / float(LINE_COUNT - 1);
    float colorPhase = iTime * 1.2;

    for (int i = 0; i < LINE_COUNT; i++) {
        float xPos = minX + float(i) * xStep;
        float u = float(i) / float(LINE_COUNT - 1); // 频率映射（左低右高）
        float spectrum = sampleSmoothSpectrum(u);
        
        // 音频驱动线条高度（bass增强整体高度）
        float heightScale = 0.6 + bass * 0.4;
        float height = spectrum * heightScale * smoothstep(0.05, 0.5, volume);
        // 线条宽度（mid控制细节）
        float width = BASE_LINE_WIDTH + mid * 0.008 * spectrum;
        
        // 生成掩码
        float mask = lineMask(uv, xPos, height, width);
        totalMask = max(totalMask, mask);
        if (mask < 0.01) continue;
        
        // 丰富颜色变化（随频率和时间变化）
        vec3 lineColor = vec3(
            sin(colorPhase + u * 6.283 + bass * 3.0),
            sin(colorPhase + u * 6.283 + mid * 3.0 + 2.094),
            sin(colorPhase + u * 6.283 + treble * 3.0 + 4.188)
        ) * 0.5 + 0.5;
        
        // 频段增强
        float freqBoost = u < 0.2 ? bass * 1.8 : (u > 0.5 ? treble * 1.8 : mid * 1.4);
        lineColor *= (1.0 + spectrum * freqBoost * volume);
        
        // 细节抖动（仅限mask内部）
        float detail = noise2D(vec2(xPos * 15.0, iTime * 4.0)) * mid * 0.6;
        lineColor = mix(lineColor, lineColor * (0.7 + detail), 0.4);
        
        // 边缘色差
        lineColor = rgbShift(lineColor, u, mid * 0.5);
        
        color += lineColor * mask;
    }
    
    totalMask = clamp(totalMask, 0.0, 1.0);
    return color;
}

// 粒子系统（随treble变化）
vec3 drawParticles(vec2 uv, float treble, float volume, float mask) {
    if (mask < 0.01 || volume < 0.02) return vec3(0.0);
    
    vec3 color = vec3(0.0);
    // 平滑粒子生成率
    float spawnFactor = smoothstep(0.1, 0.8, treble * volume);
    int spawnCount = min(MAX_PARTICLES, int(float(MAX_PARTICLES) * spawnFactor));
    float speed = 1.0 + treble * 3.0 * smoothstep(0.2, 1.0, volume);
    float maxX = 1.0 - SAFE_MARGIN;
    float minX = -maxX;
    float maxY = 1.0 - SAFE_MARGIN;
    
    for (int i = 0; i < spawnCount; i++) {
        float seed = float(i) * 41.37;
        float u = hash(vec2(seed)) * 1.0; // 频率映射
        float spectrum = sampleSmoothSpectrum(u);
        if (spectrum < 0.1) continue;
        
        // 粒子位置（横向分布，高度跟随频谱）
        float xPos = mix(minX, maxX, u);
        float yPos = mix(-maxY * 0.5, maxY * 0.5, hash(vec2(seed + 29.7))) * spectrum;
        
        // 平滑生命周期
        float t = iTime * speed + hash(vec2(seed + 53.1)) * 60.0;
        float life = pow(fract(t), 2.0) * pow(1.0 - fract(t), 2.0) * 4.0;
        life *= spawnFactor;
        
        // 粒子运动（轻微抖动）
        vec2 pos = vec2(xPos, yPos);
        pos.x += sin(t * 2.0) * 0.02 * treble;
        pos.y += cos(t * 1.5) * 0.015 * treble;
        
        // 边界约束
        pos.x = clamp(pos.x, minX, maxX);
        pos.y = clamp(pos.y, -maxY, maxY);
        
        // 粒子绘制
        float d = length(uv - pos);
        float size = 0.003 + treble * 0.005 * spectrum * volume;
        float particle = 0.0;
        
        for (int j = 0; j < PARTICLE_ITERATIONS; j++) {
            float s = size * (1.0 + float(j) * 0.1);
            particle += exp(-d * 70.0 / s) * (1.0 - float(j)/float(PARTICLE_ITERATIONS));
        }
        
        // 粒子颜色（与线条颜色呼应）
        vec3 particleColor = mix(vec3(1.0, 0.8, 0.2), vec3(0.2, 0.8, 1.0), hash(vec2(seed + 79.4)));
        color += particle * particleColor * life * treble * spectrum * mask;
    }
    
    return color;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // 坐标归一化（短边对齐，横向布局）
    float scale = min(iResolution.x, iResolution.y);
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / scale;
    
    // 获取平滑音频能量
    float bass = getBass();
    float mid = getMid();
    float treble = getTreble();
    float volume = getOverallVolume();
    
    // 绘制主体
    float mainMask = 0.0;
    vec3 linesColor = drawSpectrumLines(uv, bass, mid, treble, volume, mainMask);
    vec3 particlesColor = drawParticles(uv, treble, volume, mainMask);
    
    // 混合并应用辉光
    vec3 total = linesColor + particlesColor;
    total = screenGlow(total, GLOW_INTENSITY * (1.0 + volume * 2.0), mainMask);
    
    // 纯黑背景
    if (mainMask < 0.01) total = vec3(0.0);
    fragColor = vec4(clamp(total, 0.0, 2.0), 1.0);
}

#ifdef GL_ES
void main() {
    mainImage(gl_FragColor, gl_FragCoord.xy);
}
#else
out vec4 fragColor;
void main() {
    mainImage(fragColor, gl_FragCoord.xy);
}
#endif