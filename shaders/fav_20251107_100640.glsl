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

// Hash function
float hash12(vec2 p) {
    p = fract(p * vec2(11347.9, 34454.1));
    p += dot(p, p + 23.43);
    return fract(p.x * p.y);
}

// Rotation matrix
mat2 rotate2D(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, -s, s, c);
}

// Noise function
float noise2D(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash12(i);
    float b = hash12(i + vec2(1,0));
    float c = hash12(i + vec2(0,1));
    float d = hash12(i + vec2(1,1));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

// FBM
float fbm(vec2 p) {
    float f = 0.0;
    float amp = 0.5;
    for(int i=0; i<4; i++) {
        f += amp * noise2D(p);
        p *= 2.0;
        amp *= 0.5;
    }
    return f;
}

// Guarded texel fetch
float guardedTexelFetch(vec2 uv) {
    uv = clamp(uv, 0.001, 0.999);
    return TEX(iChannel0, uv).x;
}

// RGB shift
vec3 rgbShift(vec3 col, vec2 uv) {
    float r = TEX(iChannel0, uv + 0.001).x;
    float g = TEX(iChannel0, uv).x;
    float b = TEX(iChannel0, uv - 0.001).x;
    return col * vec3(r, g, b);
}

// Screen glow
vec3 screenGlow(vec3 col, float mask, float intensity) {
    return col * mask + (1.0 - pow(1.0 - mask, intensity)) * vec3(0.6, 0.3, 1.0);
}

#define MAX_PARTICLES 128
#define PARTICLE_ITERATIONS 32

struct Particle {
    vec2 pos;
    vec2 vel;
    float life;
    float size;
};

Particle particles[MAX_PARTICLES];

void initParticles(float bass, float treble, vec2 center) {
    for(int i=0; i<MAX_PARTICLES; i++) {
        vec2 hash = vec2(hash12(vec2(i, iTime)), hash12(vec2(i+1, iTime)));
        float spawnChance = treble * 2.0 * 0.01;
        if(hash.y < spawnChance) {
            particles[i].pos = center + (hash.x*2.0-1.0)*120.0 * bass;
            particles[i].vel = normalize(hash - 0.5) * 60.0 * treble * 0.01;
            particles[i].life = 1.0 + hash.y * 2.0;
            particles[i].size = 66.0 * bass * (1.0 - hash.y);
        } else {
            particles[i].pos += particles[i].vel * iTime * 0.02;
            particles[i].life -= 0.01;
            if(particles[i].life < 0.0 || length(particles[i].pos - center) > 250.0) {
                particles[i].pos = center;
                particles[i].vel = normalize(hash - 0.5) * 660.0 * treble * 0.01;
                particles[i].life = 1.0 + hash.y * 2.0;
                particles[i].size = 66.0 * bass * (1.0 - hash.y);
            }
        }
    }
}

float shapeMask(vec2 p, vec2 center, float size, float bass) {
    float r = length(p - center) / size;
    float distortion = fbm(p * 0.12 + bass * 0.5) * 0.22;
    r += distortion;
    return smoothstep(1.0, 0.98, r);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord.xy * 2.0 - iResolution.xy) / iResolution.y;
    vec2 center = vec2(0.0);

    float bass = guardedTexelFetch(vec2(0.1, 0.0));
    float mid = guardedTexelFetch(vec2(0.3, 0.0));
    float treble = guardedTexelFetch(vec2(0.7, 0.0));
    float overallVol = guardedTexelFetch(vec2(0.5, 0.0));

    initParticles(bass, treble, center);

    vec3 col = vec3(0.0);

    float shapeSize = 2.2 * bass * 1.5;
    uv = uv * rotate2D(bass * 22.0 + iTime * 0.5);
    float mask = shapeMask(uv, center, shapeSize, bass);

    float detail = fbm(uv * 11.0 + mid * 5.0 + iTime * 0.33);
    mask *= detail * 0.8 + 0.2;

    float glowInt = overallVol * 3.3;
    col = screenGlow(vec3(0.88, 0.22, 0.99), mask, glowInt);

    for(int i=0; i<MAX_PARTICLES; i++) {
        Particle p = particles[i];
        vec2 pUv = (fragCoord - p.pos) / (p.size * 0.5);
        float pMask = smoothstep(1.0, 0.98, length(pUv));
        float pLife = p.life / 3.3;
        vec3 pCol = vec3(treble * 0.8, bass * 0.5, 1.0 - treble) * pLife;
        col += pCol * pMask * treble * 0.5;
    }

    col = rgbShift(col, uv + mid * 0.01);

    fragColor = vec4(col, 1.0);
}

void main(){
    #ifdef GL_ES
    vec4 fragColor;
    mainImage(fragColor, gl_FragCoord.xy);
    gl_FragColor = fragColor;
    #else
    mainImage(gl_FragColor, gl_FragCoord.xy);
    #endif
}
