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
uniform sampler2D iChannel0; // fallbacks: audio time-domain or FFT
uniform sampler2D iChannel1; // preferred: FFT (low freq on left)
out vec4 fragColor;

#define R iResolution
#define T iTime
#define PI 3.1415926
#define TAU 6.2831853

// small helpers
float easeInOutExpo(float x){
    return x == 0.0
      ? 0.0
      : x == 1.0
      ? 1.0
      : x < 0.5 ? pow(2.0, 20.0 * x - 10.0) / 2.0
      : (2.0 - pow(2.0, -20.0 * x + 10.0)) / 2.0;
}

float procedural_2d(vec2 uv, float r){
    const float hw = .05;
    const float s = .01;
    float size = r;
    float circle = smoothstep(hw-s,hw, abs(length(uv)-size));
    return circle;
}

vec2 hash22(vec2 p){ p = vec2(dot(p,vec2(127.1,311.7)), dot(p,vec2(269.5,183.3))); return -1.0 + 2.0 * fract(sin(p)*43758.5453123); }
float simplex_noise(vec2 p){ const float K1=0.366025404; const float K2=0.211324865; vec2 i=floor(p+(p.x+p.y)*K1); vec2 a=p-(i-(i.x+i.y)*K2); vec2 o=(a.x<a.y)?vec2(0.0,1.0):vec2(1.0,0.0); vec2 b=a-(o-K2); vec2 c=a-(1.0-2.0*K2); vec3 h=max(0.5-vec3(dot(a,a),dot(b,b),dot(c,c)),0.0); vec3 n=h*h*h*h*vec3(dot(a,hash22(i)),dot(b,hash22(i+o)),dot(c,hash22(i+1.0))); return dot(vec3(70.0,70.0,70.0), n); }
float noise_sum(vec2 p){ float f=0.0; p*=4.0; f+=1.0*simplex_noise(p); p*=2.0; f+=0.5*simplex_noise(p); p*=2.0; f+=0.25*simplex_noise(p); p*=2.0; f+=0.125*simplex_noise(p); p*=2.0; f+=0.0625*simplex_noise(p); return f; }

// Signed distance primitives and ops
float sdSphere(vec3 p,float s){ return length(p)-s; }
float sdTorus(vec3 p, vec2 t){ vec2 q = vec2(length(p.xz)-t.x,p.y); return length(q)-t.y; }
float opSmoothUnion(float d1,float d2,float k){ float h=clamp(0.5+0.5*(d2-d1)/k,0.0,1.0); return mix(d2,d1,h)-k*h*(1.0-h); }

// Robust low-frequency spectrum sampler: average left bins from FFT texture (iChannel1) with fallback to iChannel0
float getSpectrumLow()
{
    const int N = 6; // number of bins to average
    float sum1 = 0.0;
    float sum0 = 0.0;
    for(int i=0;i<N;i++){
        float x = float(i)/float(max(1,N-1)) * 0.06; // sample first ~6% of spectrum
        vec4 s1 = TEX(iChannel1, vec2(x,0.5));
        vec4 s0 = TEX(iChannel0, vec2(x,0.5));
        sum1 += s1.r;
        sum0 += s0.r;
    }
    float avg1 = sum1 / float(N);
    float avg0 = sum0 / float(N);
    float raw = max(avg1, avg0);
    // map into a usable 0..1 range and compress
    float v = clamp(raw * 6.0, 0.0, 1.0);
    v = pow(v, 0.8);
    return v;
}

// globals used in map()/ray
float glow;

float mapScene(vec3 p)
{
    // sample low freq spectrum instead of bufferA last texel
    float spec = getSpectrumLow();
    float s = 0.6 + spec;

    float d = p.z + 4.0;
    float res = d;

    // rotation
    p.xz *= mat2(cos(iTime), sin(iTime), -sin(iTime), cos(iTime));
    p.xy *= mat2(cos(iTime), sin(iTime), -sin(iTime), cos(iTime));

    // torus + spheres
    d = sdTorus(p/s, vec2(2.0,0.7))*s;
    d = min(d, sdSphere(p+vec3(0.0,sin(fract(iTime*(0.5))*TAU)*2.0,0.0),0.3));
    const float ns = 3.0;
    for(float i=0.0;i<ns;i++){
        float a = i*TAU/ns;
        d = opSmoothUnion(d, sdSphere((p+2.0*s*vec3(sin(a),0.0,cos(a)))/s, .9 + cos(a + iTime*3.0)*.4)*s, .5);
    }

    glow += (.00095)/(.000015+pow(d,2.));
    return d;
}

void rayMarch(vec3 ro, vec3 rd, out float outD)
{
    float d = 0.0;
    for(int i=0;i<250;i++){
        vec3 p = ro + rd * d;
        float t = mapScene(p);
        if(abs(t) < d * 0.001 || d > 20.0) break;
        d += (1.1 + (sin(iTime)*0.4));
    }
    outD = d;
}

vec3 cameraDir(vec3 lp, vec3 ro, vec2 uv){ vec3 f=normalize(lp-ro); vec3 r=normalize(cross(vec3(0,1,0),f)); vec3 u=normalize(cross(f,r)); vec3 c=ro+f*0.75; vec3 i=c+uv.x*r+uv.y*u; return normalize(i-ro); }

void mainImage(out vec4 O, in vec2 F)
{
    vec2 uv = (F.xy - R.xy*0.5)/R.y;
    vec3 C = vec3(0.0);

    vec3 lp = vec3(0.0,0.0,0.0);
    vec3 ro = lp + vec3(0.0,0.0,5.5);
    vec3 rd = cameraDir(lp, ro, uv);

    float d;
    rayMarch(ro, rd, d);

    C = vec3(glow*0.4);
    C = mix(1.0 - C, C, procedural_2d(uv, easeInOutExpo(fract(iTime*0.6))*0.4));
    O = vec4(sqrt(C), 1.0);
}

void main()
{
    vec4 outColor = vec4(0.0);
    mainImage(outColor, gl_FragCoord.xy);
#ifdef GL_ES
    gl_FragColor = outColor;
#else
    fragColor = outColor;
#endif
}
