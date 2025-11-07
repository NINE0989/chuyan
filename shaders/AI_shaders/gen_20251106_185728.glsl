#version 330 core
// Simple audio-reactive particle shader with circular mask and RGB shift
// Compatibility boilerplate
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

uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;

#define MAX_PARTICLES 128
#define PARTICLE_ITERATIONS 32
#define BASS_UV 0.1
#define MID_UV 0.35
#define TREBLE_UV 0.75
#define GLOW_STRENGTH 0.8
#define SHAPE_THRESH 0.1
#define ANTIALIAS 0.02
#define RGB_SHIFT_AMT 0.005
#define NOISE_SCALE 0.02
#define PARTICLE_LIFE 3.0

float hash12(vec2 p) {
    vec3 k = vec3(0.1428, 0.5714, 0.8571);
    p = p * k.xy + k.z;
    return fract(16.0 * k.z * fract(p.x * p.y * (p.x + p.y)));
}

vec2 rotate2D(vec2 p, float a) {
    float s = sin(a);
    float c = cos(a);
    return vec2(p.x * c - p.y * s, p.x * s + p.y * c);
}

float noise2D(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash12(i);
    float b = hash12(i + vec2(1.0, 0.0));
    float c = hash12(i + vec2(0.0, 1.0));
    float d = hash12(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm(vec2 p) {
    float f = 0.0;
    float a = 0.5;
    float s = 1.0;
    for (int i=0; i<4; i++) {
        f += a * noise2D(p * s);
        s *= 2.0;
        a *= 0.5;
    }
    return f;
}

float guardedTexelFetch(float u) {
    static float cache[3];
    int idx = int(u * 2.0);
    if (cache[idx] == 0.0) {
        vec2 uv = vec2(u, 0.0);
        cache[idx] = TEX(iChannel0, uv).r;
    }
    return cache[idx];
}

vec3 rgbShift(vec3 col, vec2 uv, float amt) {
    vec2 offsetR = amt * vec2(1.0, 0.0);
    vec2 offsetG = amt * vec2(0.0, 1.0);
    vec2 offsetB = amt * vec2(-1.0, 0.0);
    float r = col.r * TEX(iChannel0, uv + offsetR).r;
    float g = col.g * TEX(iChannel0, uv + offsetG).g;
    float b = col.b * TEX(iChannel0, uv + offsetB).b;
    return vec3(r, g, b);
}

vec3 screenGlow(vec3 col, float mask, float vol) {
    float glow = mask * vol * GLOW_STRENGTH;
    return col + vec3(glow) * mask;
}

struct Particle {
    vec2 pos;
    vec2 vel;
    float life;
    vec3 color;
};

Particle particles[MAX_PARTICLES];
bool particlesInitialized = false;

float shapeMask(vec2 p) {
    vec2 center = iResolution.xy * 0.5;
    float dist = length(p - center) / (iResolution.x * 0.5);
    return 1.0 - smoothstep(0.4, 0.4 + ANTIALIAS, dist);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    if (!particlesInitialized) {
        for (int i=0; i<MAX_PARTICLES; i++) {
            vec2 center = iResolution.xy * 0.5;
            float angle = float(i) * 6.283 / float(MAX_PARTICLES);
            vec2 pos = center + vec2(cos(angle), sin(angle)) * (iResolution.x * 0.2);
            particles[i] = Particle(pos, vec2(0.0), PARTICLE_LIFE * (0.5 + 0.5 * hash12(vec2(i))), 
                vec3(0.5 + 0.5 * sin(float(i) * 0.3), 0.5 + 0.5 * sin(float(i) * 0.5), 0.5 + 0.5 * sin(float(i) * 0.7)));
        }
        particlesInitialized = true;
    }

    float bass = guardedTexelFetch(BASS_UV);
    float mid = guardedTexelFetch(MID_UV);
    float treble = guardedTexelFetch(TREBLE_UV);
    float vol = (bass + mid + treble) * 0.3333;

    for (int i=0; i<PARTICLE_ITERATIONS; i++) {
        if (i >= MAX_PARTICLES) break;
        Particle p = particles[i];
        
        p.vel += rotate2D(vec2(0.0, 0.01), bass * 2.0) * (0.5 + noise2D(p.pos * NOISE_SCALE + iTime) * 0.5);
        p.pos += p.vel + vec2(sin(iTime * mid * 0.5 + p.pos.y * 0.1), cos(iTime * mid * 0.5 + p.pos.x * 0.1)) * mid * 0.5;
        p.life -= treble * 0.5 * (1.0 + noise2D(p.pos * NOISE_SCALE + iTime * 0.5) * 0.5);
        
        if (p.life <= 0.0) {
            vec2 center = iResolution.xy * 0.5;
            float angle = iTime + float(i) * 0.1;
            p.pos = center + vec2(cos(angle), sin(angle)) * (iResolution.x * 0.2 * (0.5 + bass));
            p.vel = vec2(0.0);
            p.life = PARTICLE_LIFE * (0.5 + 0.5 * hash12(vec2(i, iTime)));
            p.color = vec3(0.5 + 0.5 * sin(float(i) * 0.3 + iTime * 0.1), 0.5 + 0.5 * sin(float(i) * 0.5 + iTime * 0.2), 0.5 + 0.5 * sin(float(i) * 0.7 + iTime * 0.3));
        }
        
        particles[i] = p;
    }

    vec2 uv = fragCoord.xy / iResolution.xy;
    vec3 col = vec3(0.0);
    float mask = shapeMask(fragCoord);
    if (mask <= SHAPE_THRESH) {
        fragColor = vec4(col, 1.0);
        return;
    }

    for (int i=0; i<PARTICLE_ITERATIONS; i++) {
        if (i >= MAX_PARTICLES) break;
        Particle p = particles[i];
        float dist = length(fragCoord - p.pos) / (iResolution.x * 0.1);
        float particleMask = smoothstep(1.0, 0.0, dist) * (p.life / PARTICLE_LIFE);
        vec3 particleCol = p.color * particleMask;
        particleCol = rgbShift(particleCol, uv, RGB_SHIFT_AMT * (1.0 + bass));
        col += particleCol;
    }

    col = screenGlow(col, mask, vol);
    fragColor = vec4(col, 1.0);
}

void main() {
    #ifdef GL_ES
    vec4 fragColor;
    mainImage(fragColor, gl_FragCoord.xy);
    gl_FragColor = fragColor;
    #else
    out vec4 fragColor;
    mainImage(fragColor, gl_FragCoord.xy);
    #endif
}
