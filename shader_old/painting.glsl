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
out vec4 fragColor;

#define S smoothstep

//noise funtion abstract from https://www.shadertoy.com/view/4sc3z2
vec2 hash22(vec2 p)
{
    p = vec2( dot(p,vec2(127.1,311.7)),
			  dot(p,vec2(269.5,183.3)));
    
    //return normalize(-1.0 + 2.0 * fract(sin(p)*43758.5453123));
    return -1.0 + 2.0 * fract(sin(p)*43758.5453123);
}

float simplex_noise(vec2 p)
{
    const float K1 = 0.366025404; // (sqrt(3)-1)/2;
    const float K2 = 0.211324865; // (3-sqrt(3))/6;
    
    vec2 i = floor(p + (p.x + p.y) * K1);
    
    vec2 a = p - (i - (i.x + i.y) * K2);
    vec2 o = (a.x < a.y) ? vec2(0.0, 1.0) : vec2(1.0, 0.0);
    vec2 b = a - (o - K2);
    vec2 c = a - (1.0 - 2.0 * K2);
    
    vec3 h = max(0.5 - vec3(dot(a, a), dot(b, b), dot(c, c)), 0.0);
    vec3 n = h * h * h * h * vec3(dot(a, hash22(i)), dot(b, hash22(i + o)), dot(c, hash22(i + 1.0)));
    
    return dot(vec3(70.0, 70.0, 70.0), n);
}

float noise_sum(vec2 p)
{
    float f = 0.0;
    p = p * 4.0;
    f += 1.0000 * simplex_noise(p); p = 2.0 * p;
    f += 0.5000 * simplex_noise(p); p = 2.0 * p;
	f += 0.2500 * simplex_noise(p); p = 2.0 * p;
	f += 0.1250 * simplex_noise(p); p = 2.0 * p;
	f += 0.0625 * simplex_noise(p); p = 2.0 * p;
    
    return f;
}



vec2 drawMountain(vec2 uv, float f, float d)
{
    float Side = uv.y + noise_sum(vec2(uv.x, mix(uv.y,0.,uv.y))*f)*0.1;
    float detal = noise_sum(vec2(uv.x, uv.y)*8.)*0.005;
    Side += detal;

    float Mountain = S(0.48, 0.49, Side);
    float fog = S(d, noise_sum(vec2(uv.x+iTime*0.06, uv.y)*0.2)*0.2, Side);
    
    return clamp(vec2(Side+fog, Mountain),0.,1.);
}

float drawSun(vec2 uv)
{
    vec2 u = uv;
    u -= 0.5;
    u.x *= iResolution.x/iResolution.y;  
    
    float Sun = S(0.09, 0.1, length(vec2(u.x-.5, u.y-.3)));
    
    float fog = S(0.7,noise_sum(vec2(uv.x+iTime*0.001, uv.y)*2.)*0.05,u.y)*1.4;
    
    return clamp(Sun+fog,0.,1.);
}

float drawBird(vec2 uv)
{
    uv = (uv-.5)*20.;
    uv.x -= uv.y;

    uv.y = uv.y+.45+(sin((iTime*0.5-abs(uv.x))*3.)-1.)*abs(uv.x)*0.5;
    
    float S1 = smoothstep(0.45,0.4,length(uv));
    
    uv.y += .1;
    float S2 = smoothstep(0.5,0.45,length(uv));
    
    float S = S1-S2;
    return S;
}

void mainImage( out vec4 fragColor_out, in vec2 fragCoord )
{
    vec2 uv = fragCoord/iResolution.xy;

    float t = iTime*0.5;

    vec3 c = vec3(1.);


    // preserve sun mask for later (keep red/orange parts unchanged)
    float Sun = drawSun(uv);
    c = mix(vec3(1.,0.2,0.0), c, Sun);  
    
    float Bird = drawBird(vec2(uv.x-.15,uv.y-.4));
    c = mix(c, vec3(1.)*.65, Bird);
    
    uv.y -= .2;
    uv.x += t*0.001;
    vec2 Mountain1 = drawMountain(uv, .4, 1.);
    c = mix(vec3(Mountain1.r), c, Mountain1.g);
    
    uv.y += .1;
    uv.x += 1.;
    uv.x += t*0.005;
    Mountain1 = drawMountain(uv, .3, .8);
    c = mix(vec3(Mountain1.r), c, Mountain1.g);
    
    uv.y += .1;
    uv.x += 2.42;
    uv.x += t*0.01;
    Mountain1 = drawMountain(uv, .2, 0.6);
    c = mix(vec3(Mountain1.r), c, Mountain1.g);
    
    uv.y += .1;
    uv.x += 12.84;
    uv.x += t*0.05;
    Mountain1 = drawMountain(uv, .2, 0.4);
    c = mix(vec3(Mountain1.r)-0.01, c, Mountain1.g);
 
       
    vec3 col = vec3(c);

    // If this pixel belongs to the sun (red/orange), keep it unchanged.
    // Otherwise convert to grayscale and invert (黑白颠倒 -> inverted luminance).
    // Use a higher sun threshold and a color-based test so fog doesn't mark everything as sun.
    float sunThreshold = 0.15;
    bool redColor = (col.r > 0.45) && (col.r > 1.2 * max(col.g, col.b));
    bool sunMask = (Sun > sunThreshold) || redColor;
    // 全画面二值阈值反转：高于阈值的像素变黑，低于阈值的像素变白（包括太阳）
    float lum = dot(col, vec3(0.299, 0.587, 0.114));
    float t = 0.5; // 阈值，可调整为 0.4/0.6 等
    float outv = (lum > t) ? 0.0 : 1.0; // 亮的变黑(0)，暗的变白(1)
    fragColor_out = vec4(vec3(outv), 1.0);
}

void main() {
    vec4 color = vec4(0.0);
    mainImage(color, gl_FragCoord.xy);
#ifdef GL_ES
    gl_FragColor = color;
#else
    fragColor = color;
#endif
}