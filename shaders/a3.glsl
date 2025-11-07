// Combined overlay of ring-ok.glsl and fft.glsl
// Single, cleaned shader: helpers, fft image, ring image, and one main() that composes them.

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
uniform sampler2D iChannel0; // time-domain
uniform sampler2D iChannel1; // FFT / spectrum

out vec4 fragColor;

// HSV helpers
vec3 rgb2hsv(vec3 c) {
    vec4 K = vec4(0.0, -1.0/3.0, 2.0/3.0, -1.0);
    vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
    vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
    float d = q.x - min(q.w, q.y);
    float e = 1e-10;
    return vec3(abs((q.z + (q.w - q.y) / (6.0 * d + e))), d / (q.x + e), q.x);
}
vec3 hsv2rgb(vec3 c) {
    vec3 p = abs(fract(c.x + vec3(0.0,2.0/3.0,1.0/3.0)) * 6.0 - 3.0);
    return c.z * mix(vec3(1.0), clamp(p - 1.0, 0.0, 1.0), c.y);
}

// FFT / ECG-style renderer (reads time-domain from iChannel0)
void main_fftImage(out vec4 outColor, in vec2 fragCoord) {
    vec2 uv = fragCoord.xy / iResolution.xy;
    vec3 col = vec3(0.0);

    float sx = uv.x;
    float sample = TEX(iChannel0, vec2(sx,0.5)).r;
    float echo = TEX(iChannel0, vec2(mod(sx - 0.0005 * sin(iTime*2.0),1.0),0.5)).r * 0.6;
    echo += TEX(iChannel0, vec2(mod(sx - 0.0012 * sin(iTime*1.3),1.0),0.5)).r * 0.3;
    sample = mix(sample, echo, 0.35);

    float centerY = 1.0/3.0;
    float amplitudeScale = 0.62;
    float ypos = centerY + sample * amplitudeScale;
    ypos = clamp(ypos, 0.0, 0.98);
    float d = abs(uv.y - ypos);
    float mask = smoothstep(0.006, 0.0, d);
    col = mix(col, vec3(0.8,1.0,1.0), mask);

    float dist = length((uv - 0.5) * vec2(iResolution.x / iResolution.y, 1.0));
    col *= mix(1.0, 0.9, smoothstep(0.6,1.0,dist));
    outColor = vec4(col,1.0);
}

