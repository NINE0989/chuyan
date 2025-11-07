// TaiChi - by CC - 2020
// License Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported License.

#version 330 core

#ifdef GL_ES
precision mediump float;
#endif

uniform vec3 iResolution;
uniform float iTime;
out vec4 fragColor;
// -------- Const parameter -------- //
const float PI = 3.1415926;

// -------- Basic graphic -------- //
float circle(vec2 st, float radius){
    vec2 l = st - vec2(0.5);
    return 1.0 - smoothstep(0.99 * radius, radius * 1.01, dot(l,l)*4.0);
}
float semicircle(vec2 st, float radius) {
    vec2 l = st;
    float pct = 1.0 - smoothstep(0.95 * radius * radius, 1.05 * radius * radius, dot(l,l));
    
    pct *= step(0.0, l.y);
    return pct;
}
float rectangle(vec2 st, vec2 size) {
    size = 0.5 - 0.5 * size;
    vec2 uv = smoothstep(size, size + vec2(1e-4), st);
    uv *= smoothstep(size, size + vec2(1e-4), vec2(1.0) - st);
    return uv.x * uv.y;
}
float bagua(vec2 uv, float n) {
    float pct = 0.0;
    vec2 st = uv;
    pct = rectangle(st + vec2(0.0, 0.15), vec2(0.5, 0.08));
    pct += rectangle(st, vec2(0.5, 0.08));
    pct += rectangle(st + vec2(0.0, -0.15), vec2(0.5, 0.08));

    pct -= (step(0.1,n) * step(n,1.0) + step(3.1,n) * step(n,4.1) + step(4.1,n) * step(n,5.) + step(6.1,n) * step(n,7.)) * rectangle(st + vec2(0.0,0.15), vec2(0.1, 0.08)); // 1,4,5,7 
    pct -= (step(1.1,n) * step(n,2.1) + step(3.1,n) * step(n,4.1) + step(5.1,n) * step(n,6.) + step(6.1,n) * step(n,7.)) * rectangle(st, vec2(0.1, 0.08));      // 2,4,6,7
    pct -= (step(2.1,n) * step(n,3.1) + step(4.1,n) * step(n,5.1) + step(5.1,n) * step(n,6.) + step(6.1,n) * step(n,7.)) * rectangle(st + vec2(0.0,-0.15), vec2(0.1, 0.08)); // 3,5,6,7

    return pct;
}

// -------- Transform -------- //
mat2 rotate2d(float angle) {
    return mat2(cos(angle), -sin(angle),
                sin(angle), cos(angle));
}
mat2 scale(vec2 scale){
    return mat2(scale.x, 0.0,
                0.0, scale.y);
}

// -------- Main -------- //
void mainImage( out vec4 fragColor, in vec2 fragCoord )
{
    // center the pattern in the viewport: convert to -0.5..0.5 then apply aspect to x
    vec2 uv = fragCoord.xy / iResolution.xy - vec2(0.5);
    uv.x *= iResolution.x / iResolution.y;
    vec3 color = vec3(0.0);
    float pct = 0.0;
    
    vec2 st = 2.0 * uv; // uv is already centered, so st in [-1,1]
    st = rotate2d(-0.5 * iTime) * st;
    pct = semicircle(st, 0.5);
    pct += semicircle(rotate2d(PI) * (st + vec2(-0.25, 0.0)), 0.25);
    pct -= semicircle((st + vec2(0.25, 0.0)), 0.25);   
    pct -= circle(st + vec2(0.25, 0.5),0.02);
    pct += circle(st + vec2(0.75, 0.5),0.02);
    
    st = 2.0 * uv;
    st = 2.0 * st * rotate2d(-0.5 * iTime);
    
    vec2 offset = -vec2(-0.5, -2.);
    pct += bagua(st- vec2(-0.5, -2.), 2.0);
    pct += bagua(st * rotate2d(PI * 0.25) + offset, 3.0);
    pct += bagua(st * rotate2d(PI * 0.5) + offset, 0.0);
    pct += bagua(st * rotate2d(PI * 0.75) + offset, 1.0);
    pct += bagua(st * rotate2d(PI) + offset, 5.0);
    pct += bagua(st * rotate2d(PI * 1.25) + offset, 4.0);
    pct += bagua(st * rotate2d(PI * 1.5) + offset, 7.0);
    pct += bagua(st * rotate2d(PI * 1.75) + offset, 6.0);   
    
    color = vec3(pct);
    fragColor = vec4(color, 1.);
}

void main()
{
    vec4 outCol = vec4(0.0);
    mainImage(outCol, gl_FragCoord.xy);
#ifdef GL_ES
    gl_FragColor = outCol;
#else
    fragColor = outCol;
#endif
}