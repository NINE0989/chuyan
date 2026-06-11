#version 330

#ifdef GL_ES
precision mediump float;
#endif

#ifndef TEX
#define TEX(s, uv) texture(s, uv)
#endif

uniform vec3 iResolution;
uniform float iTime;
uniform vec4 iMouse;
uniform sampler2D iChannel0;
uniform sampler2D iChannel1;
uniform vec3 iHandPos;
uniform float iHandAction;
uniform float iSatControl;
uniform float iDisturbControl;

out vec4 fragColor;

#define S(a, b, t) smoothstep(a, b, t)
#define NUM_LAYERS 4.

//#define SIMPLE

float AudioSample(float u) {
    float x = clamp(u, 0.0, 1.0);
    float fft1 = TEX(iChannel1, vec2(x, 0.5)).x;
    if (abs(fft1) > 1e-5) {
        return fft1;
    }
    return TEX(iChannel0, vec2(x, 0.5)).x;
}

vec3 AudioColor() {
    float low = AudioSample(0.08);
    float mid = AudioSample(0.28);
    float high = AudioSample(0.68);

    // 低中频共同推动色相，但降低推进幅度，避免过于敏感
    float hue = fract(0.56 + low * 0.38 + mid * 0.30);
    float sat = clamp(iSatControl, 0.0, 1.0);
    float val = clamp(0.24 + pow(low * 0.55 + mid * 0.75, 1.05) * 1.25 + high * 0.05, 0.0, 1.0);

    // 将 HSV 近似转为 RGB，色相对音频变化更敏感
    vec3 p = abs(fract(vec3(hue) + vec3(0.0, 2.0/3.0, 1.0/3.0)) * 6.0 - 3.0);
    vec3 rgb = clamp(p - 1.0, 0.0, 1.0);
    rgb = rgb * rgb * (3.0 - 2.0 * rgb);
    rgb = mix(vec3(1.0), rgb, sat);
    return rgb * val * 0.82;
}

vec2 HighGlitch(vec2 uv, float high) {
    float g = smoothstep(0.28, 0.85, high);
    if (g <= 0.001) {
        return vec2(0.0);
    }

    float row = floor(uv.y * 24.0);
    float n = fract(sin(row * 12.9898 + iTime * 6.0) * 43758.5453);
    float streak = step(0.72, n) * g;
    float off = (n - 0.5) * 0.08 * streak;
    return vec2(off, 0.0);
}


float N21(vec2 p) {
	vec3 a = fract(vec3(p.xyx) * vec3(213.897, 653.453, 253.098));
    a += dot(a, a.yzx + 79.76);
    return fract((a.x + a.y) * a.z);
}

vec2 GetPos(vec2 id, vec2 offs, float t) {
    float n = N21(id+offs);
    float n1 = fract(n*10.);
    float n2 = fract(n*100.);
    float a = t+n;
    return offs + vec2(sin(a*n1), cos(a*n2))*.4;
}

float GetT(vec2 ro, vec2 rd, vec2 p) {
	return dot(p-ro, rd); 
}

float LineDist(vec3 a, vec3 b, vec3 p) {
	return length(cross(b-a, p-a))/length(p-a);
}

float df_line( in vec2 a, in vec2 b, in vec2 p)
{
    vec2 pa = p - a, ba = b - a;
	float h = clamp(dot(pa,ba) / dot(ba,ba), 0., 1.);	
	return length(pa - ba * h);
}

float line(vec2 a, vec2 b, vec2 uv) {
    float r1 = .04;
    float r2 = .01;
    
    float d = df_line(a, b, uv);
    float d2 = length(a-b);
    float fade = S(1.5, .5, d2);
    
    fade += S(.05, .02, abs(d2-.75));
    return S(r1, r2, d)*fade;
}

float WobbleAmount(float high) {
    return smoothstep(0.10, 0.62, high) * 0.085 * clamp(iDisturbControl, 0.0, 2.0);
}

