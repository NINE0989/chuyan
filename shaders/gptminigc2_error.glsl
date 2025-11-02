// Horizontal spectrum lines — AUDIO_ATTACK=0.08 AUDIO_DECAY=0.30 SAFE_MARGIN=0.05
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

// Layout / safety
#define SAFE_MARGIN 0.05
#define FIT_MODE_INSIDE 1

// Audio smoothing (stateless fallback defaults)
#define AUDIO_ATTACK 0.08
#define AUDIO_DECAY  0.30
#define AUDIO_SMOOTH_K 0.85

// Configurable performance knobs
#define BANDS 64
#define MAX_PARTICLES 128
#define PARTICLE_ITERATIONS 32
#define NEBULA_OCTAVES 3
#define GLOW_INTENSITY 0.8

uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;

#ifndef GL_ES
out vec4 fragColor;
#endif

// Minimal helpers
float safeDiv(float a, float b) { return a / max(abs(b), 1e-6); }
vec2 shortEdgeNormalize(vec2 fragCoord) {
    float scale = min(iResolution.x, iResolution.y);
    return (fragCoord - 0.5 * iResolution.xy) / scale;
}

// simple HSV->RGB (compact)
vec3 hsv(float h, float s, float v){
    vec3 c = vec3(abs(fract(h + vec3(0.0,2.0/3.0,1.0/3.0))*6.0-3.0)-1.0);
    c = clamp(c,0.0,1.0);
    return v * mix(vec3(1.0), c, s);
}

// shape mask: thin horizontal band with controlled antialiasing
float horizontalBandMask(float y, float bandY, float halfWidth) {
    float d = abs(y - bandY);
    return smoothstep(halfWidth, halfWidth - 0.005, d); // finite-width AA
}

// map screen uv into safe content box [0..1] (left-to-right layout)
vec2 safeUV(vec2 fragCoord) {
    vec2 uv = fragCoord.xy / iResolution.xy;
    float left = SAFE_MARGIN;
    float right = 1.0 - SAFE_MARGIN;
    float bottom = SAFE_MARGIN;
    float top = 1.0 - SAFE_MARGIN;
    vec2 out;
    out.x = clamp((uv.x - left) / max(right - left, 1e-6), 0.0, 1.0);
    out.y = clamp((uv.y - bottom) / max(top - bottom, 1e-6), 0.0, 1.0);
    return out;
}

// stateless band sample with small neighbor averaging (N=3)
float sampleBandAvg(float u, float du) {
    float a = TEX(iChannel0, vec2(clamp(u - du, 0.0, 1.0), 0.0)).r;
    float b = TEX(iChannel0, vec2(clamp(u, 0.0, 1.0), 0.0)).r;
    float c = TEX(iChannel0, vec2(clamp(u + du, 0.0, 1.0), 0.0)).r;
    return (a + b + c) / 3.0;
}

// stateless smoothing fallback using neighbor baseline as previousApprox
float computeSmoothEnergyStateless(float u, float du, float lowBaseline) {
    float bandAvg = sampleBandAvg(u, du);
    bandAvg = clamp(bandAvg, 0.0, 1.0);
    float compressed = pow(bandAvg, 0.65);
    float rateLimit = clamp(1.0 - AUDIO_SMOOTH_K, 0.01, 0.5);
    float smoothE_approx = mix(compressed, lowBaseline, rateLimit);
    return smoothE_approx;
}

// color ramp per band (mapped to hue)
vec3 bandColor(float bandNorm, float intensity, vec2 uvShift) {
    float hue = 0.08 + 0.7 * bandNorm + 0.12 * sin(iTime * 0.5 + bandNorm * 6.28);
    float sat = 0.85;
    float val = clamp(intensity * 1.6, 0.0, 1.2);
    // subtle RGB shift using uvShift.x to offset channels
    vec3 base = hsv(hue, sat, val);
    float shift = 0.006 * uvShift.x;
    vec3 rgb;
    rgb.r = hsv(hue - shift, sat, val).r;
    rgb.g = base.g;
    rgb.b = hsv(hue + shift, sat, val).b;
    return rgb;
}

void mainImage(out vec4 outColor, in vec2 fragCoord) {
    vec2 suv = safeUV(fragCoord);
    // normalized coordinates in [0,1] inside safe box
    float x = suv.x;
    float y = suv.y;

    // low-frequency baseline (slow-moving approximate prev)
    float lowBaseline = clamp(TEX(iChannel0, vec2(0.01, 0.0)).r, 0.0, 1.0);

    vec3 col = vec3(0.0);
    float maskAccum = 0.0;
    float maxBand = 0.0;

    float du = 1.0 / float(BANDS);
    float halfWidth = 0.012; // band thickness (normalized safe-box units)

    // For vertical placement, stack bands from top to bottom within safe area
    for (int i = 0; i < BANDS; i++) {
        float fi = float(i);
        float bandNorm = fi / float(max(1, BANDS - 1));
        // place bands top-to-bottom (1.0->0.0)
        float bandY = 1.0 - bandNorm; // top at 1.0
        // sample corresponding frequency u (left-to-right mapping)
        float u = bandNorm; // map band index to u along x (could be remapped)
        // compute stateless smooth energy for this band
        float smoothE = computeSmoothEnergyStateless(u, du * 0.75, lowBaseline);

        // apply small time-varying wobble to emphasize motion left->right
        float flow = 0.15 * sin(iTime * 1.2 + fi * 0.12);
        float intensity = smoothE * (0.5 + 0.5 * sin(iTime * 0.8 + fi * 0.3)) + flow * smoothE;

        // visual masking: horizontal band mask around bandY
        float m = horizontalBandMask(y, bandY, halfWidth);
        // band-specific soft-threshold to avoid tiny noise
        float t = smoothstep(0.01, 0.02, intensity);
        float bandMask = m * t;

        if (bandMask > 0.001) {
            // produce color with slight uv-based rgb shift
            vec2 uvShift = vec2(x, iTime * 0.05);
            vec3 c = bandColor(bandNorm, intensity, uvShift);
            // add soft glow along x: emphasize center x driven by small gaussian
            float centerX = x;
            float gauss = exp(-pow((centerX - 0.5) * 2.0, 2.0) * 2.0);
            float glow = mix(0.8, 1.0, clamp(smoothE * 2.0, 0.0, 1.0)) * gauss * GLOW_INTENSITY * 0.5;
            col += c * bandMask * (0.6 + glow);
            maskAccum = max(maskAccum, bandMask);
            maxBand = max(maxBand, intensity);
        }
    }

    // Enforce hard-black background outside any mask
    if (maskAccum <= 0.0001) {
        outColor = vec4(vec3(0.0), 1.0);
        return;
    }

    // final tone mapping / slight bloom-like soft-add
    vec3 finalCol = col;
    finalCol = clamp(finalCol, 0.0, 1.2);
    finalCol = finalCol / (1.0 + finalCol); // simple filmic-ish tone

    outColor = vec4(finalCol, 1.0);
}

#ifdef GL_ES
void main() {
    vec4 result;
    mainImage(result, gl_FragCoord.xy);
    gl_FragColor = result;
}
#else
void main() {
    vec4 result;
    mainImage(result, gl_FragCoord.xy);
    fragColor = result;
}
#endif