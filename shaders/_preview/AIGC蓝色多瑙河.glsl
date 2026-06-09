#version 330

uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;  // 音频纹理

out vec4 FragColor;

// --- 伪随机哈希 ---
float hash21(vec2 p) {
    p = fract(p * vec2(234.34, 435.345));
    p += dot(p, p + 19.19);
    return fract(p.x * p.y);
}

// --- 2D 旋转 ---
vec2 rot(vec2 uv, float angle) {
    float s = sin(angle);
    float c = cos(angle);
    return vec2(uv.x * c - uv.y * s, uv.x * s + uv.y * c);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    
    // --- 音频采样（分带） ---
    // 低频：节奏基底
    float audioLow = texture(iChannel0, vec2(0.05, 0.25)).r;
    // 中频：旋律
    float audioMid = texture(iChannel0, vec2(0.25, 0.5)).r;
    // 高频：细节
    float audioHigh = texture(iChannel0, vec2(0.5, 0.75)).r;
    
    // 圆舞曲脉冲：用时间模拟3/4拍强弱弱
    float beat = sin(iTime * 6.0);  // 约 180 BPM
    float pulse = 0.5 + 0.5 * beat;
    float waltzPhase = fract(iTime * 3.0);  // 3拍循环
    
    // --- 手势交互预留层 ---
    // 模拟手势位置（实际使用时替换为真实手势输入）
    vec2 gesturePos = vec2(0.3 + 0.3 * sin(iTime * 0.5), 0.2 + 0.2 * cos(iTime * 0.7));
    float gestureRadius = 0.15 + 0.05 * audioMid;
    
    // --- 小元素系统：粒子网格 ---
    vec3 color = vec3(0.0);
    float gridSize = 12.0;
    
    // 主粒子网格
    for (float i = 0.0; i < gridSize; i++) {
        for (float j = 0.0; j < gridSize; j++) {
            vec2 cellPos = vec2(i, j) / gridSize;
            vec2 cellCenter = cellPos + 0.5 / gridSize;
            
            // 映射到屏幕坐标
            vec2 pos = cellCenter * 2.0 - 1.0;
            pos.x *= iResolution.x / iResolution.y;
            
            // 每个粒子的随机偏移
            float seed = hash21(vec2(i, j));
            float seed2 = hash21(vec2(i + 100.0, j + 200.0));
            
            // 音频驱动：低频影响位置偏移幅度
            float offsetScale = 0.03 + 0.06 * audioLow;
            // 中频影响旋转
            float rotAngle = iTime * (0.2 + 0.5 * seed) + audioMid * 3.0;
            // 高频影响闪烁
            float twinkle = 0.7 + 0.3 * sin(iTime * 10.0 + seed * 100.0 + audioHigh * 20.0);
            
            // 圆舞曲节拍影响：强弱弱
            float beatEffect = 1.0;
            float phaseOffset = fract(seed * 3.0);
            if (phaseOffset < 0.33) beatEffect = 0.6 + 0.4 * pulse;
            else if (phaseOffset < 0.66) beatEffect = 0.8 + 0.2 * pulse;
            else beatEffect = 0.5 + 0.5 * pulse;
            
            // 粒子位置偏移（随音乐起舞）
            vec2 offset = vec2(
                sin(iTime * (1.0 + seed * 2.0) + seed * 6.28),
                cos(iTime * (1.2 + seed2 * 2.0) + seed2 * 6.28)
            ) * offsetScale * beatEffect;
            
            // 手势交互影响：靠近手势的粒子被推开
            vec2 gestureDelta = pos - gesturePos;
            float distToGesture = length(gestureDelta);
            float gestureInfluence = smoothstep(gestureRadius, 0.0, distToGesture);
            offset += normalize(gestureDelta) * gestureInfluence * 0.05 * audioMid;
            
            vec2 finalPos = pos + offset;
            
            // 粒子大小
            float size = 0.012 + 0.008 * seed + 0.005 * audioMid;
            size *= beatEffect;
            
            // 粒子形状：圆点 + 小星形变化
            float d = length(uv - finalPos);
            
            // 颜色：根据种子和音频变化
            vec3 particleColor = vec3(
                0.3 + 0.7 * seed,
                0.2 + 0.8 * seed2,
                0.5 + 0.5 * hash21(vec2(i + j, i * j))
            );
            
            // 中频影响色调偏移
            particleColor = mix(particleColor, 
                vec3(0.8, 0.4, 0.6) * (0.5 + 0.5 * audioMid), 
                0.3 * audioMid);
            
            // 高频影响亮度
            float brightness = twinkle * (0.8 + 0.4 * audioHigh);
            
            // 绘制粒子
            float particle = smoothstep(size, 0.0, d);
            color += particle * particleColor * brightness;
            
            // 粒子外围辉光
            float glow = smoothstep(size * 3.0, size, d) * 0.15 * audioHigh;
            color += glow * particleColor * brightness;
        }
    }
    
    // --- 第二层：随机散布的小点（更稀疏，更亮） ---
    for (int k = 0; k < 40; k++) {
        float fi = float(k);
        float seed = hash21(vec2(fi, fi * 3.0));
        float seed2 = hash21(vec2(fi * 7.0, fi * 11.0));
        
        vec2 pos = vec2(
            (seed * 2.0 - 1.0) * (iResolution.x / iResolution.y),
            seed2 * 2.0 - 1.0
        );
        
        // 音频驱动运动
        float moveSpeed = 0.3 + 0.7 * seed;
        float angle = seed * 6.28 + iTime * (0.1 + 0.2 * seed);
        float radius = 0.1 + 0.3 * seed + 0.1 * audioLow;
        
        vec2 offset = vec2(cos(angle), sin(angle)) * radius * (0.5 + 0.5 * sin(iTime * moveSpeed + seed * 10.0));
        
        // 手势交互
        vec2 gestureDelta = pos + offset - gesturePos;
        float distToGesture = length(gestureDelta);
        float gestureInfluence = smoothstep(gestureRadius * 1.5, 0.0, distToGesture);
        offset += normalize(gestureDelta) * gestureInfluence * 0.08 * audioMid;
        
        vec2 finalPos = pos + offset;
        
        float d = length(uv - finalPos);
        float size = 0.006 + 0.004 * seed + 0.003 * audioHigh;
        
        vec3 col = vec3(
            0.6 + 0.4 * sin(seed * 6.28 + audioMid * 2.0),
            0.3 + 0.7 * cos(seed2 * 6.28 + audioMid * 1.5),
            0.8 + 0.2 * sin((seed + seed2) * 6.28 + audioHigh * 3.0)
        );
        
        float particle = smoothstep(size, 0.0, d);
        color += particle * col * (0.6 + 0.4 * audioHigh);
    }
    
    // --- 手势交互可视化（半透明指示圈） ---
    float gestureDist = length(uv - gesturePos);
    float gestureRing = smoothstep(0.005, 0.0, abs(gestureDist - gestureRadius));
    gestureRing += smoothstep(0.003, 0.0, abs(gestureDist - gestureRadius * 0.6)) * 0.5;
    color += gestureRing * vec3(0.3, 0.6, 1.0) * (0.3 + 0.3 * audioMid);
    
    // --- 背景：柔和的渐变 ---
    vec3 bg = vec3(0.02, 0.02, 0.04);
    bg += vec3(0.01, 0.005, 0.02) * sin(iTime * 0.3 + uv.y * 2.0);
    
    // 背景微光随音乐变化
    bg += vec3(0.01, 0.005, 0.01) * audioLow;
    
    vec3 finalColor = mix(bg, color, min(color.r + color.g + color.b, 1.0));
    
    // 轻微色调映射
    finalColor = finalColor / (finalColor + vec3(1.0));
    
    fragColor = vec4(finalColor, 1.0);
}

void main() {
    mainImage(FragColor, gl_FragCoord.xy);
}
