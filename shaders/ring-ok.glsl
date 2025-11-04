// Target: desktop (#version 330 core)
#version 330 core

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

#ifndef GL_ES
out vec4 fragColor;
#endif

#define N 120
#define PI 3.141593

float circle(vec2 p, float r) {
    return smoothstep(0.1, 0.0, abs(length(p) - r));
}

// Utility: RGB <-> HSV conversion (for hue rotation)
vec3 rgb2hsv(vec3 c) {
    vec4 K = vec4(0.0, -1.0/3.0, 2.0/3.0, -1.0);
    vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
    vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));

    float d = q.x - min(q.w, q.y);
    float e = 1.0e-10;
    return vec3(abs((q.z + (q.w - q.y) / (6.0 * d + e))), d / (q.x + e), q.x);
}

vec3 hsv2rgb(vec3 c) {
    vec3 p = abs(fract(c.x + vec3(0.0, 2.0/3.0, 1.0/3.0)) * 6.0 - 3.0);
    vec3 rgb = c.z * mix(vec3(1.0), clamp(p - 1.0, 0.0, 1.0), c.y);
    return rgb;
}

void mainImage( out vec4 outColor, in vec2 fragCoord )
{
    vec2 uv = fragCoord / iResolution.xy;
    vec2 p = uv * 2.0 - 1.0;
    p.x *= iResolution.x / iResolution.y;
    p *= 2.0;

    float a = atan(p.y, p.x);

    // --- sample spectrum to compute a frequency centroid for color mapping ---
    const int BANDS = 64;
    float power = 0.0;
    float sumFreq = 0.0;
    float totalAmp = 0.0;
    for (int bi = 0; bi < BANDS; bi++) {
        float uu = (float(bi) + 0.5) / float(BANDS);
        float bv = TEX(iChannel0, vec2(uu, 0.0)).x;
        power += bv * bv;
        sumFreq += bv * (float(bi) + 0.5);
        totalAmp += bv;
    }
    float spectralCentroid = 0.0;
    if (totalAmp > 1e-6) spectralCentroid = (sumFreq / totalAmp) / float(BANDS - 1);
    float rms = sqrt(power / float(BANDS) + 1e-8);

    // color tint driven by spectral centroid (low -> warm, high -> cool/bright)
    vec3 tintWarm = vec3(1.0, 0.6, 0.3);
    vec3 tintCool = vec3(0.8, 0.95, 1.0);
    // make tint more vivid by amplifying warm/cool colors based on centroid
    // slightly reduced to avoid excessive exposure
    vec3 tint = mix(tintWarm * 1.10, tintCool * 1.25, spectralCentroid);

    // time-varying vertical gradient
    // colorA and colorB oscillate slowly with time, then blended across uv.y
    // increase time modulation and contrast for more obvious changes
    float t1 = 0.5 + 0.5 * sin(iTime * 1.2);
    float t2 = 0.5 + 0.5 * sin(iTime * 0.6 + 1.2);
    vec3 colorA = mix(tint * 1.1, vec3(1.0, 0.95, 0.8), t1 * 0.8 + 0.2);
    vec3 colorB = mix(tintCool * 1.2, vec3(0.5, 0.85, 1.0), t2 * 0.9 + 0.1);
    vec3 timeGradient = mix(colorA, colorB, smoothstep(0.0, 1.0, uv.y));
    // boost contrast of gradient
    timeGradient = pow(timeGradient * 1.05, vec3(0.85));

    // rotate hue over time so the gradient slowly traverses all color families
    // speed: fraction of full hue cycle per second (e.g. 0.1 -> 10s per cycle)
    float hueSpeed = 0.1;
    float hueShift = fract(iTime * hueSpeed);
    vec3 hg = rgb2hsv(timeGradient);
    hg.x = fract(hg.x + hueShift);
    timeGradient = hsv2rgb(hg);

    vec3 col = vec3(0.0);

    for (int i = 0; i < N; i++) {
        float fi = float(i);
        float t = fi / float(N);
        float aa = (t + iTime / 12.0) * 2.0 * PI;

        float beat = TEX(iChannel0, vec2(0.05, 0.25)).x * 0.25;

        float size = 0.3 + sin(t * 6.0 * PI) * 0.1 + beat;

        float a1 = -iTime * PI / 3.0 + aa;
        a1 += sin(iTime + beat);
        a1 += sin(length(p) * 3.0 + iTime * PI / 2.0) * 0.3;
        vec2 c1 = vec2(cos(a1), sin(a1));

        float a2 = aa * (4.0 + beat * 0.05);
        vec2 c2 = vec2(cos(a2), sin(a2)) * 0.3 + c1;
        float d = abs(length(p - c2) - size);
        // avoid division by zero
        d = max(d, 1e-4);
        col.r += 0.001 / d;
        col.g += 0.0013 / d * 0.95;
        col.b += 0.0015 / d * 0.9;
    }

    // apply the animated gradient as a tint over the computed brightness
    vec3 finalCol = col * timeGradient;
    // boost saturation slightly
    float luma = dot(finalCol, vec3(0.299, 0.587, 0.114));
    finalCol = mix(vec3(luma), finalCol, 1.25);
    // amplify by volume and spectral centroid for stronger reactions
    // reduce base intensity and sensitivity to avoid overexposure
    float intensityBoost = 0.8 + rms * 1.0 + spectralCentroid * 0.35;
    finalCol *= intensityBoost;
    // clamp to avoid extreme values, then gentle tonemap/gamma
    finalCol = clamp(finalCol, vec3(0.0), vec3(2.0));
    finalCol = pow(finalCol, vec3(0.9));
    outColor = vec4(finalCol, 1.0);
}

void main() {
    vec4 color;
    mainImage(color, gl_FragCoord.xy);
#ifdef GL_ES
    gl_FragColor = color;
#else
    fragColor = color;
#endif
}