```glsl
#ifdef GL_ES
precision mediump float;
#endif

uniform vec2 u_resolution;
uniform float u_time;
uniform float u_audio_level;

void main() {
    vec2 st = gl_FragCoord.xy / u_resolution.xy;
    
    // 创建从中心向外的波纹效果
    vec2 center = vec2(0.5);
    float dist = distance(st, center);
    
    // 使用音频级别和距离创建动态波纹
    float wave = sin(dist * 20.0 - u_time * 5.0) * u_audio_level;
    float intensity = 1.0 + wave * 0.5;
    
    // 基于距离和音频级别的颜色
    vec3 color1 = vec3(0.1, 0.3, 1.0); // 蓝色
    vec3 color2 = vec3(1.0, 0.2, 0.8); // 粉色
    vec3 color3 = vec3(0.2, 1.0, 0.3); // 绿色
    
    // 混合颜色基于距离和音频
    float mixFactor1 = sin(dist * 10.0 - u_time * 2.0) * 0.5 + 0.5;
    float mixFactor2 = u_audio_level * 0.5 + 0.5;
    
    vec3 finalColor = mix(color1, color2, mixFactor1);
    finalColor = mix(finalColor, color3, mixFactor2 * 0.3);
    
    // 应用强度和距离衰减
    float alpha = intensity * (1.0 - dist * 1.5);
    alpha = clamp(alpha, 0.0, 1.0);
    
    // 添加径向渐变
    float radialGradient = 1.0 - dist * 0.8;
    finalColor *= radialGradient;
    
    gl_FragColor = vec4(finalColor, alpha);
}
```
