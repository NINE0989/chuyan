// 音频频谱动态线条 — 优化版（预采样 bands，几何早期剔除）
// Estimated texture samples per pixel: ~32 (DEFAULT_BANDS)
#ifdef GL_ES
precision mediump float;
#endif

// 强制统一采样宏
#ifndef TEX
#ifdef GL_ES
#define TEX(s, uv) texture2D(s, uv)
#else
#define TEX(s, uv) texture(s, uv)
#endif
#endif

// 性能友好默认值
#define SAFE_MARGIN 0.05
#define DEFAULT_BANDS 32
#define LINE_COUNT 32
#define MAX_NEIGHBORS 1 // 处理中心线两侧各1条 => 最多3条
#define BASE_THICKNESS 0.002
#define MAX_THICKNESS 0.010
#define RGB_SHIFT_AMOUNT 0.002
#define GLOW_INTENSITY 1.2

uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;

#ifndef GL_ES
out vec4 fragColor;
#endif

const float PI = 3.14159265359;

float hash12(vec2 p){ return fract(sin(dot(p,vec2(12.9898,78.233))) * 43758.5453123); }
vec2 rotate2D(vec2 v, float a){ float c=cos(a), s=sin(a); return vec2(v.x*c - v.y*s, v.x*s + v.y*c); }

// 线条掩码（窄带+亚像素抗锯齿）
float lineMask(vec2 localPos, float length, float thickness){
    float dist = abs(localPos.y);
    float along = abs(localPos.x);
    float lenSmooth = smoothstep(length, length - 0.02, along);
    float thickSmooth = smoothstep(thickness, thickness - 0.0015, dist);
    return lenSmooth * thickSmooth;
}

// 预采样单点（中心采样，后续用邻域平均数组平滑，避免多次纹理采样）
float sampleBandCenter(int idx, int bands){
    float du = 1.0 / float(bands);
    float u = (float(idx) + 0.5) * du;
    return TEX(iChannel0, vec2(clamp(u,0.0,1.0), 0.0)).r;
}

// 简化的 rgb shift（低成本近似）
vec3 rgbShiftCheap(vec3 col, float amt){
    return vec3(col.r * (1.0 + amt*0.6), col.g, col.b * (1.0 - amt*0.4));
}

// 近似辉光：轻量级放大亮度
vec3 addGlowCheap(vec3 c, float energy){
    float lum = dot(c, vec3(0.299,0.587,0.114));
    return c + c * clamp(pow(lum, 0.9) * energy * 0.6, 0.0, 1.5);
}

void mainImage(out vec4 outColor, in vec2 fragCoord){
    vec2 center = 0.5 * iResolution.xy;
    float scale = min(iResolution.x, iResolution.y);
    vec2 uv = (fragCoord - center) / scale;
    float maxSafe = 1.0 - SAFE_MARGIN;

    // 1) 预采样频谱到数组（每像素仅采样 DEFAULT_BANDS 次）
    float bands[DEFAULT_BANDS];
    for(int i=0;i<DEFAULT_BANDS;i++){
        bands[i] = sampleBandCenter(i, DEFAULT_BANDS);
    }
    // 2) 用数组邻域平滑（不再进行额外采样，仅算术运算）
    for(int i=0;i<DEFAULT_BANDS;i++){
        int im = (i - 1 + DEFAULT_BANDS) % DEFAULT_BANDS;
        int ip = (i + 1) % DEFAULT_BANDS;
        bands[i] = (bands[im] + bands[i] + bands[ip]) / 3.0;
    }

    vec3 finalColor = vec3(0.0);

    // 角度索引：将像素映射到与线条对应的中心索引，随后只计算附近的少量线条
    float ang = atan(uv.y, uv.x);
    if(ang < 0.0) ang += 2.0 * PI;
    float lineF = ang / (2.0 * PI) * float(LINE_COUNT);
    int centerIdx = int(floor(lineF + 0.5));

    // 处理中心线及左右邻居（MAX_NEIGHBORS 控制）
    for(int off = -MAX_NEIGHBORS; off <= MAX_NEIGHBORS; off++){
        int idx = (centerIdx + off + LINE_COUNT) % LINE_COUNT;
        // map line idx to band index
        int bandIdx = int(float(idx) / float(LINE_COUNT) * float(DEFAULT_BANDS));
        bandIdx = clamp(bandIdx, 0, DEFAULT_BANDS - 1);
        float bandEnergy = bands[bandIdx];

        float smoothE = pow(clamp(bandEnergy, 0.0, 1.0), 0.75);

        // line geometry params
        float lineAngle = float(idx) / float(LINE_COUNT) * 2.0 * PI;
        float lineLen = clamp(smoothE * 0.9 * maxSafe, 0.04, maxSafe);
        float thickness = mix(BASE_THICKNESS, MAX_THICKNESS, smoothE * (float(bandIdx) / float(DEFAULT_BANDS) * 0.6 + 0.4));

        // rotate uv into line-aligned frame
        vec2 ruv = rotate2D(uv, -lineAngle);
        float mask = lineMask(ruv, lineLen, thickness);
        if(mask < 0.005) continue;

        // colors
        vec3 base = vec3(0.2 + 0.8 * smoothE, 0.1 + 0.6 * smoothE, 0.05 + 0.9 * smoothE);
        base = rgbShiftCheap(base, mask * RGB_SHIFT_AMOUNT);
        base = addGlowCheap(base, smoothE);

        finalColor += base * mask;
    }

    // 强制安全边界外全黑
    float safeMask = step(length(uv), maxSafe + 0.01);
    finalColor *= safeMask;

    finalColor = clamp(finalColor, 0.0, 1.0);
    outColor = vec4(finalColor, 1.0);
}

void main(){
    vec4 res;
    mainImage(res, gl_FragCoord.xy);
#ifdef GL_ES
    gl_FragColor = res;
#else
    fragColor = res;
#endif
}
