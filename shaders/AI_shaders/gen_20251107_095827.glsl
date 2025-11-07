#version 330 core
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

float hash12(vec2 p) {
    p = fract(p * vec2(114.34, 237.34));
    p += dot(p, p.xy + 23.45);
    return fract(p.x * p.y);
}

mat2 rotate2D(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, -s, s, c);
}

float noise2D(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1,0)), f.x), mix(hash12(i + vec2(0,1)), hash12(i + vec2(1,1)), f.x), f.y);
}

float fbm(vec2 p) {
    float f = 0.0;
    float a = 0.5;
    for(int i=0; i<4; i++) {
        f += a * noise2D(p);
        p *= 2.0;
        a *= 0.5;
    }
    return f;
}

float guardedTexelFetch(vec2 uv) {
    uv = clamp(uv, 0.0, 1.0);
    return TEX(iChannel0, uv).x;
}

vec3 rgbShift(vec3 col, vec2 uv) {
    float shift = 0.01 * fbm(uv * 10.0 + iTime * 0.5);
    return vec3(
        col.r * smoothstep(0.0, 1.0, uv.x + shift),
        col.g * smoothstep(0.0, 1.0, uv.x),
        col.b * smoothstep(0.0, 1.0, uv.x - shift)
    );
}

vec3 screenGlow(vec3 col, float mask, float intensity) {
    return col * mask * intensity + vec3(1.0) * (1.0 - mask) * 0.11;
}

#define MAX_PARTICLES 128

float shapeMask(vec2 p, float bass, float scale) {
    p *= rotate2D(bass * 0.5);
    p *= scale;
    float d = length(p) - 0.5;
    float d2 = length(p * 1.5 + vec2(fbm(p * 5.0 + iTime * 0.3))) - 0.3;
    return smoothstep(0.02, 0.0, d) * smoothstep(0.02, 0.0, d2);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord.xy * 2.0 - iResolution.xy) / min(iResolution.x, iResolution.y);
    vec3 bg = vec3(0.0);

    float bass = guardedTexelFetch(vec2(0.1, 0.0));
    float mid = guardedTexelFetch(vec2(0.35, 0.0));
    float treble = guardedTexelFetch(vec2(0.7, 0.0));
    float volume = (bass + mid + treble) * 0.33;

    float scale = 0.8 + bass * 0.4;
    float mask = shapeMask(uv, bass, scale);

    vec3 col = vec3(0.2 + mid * 0.5, 0.5 + bass * 0.3, 0.8 + treble * 0.4);
    col *= (fbm(uv * 10.0 + iTime * 0.2) * 0.5 + 0.5);
    col *= mask;

    vec3 particles = vec3(0.0);
    for(int i=0; i<MAX_PARTICLES; i++) {
        float t = iTime + float(i) * 0.1;
        float life = fract(t * treble * 2.0 + float(i) * 0.7);
        if(life < 0.9) {
            vec2 pos = vec2(cos(t * 0.5 + float(i)), sin(t * 0.5 + float(i))) * (0.6 + bass * 0.3);
            vec2 vel = (vec2(hash12(vec2(i, t)), hash12(vec2(t, i))) * 2.0 - 1.0) * (0.1 + treble * 0.2);
            pos += vel * (11.0 - life * 10.0);
            float size = 0.03 + volume * 0.05;
            vec3 pcol = vec3(0.5 + life * 0.5, 0.7 + life * 0.3, 1.0) * (1.0 - life);
            float pmask = smoothstep(size, size - 0.01, length(uv - pos));
            particles += pcol * pmask;
        }
    }

    vec3 final = bg;
    final += col;
    final += particles * (1.0 + volume * 2.0);
    final = rgbShift(final, uv);
    final = screenGlow(final, mask + step(0.01, length(particles)), volume * 3.0);

    fragColor = vec4(final, 1.0);
}

void main(){
    #ifdef GL_ES
    vec4 fragColor;
    mainImage(fragColor, gl_FragCoord.xy);
    gl_FragColor = fragColor;
    #else
    out vec4 fragColor;
    mainImage(fragColor, gl_FragCoord.xy);
    #endif
}
