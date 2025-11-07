// Fourier Rings - audio reactive, ring array, SAFE_MARGIN=0.05 FIT_MODE=INSIDE
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

#define MAX_PARTICLES 128
#define PARTICLE_ITERATIONS 32
#define NOISE_OCTAVES 2
#define GLOW_INTENSITY 1.0
#define SAFE_MARGIN 0.05
#define FIT_MODE_INSIDE 1
#define EDGE_SMOOTH 0.008
#define RING_COUNT 32
#define BASE_RING_WIDTH 0.015

uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453123);
}

vec2 rotate2D(vec2 uv, float a) {
    float c = cos(a), s = sin(a);
    return vec2(uv.x * c - uv.y * s, uv.x * s + uv.y * c);
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

float getBass() {
    float energy = 0.0;
    for (int i = 0; i < 8; i++) energy += guardedTexelFetch(float(i)/float(RING_COUNT) * 0.2);
    return clamp(energy / 8.0, 0.0, 1.0);
}

float getMid() {
    float energy = 0.0;
    for (int i = 0; i < 12; i++) energy += guardedTexelFetch(0.2 + float(i)/float(RING_COUNT) * 0.3);
    return clamp(energy / 12.0, 0.0, 1.0);
}

float getTreble() {
    float energy = 0.0;
    for (int i = 0; i < 16; i++) energy += guardedTexelFetch(0.5 + float(i)/float(RING_COUNT) * 0.5);
    return clamp(energy / 16.0, 0.0, 1.0);
}

float getOverallVolume() {
    return clamp((getBass() + getMid() + getTreble()) / 3.0, 0.0, 1.0);
}

float ringMask(vec2 uv, float radius, float width) {
    float maxRadius = 1.0 - SAFE_MARGIN;
    radius = clamp(radius, 0.0, maxRadius);
    
    float outer = smoothstep(radius + width, radius + width - EDGE_SMOOTH, length(uv));
    float inner = smoothstep(radius - EDGE_SMOOTH, radius, length(uv));
    return outer * inner;
}

float edgeMask(float v) {
    return smoothstep(0.0, EDGE_SMOOTH, v);
}

vec3 rgbShift(vec3 col, float radius, float amount) {
    amount = clamp(amount, 0.0, 0.01);
    float shift = sin(radius * 5.0 + iTime) * amount;
    return vec3(
        col.r * (1.0 + shift * 12.0),
        col.g,
        col.b * (1.0 - shift * 12.0)
    );
}

vec3 screenGlow(vec3 col, float intensity, float mask) {
    float bright = dot(col, vec3(0.299, 0.587, 0.114));
    vec3 glow = vec3(pow(bright, 2.2)) * intensity * mask;
    return clamp(col + glow * 0.6, 0.0, 1.8);
}

vec3 drawRings(vec2 uv, float bass, float mid, float treble, out float totalMask) {
    totalMask = 0.0;
    vec3 color = vec3(0.0);
    float maxRadius = 1.0 - SAFE_MARGIN;
    float radiusStep = maxRadius / float(RING_COUNT);
    float rotation = iTime * 0.05 * (1.0 + bass * 0.3);
    float colorPhase = iTime * 1.3;

    for (int i = 0; i < RING_COUNT; i++) {
        float ringIndex = float(i);
        float u = ringIndex / float(RING_COUNT);
        float spectrum = guardedTexelFetch(u);
        
        float baseRadius = (ringIndex + 1.0) * radiusStep;
        float radius = baseRadius + spectrum * 0.2 * (1.0 + bass * 0.4);
        float width = BASE_RING_WIDTH + mid * 0.015 * spectrum;
        
        vec2 rotatedUV = rotate2D(uv, rotation * (1.0 + u * 0.5));
        float mask = ringMask(rotatedUV, radius, width);
        totalMask = max(totalMask, mask);
        
        vec3 ringColor = vec3(
            sin(colorPhase + u * 6.283),
            sin(colorPhase + u * 6.283 + 2.094),
            sin(colorPhase + u * 6.283 + 4.188)
        ) * 0.5 + 0.5;
        
        float freqBoost = u < 0.2 ? bass * 1.8 : (u > 0.5 ? treble * 1.8 : mid * 1.4);
        ringColor *= (1.0 + spectrum * freqBoost);
        
        float detail = noise2D(rotatedUV * 15.0 + iTime * 3.0) * mid * 0.7;
        ringColor = mix(ringColor, ringColor * (0.6 + detail), 0.5);
        
        ringColor = rgbShift(ringColor, radius, mid * 0.7);
        color += ringColor * mask;
    }
    
    totalMask = clamp(totalMask, 0.0, 1.0);
    return color;
}

vec3 drawParticles(vec2 uv, float treble, float mask) {
    if (mask < 0.01 || treble < 0.05) return vec3(0.0);
    
    vec3 color = vec3(0.0);
    float speed = 2.0 + treble * 5.0;
    int spawnCount = min(MAX_PARTICLES, int(float(MAX_PARTICLES) * (1.0 + treble * 1.2)));
    float maxRadius = 1.0 - SAFE_MARGIN;
    
    for (int i = 0; i < spawnCount; i++) {
        float seed = float(i) * 37.29;
        float u = hash(vec2(seed)) * 1.0;
        float spectrum = guardedTexelFetch(u);
        if (spectrum < 0.1) continue;
        
        float angle = u * 6.283 + iTime * 0.2;
        float radius = (SAFE_MARGIN + hash(vec2(seed + 19.7)) * (maxRadius - SAFE_MARGIN)) * (0.5 + spectrum * 0.5);
        
        float t = iTime * speed + hash(vec2(seed + 43.1)) * 100.0;
        float dist = fract(t);
        float life = pow(1.0 - dist, 2.0);
        
        vec2 pos = vec2(cos(angle), sin(angle)) * radius;
        pos += rotate2D(vec2(hash(vec2(seed, iTime * 0.3)), 0.0), angle + iTime) * 0.025 * treble;
        
        float d = length(uv - pos);
        float size = 0.003 + treble * 0.006 * spectrum;
        float particle = 0.0;
        
        for (int j = 0; j < PARTICLE_ITERATIONS; j++) {
            float s = size * (1.0 + float(j) * 0.1);
            particle += exp(-d * 60.0 / s) * (1.0 - float(j)/float(PARTICLE_ITERATIONS));
        }
        
        vec3 particleColor = mix(vec3(1.0, 0.9, 0.3), vec3(0.3, 0.9, 1.0), hash(vec2(seed + 67.5)));
        color += particle * particleColor * life * treble * spectrum * mask;
    }
    
    return color;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 center = 0.5 * iResolution.xy;
    float scale = min(iResolution.x, iResolution.y);
    vec2 uv = (fragCoord - center) / scale;
    
    float bass = getBass();
    float mid = getMid();
    float treble = getTreble();
    float volume = getOverallVolume();
    
    float mainMask = 0.0;
    vec3 ringsColor = drawRings(uv, bass, mid, treble, mainMask);
    vec3 particlesColor = drawParticles(uv, treble, mainMask);
    
    vec3 total = ringsColor + particlesColor;
    total = screenGlow(total, GLOW_INTENSITY * (1.0 + volume * 2.2), mainMask);
    
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