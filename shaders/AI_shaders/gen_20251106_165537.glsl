precision mediump float;
uniform float u_time;
uniform vec2 u_resolution;

void main() {
    vec2 uv = gl_FragCoord.xy / u_resolution.xy;
    uv -= 0.5;
    uv.x *= u_resolution.x / u_resolution.y; // 适配屏幕宽高比
    
    float angle = atan(uv.y, uv.x) + u_time;
    float radius = length(uv);
    
    vec3 color = vec3(
        sin(radius * 10.0 + angle * 2.0),
        cos(radius * 10.0 - angle * 3.0),
        sin(angle * 4.0)
    );
    color = 0.5 + 0.5 * color; // 将颜色值归一化到 [0,1] 范围
    
    gl_FragColor = vec4(color, 1.0);
}
