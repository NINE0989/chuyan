// Audio Spectrum Lines - horizontal bars with color shifts and glow
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

#define MAX_PARTICLES 64
#define PARTICLE_ITERATIONS 32
#define NEBULA_OCTAVES 2
#define GLOW_INTENSITY 1.2

uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;

#ifdef GL_ES
#else
out vec4 fragColor;
#endif

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(27.619, 57.583))) * 43758.5453);
}

vec2 rotate2D(vec2 uv, float a) {
    return mat2(cos(a), -sin(a), sin(a), cos(a)) * uv;
}

float noise2D(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(
        mix(hash(i + vec2(0.0, 0.0)), hash(i + vec2(1.0, 0.0)), u.x),
        mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x),
        u.y
    );
}

float fbm(vec2 p) {
    float sum = 0.0;
    float amp = 0.5;
    for(int i = 0; i < NEBULA_OCTAVES; i++) {
        sum += amp * noise2D(p);
        p *= 2.0;
        amp *= 0.5;
    }
    return sum;
}

float getSpectrum(float u) {
    u = clamp(u, 0.001, 0.999);
    return TEX(iChannel0, vec2(u, 0.0)).r;
}

float getBass() {
    float sum = 0.0;
    for(int i = 0; i < 4; i++) {
        sum += getSpectrum(float(i) * 0.05);
    }
    return sum * 0.25;
}

float getMid() {
    float sum = 0.0;
    for(int i = 0; i < 6; i++) {
        sum += getSpectrum(0.2 + float(i) * 0.05);
    }
    return sum * 0.1667;
}

float getTreble() {
    float sum = 0.0;
    for(int i = 0; i < 10; i++) {
        sum += getSpectrum(0.5 + float(i) * 0.05);
    }
    return sum * 0.1;
}

float getOverallVolume() {
    return (getBass() + getMid() + getTreble()) * 0.333;
}

vec3 rgbShift(vec3 col, float amount, vec2 dir) {
    float r = col.r * texture(iChannel0, vec2(gl_FragCoord.x + amount * dir.x, gl_FragCoord.y + amount * dir.y) / iResolution.xy).r;
    float g = col.g * texture(iChannel0, vec2(gl_FragCoord.x, gl_FragCoord.y) / iResolution.xy).g;
    float b = col.b * texture(iChannel0, vec2(gl_FragCoord.x - amount * dir.x, gl_FragCoord.y - amount * dir.y) / iResolution.xy).b;
    return vec3(r, g, b);
}

vec3 screenGlow(vec3 col, float intensity) {
    float glow = pow(max(col.r, max(col.g, col.b)), 2.0) * intensity;
    return col + glow * 0.5;
}

float shapeMask(vec2 p, float barWidth, float barHeight) {
    vec2 halfSize = vec2(barWidth * 0.5, barHeight * 0.5);
    vec2 uv = abs(p);
    vec2 edge = uv - halfSize;
    float outside = max(edge.x, edge.y);
    return 1.0 - step(0.0, outside);
}

float edgeMask(float v, float thresh) {
    return smoothstep(thresh - 0.02, thresh, v);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    uv -= 0.5;
    uv.x *= iResolution.x / iResolution.y;
    
    float bass = getBass();
    float mid = getMid();
    float treble = getTreble();
    float volume = getOverallVolume();
    
    vec3 color = vec3(0.0);
    
    float barWidth = 0.015;
    float x = uv.x * 0.5 + 0.5;
    float freqValue = getSpectrum(x);
    
    float barHeight = freqValue * 0.8 * (1.0 + bass * 0.5);
    float barY = 0.0 - barHeight * 0.5;
    
    vec2 barPos = vec2(uv.x, uv.y - barY);
    float mask = shapeMask(barPos, barWidth, barHeight);
    
    if(mask > 0.0) {
        vec3 barColor;
        if(x < 0.2) {
            barColor = mix(vec3(0.2, 0.1, 1.0), vec3(0.5, 0.2, 1.0), x / 0.2);
        } else if(x < 0.5) {
            barColor = mix(vec3(0.5, 0.2, 1.0), vec3(1.0, 0.2, 0.8), (x - 0.2) / 0.3);
        } else {
            barColor = mix(vec3(1.0, 0.2, 0.8), vec3(1.0, 0.8, 0.2), (x - 0.5) / 0.5);
        }
        
        float noise = fbm(uv * 10.0 + iTime * 2.0) * mid * 0.5;
        barColor += noise * 0.3;
        
        float shiftAmount = treble * 0.005;
        barColor = rgbShift(barColor, shiftAmount, normalize(vec2(sin(iTime), cos(iTime))));
        
        color = barColor * mask;
        color = screenGlow(color, GLOW_INTENSITY * volume);
    }
    
    fragColor = vec4(color, 1.0);
}

void main() {
    vec4 result;
    mainImage(result, gl_FragCoord.xy);
#ifdef GL_ES
    gl_FragColor = result;
#else
    fragColor = result;
#endif
}