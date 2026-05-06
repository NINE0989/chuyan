// AI_PIPELINE_HOOK
// style_profile: minimal
// generated_with: mock_mcp_adapter
#version 330 core
uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;
out vec4 FragColor;
void mainImage(out vec4 fragColor, in vec2 fragCoord){
vec2 uv = fragCoord.xy / iResolution.xy;
vec2 p = (uv - 0.5) * vec2(iResolution.x / iResolution.y, 1.0);
float bass = texture(iChannel0, vec2(0.05, 0.25)).r;
float mid = texture(iChannel0, vec2(0.25, 0.25)).r;
float tre = texture(iChannel0, vec2(0.75, 0.25)).r;
float r = length(p);
float ring = smoothstep(0.03, 0.0, abs(r - (0.25 + bass * 0.2 + 0.03*sin(iTime))));
vec3 col = vec3(0.02, 0.02, 0.03);
col += ring * vec3(0.2 + bass, 0.5 + mid, 0.8 + tre);
fragColor = vec4(col, 1.0);
}
void main(){ mainImage(FragColor, gl_FragCoord.xy); }