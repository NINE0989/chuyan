# version 330 core
#include "ShaderCommon.glsl"

#define NUM_PARTICLES 100
#define NEBULA_SIZE 0.5
#define PARTICLE_SPEED 2.0
#define GLOW_INTENSITY 0.8
#define NOISE_OCTAVES 4

// 噪声函数，用于创建星云效果
float hash(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

// 平滑噪声
float smoothNoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    
    // 四个角的噪声值
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    
    // 平滑插值
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

// 分形噪声，用于更复杂的星云效果
float fractalNoise(vec2 p) {
    float total = 0.0;
    float amplitude = 0.5;
    float frequency = 1.0;
    
    for (int i = 0; i < NOISE_OCTAVES; i++) {
        total += smoothNoise(p * frequency) * amplitude;
        amplitude *= 0.5;
        frequency *= 2.0;
    }
    
    return total;
}

// 获取音频数据
float getAudio(float u) {
    return texture(iChannel0, vec2(u, 0.0)).r;
}

// 计算低频能量
float getBassEnergy() {
    float energy = 0.0;
    const int samples = 8;
    for (int i = 0; i < samples; i++) {
        energy += getAudio(float(i) / float(samples) * 0.2);
    }
    return energy / float(samples);
}

// 计算中高频能量
float getTrebleEnergy() {
    float energy = 0.0;
    const int samples = 16;
    for (int i = 0; i < samples; i++) {
        energy += getAudio(0.5 + float(i) / float(samples) * 0.5);
    }
    return energy / float(samples);
}

// 计算整体音量
float getOverallVolume() {
    float volume = 0.0;
    const int samples = 32;
    for (int i = 0; i < samples; i++) {
        volume += getAudio(float(i) / float(samples));
    }
    return volume / float(samples);
}

// 绘制星云
vec3 drawNebula(vec2 uv, float bassEnergy) {
    // 旋转UV以实现星云旋转效果
    float angle = iTime * 0.08;
    mat2 rot = mat2(cos(angle), -sin(angle), sin(angle), cos(angle));
    vec2 rotatedUV = uv * rot;
    
    // 调整星云大小基于低频能量
    float size = NEBULA_SIZE * (1.0 + bassEnergy * 0.6);
    vec2 scaledUV = rotatedUV / size;
    
    // 计算星云噪声
    float n = fractalNoise(scaledUV * 3.0 + iTime * 0.05);
    n = pow(n, 1.2); // 增强对比度
    
    // 星云中心衰减
    float centerFalloff = 1.0 - length(scaledUV) * 0.7;
    centerFalloff = pow(centerFalloff, 2.0);
    
    // 基于低频能量增强核心亮度
    float coreBrightness = 1.0 + bassEnergy * 2.5;
    
    // 添加环形结构
    float rings = 0.5 + 0.5 * cos(length(scaledUV) * 8.0 - iTime * 0.3);
    n = mix(n, n * rings, 0.3);
    
    // 星云颜色：深蓝色和紫色
    vec3 color = mix(vec3(0.1, 0.1, 0.35), vec3(0.25, 0.05, 0.4), n * 0.8);
    color *= n * centerFalloff * coreBrightness;
    
    // 核心颜色更亮
    float core = 1.0 - smoothstep(0.0, 0.5, length(scaledUV));
    color += vec3(0.3, 0.2, 0.5) * core * bassEnergy;
    
    return color;
}

// 绘制能量粒子
vec3 drawEnergyParticles(vec2 uv, float trebleEnergy) {
    vec3 color = vec3(0.0);
    float speed = PARTICLE_SPEED * (1.0 + trebleEnergy * 2.5);
    
    // 基于中高频能量调整粒子数量
    int particles = int(float(NUM_PARTICLES) * (1.0 + trebleEnergy * 0.8));
    particles = min(particles, NUM_PARTICLES * 2); // 限制最大数量
    
    for (int i = 0; i < particles; i++) {
        // 每个粒子的随机参数
        float seed = float(i) * 4321.9876;
        float angle = hash(vec2(seed, 0.0)) * 6.283;
        vec2 dir = vec2(cos(angle), sin(angle));
        
        // 添加方向变化，使粒子流更自然
        float angleVariation = sin(iTime * 0.5 + seed) * 0.1 * trebleEnergy;
        dir = vec2(cos(angle + angleVariation), sin(angle + angleVariation));
        
        // 粒子速度和位置
        float t = iTime * speed + hash(vec2(seed + 123.45, 0.0)) * 100.0;
        float distance = fract(t);  // 0到1之间循环
        float life = 1.0 - distance;  // 粒子寿命衰减
        
        // 基于中高频能量调整发射频率
        float emissionThreshold = 0.6 - trebleEnergy * 0.3;
        emissionThreshold = clamp(emissionThreshold, 0.1, 0.9);
        if (distance > emissionThreshold) continue;
        
        // 粒子位置
        float maxDistance = 1.8;
        vec2 pos = dir * distance * maxDistance;
        float particleSize = 0.01 + trebleEnergy * 0.008;
        
        // 绘制粒子和轨迹
        float d = length(uv - pos);
        float particle = exp(-d * 50.0 / particleSize) * life;
        float trail = exp(-d * 20.0 / (particleSize * 3.0)) * pow(life, 3.0);
        particle += trail * 0.3;
        
        // 能量粒子颜色：青色或白色
        vec3 particleColor = mix(vec3(0.5, 1.0, 1.0), vec3(1.0), hash(vec2(seed + 456.78, 0.0)));
        color += particle * particleColor * (1.0 + trebleEnergy);
    }
    
    return color;
}

// 辉光效果
vec3 applyGlow(vec3 color, float glowAmount) {
    float glow = pow(length(color), 2.0) * glowAmount;
    return color + vec3(glow) * 0.6;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // 标准化UV坐标，中心为原点
    vec2 uv = (fragCoord * 2.0 - iResolution.xy) / min(iResolution.x, iResolution.y);
    
    // 获取音频数据
    float bassEnergy = getBassEnergy();
    float trebleEnergy = getTrebleEnergy();
    float overallVolume = getOverallVolume();
    
    // 绘制各元素
    vec3 nebula = drawNebula(uv, bassEnergy);
    vec3 particles = drawEnergyParticles(uv, trebleEnergy);
    
    // 混合效果并应用辉光
    vec3 totalColor = nebula + particles;
    float glowIntensity = GLOW_INTENSITY * (1.0 + overallVolume * 2.0);
    totalColor = applyGlow(totalColor, glowIntensity);
    
    // 限制亮度，避免过曝
    totalColor = clamp(totalColor, 0.0, 1.2);
    
    // 输出最终颜色
    fragColor = vec4(totalColor, 1.0);
}

// Adapter: provide a standard `main` entry point so this GLSL can be
// compiled in environments that expect `void main()` (e.g., desktop
// GLSL pipeline). It calls the existing `mainImage` function.
out vec4 fragColor_out;
void main() {
    // gl_FragCoord.xy provides the fragment coordinates in pixels
    vec2 fragCoord = gl_FragCoord.xy;
    mainImage(fragColor_out, fragCoord);
}