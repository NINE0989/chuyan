// Electronic music lines viz - sharp edges, audio reactive, SAFE_MARGIN=0.05 FIT_MODE=INSIDE
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
#define NOISE_OCTAVES 3
#define GLOW_INTENSITY 1.0
#define SAFE_MARGIN 0.05
#define FIT_MODE_INSIDE 1
#define EDGE_SMOOTH 0.01
#define SPECTRUM_SIZE 512.0

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
    for (int i = 0; i < NOISE_OCTAVES; i++) {
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

float lineMask(vec2 uv, float angle, float width, float bass) {
    uv = rotate2D(uv, angle);
    float maxRadius = 1.0 - SAFE_MARGIN;
    float distFromCenter = length(uv);
    float radiusMask = smoothstep(maxRadius, maxRadius - EDGE_SMOOTH, distFromCenter);
    float line = smoothstep(width, 0.0, abs(uv.y));
    return line * radiusMask;
}

float edgeMask(float v) {
    return smoothstep(0.0, EDGE_SMOOTH, v);
}

vec3 rgbShift(vec3 col, vec2 uv, float amount, float mask) {
    amount = clamp(amount * mask, 0.0, 0.01);
    return vec3(
        col.r * (1.0 + edgeMask(mask) * amount * 10.0) * smoothstep(amount, 0.0, uv.x),
        col.g,
        col.b * (1.0 + edgeMask(mask) * amount * 10.0) * smoothstep(amount, 0.0, -uv.x)
    );
}

vec3 screenGlow(vec3 col, float intensity, float mask) {
    float bright = dot(col, vec3(0.299, 0.587, 0.114));
    vec3 glow = vec3(pow(bright, 2.0)) * intensity * mask;
    return clamp(col + glow * 0.5, 0.0, 1.5);
}

vec3 drawLines(vec2 uv, float bass, float mid, out float totalMask) {
    totalMask = 0.0;
    vec3 color = vec3(0.0);
    float maxLines = 12.0 + floor(bass * 8.0);
    float angleStep = 6.283 / maxLines;
    float colorPhase = iTime * 1.2 + bass * 3.0;
    
    for (int i = 0; i < 20; i++) {
        if (float(i) >= maxLines) break;
        
        float angle = float(i) * angleStep + iTime * 0.1 * (1.0 + bass * 0.3);
        float width = 0.02 + mid * 0.03;
        float mask = lineMask(uv, angle, width, bass);
        totalMask += mask;
        
        vec3 lineColor = vec3(
            sin(colorPhase + float(i) * 0.5),
            sin(colorPhase + float(i) * 0.5 + 2.094),
            sin(colorPhase + float(i) * 0.5 + 4.188)
        ) * 0.5 + 0.5;
        
        float detail = fbm(uv * 15.0 + iTime * 5.0) * mid * 0.8;
        lineColor = mix(lineColor, lineColor * (0.7 + detail), 0.6);
        
        float radius = length(uv);
        float brightness = 1.0 - smoothstep(0.0, 1.0 - SAFE_MARGIN, radius);
        brightness = mix(brightness, brightness * (1.0 + bass * 2.0), 0.5);
        
        lineColor = rgbShift(lineColor, uv, mid * 0.5, mask);
        color += lineColor * mask * brightness;
    }
    
    totalMask = clamp(totalMask, 0.0, 1.0);
    return color;
}

vec3 drawParticles(vec2 uv, float treble, float mask) {
    if (mask < 0.01) return vec3(0.0);
    
    vec3 color = vec3(0.0);
    float speed = 2.0 + treble * 6.0;
    int spawnCount = min(MAX_PARTICLES, int(float(MAX_PARTICLES) * (1.0 + treble * 1.2)));
    float maxRadius = 1.0 - SAFE_MARGIN;
    
    for (int i = 0; i < spawnCount; i++) {
        float seed = float(i) * 47.231;
        float angle = hash(vec2(seed)) * 6.283;
        vec2 dir = vec2(cos(angle), sin(angle));
        
        float t = iTime * speed + hash(vec2(seed + 31.7)) * 100.0;
        float dist = fract(t);
        float life = pow(1.0 - dist, 2.0);
        
        float spawnThresh = 0.8 - treble * 0.5;
        if (dist > spawnThresh) continue;
        
        float particleRadius = SAFE_MARGIN + dist * (maxRadius - SAFE_MARGIN);
        vec2 pos = dir * particleRadius;
        pos += rotate2D(vec2(hash(vec2(seed, iTime * 0.2)), 0.0), iTime * 2.0) * 0.03 * treble;
        
        float d = length(uv - pos);
        float size = 0.005 + treble * 0.007;
        float particle = 0.0;
        
        for (int j = 0; j < PARTICLE_ITERATIONS; j++) {
            float s = size * (1.0 + float(j) * 0.15);
            particle += exp(-d * 50.0 / s) * (1.0 - float(j)/float(PARTICLE_ITERATIONS));
        }
        
        vec3 particleColor = mix(vec3(1.0, 0.8, 0.2), vec3(0.2, 0.8, 1.0), hash(vec2(seed + 93.4)));
        color += particle * particleColor * life * treble * mask;
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
    vec3 linesColor = drawLines(uv, bass, mid, mainMask);
    vec3 particlesColor = drawParticles(uv, treble, mainMask);
    
    vec3 total = linesColor + particlesColor;
    total = screenGlow(total, GLOW_INTENSITY * (1.0 + volume * 2.0), mainMask);
    
    if (mainMask < 0.01) total = vec3(0.0);
    fragColor = vec4(clamp(total, 0.0, 1.8), 1.0);
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