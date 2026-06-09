#version 330

uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;

out vec4 FragColor;

// 2D 旋转
mat2 rot(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, -s, s, c);
}

// 灯塔主体 SDF
float lighthouseSDF(vec2 p) {
    // 塔身 - 梯形
    float body = max(abs(p.x) * (1.0 - p.y * 0.3) - 0.08, p.y - 0.6);
    // 塔基
    float base = max(abs(p.x) - 0.15, p.y - 0.05);
    // 塔顶平台
    float top = max(abs(p.x) - 0.06, 0.6 - p.y);
    // 塔尖
    float spire = max(abs(p.x) - 0.02, 0.8 - p.y);
    
    float d = body;
    d = min(d, base);
    d = min(d, top);
    d = min(d, spire);
    return d;
}

// 灯光
float lightSDF(vec2 p, float t) {
    vec2 lp = p - vec2(0.0, 0.55);
    float glow = length(lp) - 0.04;
    // 光束
    float beam = abs(lp.x) - 0.002;
    beam = max(beam, abs(lp.y + 0.1) - 0.3);
    return min(glow, beam);
}

// 水面高度
float waterHeight(vec2 pos, float time, float audio) {
    float wave1 = sin(pos.x * 3.0 + time * 1.2) * 0.02;
    float wave2 = sin(pos.x * 5.0 + time * 0.8 + 1.3) * 0.015;
    float wave3 = sin(pos.x * 7.0 + time * 1.5 + 2.7) * 0.01;
    return (wave1 + wave2 + wave3) * (0.5 + audio * 2.0);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    
    // 音频采样
    float audioLow = texture(iChannel0, vec2(0.05, 0.0)).r;
    float audioMid = texture(iChannel0, vec2(0.3, 0.0)).r;
    float audioHigh = texture(iChannel0, vec2(0.7, 0.0)).r;
    
    // 水面位置（水平线在 y=0 附近）
    float waterLine = 0.0;
    
    // 判断是否在水面以下（倒影区域）
    bool isReflection = uv.y < waterLine;
    
    // 倒影 UV
    vec2 refUV = uv;
    if (isReflection) {
        refUV.y = -refUV.y; // 镜像翻转
        // 水面扰动
        float waveOffset = waterHeight(vec2(refUV.x, 0.0), iTime, audioLow);
        refUV.y += waveOffset * 2.0;
        refUV.x += waveOffset * 0.5;
    }
    
    // 构建场景
    vec3 col = vec3(0.0);
    
    // 天空渐变
    float skyGrad = smoothstep(-0.5, 0.5, uv.y);
    vec3 skyColor = mix(vec3(0.02, 0.02, 0.05), vec3(0.1, 0.08, 0.15), skyGrad);
    
    if (!isReflection) {
        // 天空区域
        col = skyColor;
        
        // 灯塔
        float d = lighthouseSDF(refUV);
        float dLight = lightSDF(refUV, iTime);
        
        // 灯塔主体
        float bodyMask = 1.0 - smoothstep(0.0, 0.01, d);
        vec3 lighthouseColor = vec3(0.15, 0.12, 0.1);
        col = mix(col, lighthouseColor, bodyMask);
        
        // 灯塔边缘高光
        float edge = 1.0 - smoothstep(0.0, 0.005, abs(d - 0.002));
        col = mix(col, vec3(0.3, 0.25, 0.2), edge * 0.5);
        
        // 灯光
        float lightMask = 1.0 - smoothstep(0.0, 0.01, dLight);
        vec3 lightColor = vec3(1.0, 0.9, 0.6);
        float lightPulse = 0.8 + 0.2 * sin(iTime * 2.0 + audioHigh * 3.0);
        col = mix(col, lightColor * lightPulse, lightMask);
        
        // 灯光辉光
        float glow = exp(-length(refUV - vec2(0.0, 0.55)) * 8.0) * 0.3;
        glow *= 0.8 + 0.2 * sin(iTime * 2.0);
        col += lightColor * glow * (0.5 + audioHigh * 2.0);
        
        // 星星
        for (int i = 0; i < 30; i++) {
            float seed = float(i) * 1.7;
            vec2 starPos = vec2(
                fract(seed * 12.9898) * 2.0 - 1.0,
                fract(seed * 78.233) * 0.5 + 0.3
            );
            float starDist = length(uv - starPos);
            float starBright = smoothstep(0.02, 0.0, starDist);
            float twinkle = 0.5 + 0.5 * sin(iTime * (1.0 + seed * 0.3) + seed * 10.0);
            col += vec3(1.0) * starBright * twinkle * 0.3;
        }
    } else {
        // 倒影区域 - 先渲染倒影内容
        col = skyColor * 0.6; // 倒影天空更暗
        
        // 倒影灯塔
        float d = lighthouseSDF(refUV);
        float dLight = lightSDF(refUV, iTime);
        
        float bodyMask = 1.0 - smoothstep(0.0, 0.01, d);
        vec3 lighthouseColor = vec3(0.15, 0.12, 0.1);
        col = mix(col, lighthouseColor * 0.5, bodyMask);
        
        float lightMask = 1.0 - smoothstep(0.0, 0.01, dLight);
        vec3 lightColor = vec3(1.0, 0.9, 0.6);
        float lightPulse = 0.8 + 0.2 * sin(iTime * 2.0 + audioHigh * 3.0);
        col = mix(col, lightColor * lightPulse * 0.4, lightMask);
        
        // 倒影辉光 - 被水波扭曲
        float glow = exp(-length(refUV - vec2(0.0, 0.55)) * 6.0) * 0.15;
        glow *= 0.8 + 0.2 * sin(iTime * 2.0);
        col += lightColor * glow * (0.3 + audioLow * 1.5);
        
        // 水面效果
        float waveH = waterHeight(vec2(uv.x, 0.0), iTime, audioLow);
        float waterDist = abs(uv.y - waterLine);
        float waterSurface = exp(-waterDist * 40.0) * (0.3 + audioMid * 2.0);
        
        // 水面波纹纹理
        float ripple = sin(uv.x * 20.0 + iTime * 2.0 + audioLow * 5.0) * 0.5 + 0.5;
        ripple *= sin(uv.x * 35.0 + iTime * 1.5 + audioMid * 4.0) * 0.5 + 0.5;
        ripple *= exp(-waterDist * 15.0);
        
        vec3 waterColor = vec3(0.02, 0.04, 0.08);
        col = mix(col, waterColor, 0.3);
        col += vec3(0.1, 0.15, 0.2) * waterSurface * 0.5;
        col += vec3(0.3, 0.4, 0.5) * ripple * 0.15;
        
        // 水面高光线
        float specular = pow(max(0.0, 1.0 - abs(uv.y - waterLine) * 20.0), 4.0);
        specular *= (0.5 + 0.5 * sin(uv.x * 30.0 + iTime * 3.0 + audioLow * 8.0));
        col += vec3(0.5, 0.6, 0.8) * specular * 0.3;
    }
    
    // 水平线
    float horizon = 1.0 - smoothstep(0.0, 0.005, abs(uv.y - waterLine));
    col = mix(col, vec3(0.2, 0.25, 0.3), horizon * 0.3);
    
    // 音频驱动的整体闪烁
    float flash = 1.0 + audioHigh * 0.1;
    col *= flash;
    
    // 暗角
    float vignette = 1.0 - length(uv * 0.8);
    col *= vignette;
    
    fragColor = vec4(col, 1.0);
}

void main() {
    vec4 color;
    mainImage(color, gl_FragCoord.xy);
    FragColor = color;
}