float NetLayer(vec2 st, float n, float t) {
    vec2 id = floor(st)+n;

    st = fract(st)-.5;
   
    vec2 p[9];
    int i=0;
    for(float y=-1.; y<=1.; y++) {
    	for(float x=-1.; x<=1.; x++) {
            p[i++] = GetPos(id, vec2(x,y), t);
    	}
    }

    float high = AudioSample(0.68);
    float netWobble = smoothstep(0.08, 0.70, high) * 0.075 * clamp(iDisturbControl, 0.0, 2.0);
    for (int j = 0; j < 9; j++) {
        float phase = t * 5.0 + float(j) * 1.7 + n * 3.1;
        p[j] += vec2(
            sin((p[j].y + phase) * 10.0),
            cos((p[j].x - phase) * 8.0)
        ) * netWobble;
    }
    
    float m = 0.;
    float sparkle = 0.;
    
    for(int i=0; i<9; i++) {
        m += line(p[4], p[i], st);

        float d = length(st-p[i]);

        float s = (.005/(d*d));
        s *= S(1., .7, d);
        float pulse = sin((fract(p[i].x)+fract(p[i].y)+t)*5.)*.4+.6;
        pulse = pow(pulse, 20.);

        s *= pulse;
        sparkle += s;
    }
    
    m += line(p[1], p[3], st);
	m += line(p[1], p[5], st);
    m += line(p[7], p[5], st);
    m += line(p[7], p[3], st);
    
    float sPhase = (sin(t+n)+sin(t*.1))*.25+.5;
    sPhase += pow(sin(t*.1)*.5+.5, 50.)*5.;
    m += sparkle*sPhase;//(*.5+.5);
    
    return m;
}

void mainImage( out vec4 fragColor, in vec2 fragCoord )
{
    vec2 uv = (fragCoord-iResolution.xy*.5)/iResolution.y;
    vec2 M = iHandPos.xy - 0.5;
    if (iMouse.z > 0.0 || iMouse.w > 0.0) {
        M = iMouse.xy / max(iResolution.xy, vec2(1.0)) - 0.5;
    }

    // iHandAction 接近 0 视为张开，接近 1 视为握拳；张开时整体平滑放大
    float handOpen = 1.0 - clamp(iHandAction, 0.0, 1.0);
    float gestureScale = mix(1.0, 1.24, smoothstep(0.0, 1.0, handOpen));
    uv /= gestureScale;
    M /= gestureScale;
    
    float low  = AudioSample(0.08);
    float mid  = AudioSample(0.28);
    float high = AudioSample(0.68);

    vec2 glitch = HighGlitch(uv, high);
    uv += glitch;
    M += glitch;

    float t = iTime*.1;
    
    float s = sin(t);
    float c = cos(t);
    mat2 rot = mat2(c, -s, s, c);
    vec2 st = uv*rot;  
	M *= rot*2.;
    
    float m = 0.;
    float wobble = WobbleAmount(high);
    for(float i=0.; i<1.; i+=1./NUM_LAYERS) {
        float z = fract(t+i);
        float size = mix(15., 1., z);
        float fade = S(0., .6, z)*S(1., .8, z);
        
        vec2 layerUV = st*size - M*z;
        layerUV += vec2(
            sin((layerUV.y + iTime * 2.0) * 28.0),
            cos((layerUV.x + iTime * 1.7) * 22.0)
        ) * wobble * high;
        m += fade * NetLayer(layerUV, i, iTime);
    }
    
    float fft  = AudioSample(0.7);
    float glow = -uv.y*fft*2. * (0.80 + 0.20 * high);

    vec3 baseCol = AudioColor();
    baseCol += vec3(0.15 * low, 0.08 * mid, 0.20 * high);
    vec3 col = baseCol*m;
    col += baseCol*glow;
    col += vec3(high * 0.35, mid * 0.25, low * 0.20) * (0.30 + 0.55 * m);

    // 高频驱动的廉价故障：分段行偏移 + 颜色错位
    float glitchAmt = smoothstep(0.30, 0.88, high) * clamp(iDisturbControl, 0.0, 2.0);
    if (glitchAmt > 0.001) {
        float band = floor((fragCoord.y + iTime * 24.0) * 0.22);
        float rn = fract(sin(band * 91.7 + iTime * 12.0) * 43758.5453);
        float shift = (rn - 0.5) * glitchAmt * 0.12;
        col = mix(col, col + vec3(shift, -shift * 0.35, shift * 0.9), glitchAmt * 0.8);
    }
    
    #ifdef SIMPLE
    uv *= 10.;
    col = vec3(1)*NetLayer(uv, 0., iTime);
    uv = fract(uv);
    //if(uv.x>.98 || uv.y>.98) col += 1.;
    #endif
    #ifndef SIMPLE
    col *= 1.-dot(uv,uv);
    t = mod(iTime, 230.);
    col *= S(0., 20., t)*S(224., 200., t);
    #endif
    
    fragColor = vec4(col,1);
}

void main() {
    mainImage(fragColor, gl_FragCoord.xy);
}
