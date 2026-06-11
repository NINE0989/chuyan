// Audio Reactive Spectrum Wave
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

#define SAFE_MARGIN 0.05
#define FIT_MODE_INSIDE 1

#define AUDIO_ATTACK 0.08
#define AUDIO_DECAY 0.30
#define AUDIO_SMOOTH_K 0.85
#define MAX_PARTICLES 64
#define PARTICLE_ITERATIONS 32
#define GLOW_INTENSITY 0.8

float hash12(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

vec2 rotate2D(vec2 p, float a) {
    float s = sin(a), c = cos(a);
    return vec2(p.x * c - p.y * s, p.x * s + p.y * c);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    
    float a = hash12(i);
    float b = hash12(i + vec2(1.0, 0.0));
    float c = hash12(i + vec2(0.0, 1.0));
    float d = hash12(i + vec2(1.0, 1.0));
    
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm(vec2 p, int octaves) {
    float value = 0.0;
    float amplitude = 0.5;
    for (int i = 0; i < octaves; i++) {
        value += amplitude * noise(p);
        p *= 2.0;
        amplitude *= 0.5;
    }
    return value;
}

float shapeMask(vec2 localPos, float radius) {
    return smoothstep(radius + 0.01, radius - 0.01, length(localPos));
}

float edgeMask(vec2 p, float r, float width) {
    float d = length(p);
    return smoothstep(r + width, r - width, d);
}

float sampleBand(float u) {
    float du = 1.0 / 512.0;
    float e = 0.0;
    e += TEX(iChannel0, vec2(u - 2.0 * du, 0.0)).r;
    e += TEX(iChannel0, vec2(u - du, 0.0)).r;
    e += TEX(iChannel0, vec2(u, 0.0)).r;
    e += TEX(iChannel0, vec2(u + du, 0.0)).r;
    e += TEX(iChannel0, vec2(u + 2.0 * du, 0.0)).r;
    return e / 5.0;
}

vec3 hsl2rgb(vec3 c) {
    vec3 rgb = clamp(abs(mod(c.x * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0);
    return c.z + c.y * (rgb - 0.5) * (1.0 - abs(2.0 * c.z - 1.0));
}

vec3 rgbShift(vec2 uv, vec3 color, float amount) {
    float r = TEX(iChannel0, uv + vec2(0.02, 0.0) * amount).r;
    float g = TEX(iChannel0, uv + vec2(0.0, 0.0) * amount).r;
    float b = TEX(iChannel0, uv + vec2(-0.02, 0.0) * amount).r;
    return color * vec3(r, g, b);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    float aspect = iResolution.x / iResolution.y;
    
    vec2 centeredUV = (uv - 0.5) * 2.0;
    if (aspect > 1.0) {
        centeredUV.x *= aspect;
    } else {
        centeredUV.y /= aspect;
    }
    
    float scale = 1.0 - 2.0 * SAFE_MARGIN;
    centeredUV /= scale;
    
    vec3 col = vec3(0.0);
    
    float overallEnergy = 0.0;
    for (int i = 0; i < 8; i++) {
        float u = float(i) / 8.0;
        overallEnergy += sampleBand(u);
    }
    overallEnergy /= 8.0;
    overallEnergy = pow(overallEnergy, 0.65);
    
    float tMix = smoothstep(0.0, 0.02, overallEnergy);
    
    for (int i = 0; i < PARTICLE_ITERATIONS; i++) {
        if (i >= MAX_PARTICLES) break;
        
        float fi = float(i);
        float u = fi / float(MAX_PARTICLES);
        
        float bandEnergy = sampleBand(u);
        bandEnergy = pow(bandEnergy, 0.65);
        
        float x = -1.0 + 2.0 * u;
        float idleY = 0.1 * sin(iTime * 0.5 + u * 10.0);
        float audioY = 0.8 * bandEnergy * sin(iTime * 2.0 + u * 15.0);
        float y = mix(idleY, audioY, tMix);
        
        vec2 particlePos = vec2(x, y);
        vec2 toPixel = centeredUV - particlePos;
        
        float hue = u + iTime * 0.1 + bandEnergy * 0.5;
        vec3 particleColor = hsl2rgb(vec3(hue, 0.8, 0.6 + 0.4 * bandEnergy));
        
        float radius = 0.02 + 0.08 * bandEnergy;
        radius *= mix(0.5, 1.0, tMix);
        
        float mask = shapeMask(toPixel, radius);
        
        if (mask > 0.0) {
            vec3 shiftedColor = rgbShift(uv, particleColor, bandEnergy * 0.3);
            col += mask * shiftedColor * (0.8 + 0.4 * bandEnergy);
        }
    }
    
    col = mix(col, col * (1.0 + GLOW_INTENSITY * overallEnergy), tMix);
    
    float edge = edgeMask(centeredUV, 1.0, 0.05);
    col *= edge;
    
    fragColor = vec4(col, 1.0);
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