// Target: desktop (#version 330 core)
#version 330 core

// Estimated texture samples per pixel: ~0 (procedural)

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

// Uniforms
uniform vec3 iResolution;
uniform float iTime;
uniform vec4 iMouse;
uniform sampler2D iChannel0; // audio spectrum texture (normalized coords)

#ifndef GL_ES
out vec4 fragColor;
#endif

// --------------------
// Utility / common from shadertoy
#define PI 3.14159265359

// iSphere from original
float iSphere( in vec3 ro, in vec3 rd, in vec4 sph )
{
    vec3 oc = ro - sph.xyz;
    float b = dot( oc, rd );
    float c = dot( oc, oc ) - sph.w*sph.w;
    float h = b*b - c;
    if( h<0.0 ) return -1.0;
    return -b - sqrt( h );
}

// Hash and noise utilities (David Hoskins)
#define HASHSCALE1 .1031
#define HASHSCALE3 vec3(.1031, .1030, .0973)
#define HASHSCALE4 vec4(.1031, .1030, .0973, .1099)

float hash11(float p)
{
    vec3 p3  = fract(vec3(p) * HASHSCALE1);
    p3 += dot(p3, p3.yzx + 19.19);
    return fract((p3.x + p3.y) * p3.z);
}

float hash13(vec3 p3)
{
    p3  = fract(p3 * HASHSCALE1);
    p3 += dot(p3, p3.yzx + 19.19);
    return fract((p3.x + p3.y) * p3.z);
}

vec3 hash33(vec3 p3)
{
    p3 = fract(p3 * HASHSCALE3);
    p3 += dot(p3, p3.yzx+19.19);
    return fract((p3.xxy + p3.yxx) * p3.zyx);
}

float Noise(in vec3 p)
{
    vec3 i = floor(p);
    vec3 f = fract(p);
    f *= f * (3.0-2.0*f);
    return mix(
        mix(mix(hash13(i + vec3(0.,0.,0.)), hash13(i + vec3(1.,0.,0.)),f.x),
            mix(hash13(i + vec3(0.,1.,0.)), hash13(i + vec3(1.,1.,0.)),f.x),
            f.y),
        mix(mix(hash13(i + vec3(0.,0.,1.)), hash13(i + vec3(1.,0.,1.)),f.x),
            mix(hash13(i + vec3(0.,1.,1.)), hash13(i + vec3(1.,1.,1.)),f.x),
            f.y),
        f.z);
}

const mat3 m = mat3( 0.00,  0.80,  0.60,
                    -0.80,  0.36, -0.48,
                    -0.60, -0.48,  0.64 ) * 1.7;

// lighter FBM: fewer octaves for performance
float FBM( vec3 p )
{
    float f = 0.0;
    f = 0.5 * Noise(p); p = m*p;
    f += 0.25 * Noise(p); p = m*p;
    f += 0.125 * Noise(p); p = m*p;
    f += 0.0625 * Noise(p);
    return f;
}

// lighter procedural craters: smaller neighborhood for perf
float craters(vec3 x) {
    vec3 p = floor(x);
    vec3 f = fract(x);
    float va = 0.;
    float wt = 0.;
    // reduce neighborhood from -2..2 to -1..1 (27 samples instead of 125)
    for (int i = -1; i <= 1; i++) for (int j = -1; j <= 1; j++) for (int k = -1; k <= 1; k++) {
        vec3 g = vec3(i,j,k);
        vec3 o = 0.8 * hash33(p + g);
        float d = distance(f - g, o);
        float w = exp(-4. * d);
        va += w * sin(2.0*PI * sqrt(d));
        wt += w;
    }
    return abs(va / max(wt, 1e-6));
}

// map: evaluate procedural surface value at point on sphere
float mapProcedural(vec3 p) {
    // convert 3D point to lat/lon uv
    float lat = 90.0 - acos(p.y / length(p)) * 180.0/PI;
    float lon = atan(p.x, p.z) * 180.0/PI;
    // build local sampling point for craters/noise
    // scale coordinates to get variation across lat/lon
    vec3 sampleP = vec3(lon, lat, 0.0) * 0.01;
    float accum = 0.0;
    // multi-scale crater + noise accumulation (lighter version: 3 scales)
    for (int i = 0; i < 3; i++) {
        float scale = 0.4 * pow(2.2, float(i));
        float c = craters(scale * sampleP);
        float noise = 0.4 * exp(-3.0 * c) * FBM(10.0 * sampleP * scale);
        float w = clamp(3.0 * pow(0.4, float(i)), 0.0, 1.0);
        accum += w * (c + noise);
    }
    accum = pow(accum, 3.0);
    return accum;
}