// Ring visualization (samples spectrum from iChannel0)
#define N 120
#define PI 3.141593
void main_ringImage(out vec4 outColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec2 p = uv * 2.0 - 1.0;
    p.x *= iResolution.x / iResolution.y;
    p *= 2.0;

    const int BANDS = 64;
    float power=0.0,sumFreq=0.0,totalAmp=0.0;
    for(int bi=0;bi<BANDS;bi++){ float uu=(float(bi)+0.5)/float(BANDS); float bv=TEX(iChannel1,vec2(uu,0.0)).x; power+=bv*bv; sumFreq+=bv*(float(bi)+0.5); totalAmp+=bv; }
    float spectralCentroid=0.0; if(totalAmp>1e-6) spectralCentroid=(sumFreq/totalAmp)/float(BANDS-1);
    float rms = sqrt(power/float(BANDS)+1e-8);

    vec3 tintWarm = vec3(1.0,0.6,0.3);
    vec3 tintCool = vec3(0.8,0.95,1.0);
    vec3 tint = mix(tintWarm*1.10, tintCool*1.25, spectralCentroid);
    float t1 = 0.5 + 0.5 * sin(iTime * 1.2);
    float t2 = 0.5 + 0.5 * sin(iTime * 0.6 + 1.2);
    vec3 colorA = mix(tint*1.1, vec3(1.0,0.95,0.8), t1*0.8+0.2);
    vec3 colorB = mix(tintCool*1.2, vec3(0.5,0.85,1.0), t2*0.9+0.1);
    vec3 timeGradient = mix(colorA, colorB, smoothstep(0.0,1.0,uv.y)); timeGradient = pow(timeGradient*1.05, vec3(0.85));
    float hueShift = fract(iTime * 0.1);
    vec3 hg = rgb2hsv(timeGradient); hg.x = fract(hg.x + hueShift); timeGradient = hsv2rgb(hg);

    vec3 col = vec3(0.0);
    for(int i=0;i<N;i++){
        float fi=float(i); float t=fi/float(N); float aa=(t + iTime/12.0) * 2.0 * PI;
    float beat = TEX(iChannel1, vec2(0.05,0.25)).x * 0.25;
        float size = 0.3 + sin(t * 6.0 * PI) * 0.1 + beat;
        float a1 = -iTime * PI / 3.0 + aa; a1 += sin(iTime + beat); a1 += sin(length(p) * 3.0 + iTime * PI / 2.0) * 0.3; vec2 c1 = vec2(cos(a1), sin(a1));
        float a2 = aa * (4.0 + beat * 0.05); vec2 c2 = vec2(cos(a2), sin(a2)) * 0.3 + c1;
        float d = abs(length(p - c2) - size); d = max(d, 1e-4);
        col.r += 0.001 / d; col.g += 0.0013 / d * 0.95; col.b += 0.0015 / d * 0.9;
    }
    vec3 finalCol = col * timeGradient; float luma = dot(finalCol, vec3(0.299,0.587,0.114)); finalCol = mix(vec3(luma), finalCol, 1.25);
    float intensityBoost = 0.8 + rms * 1.0 + spectralCentroid * 0.35; finalCol *= intensityBoost; finalCol = clamp(finalCol, vec3(0.0), vec3(2.0)); finalCol = pow(finalCol, vec3(0.9));
    outColor = vec4(finalCol,1.0);
}

void main(){
    vec4 a = vec4(0.0); vec4 b = vec4(0.0);
    main_ringImage(a, gl_FragCoord.xy);
    main_fftImage(b, gl_FragCoord.xy);
    vec3 sum = a.rgb + b.rgb; sum = clamp(sum, vec3(0.0), vec3(1.0)); fragColor = vec4(sum,1.0);
}
// Combined overlay of ring-ok.glsl and fft.glsl
// Both shaders' implementation logic and parameters are preserved; their outputs are added together.

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
vec3 hsv2rgb(vec3 c) {
    vec3 p = abs(fract(c.x + vec3(0.0, 2.0/3.0, 1.0/3.0)) * 6.0 - 3.0);
    vec3 rgb = c.z * mix(vec3(1.0), clamp(p - 1.0, 0.0, 1.0), c.y);
    return rgb;
}

void main_ringImage(out vec4 outColor, in vec2 fragCoord)
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
    vec3 tint = mix(tintWarm * 1.10, tintCool * 1.25, spectralCentroid);

    float t1 = 0.5 + 0.5 * sin(iTime * 1.2);
    float t2 = 0.5 + 0.5 * sin(iTime * 0.6 + 1.2);
    vec3 colorA = mix(tint * 1.1, vec3(1.0, 0.95, 0.8), t1 * 0.8 + 0.2);
    vec3 colorB = mix(tintCool * 1.2, vec3(0.5, 0.85, 1.0), t2 * 0.9 + 0.1);
    vec3 timeGradient = mix(colorA, colorB, smoothstep(0.0, 1.0, uv.y));
    timeGradient = pow(timeGradient * 1.05, vec3(0.85));

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
        d = max(d, 1e-4);
        col.r += 0.001 / d;
        col.g += 0.0013 / d * 0.95;
        col.b += 0.0015 / d * 0.9;
    }

    vec3 finalCol = col * timeGradient;
    float luma = dot(finalCol, vec3(0.299, 0.587, 0.114));
    finalCol = mix(vec3(luma), finalCol, 1.25);
    float intensityBoost = 0.8 + rms * 1.0 + spectralCentroid * 0.35;
    finalCol *= intensityBoost;
    finalCol = clamp(finalCol, vec3(0.0), vec3(2.0));
    finalCol = pow(finalCol, vec3(0.9));
    outColor = vec4(finalCol, 1.0);
}

