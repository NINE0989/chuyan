// Fourier Lines - audio reactive, horizontal spectrum, SAFE_MARGIN=0.05 FIT_MODE=INSIDE
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
#define GLOW_INTENSITY 1.2
#define SAFE_MARGIN 0.05
#define FIT_MODE_INSIDE 1
#define EDGE_SMOOTH 0.006
#define LINE_COUNT 64
#define BASE_LINE_WIDTH 0.015

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
    for (int i = 0; i < 8; i++) energy += guardedTexelFetch(float(i)/float(LINE_COUNT) * 0.2);
    return clamp(energy / 8.0, 0.0, 1.0);
}

float getMid() {
    float energy = 0.0;
    for (int i = 0; i < 16; i++) energy += guardedTexelFetch(0.2 + float(i)/float(LINE_COUNT) * 0.3);
    return clamp(energy / 16.0, 0.0, 1.0);
}

float getTreble() {
    float energy = 0.0;
    for (int i = 0; i < 24; i++) energy += guardedTexelFetch(0.5 + float(i)/float(LINE_COUNT) * 0.5);
    return clamp(energy / 24.0, 0.0, 1.0);
}

float getOverallVolume() {
    return clamp((getBass() + getMid() + getTreble()) / 3.0, 0.0, 1.0);
}

float lineMask(vec2 uv, float xPos, float height, float width) {
    float maxX = 1.0 - SAFE_MARGIN;
    float minX = -maxX;
    float maxY = 1.0 - SAFE_MARGIN;
    
    float xMask = smoothstep(xPos - width, xPos, uv.x) - 
                  smoothstep(xPos, xPos + width, uv.x);
    float yMask = smoothstep(0.0, EDGE_SMOOTH, uv.y) - 
                  smoothstep(height, height + EDGE_SMOOTH, uv.y);
    float boundMask = step(uv.x, maxX) * step(minX, uv.x) * step(uv.y, maxY);
    
    return xMask * yMask * boundMask;
}

float edgeMask(float v) {
    return smoothstep(0.0, EDGE_SMOOTH, v);
}

vec3 rgbShift(vec3 col, float freq, float amount) {
    amount = clamp(amount, 0.0, 0.012);
    float shift = sin(freq * 6.283 + iTime) * amount;
    return vec3(
        col.r * (1.0 + shift * 10.0),
        col.g,
        col.b * (1.0 - shift * 10.0)
    );
}

vec3 screenGlow(vec3 col, float intensity, float mask) {
    float bright = dot(col, vec3(0.299, 0.587, 0.114));
    vec3 glow = vec3(pow(bright, 2.0)) * intensity * mask;
    return clamp(col + glow * 0.5, 0.0, 1.8);
}

vec3 drawSpectrumLines(vec2 uv, float bass, float mid, float treble, out float totalMask) {
    totalMask = 0.0;
    vec3 color = vec3(0.0);
    float maxX = 1.0 - SAFE_MARGIN;
    float minX = -maxX;
    float xStep = (maxX - minX) / float(LINE_COUNT - 1);
    float colorPhase = iTime * 1.2;

    for (int i = 0; i < LINE_COUNT; i++) {
        float xPos = minX + float(i) * xStep;
        float u = float(i) / float(LINE_COUNT - 1);
        float spectrum = guardedTexelFetch(u);
        
        float heightScale = 0.7;
        float height = spectrum * heightScale * (1.0 + bass * 0.5);
        float width = BASE_LINE_WIDTH + mid * 0.01;
        
        float mask = lineMask(uv, xPos, height, width);
        totalMask = max(totalMask, mask);
        
        vec3 lineColor = vec3(
            sin(colorPhase + u * 6.283),
            sin(colorPhase + u * 6.283 + 2.094),
            sin(colorPhase + u * 6.283 + 4.188)
        ) * 0.5 + 0.5;
        
        float freqBoost = u < 0.2 ? bass * 2.0 : (u > 0.5 ? treble * 2.0 : mid * 1.5);
        lineColor *= (1.0 + spectrum * freqBoost);
        
        float detail = noise2D(vec2(xPos * 10.0, iTime * 4.0)) * mid * 0.6;
        lineColor = mix(lineColor, lineColor * (0.7 + detail), 0.4);
        
        lineColor = rgbShift(lineColor, u, mid * 0.6);
        color += lineColor * mask;
    }
    
    totalMask = clamp(totalMask, 0.0, 1.0);
    return color;
}

vec3 drawParticles(vec2 uv, float treble, float mask) {
    if (mask < 0.01 || treble < 0.05) return vec3(0.0);
    
    vec3 color = vec3(0.0);
    float speed = 1.5 + treble * 4.0;
    int spawnCount = min(MAX_PARTICLES, int(float(MAX_PARTICLES) * (1.0 + treble * 1.0)));
    float maxX = 1.0 - SAFE_MARGIN;
    float minX = -maxX;
    float maxY = 1.0 - SAFE_MARGIN;
    
    for (int i = 0; i < spawnCount; i++) {
        float seed = float(i) * 41.37;
        float u = hash(vec2(seed)) * 1.0;
        float spectrum = guardedTexelFetch(u);
        if (spectrum < 0.15) continue;
        
        float xPos = mix(minX, maxX, u);
        float yPos = hash(vec2(seed + 29.7)) * spectrum * 0.7 * (1.0 + getBass() * 0.5);
        
        float t = iTime * speed + hash(vec2(seed + 53.1)) * 60.0;
        float life = pow(fract(t), 2.0) * pow(1.0 - fract(t), 2.0) * 4.0;
        
        vec2 pos = vec2(xPos, yPos);
        pos.x += sin(t * 2.0) * 0.02 * treble;
        pos.y += cos(t * 1.5) * 0.015 * treble;
        
        pos.x = clamp(pos.x, minX, maxX);
        pos.y = clamp(pos.y, 0.0, maxY);
        
        float d = length(uv - pos);
        float size = 0.004 + treble * 0.005 * spectrum;
        float particle = 0.0;
        
        for (int j = 0; j < PARTICLE_ITERATIONS; j++) {
            float s = size * (1.0 + float(j) * 0.1);
            particle += exp(-d * 70.0 / s) * (1.0 - float(j)/float(PARTICLE_ITERATIONS));
        }
        
        vec3 particleColor = mix(vec3(1.0, 0.8, 0.2), vec3(0.2, 0.8, 1.0), hash(vec2(seed + 79.4)));
        color += particle * particleColor * life * treble * spectrum * mask;
    }
    
    return color;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    float scale = min(iResolution.x, iResolution.y);
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / scale;
    uv.y = -uv.y;
    
    float bass = getBass();
    float mid = getMid();
    float treble = getTreble();
    float volume = getOverallVolume();
    
    float mainMask = 0.0;
    vec3 linesColor = drawSpectrumLines(uv, bass, mid, treble, mainMask);
    vec3 particlesColor = drawParticles(uv, treble, mainMask);
    
    vec3 total = linesColor + particlesColor;
    total = screenGlow(total, GLOW_INTENSITY * (1.0 + volume * 2.0), mainMask);
    
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