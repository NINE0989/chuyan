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
uniform sampler2D iChannel1; // preferred: FFT
uniform sampler2D iChannel0; // fallback
out vec4 fragColor;

#define S smoothstep

// helpers
vec2 hash22(vec2 p){ p = vec2( dot(p,vec2(127.1,311.7)), dot(p,vec2(269.5,183.3))); return -1.0 + 2.0 * fract(sin(p)*43758.5453123); }
float simplex_noise(vec2 p){ const float K1 = 0.366025404; const float K2 = 0.211324865; vec2 i = floor(p + (p.x + p.y) * K1); vec2 a = p - (i - (i.x + i.y) * K2); vec2 o = (a.x < a.y) ? vec2(0.0,1.0) : vec2(1.0,0.0); vec2 b = a - (o - K2); vec2 c = a - (1.0 - 2.0 * K2); vec3 h = max(0.5 - vec3(dot(a,a),dot(b,b),dot(c,c)), 0.0); vec3 n = h*h*h*h*vec3(dot(a,hash22(i)), dot(b,hash22(i+o)), dot(c,hash22(i+1.0))); return dot(vec3(70.0,70.0,70.0), n); }
float noise_sum(vec2 p){ float f=0.0; p*=4.0; f+=1.0*simplex_noise(p); p*=2.0; f+=0.5*simplex_noise(p); p*=2.0; f+=0.25*simplex_noise(p); p*=2.0; f+=0.125*simplex_noise(p); p*=2.0; f+=0.0625*simplex_noise(p); return f; }

// Modified drawMountain: adds a gentle audio-driven offset to Side
vec2 drawMountainAudio(vec2 uv, float f, float d, float audioAmp)
{
    // base noise-derived Side
    float Side = uv.y + noise_sum(vec2(uv.x, mix(uv.y,0.,uv.y))*f)*0.1;
    float detal = noise_sum(vec2(uv.x, uv.y)*8.)*0.005;
    Side += detal;

    // audio-driven gentle wobble: small sinusoidal offset along x
    // audioAmp in [0,1]; scale down to a subtle value so effect is gentle
    float wobbleStrength = 0.02; // base amplitude of wobble
    float wobble = sin(uv.x * 40.0 + iTime * 2.0) * (wobbleStrength * audioAmp);
    Side += wobble;

    float Mountain = S(0.48, 0.49, Side);
    // reduce fog intensity slightly (was *0.2) to make atmosphere lighter
    float fog = S(d, noise_sum(vec2(uv.x+iTime*0.06, uv.y)*0.2)*0.12, Side);
    return clamp(vec2(Side+fog, Mountain), 0., 1.);
}

// audio helper: sample low-frequency energy robustly from iChannel1 (FFT) with fallback to iChannel0
float getAudioLevel()
{
    const int N = 8;
    float sum1 = 0.0;
    float sum0 = 0.0;
    for (int i = 0; i < N; i++) {
        float x = float(i) / float(max(1, N-1)) * 0.06; // first ~6% of spectrum
        vec4 s1 = TEX(iChannel1, vec2(x, 0.5));
        vec4 s0 = TEX(iChannel0, vec2(x, 0.5));
        sum1 += s1.r;
        sum0 += s0.r;
    }
    float avg1 = sum1 / float(N);
    float avg0 = sum0 / float(N);
    float raw = max(avg1, avg0);
    float scaled = clamp(raw * 8.0, 0.0, 1.0);
    float level = pow(scaled, 0.7);
    return level;
}

// bird shape (aspect-correct) - simplified copy
float drawBirdAt(vec2 uv, vec2 center, float size, float flapAmp)
{
    float aspect = iResolution.x / iResolution.y;
    vec2 rel = uv - center; rel.x *= aspect;
    vec2 v = rel * (20.0 / size);
    v.x -= v.y;
    v.y = v.y + .45 + (sin((iTime*0.5 - abs(v.x)) * 3.0) - 1.0) * abs(v.x) * (0.5 * flapAmp);
    float S1 = smoothstep(0.45, 0.4, length(v));
    v.y += 0.1;
    float S2 = smoothstep(0.5, 0.45, length(v));
    return S1 - S2;
}

// sun (unchanged)
float drawSun(vec2 uv, float audioSmooth)
{
    vec2 u = uv; u -= 0.5; u.x *= iResolution.x/iResolution.y;
    float Sun = S(0.18, 0.20, length(vec2(u.x-.5, u.y-.3)));
    float baseFogNoise = noise_sum(vec2(uv.x+iTime*0.001, uv.y)*2.)*0.05;
    float audioMul = clamp(audioSmooth * 0.9, 0.0, 1.0);
    // make fog slightly lighter by reducing multipliers and audio responsiveness
    float fog = S(0.7, baseFogNoise * (1.0 + audioMul * 0.6), u.y) * (1.0 + audioMul * 0.4);
    return clamp(Sun + fog, 0.0, 1.0);
}

void mainImage(out vec4 fragColor_out, in vec2 fragCoord)
{
    vec2 uv = fragCoord / iResolution.xy;
    float t = iTime * 0.5;

    float audio = getAudioLevel();
    // small temporal bias to keep subtle motion even during silence
    float slow = 0.5 + 0.5 * sin(iTime * 0.5);
    float audioSmooth = mix(audio * 0.9, slow * 0.06, 0.12);

    // flap amplitude mapping
    float flapAmp = mix(1.0, 1.6, audioSmooth * 0.85);
    // mountain audio amplitude (smaller scaling to keep subtle)
    float mountainAmp = audioSmooth * 0.9;

    vec3 c = vec3(1.0);
    float Sun = drawSun(uv, audioSmooth);
    c = mix(vec3(1.,0.2,0.0), c, Sun);

    // birds
    float birdMask = 0.0;
    const int BIRD_COUNT = 12;
    for (int bi = 0; bi < BIRD_COUNT; bi++) {
        vec2 rnd = 0.5 * (hash22(vec2(float(bi) * 12.9898, float(bi) * 78.233)) + 1.0);
        vec2 pos = vec2(mix(0.05, 0.95, rnd.x), mix(0.55, 0.9, rnd.y));
        float size = mix(1.0, 5.0, rnd.y);
        pos.x += 0.12 * sin(iTime * 0.2 + float(bi));
        float b = drawBirdAt(uv, pos, size, flapAmp);
        birdMask = max(birdMask, b);
    }

    // mountains: use audio-modulated drawMountainAudio
    uv.y -= .2;
    uv.x += t*0.001;
    vec2 Mountain1 = drawMountainAudio(uv, .4, 1.0, mountainAmp);
    c = mix(vec3(Mountain1.r), c, Mountain1.g);

    uv.y += .1;
    uv.x += 1.;
    uv.x += t*0.005;
    Mountain1 = drawMountainAudio(uv, .3, .8, mountainAmp);
    c = mix(vec3(Mountain1.r), c, Mountain1.g);

    uv.y += .1;
    uv.x += 2.42;
    uv.x += t*0.01;
    Mountain1 = drawMountainAudio(uv, .2, 0.6, mountainAmp);
    c = mix(vec3(Mountain1.r), c, Mountain1.g);

    uv.y += .1;
    uv.x += 12.84;
    uv.x += t*0.05;
    Mountain1 = drawMountainAudio(uv, .2, 0.4, mountainAmp);
    c = mix(vec3(Mountain1.r)-0.01, c, Mountain1.g);

    // apply birds
    c = mix(c, vec3(0.0), clamp(birdMask * 1.4, 0.0, 1.0));

    vec3 col = vec3(c);
    fragColor_out = vec4(vec3(1.0) - col, 1.0);
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
