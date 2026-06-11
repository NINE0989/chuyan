#version 330
// AI_PIPELINE_HOOK
// style_profile: minimal
// generated_with: langgraph_agent

uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;
uniform sampler2D iChannel1;

out vec4 FragColor;

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
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

mat2 rot(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, -s, s, c);
}

float waltzBeat(float t) {
    float beat = floor(t * 1.5);
    float phase = fract(t * 1.5);
    float strength = 1.0 - smoothstep(0.0, 0.3, phase);
    return strength;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / min(iResolution.x, iResolution.y);
    float t = iTime;
    
    vec4 audioSample = texture(iChannel0, vec2(0.5, 0.0));
    float audioEnergy = audioSample.x;
    float audioMid = audioSample.y;
    float audioHigh = audioSample.z;
    
    float beat = waltzBeat(t);
    float waltzPulse = 0.5 + 0.5 * sin(t * 3.0 * 3.14159);
    float energy = mix(waltzPulse, audioEnergy, 0.3);
    float midEnergy = mix(0.5 + 0.3 * sin(t * 6.0), audioMid, 0.3);
    float highEnergy = mix(0.3 + 0.2 * sin(t * 9.0), audioHigh, 0.3);
    
    vec2 handUV = fragCoord / iResolution.xy;
    vec4 handTex = texture(iChannel1, handUV);
    float handInfluence = handTex.r;
    
    vec2 p = uv;
    float rotAngle = t * 0.15 + energy * 0.5;
    p = rot(rotAngle) * p;
    
    float r = length(p);
    float a = atan(p.y, p.x);
    
    float rings = 6.0 + 3.0 * energy;
    float ringIdx = floor(r * rings);
    float ringFrac = fract(r * rings);
    
    float petals = 8.0 + 4.0 * midEnergy;
    float petalAngle = a * petals / 6.2832;
    float petalIdx = floor(petalAngle);
    float petalFrac = fract(petalAngle);
    
    vec2 elemPos = vec2(
        ringFrac - 0.5 + 0.1 * sin(t * 2.0 + ringIdx * 1.7 + petalIdx * 2.3),
        petalFrac - 0.5 + 0.1 * cos(t * 1.8 + ringIdx * 2.1 + petalIdx * 1.9)
    );
    
    float elemSize = 0.08 + 0.06 * energy + 0.04 * highEnergy;
    float d = length(elemPos) - elemSize;
    
    vec2 noiseUV = vec2(
        ringIdx * 0.3 + petalIdx * 0.7 + t * 0.2,
        ringIdx * 0.7 + petalIdx * 0.3 + t * 0.15
    );
    float n = smoothNoise(noiseUV);
    
    vec3 color1 = vec3(0.2, 0.6, 0.9);
    vec3 color2 = vec3(0.9, 0.7, 0.2);
    vec3 color3 = vec3(0.9, 0.3, 0.5);
    
    float mixVal = 0.5 + 0.5 * sin(ringIdx * 0.5 + petalIdx * 0.3 + t * 0.5);
    vec3 baseColor = mix(color1, color2, mixVal);
    baseColor = mix(baseColor, color3, 0.3 * sin(t * 0.7 + ringIdx));
    
    vec3 elemColor = baseColor * (0.7 + 0.3 * energy + 0.2 * highEnergy * n);
    
    float smoothness = 0.02;
    float alpha = 1.0 - smoothstep(0.0, smoothness, d);
    float glow = exp(-abs(d) * 20.0) * (0.5 + 0.5 * highEnergy);
    
    vec3 bgColor = vec3(0.02, 0.03, 0.06);
    float wave = 0.5 + 0.5 * sin(uv.x * 10.0 + uv.y * 8.0 + t * 0.5);
    bgColor += vec3(0.01, 0.02, 0.04) * wave;
    float centerGlow = exp(-r * 3.0) * (0.1 + 0.1 * energy);
    bgColor += vec3(0.1, 0.2, 0.4) * centerGlow;
    
    vec3 finalColor = bgColor;
    finalColor = mix(finalColor, elemColor, alpha * 0.9);
    finalColor += glow * elemColor * 0.5;
    
    float handEffect = handInfluence * 0.3;
    finalColor += vec3(0.1, 0.05, 0.15) * handEffect;
    
    vec2 starUV = uv * 30.0;
    vec2 starId = floor(starUV);
    vec2 starFrac = fract(starUV) - 0.5;
    float starHash = hash(starId);
    if (starHash > 0.97 && length(starFrac) < 0.02 + 0.02 * highEnergy) {
        float twinkle = 0.5 + 0.5 * sin(t * 3.0 + starId.x * 100.0 + starId.y * 50.0);
        finalColor += vec3(1.0, 0.9, 0.7) * twinkle * highEnergy * 0.3;
    }
    
    finalColor = finalColor / (finalColor + vec3(1.0));
    float vignette = 1.0 - 0.3 * length(uv);
    finalColor *= vignette;
    
    fragColor = vec4(finalColor, 1.0);
}

void main() {
    vec4 fragColor;
    mainImage(fragColor, gl_FragCoord.xy);
    FragColor = fragColor;
}
