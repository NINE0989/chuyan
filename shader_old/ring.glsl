// based off https://www.shadertoy.com/view/MdVyRK

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

#define SEED 0.12345679

#define TRI 64.0
#define SP 0.5
#define COLOR vec3(0.0, 0.0, 0.0)

#define PI 3.14159265359
#define TWO_PI 6.28318530718
#define HALFPI 1.5707963268

float rand (vec2 p) {
    return fract(sin(dot(p.xy,
                         vec2(6.8245,7.1248)))*
        9.1283);
}

float tri(vec2 uv, vec2 p, float s){
    vec2 v = uv;
    v -= p;
    v /= max(s, 0.01);
    
	float a = atan(v.x, v.y) + PI;
    float r = TWO_PI / 3.0;
    
    float t = cos(floor(0.5 + a / r) * r - a) * length(v);
    
    return smoothstep(0.4, 0.41, t);
}

float yPos(float i){
    vec2 p = vec2(SEED, i);
    
    float r = rand(p);
    return fract(iTime * SP + r);
}

float xPos(float i, float t){
    vec2 p = vec2(i, t - iTime * SP);
    return rand(p) + .375;
}

vec3 triCol(float i, float t){
    vec3 col = COLOR;
    float r = xPos(i + 1.0, t);
    col *= mix(0.9, 1.1, r);
    return col;
}