///////////////////////////////////////////////////////////////////////////
// --- final composition -------------------------------------------------
///////////////////////////////////////////////////////////////////////////

void main() {
    vec4 a = vec4(0.0);
    vec4 b = vec4(0.0);
    main_ringImage(a, gl_FragCoord.xy);
    main_fftImage(b, gl_FragCoord.xy);

    // Direct overlay: add both RGB contributions and clamp
    vec3 sum = a.rgb + b.rgb;
    sum = clamp(sum, vec3(0.0), vec3(1.0));
    fragColor = vec4(sum, 1.0);
}
// Extracted radial FFT lines from ring.glsl
// Only draws the outer radial spectrum vertical lines.

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
uniform sampler2D iChannel0; // FFT / spectrum texture (assumed horizontal)

out vec4 fragColor;

#define PI 3.14159265359
#define TWO_PI 6.28318530718

void mainImage(out vec4 fragColor_out, in vec2 fragCoord){
    // normalized coords and aspect correction (matched to original project)
    vec2 uv = fragCoord / iResolution.xy;
    uv.x *= iResolution.x / iResolution.y;
    vec2 mid = vec2(0.5 * iResolution.x / iResolution.y, 0.5);

    vec2 p = uv - mid;
    float dist = length(p);
    float ang = atan(p.y, p.x); // -PI..PI
    float angN = (ang + PI) / TWO_PI; // 0..1

    // ring region (same as original): only draw between these radii
    float innerR = 0.40;
    float outerR = 0.65;

    vec3 col = vec3(0.0); // background black

    // Only render if we're in the ring band area
    if (dist >= innerR && dist <= outerR) {
        // Number of angular bins to place radial lines
        float bins = 128.0; // adjust for density (128 is a good balance)

        // Find nearest bin center for this fragment's angle
        float binIndex = floor(angN * bins);
        float binCenter = (binIndex + 0.5) / bins;

        // angular distance to the bin center (wrap-around aware)
        float aDist = abs(angN - binCenter);
        aDist = min(aDist, 1.0 - aDist);

        // angular thickness of the radial line
        float angWidth = 0.5 / bins; // half-bin width ~ sharp lines

        // smooth angular mask for the thin line
        float angMask = smoothstep(angWidth, 0.0, aDist);

        // sample the FFT / spectrum texture at the bin center
        float spec = clamp(TEX(iChannel0, vec2(binCenter, 0.1)).x, 0.0, 1.0);
        // amplify and shape the spectrum so lines are visible
        float amp = pow(spec, 1.2) * 1.6;

        // radial cutoff based on amplitude: lines extend outward from innerR
        float lineMaxR = innerR + amp * (outerR - innerR);

        // radial falloff for smooth line ends
        float radialMask = smoothstep(lineMaxR + 0.01, lineMaxR - 0.02, dist);

        // final mask: only keep where both angular and radial masks are present
        float mask = angMask * radialMask;

        // color of the radial lines (no white ring, no red label)
        vec3 lineColor = vec3(0.6, 0.9, 1.0); // pale cyan/white

        col += lineColor * mask;
    }

    // slight vignette to help readability
    float vign = smoothstep(0.0, 0.9, 1.0 - dist * 1.25);
    col *= 0.85 + 0.15 * vign;

    fragColor_out = vec4(col, 1.0);
}

void main() {
    vec4 color = vec4(0.0);
    mainImage(color, gl_FragCoord.xy);
#ifdef GL_ES
    gl_FragColor = color;
#else
    fragColor = color;
#endif
}
