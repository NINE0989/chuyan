#version 330
uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;

out vec4 FragColor;

float hash21(vec2 p) {
    p = fract(p * vec2(234.34, 435.345));
    p += dot(p, p + 19.19);
    return fract(p.x * p.y);
}

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float smoothNoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float sdCircle(vec2 p, float r) {
    return length(p) - r;
}

float sdStar(vec2 p, float r, float n) {
    float a = atan(p.y, p.x);
    float seg = 3.14159 * 2.0 / n;
    a = mod(a - seg * 0.5, seg) - seg * 0.5;
    float d = length(p);
    float rad = r * cos(a) / cos(mod(a, seg) - seg * 0.5);
    return d - rad * 0.8;
}

float sdDiamond(vec2 p, float r) {
    float d = abs(p.x) + abs(p.y);
    return d - r;
}

float sdHexagon(vec2 p, float r) {
    vec2 q = abs(p);
    return max(q.x * 0.866025 + q.y * 0.5, q.y) - r;
}

float shape(vec2 p, float r, float type) {
    if (type < 0.25) return sdCircle(p, r);
    else if (type < 0.5) return sdStar(p, r, 5.0);
    else if (type < 0.75) return sdDiamond(p, r);
    else return sdHexagon(p, r);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / min(iResolution.x, iResolution.y);
    
    vec2 audioUV = fragCoord / iResolution.xy;
    vec4 audioTex = texture(iChannel0, audioUV);
    
    float bass = audioTex.x * 0.6 + 0.4 * (0.5 + 0.5 * sin(iTime * 1.5));
    float mid = audioTex.y * 0.5 + 0.5 * (0.5 + 0.5 * sin(iTime * 2.3 + 1.2));
    float treble = audioTex.z * 0.4 + 0.6 * (0.5 + 0.5 * sin(iTime * 3.7 + 2.8));
    
    float gesture = audioTex.w;
    
    float gridSize = 16.0;
    vec2 gridUV = uv * gridSize;
    vec2 cellId = floor(gridUV);
    vec2 cellPos = fract(gridUV) - 0.5;
    
    float seed = hash21(cellId);
    float typeSeed = hash21(cellId + vec2(100.0));
    float phase = hash21(cellId + vec2(200.0)) * 6.283;
    
    float shapeType = typeSeed;
    
    float bassOffset = bass * 0.15;
    vec2 offset = vec2(
        sin(iTime * 1.2 + phase + bass * 4.0) * bassOffset,
        cos(iTime * 1.5 + phase * 0.7 + bass * 3.0) * bassOffset
    );
    
    float sizeBase = 0.12 + seed * 0.15;
    float sizeMod = mid * 0.2;
    float size = sizeBase + sizeMod;
    
    float glow = treble * 0.8 + 0.2;
    
    float waltzBeat = sin(iTime * 2.0 * 3.14159 * 1.0) * 0.5 + 0.5;
    float pulse = bass * 0.7 + waltzBeat * 0.3;
    
    vec2 p = cellPos + offset;
    float d = shape(p, size, shapeType);
    
    vec3 col1 = vec3(0.1, 0.6, 0.9);
    vec3 col2 = vec3(0.9, 0.3, 0.5);
    vec3 col3 = vec3(0.2, 0.8, 0.6);
    vec3 col4 = vec3(0.9, 0.7, 0.1);
    
    vec3 baseColor = col1;
    if (typeSeed < 0.25) baseColor = col1;
    else if (typeSeed < 0.5) baseColor = col2;
    else if (typeSeed < 0.75) baseColor = col3;
    else baseColor = col4;
    
    float brightness = 1.2 + bass * 0.8 + mid * 0.4;
    
    float glowIntensity = glow * 0.6;
    float edgeGlow = smoothstep(size - 0.02, size, abs(d)) * glowIntensity;
    
    float shapeMask = 1.0 - smoothstep(0.0, 0.03, d);
    float shapeGlow = exp(-abs(d) * 8.0) * glowIntensity;
    
    vec3 color = vec3(0.0);
    
    color += baseColor * shapeMask * brightness * (0.8 + pulse * 0.4);
    color += baseColor * shapeGlow * brightness;
    color += vec3(1.0) * edgeGlow * treble * 1.5;
    
    float extraSeed = hash21(cellId + vec2(50.0, 50.0));
    if (extraSeed > 0.3) {
        vec2 extraOffset = vec2(
            sin(iTime * 2.0 + extraSeed * 10.0 + bass * 3.0) * 0.08,
            cos(iTime * 2.3 + extraSeed * 7.0 + bass * 2.5) * 0.08
        );
        float extraSize = 0.03 + extraSeed * 0.06 + mid * 0.05;
        float extraType = hash21(cellId + vec2(300.0));
        float d2 = shape(cellPos + extraOffset, extraSize, extraType);
        float extraMask = 1.0 - smoothstep(0.0, 0.02, d2);
        float extraGlow = exp(-abs(d2) * 12.0) * glowIntensity * 0.5;
        
        vec3 extraColor = mix(col3, col4, extraSeed);
        color += extraColor * extraMask * brightness * 0.7;
        color += extraColor * extraGlow * 0.8;
    }
    
    color += vec3(0.3, 0.5, 0.8) * gesture * 0.3;
    
    vec3 bg = vec3(0.02, 0.03, 0.05);
    color = mix(bg, color, 1.0 - exp(-length(color) * 2.0));
    
    color *= 1.3;
    
    color = color / (color + vec3(1.0));
    color = pow(color, vec3(1.0 / 2.2));
    
    fragColor = vec4(color, 1.0);
}

void main() {
    vec4 color;
    mainImage(color, gl_FragCoord.xy);
    FragColor = color;
}
