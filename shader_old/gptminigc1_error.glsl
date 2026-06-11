// Nebula + Energy Flow (rgbshift, chromatic, radial, cyclic)
// Self-contained GLSL fragment shader
// Exposes mainImage(...) for Shadertoy-style loaders and a standard main() adapter.

// =======================
// Configuration
// =======================
#define MAX_PARTICLES 128        // <=256 recommended
#define NEBULA_OCTAVES 4
#define PARTICLE_SCALE 1.6
#define PARTICLE_SPEED 1.6
#define BASE_GLOW 0.9
#define CHROMA_SHIFT 0.008      // chromatic aberration offset
#define PI 3.14159265359
#define EPS 1e-6

uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0; // audio texture: 512x2 ; y=0.0 -> FFT (spectrum)

// =======================
// Helpers: hash / noise
// =======================
float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 78.233);
    return fract(p.x * p.y);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    // Four corners
    float a = hash21(i + vec2(0.0,0.0));
    float b = hash21(i + vec2(1.0,0.0));
    float c = hash21(i + vec2(0.0,1.0));
    float d = hash21(i + vec2(1.0,1.0));
    vec2 u = f*f*(3.0-2.0*f);
    return mix(mix(a,b,u.x), mix(c,d,u.x), u.y);
}

float fbm(vec2 p) {
    float v = 0.0;
    float amp = 0.5;
    float freq = 1.0;
    for (int i=0;i<NEBULA_OCTAVES;i++){
        v += amp * noise(p * freq);
        freq *= 2.0;
        amp *= 0.5;
    }
    return v;
}

// rotate 2D
mat2 rot(float a){ float s = sin(a), c = cos(a); return mat2(c,-s,s,c); }

// clamp safe
float safeDiv(float a, float b){ return a / max(abs(b), EPS); }

// =======================
// Audio helpers (spectrum sampling)
// iChannel0: 512x2 texture, y=0.0 => spectrum
// =======================
float spectrumAt(float u){
    // clamp u to [0,1)
    u = clamp(u, 0.0, 0.9999);
    return texture(iChannel0, vec2(u, 0.0)).r;
}

float sampleRangeAvg(float u0, float u1, int steps){
    float sum = 0.0;
    for(int i=0;i<steps;i++){
        float t = float(i) / float(steps-1);
        float u = mix(u0, u1, t);
        sum += spectrumAt(u);
    }
    return sum / float(steps);
}

float getBass(){
    // low freq avg [0,0.2]
    return sampleRangeAvg(0.0, 0.20, 8);
}
float getTreble(){
    // high freq avg [0.5,1.0]
    return sampleRangeAvg(0.50, 0.99, 8);
}
float getOverall(){
    return sampleRangeAvg(0.0, 0.99, 16);
}

// =======================
// Color helpers: palette + chromatic shift
// =======================
vec3 nebulaPalette(float t){
    // deep blue -> purple
    vec3 a = vec3(0.05, 0.06, 0.25);
    vec3 b = vec3(0.25, 0.03, 0.4);
    vec3 c = vec3(0.9, 0.7, 1.0);
    return mix(mix(a,b,t), c, smoothstep(0.6,1.0,t));
}

vec3 chromaShiftedColor(vec2 coord, vec3 col){
    // approximate chromatic aberration by offsetting coords and modulating channels
    vec3 outc;
    outc.r = texture(iChannel0, vec2(fract(coord.x + CHROMA_SHIFT), 0.0)).r * 0.0 + col.r; // keep channel base
    // we simply tint channels slightly to emulate chroma / rgbshift without extra texture fetches
    outc.r = col.r * 1.05;
    outc.g = col.g * 1.02;
    outc.b = col.b * 0.98;
    return outc;
}

// =======================
// Nebula: radial + fbm noise
// =======================
vec3 drawNebula(vec2 uv, float bassEnergy){
    // uv centered [-1,1], aspect corrected
    float r = length(uv);
    float angle = atan(uv.y, uv.x);
    // rotating noise to create cyclic motion
    vec2 ncoord = uv * (1.0 + bassEnergy*0.8);
    ncoord = ncoord * 1.5;
    ncoord = rot(iTime * 0.02) * ncoord;
    float n = fbm(ncoord * 0.8);
    n = pow(n, 1.2);

    // radial falloff and core boost by bass
    float fall = smoothstep(1.2, 0.0, r);
    float core = pow(max(0.0, 1.0 - r*1.6), 2.0) * (1.0 + bassEnergy*2.5);

    float rings = 0.5 + 0.5 * cos(r * 12.0 - iTime*0.3);
    float pattern = mix(n, n * rings, 0.25);

    float intensity = pattern * fall * core;

    vec3 base = nebulaPalette(clamp(pattern, 0.0, 1.0));
    base *= intensity;

    // slight radial scaling shimmer (cyclic)
    base *= 0.8 + 0.25 * sin(iTime*0.5 + r*10.0);

    return base;
}

