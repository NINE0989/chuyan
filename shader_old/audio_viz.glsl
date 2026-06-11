// Basic audio visualization shader

#version 330 core
#include "ShaderCommon.glsl"

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = fragCoord / iResolution.xy;

    // Get frequency data from audio texture
    float fft = texture(iChannel0, vec2(uv.x, 0.0)).r;

    // Create visualization
    vec3 col = vec3(0.0);

    // Make FFT more visible: apply gentle amplification and sqrt for perceptual scaling
    float amp = sqrt(fft) * 6.0;

    // Frequency bars (wider, lower threshold)
    float barThreshold = 0.85 - fft * 0.7; // lower threshold when fft increases
    float bar = step(barThreshold, uv.y);
    col += bar * vec3(1.0 - uv.y, uv.x * 0.5, uv.y) * amp;

    // Add some glow that scales with fft
    float glow = amp * 0.25 * (1.0 - uv.y);
    col += glow * vec3(0.9, 0.4, 0.2);

    // Add time-based color variation (subtle)
    col *= 0.6 + 0.4 * (0.5 + 0.5 * cos(iTime + uv.xyx + vec3(0,2,4)));

    // Output to screen
    fragColor = vec4(col, 1.0);
}

// Standard main entrypoint to call the ShaderToy-style mainImage
void main() {
    mainImage(fragColor, gl_FragCoord.xy);
}