// Simple Audio-Reactive Particle & Wave Shader
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
    p = fract(p * vec2(114.233, 233.444));
    p += dot(p, p + 33.33);
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
    float a = hash12(i);
    float b = hash12(i + vec2(1,0));
    float c = hash12(i + vec2(0,1));
    float d = hash12(i + vec2(1,1));
    return mix(mix(a,b,f.x), mix(c,d,f.x), f.y);
}

float fbm(vec2 p) {
    float sum = 0.0, amp = 0.5;
    for(int i=0; i<4; i++) {
        sum += amp * noise2D(p);
        p *= 2.0;
        amp *= 0.5;
    }
    return sum;
}

float guardedTexelFetch(float u) {
    return TEX(iChannel0, vec2(clamp(u,0.,1.), 0.)).r;
}

vec3 rgbShift(vec2 uv, float shift) {
    vec3 col;
    col.r = TEX(iChannel0, uv+shift).r;
    col.g = TEX(iChannel0, uv).g;
    col.b = TEX(iChannel0, uv-shift).b;
    return col;
}

vec3 screenGlow(vec3 col, float glow) {
    return col + col*glow - col*col*glow;
}

#define MAX_PARTICLES 128
#define PARTICLE_ITERATIONS 32

vec2 getParticlePos(int idx, float time) {
    vec2 pos = vec2(hash12(vec2(idx,0))*2.-1., hash12(vec2(idx,1))*2.-1.);
    vec2 vel = vec2(hash12(vec2(idx,2))*0.5-0.25, hash12(vec2(idx,3))*0.5-0.25);
    pos += vel * time * 0.5;
    return fract(pos + 0.5)*2.-1.;
}

float shapeMask(vec2 p, float bass) {
    float radius = 0.3 + bass*0.2;
    float circle = smoothstep(radius+0.01, radius, length(p));
    float mid = guardedTexelFetch(0.35);
    float waves = sin(length(p)*10. - iTime*5. + mid*2.)*0.1;
    return circle * (1. - waves);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord*2. - iResolution.xy)/iResolution.y;
    uv *= rotate2D(iTime*0.5 + guardedTexelFetch(0.1)*0.3);
    
    float bass = guardedTexelFetch(0.1);
    float mid = guardedTexelFetch(0.35);
    float treble = guardedTexelFetch(0.6);
    float volume = (bass+mid+treble)/3.;
    
    vec3 col = vec3(0.);
    
    float mask = shapeMask(uv, bass);
    if(mask>0.) {
        vec3 shapeCol = vec3(bass*1.2, mid*1.5, treble*1.8);
        col = screenGlow(shapeCol, volume*22.);
    }
    
    float pDensity = treble*0.8 + 0.2;
    for(int i=0; i<MAX_PARTICLES; i++) {
        vec2 pPos = getParticlePos(i, iTime);
        float dist = length(uv - pPos);
        float size = 0.01 + mid*0.02;
        float pMask = smoothstep(size+0.005, size, dist);
        vec3 pCol = vec3(treble*1.5, bass*1.0, 0.5);
        col += pCol * pMask * pDensity;
    }
    
    fragColor = vec4(col, 1.);
}

void main(){
    #ifdef GL_ES
    vec4 fragColor;
    mainImage(fragColor, gl_FragCoord.xy);
    gl_FragColor = fragColor;
    #else
    mainImage(fragColor, gl_FragCoord.xy);
    #endif
}