// =======================
// Particles: energy stream outward
// =======================
vec3 drawParticles(vec2 uv, float trebleEnergy, float overall){
    vec3 col = vec3(0.0);
    float speed = PARTICLE_SPEED * (1.0 + trebleEnergy * 3.0);
    float spawnBias = 0.6 - trebleEnergy * 0.45; // lower threshold => more spawns
    spawnBias = clamp(spawnBias, 0.05, 0.9);

    // loop over a moderate fixed set of seeds
    for(int i=0; i<MAX_PARTICLES; i++){
        // distribute particle seeds radially using hash
        float fi = float(i);
        // random angle per particle
        float seed = hash21(vec2(fi, floor(iTime * 0.1)));
        float angle = seed * 6.283185 + iTime * 0.2 * (0.5 + seed);
        // slight cyclic modulation to keep pattern interesting
        angle += sin(iTime * 0.3 + fi * 0.12) * 0.3;

        // radial progress
        // use time+seed to compute distance [0..1)
        float t = fract(iTime * speed * (0.05 + seed*0.95) + seed * 7.3);
        // particle spawned only when t less than threshold (emission)
        if (t > spawnBias) continue;

        // particle position in world
        float distance = t * (1.8 + trebleEnergy * 1.8);
        vec2 pos = vec2(cos(angle), sin(angle)) * distance;

        // particle soft size scaled by treble
        float psize = 0.012 + 0.018 * trebleEnergy + 0.002 * fract(seed*10.0);

        // draw soft particle (gaussian-ish)
        float d = length(uv - pos);
        float particle = exp(-d * 40.0 / max(psize, 0.001)) * (1.0 - t);
        // trail: sample past position for motion blur
        vec2 prevPos = vec2(cos(angle), sin(angle)) * max(distance - 0.06, 0.0);
        float trail = exp(-length(uv - prevPos) * 16.0 / max(psize, 0.001)) * 0.25 * (1.0 - t);

        // color: bright cyan-white with slight hue variation from seed
        float hueMix = fract(seed * 3.7);
        vec3 particleColor = mix(vec3(0.5, 1.0, 1.0), vec3(1.0), hueMix*0.6);
        vec3 particleCol = (particle + trail) * particleColor * (1.0 + trebleEnergy*1.4);

        // attenuate with radial distance for scene depth
        particleCol *= smoothstep(1.8, 0.3, distance);

        col += particleCol;
    }

    // moderate tone mapping
    col *= 1.2;
    // slight chromatic tint based on overall volume
    col = mix(col, vec3(col.r*1.05, col.g*1.02, col.b*0.98), clamp(overall*1.5,0.0,1.0));

    return col;
}

// =======================
// Glow / post
// =======================
vec3 applyGlow(vec3 color, float glowAmt){
    // simple per-pixel glow boost (not full-screen blur for performance)
    float luminance = dot(color, vec3(0.299,0.587,0.114));
    return color + vec3(pow(luminance,1.6)) * glowAmt * 0.7;
}

// =======================
// mainImage: Shadertoy entry
// =======================
void mainImage(out vec4 fragColor, in vec2 fragCoord){
    // Normalize coords: center origin, -1..1 (aspect-corrected)
    vec2 uv = (fragCoord.xy - 0.5 * iResolution.xy) / min(iResolution.x, iResolution.y);

    // sample audio aggregates
    float bass = getBass();        // [0..1]
    float treble = getTreble();    // [0..1]
    float overall = getOverall();  // [0..1]

    // nebula and particles
    vec3 neb = drawNebula(uv, bass);
    vec3 parts = drawParticles(uv, treble, overall);

    // combine with radial scaling for focal center
    float radial = smoothstep(1.6, 0.0, length(uv));
    vec3 color = neb * 0.9 + parts * 1.2;
    color *= mix(0.85, 1.1, radial);

    // apply glow / bloom intensity controlled by overall audio
    float glow = BASE_GLOW * (0.6 + overall * 2.5);
    color = applyGlow(color, glow);

    // small chromatic shift (baked)
    vec3 finalColor = chromaShiftedColor(uv, color);

    // clamp and gamma
    finalColor = clamp(finalColor, 0.0, 1.3);
    finalColor = pow(finalColor, vec3(0.95)); // slight gamma

    fragColor = vec4(finalColor, 1.0);
}

// =======================
// Adapter: provide standard main() for GL compilers expecting void main()
// =======================
#ifndef GL_ES
out vec4 fragColor;
#endif

void main(){
    vec4 outCol;
    vec2 fragCoord = gl_FragCoord.xy;
    mainImage(outCol, fragCoord);
#ifdef GL_ES
    gl_FragColor = outCol;
#else
    fragColor = outCol;
#endif
}