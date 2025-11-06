// ECG-style waveform visualization using time-domain audio in iChannel0
// Expects iChannel0 to be a 1xN texture where R channel holds time-domain samples (-1..1)

#version 330 core

#ifdef GL_ES
precision mediump float;
#endif

#ifndef TEX
#ifdef GL_ES
#define TEX(s, uv) texture2D(s, uv)
#else
#define TEX(s, uv) texture(s, uv)
#endif
#endif

uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0; // time-domain: shape (1, chunk_size, 4), R channel holds samples

out vec4 fragColor;

void mainImage(out vec4 outColor, in vec2 fragCoord) {
    vec2 uv = fragCoord.xy / iResolution.xy;
    vec3 bg = vec3(0.0, 0.0, 0.0);
    vec3 col = bg;

    // visual params
    int rows = 1; // number of waveform stripes (keep only center line)
    float padding = 0.06; // top/bottom padding
    float usable = 1.0 - 2.0 * padding;
    float rowH = usable / float(rows);

    // thickness and brightness
    float line_thickness = 0.006; // in normalized screen Y
    float gain = 0.9; // amplitude gain

    // X sample coordinate into time-domain texture
    float sx = uv.x;
    // sample from iChannel0 (assumed 1-row texture)
    float sample = TEX(iChannel0, vec2(sx, 0.5)).r; // raw -1..1

    // make several harmonics/echoes for a fuller trace
    float echo = 0.0;
    echo += TEX(iChannel0, vec2(mod(sx - 0.0005 * sin(iTime*2.0), 1.0), 0.5)).r * 0.6;
    echo += TEX(iChannel0, vec2(mod(sx - 0.0012 * sin(iTime*1.3), 1.0), 0.5)).r * 0.3;
    sample = mix(sample, echo, 0.35);

    // Draw each row's waveform
    for (int i = 0; i < 8; i++) {
    float fi = float(i);
    // place baseline at 1/3 from bottom
    float centerY = 1.0/2.0;

    // amplitude scaling per row (small variation for visual interest)
    float rowGain = gain * (0.6 + 0.5 * sin(float(i) * 1.3 + iTime * 0.2));

    // map sample (-1..1) to vertical offset within the row
    // increase amplitude so the waveform nearly reaches the top but doesn't exceed it
    float amplitudeScale = 0.62; // tuned so peak approaches top without overflowing
    float ypos = centerY + sample * amplitudeScale * rowH * rowGain;
    // clamp to avoid drawing beyond the viewport top
    ypos = clamp(ypos, 0.0, 0.98);

        // line mask
        float d = abs(uv.y - ypos);
        float mask = smoothstep(line_thickness, 0.0, d);

        // color per row (gradients)
        vec3 rowColor = mix(vec3(0.6275, 1.0, 1.0), vec3(1.0, 1.0, 1.0), fi / float(rows));
        // fade edges
        float fade = smoothstep(0.0, 0.25, abs(centerY - 0.5));

        col = mix(col, rowColor, mask * (1.0 - 0.5 * fade));
    }

    // (Only center waveform is drawn; no extra guiding line)

    // slight vignette
    float dist = length((uv - 0.5) * vec2(iResolution.x / iResolution.y, 1.0));
    col *= mix(1.0, 0.9, smoothstep(0.6, 1.0, dist));

    outColor = vec4(col, 1.0);
}

void main() {
    vec4 color = vec4(0.0);
    mainImage(color, gl_FragCoord.xy);
    fragColor = color;
}
