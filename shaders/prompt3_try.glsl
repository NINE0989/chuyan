// Electronic Music Viz - hard-edge rings, particles, RGB shift (high contrast)
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

#define MAX_PARTICLES 192
#define PARTICLE_ITERATIONS 32
#define NEBULA_OCTAVES 3
#define GLOW_INTENSITY 1.2
#define SPECTRUM_SIZE 512.0
#define EDGE_SMOOTH 0.015

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

float fbm(vec2 p) {
    float total = 0.0, amp = 0.5;
    for (int i = 0; i < NEBULA_OCTAVES; i++) {
        total += noise2D(p) * amp;
        p *= 2.0;
        amp *= 0.5;
    }
    return clamp(total, 0.0, 1.0);
}

float guardedTexelFetch(float u) {
    u = clamp(u, 0.0, 1.0);
    return TEX(iChannel0, vec2(u, 0.0)).r;
}

float shapeMask(vec2 uv, float bass, float mid) {
    uv = rotate2D(uv, iTime * 0.1 * (1.0 + bass * 0.2));
    float radius = length(uv);
    float baseSize = 0.6 + bass * 0.8;
    
    float ring1 = smoothstep(baseSize - EDGE_SMOOTH, baseSize, radius) - 
                  smoothstep(baseSize + EDGE_SMOOTH, baseSize + 2.0 * EDGE_SMOOTH, radius);
    float ring2 = smoothstep(baseSize * 1.5 - EDGE_SMOOTH, baseSize * 1.5, radius) - 
                  smoothstep(baseSize * 1.5 + EDGE_SMOOTH, baseSize * 1.5 + 2.0 * EDGE_SMOOTH, radius);
    
    float midDetail = sin(radius * 20.0 + iTime * 5.0 * (1.0 + mid)) * 0.5 + 0.5;
    midDetail = pow(midDetail, 2.0) * mid * 0.4;
    
    return clamp(ring1 + ring2 + midDetail, 0.0, 1.0);
}

float edgeMask(float v, float thresh) {
    return smoothstep(thresh - EDGE_SMOOTH, thresh, v);
}

vec3 rgbShift(vec3 col, vec2 uv, float amount, float mask) {
    amount = clamp(amount * mask, 0.0, 0.012);
    vec3 shift = vec3(
        noise2D(uv + vec2(amount, 0.0)),
        noise2D(uv),
        noise2D(uv - vec2(amount, 0.0))
    );
    return mix(col, col * shift * 1.2, 0.4 * mask);
}

vec3 screenGlow(vec3 col, float intensity, float mask) {
    float bright = dot(col, vec3(0.299, 0.587, 0.114));
    vec3 glow = vec3(pow(bright, 2.0)) * intensity * mask;
    return clamp(col + glow * 0.6, 0.0, 1.8);
}

float getBass() {
    float energy = 0.0;
    for (int i = 0; i < 16; i++) energy += guardedTexelFetch(float(i) / SPECTRUM_SIZE * 0.2);
    return clamp(energy / 16.0, 0.0, 1.0);
}

float getMid() {
    float energy = 0.0;
    for (int i = 0; i < 24; i++) energy += guardedTexelFetch(0.2 + float(i) / SPECTRUM_SIZE * 0.3);
    return clamp(energy / 24.0, 0.0, 1.0);
}

float getTreble() {
    float energy = 0.0;
    for (int i = 0; i < 32; i++) energy += guardedTexelFetch(0.5 + float(i) / SPECTRUM_SIZE * 0.5);
    return clamp(energy / 32.0, 0.0, 1.0);
}

float getOverallVolume() {
    return clamp((getBass() + getMid() + getTreble()) / 3.0, 0.0, 1.0);
}

vec3 drawRings(vec2 uv, float bass, float mid, out float mask) {
    mask = shapeMask(uv, bass, mid);
    if (mask < 0.01) return vec3(0.0);
    
    vec2 rotatedUV = rotate2D(uv, iTime * 0.08 * (1.0 + bass));
    float radius = length(rotatedUV);
    
    float colorPhase = iTime * 1.5 + bass * 4.0;
    vec3 hue1 = vec3(sin(colorPhase), sin(colorPhase + 2.094), sin(colorPhase + 4.188)) * 0.5 + 0.5;
    vec3 hue2 = vec3(sin(colorPhase + 1.047), sin(colorPhase + 3.141), sin(colorPhase + 5.236)) * 0.5 + 0.5;
    
    float ringMix = smoothstep(0.6, 1.5, radius);
    vec3 col = mix(hue1, hue2, ringMix);
    
    float midNoise = fbm(rotatedUV * 12.0 + iTime * 3.0) * mid * 0.8;
    col = mix(col, col * (0.8 + midNoise), 0.5);
    
    float coreBright = 1.0 - smoothstep(0.0, 0.4 + bass * 0.3, radius);
    col += vec3(0.4, 0.2, 0.6) * coreBright * bass * 2.0;
    
    col = rgbShift(col, rotatedUV, mid * 0.8, mask);
    return col * mask;
}

vec3 drawParticles(vec2 uv, float treble, float mask) {
    if (mask < 0.01) return vec3(0.0);
    
    vec3 color = vec3(0.0);
    float speed = 3.0 + treble * 5.0;
    int spawnCount = min(MAX_PARTICLES, int(float(MAX_PARTICLES) * (1.0 + treble * 1.5)));
    
    for (int i = 0; i < spawnCount; i++) {
        float seed = float(i) * 73.291;
        vec2 dir = rotate2D(vec2(1.0, 0.0), hash(vec2(seed)) * 6.283);
        float t = iTime * speed + hash(vec2(seed + 45.1)) * 100.0;
        float dist = fract(t);
        float life = pow(1.0 - dist, 3.0);
        
        float spawnThresh = 0.75 - treble * 0.4;
        if (dist > spawnThresh) continue;
        
        vec2 pos = dir * (0.8 + dist * 1.2) * (1.0 + treble * 0.2);
        pos = rotate2D(pos, iTime * 0.2 * (1.0 + treble));
        
        float d = length(uv - pos);
        float size = 0.006 + treble * 0.005;
        float particle = 0.0;
        
        for (int j = 0; j < PARTICLE_ITERATIONS; j++) {
            float s = size * (1.0 + float(j) * 0.12);
            particle += exp(-d * 40.0 / s) * (1.0 - float(j)/float(PARTICLE_ITERATIONS));
        }
        
        vec3 particleCol = mix(vec3(0.3, 1.0, 1.0), vec3(1.0, 0.5, 1.0), hash(vec2(seed + 91.7)));
        color += particle * particleCol * life * treble * mask;
    }
    
    return color;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord * 2.0 - iResolution.xy) / min(iResolution.x, iResolution.y);
    float bass = getBass();
    float mid = getMid();
    float treble = getTreble();
    float volume = getOverallVolume();
    
    float mainMask = 0.0;
    vec3 ringsCol = drawRings(uv, bass, mid, mainMask);
    vec3 particlesCol = drawParticles(uv, treble, mainMask);
    
    vec3 total = ringsCol + particlesCol;
    total = screenGlow(total, GLOW_INTENSITY * (1.0 + volume * 2.5), mainMask);
    
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