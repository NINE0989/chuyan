#version 330 core
// Simple audio-responsive particle system with color shifts and glow
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

// Helper functions
float hash12(vec2 p) {
    p = fract(p * vec2(456.78, 789.45));
    p += dot(p, p + 34.56);
    return fract(p.x * p.y);
}

mat2 rotate2D(float a) {
    float c = cos(a);
    float s = sin(a);
    return mat2(c, -s, s, c);
}

float noise2D(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    float a = hash12(i);
    float b = hash12(i + vec2(1.0, 0.0));
    float c = hash12(i + vec2(0.0, 1.0));
    float d = hash12(i + vec2(1.0, 1.0));
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}

float fbm(vec2 p, int octaves) {
    float f = 0.0;
    float amp = 0.5;
    float freq = 1.0;
    for (int i = 0; i < octaves; i++) {
        f += amp * noise2D(p * freq);
        amp *= 0.5;
        freq *= 2.0;
    }
    return f;
}

float guardedTexelFetch(float u) {
    vec2 uv = vec2(u, 0.0);
    return TEX(iChannel0, uv).r;
}

vec3 rgbShift(vec3 color, float shift, vec2 uv) {
    float s = shift * 0.002;
    float r = TEX(iChannel0, uv + vec2(s, 0.0)).r;
    float g = TEX(iChannel0, uv).r;
    float b = TEX(iChannel0, uv - vec2(s, 0.0)).r;
    return vec3(r, g, b) * color;
}

vec3 screenGlow(vec3 color, float mask, float strength) {
    float glow = smoothstep(0.0, 0.1, mask) * strength;
    return color + vec3(glow) * mask;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord.xy / iResolution.xy;
    uv -= 0.5;
    uv.x *= iResolution.x / iResolution.y;

    // Audio sampling
    float bass = guardedTexelFetch(0.1);
    float mid = guardedTexelFetch(0.35);
    float treble = guardedTexelFetch(0.75);
    float volume = (bass + mid + treble) * 0.333;

    // Particle arrays (initialized per frame)
    vec2 pos[MAX_PARTICLES];
    vec2 vel[MAX_PARTICLES];
    float life[MAX_PARTICLES];
    for (int i = 0; i < MAX_PARTICLES; i++) {
        if (life[i] <= 0.0 || iTime < 0.1) {
            pos[i] = vec2(hash12(vec2(i, iTime)) - 0.5, hash12(vec2(i, iTime + 1.0)) - 0.5) * 0.2;
            vel[i] = vec2(hash12(vec2(i, iTime + 2.0)) - 0.5, hash12(vec2(i, iTime + 3.0)) - 0.5) * treble * 0.1;
            life[i] = 1.0 + mid * 5.0;
        }
    }

    // Update particles
    for (int i = 0; i < MAX_PARTICLES; i++) {
        if (life[i] <= 0.0) continue;
        float rot = bass * 2.0 * 3.14159;
        vel[i] = rotate2D(rot) * vel[i];
        pos[i] += vel[i];
        life[i] -= 0.01 + treble * 0.05;
        if (abs(pos[i].x) > 0.5 || abs(pos[i].y) > 0.5) {
            vel[i] = -vel[i] * 0.8;
        }
    }

    // Render
    vec3 col = vec3(0.0);
    for (int i = 0; i < MAX_PARTICLES; i++) {
        if (life[i] <= 0.0) continue;
        float dist = length(uv - pos[i]);
        float size = 0.1 + bass * 0.05;
        float mask = 1.0 - dist / size;
        mask = smoothstep(0.0, 0.02, mask);
        if (mask <= 0.01) continue;

        vec3 particleColor = vec3(0.8, 0.5, 1.0) * (0.5 + mid * 0.5);
        particleColor = rgbShift(particleColor, mid * 5.0, uv - pos[i]);
        particleColor = screenGlow(particleColor, mask, volume * 2.0);

        col += particleColor * mask;
    }

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
