// Target: generic (no #version)
// Estimated texture samples per pixel: ~30
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

// Layout constants
#define SAFE_MARGIN 0.05
#define FIT_MODE_INSIDE 1

// Audio smoothing constants
#define AUDIO_ATTACK 0.08
#define AUDIO_DECAY 0.30
#define AUDIO_SMOOTH_K 0.85

// Performance and visual constants
#define DEFAULT_BANDS 32
#define CIRCLE_COUNT 16
#define SAMPLE_COUNT 3
#define MAX_RADIUS 0.4
#define BASE_THICKNESS 0.008
#define MAX_THICKNESS 0.03
#define RGB_SHIFT 0.002
#define GLOW_INTENSITY 1.2

// Uniforms
uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;

// Output variable for desktop GL
#ifndef GL_ES
out vec4 fragColor;
#endif

// 2D hash function
float hash12(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

// Circle mask function with smooth edges
float circleMask(vec2 uv, float radius, float thickness) {
    float d = length(uv);
    // ensure edge0 <= edge1 for smoothstep
    float eps = 0.005;
    float outer = smoothstep(radius - eps, radius, d);
    float inner = smoothstep(radius - thickness - eps, radius - thickness, d);
    return clamp(outer - inner, 0.0, 1.0);
}

// Sample audio band with neighborhood averaging
float sampleBand(int bandIdx) {
    float u = float(bandIdx) / float(DEFAULT_BANDS - 1);
    float sum = 0.0;
    float step = 0.0025;
    
    for(int i = -SAMPLE_COUNT/2; i <= SAMPLE_COUNT/2; i++) {
        float uu = clamp(u + float(i) * step, 0.0, 1.0);
        sum += TEX(iChannel0, vec2(uu, 0.0)).r;
    }
    
    return sum / float(SAMPLE_COUNT);
}

// Audio energy smoothing (stateless fallback)
float smoothAudioEnergy(float target, float prev) {
    float compressed = pow(target, 0.65);
    float alpha = (target > prev) ? 
        (1.0 - exp(-1.0 / (AUDIO_ATTACK * 60.0))) : 
        (1.0 - exp(-1.0 / (AUDIO_DECAY * 60.0)));
    return mix(prev, compressed, alpha);
}

// RGB shift effect
vec3 rgbShift(vec3 color, vec2 uv, float amount, float mask) {
    vec2 dir = normalize(uv) * amount * mask;
    return vec3(
        color.r * smoothstep(length(dir), 0.0, mask),
        color.g * smoothstep(length(dir) * 0.8, 0.0, mask),
        color.b * smoothstep(length(dir) * 1.2, 0.0, mask)
    );
}

// Glow effect
vec3 addGlow(vec3 color, float mask, float energy) {
    float glow = pow(mask, 0.3) * energy * GLOW_INTENSITY;
    return clamp(color + color * glow, 0.0, 1.0);
}

// HSV to RGB conversion
vec3 hsv2rgb(vec3 c) {
    vec4 K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

// Idle state color (low energy)
vec3 idleColor(int circleIdx, float time) {
    float hue = fract(float(circleIdx) * 0.15 + time * 0.05);
    // increase base brightness for visibility when idle
    return hsv2rgb(vec3(hue, 0.7, 0.35));
}

// Audio-driven color
vec3 audioColor(int circleIdx, float energy, float angle, float time) {
    float hue = fract(float(circleIdx) * 0.12 + angle * 0.15 + time * 0.2 + hash12(vec2(circleIdx)) * 0.3);
    return hsv2rgb(vec3(hue, 0.9, 0.9 * energy));
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // Centered, short-edge normalized coordinates
    vec2 center = 0.5 * iResolution.xy;
    float scale = min(iResolution.x, iResolution.y);
    vec2 uv = (fragCoord - center) / scale;
    float maxSafe = 1.0 - SAFE_MARGIN;
    
    // Pre-sample audio spectrum to control texture access
    float bands[DEFAULT_BANDS];
    float prevBands[DEFAULT_BANDS];
    for(int i = 0; i < DEFAULT_BANDS; i++) {
        bands[i] = sampleBand(i);
        prevBands[i] = (i > 0) ? bands[i-1] : bands[0];
    }
    
    // Calculate overall energy and activity factor
    float totalEnergy = 0.0;
    for(int i = 0; i < DEFAULT_BANDS; i++) {
        totalEnergy += bands[i];
    }
    totalEnergy /= float(DEFAULT_BANDS);
    // be more sensitive to low audio levels
    float activity = smoothstep(0.0, 0.005, totalEnergy);
    
    vec3 color = vec3(0.0);
    float radiusStep = (maxSafe * MAX_RADIUS) / float(CIRCLE_COUNT - 1);
    
    // Calculate closest circle for early culling
    float d = length(uv);
    int closestCircle = int(d / radiusStep + 0.5);
    closestCircle = clamp(closestCircle, 0, CIRCLE_COUNT - 1);
    
    // Only process closest circles (early culling optimization)
    for(int offset = -1; offset <= 1; offset++) {
        int circleIdx = closestCircle + offset;
        if(circleIdx < 0 || circleIdx >= CIRCLE_COUNT) continue;
        
        // Base circle parameters
        float baseRadius = float(circleIdx) * radiusStep;
        float angle = atan(uv.y, uv.x);
        
        // Map angle to frequency band
        float angleNorm = (angle + 3.14159) / (2.0 * 3.14159);
        int bandIdx = clamp(int(angleNorm * float(DEFAULT_BANDS)), 0, DEFAULT_BANDS - 1);
        
        // Get smoothed audio energy
        float energy = smoothAudioEnergy(bands[bandIdx], prevBands[bandIdx]);
        energy = mix(0.05, energy * 1.8, activity);
        
        // Animate radius based on audio energy
        float animRadius = baseRadius + sin(angle * 3.0 + iTime * 2.0) * 0.03 * energy;
        animRadius = clamp(animRadius, 0.0, maxSafe * MAX_RADIUS);
        
        // Adjust thickness based on circle index and energy
        float thickness = mix(BASE_THICKNESS, MAX_THICKNESS, 
            (float(circleIdx) / float(CIRCLE_COUNT)) * (energy + 0.3));
        
        // Early geometric culling
        float minDist = animRadius - thickness - 0.01;
        float maxDist = animRadius + 0.01;
        if(d < minDist || d > maxDist) continue;
        
        // Calculate circle mask
        float mask = circleMask(uv, animRadius, thickness);
        if(mask < 0.01) continue;
        
        // Mix idle and audio colors
        vec3 idleCol = idleColor(circleIdx, iTime);
        vec3 audioCol = audioColor(circleIdx, energy, angle, iTime);
        vec3 circleColor = mix(idleCol, audioCol, activity);
        
        // Apply RGB shift and glow
        circleColor = rgbShift(circleColor, uv, RGB_SHIFT, mask);
        circleColor = addGlow(circleColor, mask, energy);
        
        // Accumulate color
        color = clamp(color + circleColor * mask, 0.0, 1.0);
    }
    
    // Ensure safe area is respected
    float safeMask = step(d, maxSafe * MAX_RADIUS + 0.01);
    color *= safeMask;
    
    fragColor = vec4(color, 1.0);
}

// Main adapter function
void main() {
#ifdef GL_ES
    vec4 result;
    mainImage(result, gl_FragCoord.xy);
    gl_FragColor = result;
#else
    mainImage(fragColor, gl_FragCoord.xy);
#endif
}