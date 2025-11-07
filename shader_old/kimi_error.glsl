// Horizontal spectrum bars, audio-reactive, rgb-shift glow
#ifdef GL_ES
precision mediump float;
#endif

#ifndef TEX
#ifdef GL_ES
#define TEX(s,uv) texture2D(s,uv)
#else
#define TEX(s,uv) texture(s,uv)
#endif
#endif

// SAFE_MARGIN=0.05 FIT_MODE=INSIDE
#define SAFE_MARGIN 0.05
#define FIT_MODE_INSIDE 1
#define MAX_PARTICLES 128
#define PARTICLE_ITERATIONS 32
#define GLOW_INTENSITY 0.8
#define AUDIO_ATTACK 0.08   // seconds
#define AUDIO_DECAY  0.30   // seconds
#define AUDIO_SMOOTH_K 0.85 // fallback coeff

uniform vec3  iResolution;
uniform float iTime;
uniform sampler2D iChannel0;

#ifndef GL_ES
out vec4 fragColor; // desktop GL3.3
#endif

// ---------- utilities ----------
float hash12(vec2 p){
    return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);
}
vec2 rotate2D(vec2 p,float a){
    float c=cos(a),s=sin(a);
    return vec2(c*p.x-s*p.y,s*p.x+c*p.y);
}
float smoothAudio(float u){
    float s=0.0;
    for(int i=-3;i<=3;i++){
        float du=float(i)*0.003;
        s+=TEX(iChannel0,vec2(clamp(u+du,0.0,1.0),0.0)).r;
    }
    return s/7.0;
}
float envelope(float target,float prev){
    float a=(target>prev)?(1.0-exp(-1.0/(AUDIO_ATTACK*60.0))):(1.0-exp(-1.0/(AUDIO_DECAY*60.0)));
    return mix(prev,target,a);
}
vec3 rgbShift(vec3 c,vec2 uv,float amt){
    float r=TEX(iChannel0,vec2(uv.x+amt*0.01,0.0)).r;
    float g=TEX(iChannel0,vec2(uv.x,0.0)).r;
    float b=TEX(iChannel0,vec2(uv.x-amt*0.01,0.0)).r;
    return vec3(c.r*(0.7+0.3*r),c.g*(0.7+0.3*g),c.b*(0.7+0.3*b));
}
float shapeMask(vec2 p,float r){
    float d=length(p);
    return smoothstep(r,r-0.008,d);
}

// ---------- audio ----------
vec4 getAudio(){
    float bass=smoothAudio(0.08);
    float mid=smoothAudio(0.30);
    float treb=smoothAudio(0.70);
    float overall=smoothAudio(0.50);
    // non-persistent fallback smoothing (compatible with GLSL ES)
    float pbass=0.0, pmid=0.0, ptreb=0.0, poverall=0.0;
    bass = envelope(bass, pbass); pbass = bass;
    mid  = envelope(mid,  pmid);  pmid  = mid;
    treb = envelope(treb, ptreb); ptreb = treb;
    overall = envelope(overall, poverall); poverall = overall;
    return vec4(bass,mid,treb,overall);
}

// ---------- main ----------
void mainImage(out vec4 fragColor, in vec2 fragCoord){
    vec2 uv=(fragCoord-0.5*iResolution.xy)/min(iResolution.x,iResolution.y);
    // fit inside safe box
    uv*=1.0-2.0*SAFE_MARGIN;

    vec4 aud=getAudio();
    float bass=aud.x,mid=aud.y,treb=aud.z,overall=aud.w;

    vec3 col=vec3(0.0);

    // horizontal spectrum bars
    const int bars=64;
    for(int i=0;i<bars;i++){
        float u=float(i)/float(bars);
        float freq=smoothAudio(u);
        float h=freq*0.5;
        vec2 center=vec2(u*2.0-1.0,0.0);
        float halfH=h*0.5;
        vec2 local=uv-center;
        // vertical bar
        float insideX=step(abs(local.x),0.008);
        float insideY=step(abs(local.y),halfH);
        float m=insideX*insideY;
        // glow
        float glow=exp(-abs(local.y)/(halfH+0.001))*GLOW_INTENSITY*overall;
        vec3 barCol=0.5+0.5*cos(iTime*0.5+vec3(0,2,4)+u*6.0+freq*8.0);
        barCol=rgbShift(barCol,uv,overall*0.5);
        col+=m*barCol*glow;
    }

    // particles on top
    for(int j=0;j<PARTICLE_ITERATIONS;j++){
        float n=float(j)/float(PARTICLE_ITERATIONS);
        vec2 seed=vec2(n,iTime*0.1);
        vec2 pos=vec2(n*2.0-1.0,0.0);
        float size=0.003+treb*0.015;
        float phase=iTime*1.5+bass*4.0+n*6.28;
        pos.y+=sin(phase)*0.2*mid;
        pos=rotate2D(pos,iTime*0.2+n*3.0);
        vec2 p=uv-pos;
        float m=shapeMask(p,size);
        vec3 pCol=0.5+0.5*cos(phase+vec3(0,2,4));
        col+=m*pCol*overall*2.0;
    }

    // idle fallback
    float t=smoothstep(0.0,0.02,overall);
    vec3 idle=0.03*cos(iTime*0.2+uv.yx*3.0+vec3(0,1,2));
    col=mix(idle,col,t);

    fragColor=vec4(col,1.0);
}

void main(){
    vec4 outCol;
    mainImage(outCol, gl_FragCoord.xy);
#ifdef GL_ES
    gl_FragColor = outCol;
#else
    fragColor = outCol;
#endif
}