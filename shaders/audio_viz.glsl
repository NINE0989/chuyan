// Basic audio visualization shader
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = fragCoord/iResolution.xy;
    
    // Get frequency data from audio texture
    float fft = texture(iChannel0, vec2(uv.x, 0.0)).r;
    
    // Create visualization
    vec3 col = vec3(0.0);
    
    // Frequency bars
    float bar = step(1.0 - fft * 0.95, uv.y);
    col += bar * vec3(1.0 - uv.y, uv.x * 0.5, uv.y);
    
    // Add some glow
    float glow = fft * 0.5 * (1.0 - uv.y);
    col += glow * vec3(0.5, 0.2, 0.1);
    
    // Add time-based color variation
    col *= 0.8 + 0.2 * cos(iTime + uv.xyx + vec3(0,2,4));
    
    // Output to screen
    fragColor = vec4(col, 1.0);
}