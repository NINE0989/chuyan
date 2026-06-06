#version 330

uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;

out vec4 FragColor;

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    
    // 低频 bass — 控制主形体尺度
    float bass = texture(iChannel0, vec2(0.1, 0.0)).x;
    
    // 中频 mid — 控制纹理细节
    float mid = texture(iChannel0, vec2(0.5, 0.0)).x;
    
    // 高频 treble — 控制辉光
    float treble = texture(iChannel0, vec2(0.9, 0.0)).x;
    
    // 极简背景（浅灰渐变）
    vec3 col = vec3(0.95, 0.95, 0.97);
    
    // 主圆环 — 低频 bass 控制半径和厚度
    float r = length(uv);
    float ringRadius = 0.35 + bass * 0.25;
    float ringThick = 0.015 + mid * 0.025;
    float ring = smoothstep(ringThick, 0.0, abs(r - ringRadius));
    
    // 中频控制径向线条密度
    float angle = atan(uv.y, uv.x);
    float lines = smoothstep(0.008, 0.0, abs(sin(angle * (6.0 + mid * 8.0) + iTime * 0.3)));
    
    // 高频控制中心辉光
    float glow = treble * 0.6 * exp(-r * 4.0);
    
    // 极简配色 — 深灰/黑色为主
    vec3 ringColor = vec3(0.15, 0.15, 0.18);
    vec3 lineColor = vec3(0.3, 0.3, 0.35);
    vec3 glowColor = vec3(0.1, 0.1, 0.12);
    
    col = mix(col, ringColor, ring);
    col += lines * lineColor * 0.2;
    col += glow * glowColor;
    
    // 时间呼吸 — 极简微动
    float pulse = 0.5 + 0.5 * sin(iTime * 0.5);
    col *= (0.98 + 0.02 * pulse);
    
    col = clamp(col, 0.0, 1.0);
    fragColor = vec4(col, 1.0);
}

void main() {
    mainImage(FragColor, gl_FragCoord.xy);
}