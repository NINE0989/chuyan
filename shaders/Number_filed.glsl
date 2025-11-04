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

// Tunable uniforms (replaces original consts so host can adjust at runtime)
uniform float uPI; // optional override; if zero, we'll set in shader
uniform float uRadius1;
uniform float uRadius2;
uniform float uSpeed1;
uniform float uSpeed2;
uniform float uSpeed3;

uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;
uniform sampler2D iChannel1;
uniform sampler2D iChannel2;

out vec4 fragColor;

// fallback defaults if uniforms are zero/unset
float PI_f() { return (uPI == 0.0) ? radians(180.0) : uPI; }
float Radius1_f() { return (uRadius1 == 0.0) ? 15.0 : uRadius1; }
float Radius2_f() { return (uRadius2 == 0.0) ? 5.0 : uRadius2; }
float Speed1_f() { return (uSpeed1 == 0.0) ? 1.0/50.0 : uSpeed1; }
float Speed2_f() { return (uSpeed2 == 0.0) ? 5.0 : uSpeed2; }
float Speed3_f() { return (uSpeed3 == 0.0) ? 0.0 : uSpeed3; }

// Include code borrowed from IQ

float sdTorus( vec3 p, vec2 t )
{
  vec2 q = vec2(length(p.xz)-t.x,p.y);
  return length(q)-t.y;
}


float map(in vec3 pos)
{
    vec3 q = pos;
    float d = -sdTorus( q.xzy, vec2(Radius1_f(),Radius2_f()) ) ;
    
    return d;
}

vec3 calcNormal( in vec3 pos )
{
    const float ep = 0.0001;
    vec2 e = vec2(1.0,-1.0)*0.5773;
    return normalize( e.xyy*map( pos + e.xyy*ep ) + 
                      e.yyx*map( pos + e.yyx*ep ) + 
                      e.yxy*map( pos + e.yxy*ep ) + 
                      e.xxx*map( pos + e.xxx*ep ) );
}



vec3 applyFog( in vec3  rgb, in float distance, in float strength )
{
    float fogAmount = 1.0 - exp( -distance*strength );
    vec3  fogColor  = vec3(0.0);
    return mix( rgb, fogColor, fogAmount );
}

void mainVR( out vec4 fragColor_local, in vec2 fragCoord, in vec3 ro, in vec3 rd )
{
    float R1 = Radius1_f();
    ro += vec3(0.0,R1,0);
    rd = rd.zxy;
    
    float time = iTime*Speed1_f();
    
    mat3 m=mat3(
        1.0,0.0,0.0,
        0.0,cos(time),sin(time),
        0.0,-sin(time),cos(time));
    
    rd = m*rd;

    float t = 0.5;
    for( int i=0; i<64; i++ )
    {
        vec3 p = ro + t*rd;
        float h = map(p);
        if( abs(h)<0.001 ) break;
        t += h;
    }

    vec3 p = ro + t*rd;
    float PI = PI_f();
    float theta = (atan(p.x,p.y)/PI + 1.0)*150.0 - iTime*Speed2_f();
    int tata = int(theta);
    //float incPhi = (tata&1)==0?iTime*Speed3:-iTime*Speed3;
    float phi   = (atan(length(p.xy)-R1,p.z)/PI + 1.0)*30.0; // + incPhi;
    float itheta = floor(theta);
    float iphi   = floor(phi);
    float ftheta = theta - itheta;
    float fphi   = phi - iphi;
    ftheta = clamp(ftheta * 0.6 + 0.2,0.0,1.0);
    fphi = clamp(fphi * 0.8 + 0.1,0.0,1.0);
    vec4  rand = TEX( iChannel1, vec2(iphi,itheta)*0.386557);
    float digit = floor(rand.r * 10.0);
    float freq = TEX( iChannel2, vec2(rand.g,0.25)*0.386557).r;


    digit = mod(digit + (freq > 0.5?1.0:0.0),10.0);

    vec3 color = vec3(smoothstep( 0.51,0.49,TEX( iChannel0, vec2((1.0-ftheta+digit)/16.0,(fphi+12.0)/16.0)).a));

    vec3 norm = calcNormal(p);
    color = applyFog(color,t,0.2*((norm.z*norm.z)/3.0 + 0.1 + clamp(norm.y*0.4,0.0,1.0))); // Hack to dim pixels with lots of aliasing
    fragColor_local = vec4(color,1.0);
}

void mainImage( out vec4 fragColor_local, in vec2 fragCoord )
{
    vec3 tot = vec3(0);
#ifdef AA
    vec2 rook[4];
    rook[0] = vec2( 1./8., 3./8.);
    rook[1] = vec2( 3./8.,-1./8.);
    rook[2] = vec2(-1./8.,-3./8.);
    rook[3] = vec2(-3./8., 1./8.);
    for( int n=0; n<4; n++ )
    {
        // pixel coordinates
        vec2 o = rook[n];
        vec2 p = (-iResolution.xy + 2.0*(fragCoord+o))/iResolution.y;
#else //AA    
        vec2 p = (-iResolution.xy + 2.0*fragCoord)/iResolution.y;
#endif // AA
 
        vec3 ro = vec3(0);
        vec3 rd = normalize(vec3(p,-1.0));
        
        vec4 color;
        mainVR( color,fragCoord,ro,rd );
        tot += color.xyz;
        

#ifdef AA
    }
    tot /= 4.;
#endif //AA

    fragColor_local = vec4( tot, 1.0 );
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
