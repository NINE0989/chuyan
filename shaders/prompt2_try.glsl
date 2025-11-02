// Electronic Music Viz — rgbshift, nebula, particles, radial

// Compatibility boilerplate: use TEX(sampler, uv) for cross-version texture sampling
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

#ifdef GL_ES
// Shadertoy/WebGL: use gl_FragColor
#else
// Desktop GL: declare output
out vec4 fragColor;
#endif

#define MAX_PARTICLES 192
#define PARTICLE_ITERATIONS 48
#define NEBULA_OCTAVES 3
#define GLOW_INTENSITY 1.5
#define SPECTRUM_WIDTH 512.0

uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;

// Hash function
float hash(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453123);
}

// 2D rotation
vec2 rotate2D(vec2 uv, float a) {
    float c = cos(a), s = sin(a);
    return vec2(uv.x * c - uv.y * s, uv.x * s + uv.y * c);
}

// 2D noise
float noise2D(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

// FBM for nebula
float fbm(vec2 p) {
    float total = 0.0, amp = 0.5;
    for (int i = 0; i < NEBULA_OCTAVES; i++) {
        total += noise2D(p) * amp;
        p *= 2.0;
        amp *= 0.5;
    }
    return clamp(total, 0.0, 1.0);
}

// Nebula density field
float nebulaDensity(vec2 p, float bass) {
    p = rotate2D(p, iTime * 0.05 * (1.0 + bass * 0.3));
    float density = fbm(p * (2.0 + bass * 0.4));
    float radialFalloff = 1.0 - smoothstep(0.0, 1.8 + bass * 0.6, length(p));
    return clamp(density * radialFalloff, 0.0, 1.0);
}

// Safe spectrum sampling
float guardedTexelFetch(float u) {
    u = clamp(u, 0.0, 1.0);
    return TEX(iChannel0, vec2(u, 0.0)).r;
}

// Audio band energy
float getBass() {
    float energy = 0.0;
    for (int i = 0; i < 16; i++) energy += guardedTexelFetch(float(i)/SPECTRUM_WIDTH * 0.2);
    return energy / 16.0;
}

float getMid() {
    float energy = 0.0;
    for (int i = 0; i < 24; i++) energy += guardedTexelFetch(0.2 + float(i)/SPECTRUM_WIDTH * 0.3);
    return energy / 24.0;
}

float getTreble() {
    float energy = 0.0;
    for (int i = 0; i < 32; i++) energy += guardedTexelFetch(0.5 + float(i)/SPECTRUM_WIDTH * 0.5);
    return energy / 32.0;
}

float getOverallVolume() {
    return (getBass() + getMid() + getTreble()) / 3.0;
}

// RGB shift effect
vec3 rgbShift(vec3 col, vec2 uv, float amount) {
    amount = clamp(amount, 0.0, 0.01);
    float r = noise2D(uv + vec2(amount, 0.0) + iTime * 0.5);
    float g = noise2D(uv + iTime * 0.3);
    float b = noise2D(uv - vec2(amount, 0.0) - iTime * 0.4);
    return mix(col, vec3(r, g, b), 0.3);
}

// Screen glow
vec3 screenGlow(vec3 col, float intensity) {
    float bright = dot(col, vec3(0.299, 0.587, 0.114));
    vec3 glow = vec3(pow(bright, 2.0)) * intensity;
    return clamp(col + glow * 0.7, 0.0, 2.0);
}

// Particle struct (inline usage)
vec3 drawParticles(vec2 uv, float treble) {
    vec3 color = vec3(0.0);
    float speed = 2.0 + treble * 4.0;
    int spawnCount = min(MAX_PARTICLES, int(float(MAX_PARTICLES) * (1.0 + treble * 1.2)));
    
    for (int i = 0; i < spawnCount; i++) {
        float seed = float(i) * 45.678;
        vec2 dir = rotate2D(vec2(1.0, 0.0), hash(vec2(seed)) * 6.283);
        float t = iTime * speed + hash(vec2(seed + 123.0)) * 50.0;
        float dist = fract(t);
        float life = pow(1.0 - dist, 2.0);
        
        if (dist > 0.8 - treble * 0.5) continue;
        
        vec2 pos = dir * dist * (1.5 + treble * 0.3);
        pos += rotate2D(vec2(hash(vec2(seed, iTime)), hash(vec2(seed + 456.0, iTime))), iTime) * 0.02 * treble;
        
        float d = length(uv - pos);
        float size = 0.008 + treble * 0.006;
        float particle = 0.0;
        
        for (int j = 0; j < PARTICLE_ITERATIONS; j++) {
            float s = size * (1.0 + float(j) * 0.15);
            particle += exp(-d * 35.0 / s) * (1.0 - float(j)/float(PARTICLE_ITERATIONS));
        }
        
        vec3 hue = mix(vec3(0.8, 0.2, 1.0), vec3(0.2, 1.0, 1.0), hash(vec2(seed + 789.0)));
        hue = mix(hue, vec3(1.0), treble * 0.4);
        color += particle * hue * life * (1.0 + treble);
    }
    
    return color;
}

// Radial rings for beats
vec3 drawRings(vec2 uv, float bass) {
    vec3 color = vec3(0.0);
    float radius = length(uv);
    float ring = sin(radius * 12.0 - iTime * 4.0 - bass * 8.0) * 0.5 + 0.5;
    ring *= smoothstep(0.0, 0.2, bass);
    ring *= 1.0 - smoothstep(0.8, 1.2, radius);
    color += vec3(ring * 0.3) * mix(vec3(1.0, 0.5, 1.0), vec3(0.5, 1.0, 1.0), hash(vec2(radius, iTime)));
    return color;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord * 2.0 - iResolution.xy) / min(iResolution.x, iResolution.y);
    float bass = getBass();
    float mid = getMid();
    float treble = getTreble();
    float volume = getOverallVolume();
    
    // Nebula base
    float density = nebulaDensity(uv, bass);
    vec3 nebulaCol = mix(vec3(0.3, 0.1, 0.8), vec3(0.1, 0.4, 0.9), density);
    nebulaCol *= density * (1.0 + bass * 2.5);
    
    // Add mid-driven detail
    vec2 midUV = uv + noise2D(uv * 8.0 + iTime * 2.0) * mid * 0.1;
    float detail = fbm(midUV * 6.0);
    nebulaCol = mix(nebulaCol, nebulaCol * 1.3, detail * mid);
    
    // RGB shift
    nebulaCol = rgbShift(nebulaCol, uv, mid * 0.008);
    
    // Particles and rings
    vec3 particles = drawParticles(uv, treble);
    vec3 rings = drawRings(uv, bass);
    
    // Combine and glow
    vec3 total = nebulaCol + particles + rings;
    total = screenGlow(total, GLOW_INTENSITY * (1.0 + volume * 2.2));
    
    // Final clamp
    total = clamp(total, 0.0, 1.8);
    fragColor = vec4(total, 1.0);
}

// Desktop / WebGL adapter
void main() {
    vec4 outCol = vec4(0.0);
    mainImage(outCol, gl_FragCoord.xy);
#ifdef GL_ES
    gl_FragColor = outCol;
#else
    fragColor = outCol;
#endif
}