// estimate normal by finite differences of the procedural map
vec3 estimateNormal(vec3 p) {
    vec2 e = vec2(1.0,0.0)/1000.0;
    vec3 q = p;
    float dx = mapProcedural(normalize(q + vec3(e.x,0,0))) - mapProcedural(normalize(q - vec3(e.x,0,0)));
    float dy = mapProcedural(normalize(q + vec3(0,e.x,0))) - mapProcedural(normalize(q - vec3(0,e.x,0)));
    float dz = mapProcedural(normalize(q + vec3(0,0,e.x))) - mapProcedural(normalize(q - vec3(0,0,e.x)));
    vec3 n = vec3(dx, dy, dz) / (2.0 * length(e));
    return normalize(n + 1e-6);
}

// mainImage: single-file combined Image using procedural surface (no buffers)
void mainImage(out vec4 outColor, in vec2 fragCoord) {
    // --- pre-sample audio spectrum (FFT) into small array ---
    const int BANDS = 64;
    float bands[BANDS];
    for (int i = 0; i < BANDS; i++) {
        float u = (float(i) + 0.5) / float(BANDS);
        // sample row 0 of iChannel0 (convention: audio spectrum stored as 1D texture)
        bands[i] = texture(iChannel0, vec2(u, 0.0)).r;
    }

    vec2 p = (2.0 * fragCoord.xy - iResolution.xy) / iResolution.y;
    float lat = 15.0 * sin(0.1 * iTime);
    float lon = 7.5 * iTime + 100.0;
    if (iMouse.z > 0.0) {
        lat = 90.0 - 180.0 * iMouse.y / iResolution.y;
        lon = 180.0 - 360.0 * iMouse.x / iResolution.x;
    }
    vec3 camPos = 10.0 * vec3(sin(lon*PI/180.0) * cos(lat*PI/180.0), sin(lat*PI/180.0), cos(lon*PI/180.0) * cos(lat*PI/180.0));
    vec3 w = normalize(-camPos);
    vec3 u = normalize(cross(w, vec3(0.0,1.0,0.0)));
    vec3 v = normalize(cross(u, w));
    mat3 camera = mat3(u, v, w);

    vec3 dir = normalize(camera * vec3(p / 0.95, length(camPos)));
    float dist = iSphere(camPos, dir, vec4(0.0,0.0,0.0,1.0));
    outColor = vec4(0.0);
    if (dist > 0.0) {
        vec3 q = camPos + dir * dist;
        // use procedural map directly
        float c = mapProcedural(normalize(q));
        vec3 n = estimateNormal(normalize(q));
        float light = clamp(dot(n, normalize(vec3(-4.0,1.0,2.0))), 0.0, 1.0);
        float heat = clamp(2.0 / max(iTime*iTime, 1e-6), 0.0, 1.0);
        vec3 col = mix(vec3(0.58, 0.57, 0.55), vec3(0.15, 0.13, 0.1), smoothstep(0.0, 3.0, c));
        col += 5.0 * c * heat * vec3(1.0, 0.15, 0.05);
        outColor = vec4(light * col, 1.0);
        outColor.rgb += 5.0 * c * heat * vec3(1.0, 0.15, 0.05);
    }
    outColor.rgb = mix(outColor.rgb, vec3(0.0), smoothstep(0.95 - 4.0/iResolution.y, 0.95 + 1.0/iResolution.y, length(p)));

    // --- overlay FFT waveform (ECG-style) horizontally ---
    vec2 uv = fragCoord.xy / iResolution.xy; // uv.y: 0 bottom, 1 top
    // choose baseline near bottom (15% up) and vertical span
    float base = 0.12; // baseline (uv)
    float span = 0.5; // vertical span of waveform
    // pick band corresponding to current x
    int idx = int(clamp(floor(uv.x * float(BANDS)), 0.0, float(BANDS - 1)));
    float bandVal = bands[idx];
    // map band value to uv.y coordinate (clamp to [0,1])
    float waveY = clamp(base + bandVal * span, 0.0, 1.0);
    // distance in pixels
    float d = abs(uv.y - waveY) * iResolution.y;
    // thin main line (1.0 px thick) with soft anti-alias
    float thickness = 1.5;
    float aa = 1.0;
    float line = 1.0 - smoothstep(0.0, thickness + aa, d);
    // neon/glow: additive multi-radius soft glows
    float glow = 0.0;
    glow += (1.0 - smoothstep(2.0, 6.0, d)) * 0.6;
    glow += (1.0 - smoothstep(6.0, 14.0, d)) * 0.35;
    glow += (1.0 - smoothstep(14.0, 30.0, d)) * 0.15;
    // compose overlay: pure white line + glow (additive)
    vec3 neon = vec3(1.0);
    vec3 overlay = neon * line + neon * glow * 0.5;

    outColor.rgb = outColor.rgb + overlay; // additive overlay

    outColor.rgb = pow(outColor.rgb, vec3(1.0/2.2));
}

// adapter main
void main() {
    vec4 color;
    mainImage(color, gl_FragCoord.xy);
#ifdef GL_ES
    gl_FragColor = color;
#else
    fragColor = color;
#endif
}