float atan2(float y, float x) {
 	if(x>0.)return atan(y/x);
    if(x==0.)if(y>0.)return HALFPI;else return -HALFPI;
    if(y<0.)return atan(y/x)-PI;return atan(y/x)+PI;
}
float atan2(vec2 v){return atan2(v.y,v.x);}
float steq(float x,float a,float b){return step(a,x)*step(x,b);}
vec2 cub_(float t,vec2 a,vec2 b){
    float ct=1.-t;
    return 3.*ct*ct*t*a+3.*ct*t*t*b+t*t*t;
}
float cub(float x,vec2 a,vec2 b){
    vec2 it=vec2(0.,1.);
    for (int i=0;i<7;i++) {
        float pos=(it.x+it.y)/2.;
        vec2 r=cub_(pos,a,b);
        if (r.x>x){
            it.y=pos;
        }else{
            it.x=pos;
        }
    }
    return cub_((it.x+it.y)/2.,a,b).y;
}
float isine(float t){return -1.*cos(t*HALFPI)+1.;}
float osine(float t){return sin(t*HALFPI);}
float iquad(float t){return t*t;}
float oc(float t){t=t-1.;return t*t*t+1.;}
vec2 oc(vec2 v){return vec2(oc(v.x),oc(v.y));}
float icirc(float t){return -1.*(sqrt(1.-t*t)-1.);}
vec3 spin(vec3 col_,vec2 fc) {
    vec3 col=col_;
    float a=mod(degrees(atan2(fc-iResolution.xy/2.-.5)),360.);
    float b=mod(iTime*100.,360.);
    float s=25.;
    float mi=mod(b-s,360.);
    float ma=mod(b+s,360.);
    float d=abs(b-a);
    if(d>180.)d=a<b?a-b+360.:b+360.-a;
    if((a>mi||(mi>ma&&a<ma))&&(a<ma||mi>ma))col+=1.-iquad(d/s);
    return col;
}
float mb(){
    return clamp(TEX(iChannel0,vec2(0.02,0.2)),0.,1.).x;
}
vec3 barz(float d,vec2 fc,float off,float sp) {
    float a=degrees(atan2(fc-iResolution.xy/2.-.5))/180.+1.;
    a=mod(a+iTime/sp+off+mb()/3.,2.);
    a-=1.;
    if(a<0.)a=-a+0.01;
    float m=mod(a,.025);
    if(m<0.01*(1.+d*.6))return vec3(0.);
    a-=m;
    float v=clamp(TEX(iChannel0,vec2(a,0.1)).x,0.,1.);
    if (v>d) return vec3(1.);
    return vec3(0.);
}
float osu_excdot(vec2 uv) {
    const float ds=.07;
    vec2 exc=oc((ds*2.-abs(uv))/ds/2.)*.04;
    return steq(uv.x,-ds-exc.y,ds+exc.y)*steq(uv.y,-ds-exc.x,ds+exc.x);
}
float osu_excbody(vec2 uv) {
    float e=oc((.2-abs(uv.x))/.2)*.04;
    float ew=(uv.y+.15)*.01;
    return steq(uv.x,-.1-ew,.1+ew)*steq(uv.y,-.2-e,.2+e);
}
float osu_u(vec2 uv) {
    float r=1.18181818;
    uv+=vec2(.5/r,.5);
    uv.x*=r;
    uv.y=1.-uv.y;
    float c=1.;
    c-=steq(uv.x,.31,.69)*steq(uv.y,.0,.765-.245*cub(1.-(uv.x-.31)/.38,vec2(.4,-.116),vec2(.994,-.27)));
    float b=.48*cub(1.-uv.x,vec2(.252,-.164),vec2(1.038,-.52));
    return c*steq(uv.x,0.,1.)*steq(uv.y,.02*isine(abs(mod(uv.x,.69)-.155)/.31),.933-b);
}
float osu_sunpy(vec2 uv) {
    float r=1.397928994;
    uv+=vec2(.5/r,.5);
    uv.x*=r;
    if (steq(uv.x,0.,1.)*steq(uv.y,0.,1.)==0.) {
        return 0.;
    }
    uv.y=1.-uv.y;
    float c=1.;
    c-=steq(uv.x,.0,.035+.515*icirc((.3-uv.y)/.3))*steq(uv.y,.0,.3);
    c-=steq(uv.x,.55,1.)*steq(uv.y,.0,.055*isine(clamp((uv.x-.55)/.4,.0,1.)));
    c-=steq(uv.x,.95-.07*isine(clamp((uv.y-.055)/.192/*.195*/,.0,1.)),1.)*steq(uv.y,.055,.28);
    c-=steq(uv.x,.59,.88)*steq(uv.y,.2+.045*isine((uv.x-.59)/.29),.28);
    c-=steq(uv.x,.4+.19*icirc(1.-(uv.y-.2)/.08),.59)*steq(uv.y,.2,.28);
    c-=steq(uv.x,.4+.6*cub((uv.y-.28)/.395,vec2(.408,.011),vec2(.104,1.014)),1.)*steq(uv.y,.28,.675);
    c-=steq(uv.x,1.-.585*icirc((uv.y-.675)/.325),1.)*steq(uv.y,.675,1.);
    c-=steq(uv.x,.0,.415)*steq(uv.y,.94+.06*osine(uv.x/.415),1.);
    c-=steq(uv.x,.0,.085*isine(1.-(uv.y-.75)/.19))*steq(uv.y,.75,.94);
    c-=steq(uv.x,.0,.4)*steq(uv.y,.69,.75+.045*osine(clamp((uv.x-.085)/.315,0.,1.)));
    c-=steq(uv.x,.4,.645)*steq(uv.y,.69,.795-.105*icirc((uv.x-.4)/.245));
    c-=steq(uv.x,.0,.035+.61*cub((uv.y-.3)/.39,vec2(.891,-.042),vec2(.592,.977)))*steq(uv.y,.3,.69);
    return c;
}
float osu_o(vec2 uv) {
    float r=1.091666;
    uv.x*=r;
    uv.y=1.-abs(uv.y);
    uv.x=abs(uv.x);
    float te=cub(uv.x,vec2(.667,.013),vec2(.988,.366));
    float be=1.-cub(clamp(uv.x/.402,0.,1.),vec2(.783,.035),vec2(.915,.241));
    return steq(uv.x,0.,1.)*steq(uv.y,0.+te,1.-.595*be);
}
float osu(vec2 uv) {
    float col=0.;
    col+=osu_excdot((uv-vec2(.806,-.192))*1.4);
    col+=osu_excbody((uv-vec2(.806,.23))*vec2(1.35,.9));
    col+=osu_u((uv-vec2(.379,.0))*1.7);
    col+=osu_sunpy((uv-vec2(-.134,.0))*1.7);
    col+=osu_o((uv-vec2(-.667,.0))*3.4);
    return col;
}
void mainImage(out vec4 fragColor_out, in vec2 fragCoord){
    float s = 1.2 - TEX(iChannel0, vec2(0.52,0.2)).x * .4;
    vec2 uv = fragCoord/iResolution.xy * s-(s-1.)*.5;
    uv.x *= iResolution.x/iResolution.y;
    
    vec3 col = COLOR;
    
    // Generate all dem triangles
    for (float i = TRI; i > 0.0; i--){
        float id = i / TRI;
        float y = yPos(id);
        float x = xPos(id, y);
        float s = min(0.89, max(0.071, id * 0.5));
        float shad = tri(
            uv,
            vec2(x, mix(-s, 1.0 + s / 2.0, y)),
            s
        );
        
        if (shad < 0.1)
        	col = triCol(id, y) * (1.0 - shad);
    }
    
    // Set background mask
    vec2 mid=vec2(.5*iResolution.x/iResolution.y,.5);
    float dist = distance(uv,mid);
    if (dist > 0.4) {
        col = vec3(0.0);
        if (dist<0.65){
            float sp=3.;
            float el=.1+.2*mb();
            float d=(dist-.4)/.25;
          	col+=barz(d,fragCoord,0.,sp);
          	col+=barz(d,fragCoord,.5,sp);
          	col+=barz(d,fragCoord,1.,sp);
          	col+=barz(d,fragCoord,1.5,sp);
            col*=el;
            col.x*=.75;
            col.y*=.75;
        }
    } else
        if(dist>0.32&&dist<0.37)col=spin(col,fragCoord);
    
    // Make circle logo shadow
    float dist_shad = distance(uv, vec2(0.5 * iResolution.x / iResolution.y, 0.49));
    float l_shad = abs(dist_shad - 0.4);
    col *= mix(0.3, 1.0, min(1.0, l_shad * 30.0));
    
    // Make circle logo
    float l = abs(dist - 0.4);
    col += vec3(smoothstep(0.96, 0.97, 1.0 - l));
    
    // osu logo removed
    // if(dist<0.3) col+=vec3(osu((uv-mid)/.3));

    // Replace center transparency with a vinyl-record-like graphic
    if (dist < 0.32) {
        // normalized radius within record (0 = center, 1 = edge)
        float rnorm = dist / 0.32;

        // base vinyl color (very dark)
        vec3 vinyl = vec3(0.03, 0.03, 0.035);

        // Grooves: concentric rings produced by fract of scaled distance
        float grooveFreq = 260.0; // number of grooves (higher -> tighter)
        float g = abs(fract(dist * grooveFreq) - 0.5);
        float grooveMask = smoothstep(0.0, 0.006, g);

        // Slight radial falloff to simulate rim shading
        float rim = smoothstep(0.32, 0.28, dist) * 0.25;

        vec3 grooveColor = mix(vinyl * 0.7, vinyl * 1.1, grooveMask);

        // small animated specular stripe for realism (subtle)
        float ang = atan2(uv - mid);
        float spec = 0.02 * (0.5 + 0.5 * sin(ang * 6.0 + iTime * 2.0));

        // label in the center
        float labelR = 0.08;
        vec3 labelColor = vec3(0.85, 0.15, 0.12);

        if (dist < labelR) {
            // draw label with subtle radial vignette
            float labFade = smoothstep(labelR, labelR - 0.02, dist);
            col = mix(labelColor, vinyl * 0.2, labFade);
        } else {
            col = grooveColor + vec3(spec) - rim;
        }
    }

    fragColor_out = vec4(col, 1.0);
}

void main() {
    vec4 color = vec4(0.0);
    mainImage(color, gl_FragCoord.xy);
#ifdef GL_ES
    gl_FragColor = color;
#else
    // Write to the project's expected output (fragColor) provided by ShaderCommon.glsl
    fragColor = color;
    // (fragColor is the output expected by the host)
#endif
}