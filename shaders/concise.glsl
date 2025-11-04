// Target: desktop (#version 330 core)
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
uniform sampler2D iChannel0;

out vec4 fragColor;

#define PI 3.14159265359
#define TWO_PI 6.28318530718

float random (vec2 st) {
    return fract(sin(dot(st.xy,vec2(12.9898,78.233)))*43758.5453123);
}

float random(float seed, float min, float max) {
    return floor(min + random(vec2(seed)) * (max/min));
}

vec2 rotate2D(vec2 _uv, float _angle){
    _uv =  mat2(cos(_angle),-sin(_angle),
                sin(_angle),cos(_angle)) * _uv;
    return _uv;
}

float polygon(vec2 _uv, float size, float width, float sides) {
    // Angle and radius from the current pixel
    float a = atan(_uv.x,_uv.y)+PI;
    float r = TWO_PI/float(sides);

    // Shaping function that modulate the distance
    float d = cos(floor(.5+a/r)*r-a)*length(_uv);

    // ensure smoothstep has increasing edges
    return smoothstep(0.0, 0.005, abs(d-size)-width/2.0);
}

// five-point star mask: keep signature similar to polygon()
float star(vec2 _uv, float outerR, float width, float points) {
    // produce a sharp-pointed star using angular cosine lobes
    // inner radius smaller -> sharper points
    float innerR = outerR * 0.35;
    float a = atan(_uv.y, _uv.x);
    float r = length(_uv);
    float n = points;
    // create n lobes using cos(n * angle). Raise to a high power to sharpen points.
    float lobes = cos(a * n);
    float sharp = pow(max(0.0, lobes), 40.0);
    float desired = mix(innerR, outerR, sharp);
    return smoothstep(0.0, 0.005, abs(r - desired) - width/2.0);
}

// audio texture width used for normalized lookup
const int AUDIO_BANDS = 512;

void mainImage( out vec4 outColor, in vec2 fragCoord )
{
    vec2 uv = fragCoord / iResolution.xy;
    uv = uv * 2.0 - 1.0;
    uv.x *= iResolution.x / iResolution.y;

    // sample approximate bands using normalized texture coordinates
    float bass = 0.0;
    for (int i = 0; i < 10; ++i) {
        float uu = (float(i) + 0.5) / float(AUDIO_BANDS);
        bass += TEX(iChannel0, vec2(uu, 0.0)).x;
    }
    bass /= 10.0;

    float med = 0.0;
    for (int i = 0; i < 20; ++i) {
        float idx = 240.0 - float(i);
        float uu = (idx + 0.5) / float(AUDIO_BANDS);
        med += TEX(iChannel0, vec2(uu, 0.0)).x;
    }
    med /= 20.0;

    float high = 0.0;
    for (int i = 0; i < 20; ++i) {
        float idx = 500.0 - float(i);
        float uu = (idx + 0.5) / float(AUDIO_BANDS);
        high += TEX(iChannel0, vec2(uu, 0.0)).x;
    }
    high /= 20.0;

    float vol = (bass + med + high) / 3.0;
    // Determine spectral balance between high and low bands as a proxy for "frequency increasing/decreasing".
    // If high energy significantly exceeds low energy -> treat as increasing (clockwise);
    // if low energy significantly exceeds high energy -> treat as decreasing (counter-clockwise).
    const int CHECK_BANDS = 64;
    float lowSum = 0.0;
    float highSum = 0.0;
    for (int bi = 0; bi < CHECK_BANDS; ++bi) {
        float uuLow = (float(bi) + 0.5) / float(AUDIO_BANDS);
        float uuHigh = (float(AUDIO_BANDS - 1 - bi) + 0.5) / float(AUDIO_BANDS);
        lowSum += TEX(iChannel0, vec2(uuLow, 0.0)).x;
        highSum += TEX(iChannel0, vec2(uuHigh, 0.0)).x;
    }
    float lowAvg = lowSum / float(CHECK_BANDS);
    float highAvg = highSum / float(CHECK_BANDS);
    float balance = highAvg - lowAvg; // positive -> more high freq energy

    // threshold to avoid rapid flips in rotation direction
    float dirThreshold = 0.03; // raised threshold so direction only flips on significant change
    float dirSign = 0.0;
    if (balance > dirThreshold) dirSign = 1.0;
    else if (balance < -dirThreshold) dirSign = -1.0;

    // rotation: base time rotation plus audio-driven component
    float baseSpeed = 0.1; // keep time-based rotation baseline unchanged in magnitude
    // audio-driven rotation magnitude: increases with how strongly balance changes and overall volume
    float audioRot = vol * abs(balance) * 6.0; // scale factor to make effect perceptible
    float angle = iTime * baseSpeed + dirSign * audioRot;
    uv = rotate2D(uv, angle);

    float seed = 8.0; // = floor(bass * 5.);
    // Increase star scale so it approaches the top/bottom edges without overflowing.
    // Keep audio-driven behavior but raise the overall scale and add a small base so
    // the star is larger even at low bass. Clamp to avoid exceeding the view bounds.
    float size = clamp(0.6 * bass * 2.0 + 0.18, 0.0, 0.95);
    float width = 0.02 + 0.3 * vol;
    float rgbShift = 0.02 * vol;
    // replace polygon with five-point star while keeping other params unchanged
    float colorR = star(uv - vec2(rgbShift, 0.0), size, width, 5.0);
    float colorG = star(uv, size, width, 5.0);
    float colorB = star(uv + vec2(rgbShift, 0.0), size, width, 5.0);
    vec3 shapeColor = vec3(colorR, colorG, colorB);

    // only draw the star; invert so subject is white (1.0) and background is black (0.0)
    outColor = vec4(1.0 - shapeColor, 1.0);
}

void main() {
    vec4 color;
    mainImage(color, gl_FragCoord.xy);
#ifdef GL_ES
    gl_FragColor = color;
#else
    fragColor = color;
#endif
}
