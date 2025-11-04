#version 330 core

#ifdef GL_ES
precision mediump float;
#endif

// Keep existing feature flags
#define FFT_GAIN 2.5
//#define FFT_CONTRAST_VIEW

// Post-processing options
const float Piano_height = .15;
const float Intensity_height = .03;

//Post-processing options
const float Sharpness = 25.;

//Blue Key : 261.6 Hz (Key 40,                Middle C)
//Red  Key : 440   Hz (Key 49, First  A after Middle C)

const float ATone     = 0.0370;       //so 0.0370 texture space is 440Hz(found by trial-and-error)
const float ATone2     = 0.0390;       //so 0.0370 texture space is 440Hz(found by trial-and-error)
const float ATone3     = 0.0420;       //so 0.0370 texture space is 440Hz(found by trial-and-error)

const float Semitone  = 1.05946309436; //12 notes between an octave, octave is 2, so a semitone is 2^(1/12)

// TEX macro for portability
#ifndef TEX
#ifdef GL_ES
#define TEX(s, uv) texture2D(s, uv)
#else
#define TEX(s, uv) texture(s, uv)
#endif
#endif

uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0; // audio FFT / spectrum
uniform sampler2D iChannel1; // optional background or lookup

out vec4 fragColor;

float KeyToFrequency(int n){
    return pow(Semitone,float(n-49))*440.;
}

float FrequencyToTexture(float Frequency){
    if (Frequency>=300.0) {
        return Frequency/440.*ATone;
    } else if ((Frequency>=130.0) && (Frequency<300.0)) {
        return Frequency/440.*ATone2;
    } else{
        return Frequency/440.*ATone3;
    }
}

vec3 hsv2rgb_smooth( in vec3 c )
{
    vec3 rgb = clamp( abs(mod(c.x*6.0+vec3(0.0,4.0,2.0),6.0)-3.0)-1.0, 0.0, 1.0 );

    rgb = rgb*rgb*(3.0-2.0*rgb); // cubic smoothing    

    return c.z * mix( vec3(1.0), rgb, c.y);
}

mat3 get_formants(int key){
    float Frequency = KeyToFrequency(key);
    float Frequency_up1 = KeyToFrequency(key+1);
    float Frequency_up2 = KeyToFrequency(key+2);
    float Frequency_down1 = KeyToFrequency(key-1);
    float Frequency_down2 = KeyToFrequency(key-2);
    float Frequency_over1 = KeyToFrequency(key+12);
    float Frequency_over2 = KeyToFrequency(key+17);
    float Frequency_lower1 = KeyToFrequency(key-12);

    float Amplitude = TEX(iChannel0,vec2(FrequencyToTexture(Frequency),.05)).x;
    float Amplitude_up1 = TEX(iChannel0,vec2(FrequencyToTexture(Frequency_up1),.05)).x;
    float Amplitude_up2 = TEX(iChannel0,vec2(FrequencyToTexture(Frequency_up2),.05)).x;
    float Amplitude_down1 = TEX(iChannel0,vec2(FrequencyToTexture(Frequency_down1),.05)).x;
    float Amplitude_down2 = TEX(iChannel0,vec2(FrequencyToTexture(Frequency_down2),.05)).x;
    float Amplitude_over1 = TEX(iChannel0,vec2(FrequencyToTexture(Frequency_over1),.05)).x;
    float Amplitude_over2 = TEX(iChannel0,vec2(FrequencyToTexture(Frequency_over2),.05)).x;
    float Amplitude_lower1 = TEX(iChannel0,vec2(FrequencyToTexture(Frequency_lower1),.05)).x;

    float Perceived = log(1. + Amplitude*Amplitude*1.)*.3;
    float Perceived_up1 = log(1. + Amplitude_up1*Amplitude_up1*1.)*.3;
    float Perceived_up2 = log(1. + Amplitude_up2*Amplitude_up2*1.)*.3;
    float Perceived_down1 = log(1. + Amplitude_down1*Amplitude_down1*1.)*.3;
    float Perceived_down2 = log(1. + Amplitude_down2*Amplitude_down2*1.)*.3;
    float Perceived_over1 = log(1. + Amplitude_over1*Amplitude_over1*1.)*.3;
    float Perceived_over2 = log(1. + Amplitude_over2*Amplitude_over2*1.)*.3; 
    float Perceived_lower1 = log(1. + Amplitude_lower1*Amplitude_lower1*1.)*.3; 
    return mat3(vec3(Amplitude, Perceived, Perceived_up1),
                vec3(Perceived_up2, Perceived_over1,Perceived_over2),
                vec3(Perceived_down1, Perceived_down2, Perceived_lower1));
}

void mainImage( out vec4 fragColor_out, in vec2 fragCoord ){
        vec3 Color = vec3(0.0);
        vec3 color2 = vec3(0.0);
        vec2 Scaled     = fragCoord.xy/iResolution.xy;
    #ifdef RIVER_BACKGROUND
    Color = TEX(iChannel1,Scaled.xy).rgb;
    #else
    // Use pure black background when RIVER_BACKGROUND is not defined
    Color = vec3(0.0);
    #endif
    //Piano
        int   Key       = 1+int(Scaled.x*87.);//1 to 88 (full piano)
        int   Note      = Key%12;//A to G(Octave)

    //Sound

    //Music Visualization
      mat3 formants = get_formants(Key);
      float amp = formants[0].x;
      float org = formants[0].y;
      float up1 = formants[0].z;
      float up2 = formants[1].x;
      float over1 = formants[1].y;
      float over2 = formants[1].z;
      float down1 = formants[2].x;
      float down2 = formants[2].y;
      float lower1 = formants[2].z;
      
      vec3 amp3 = vec3(smoothstep(0.0,1.0,1.0-amp),0.75,0.75);
      float perceived_color = org*FFT_GAIN;
      color2 = 1.95*hsv2rgb_smooth((amp3))*smoothstep(0.01,0.,Scaled.y-Piano_height-perceived_color*0.85)-Intensity_height;
            
      
      float threshold = 1.0-0.75*cos(fragCoord.x*0.0075-0.75);
    //Piano Drawing
        bool second_filter = false;
        bool octave_filter = false;
        if (Key>=40){
            second_filter =(org>up1+org*0.05*Scaled.x/4.0)&&(org>down1+org*0.05*Scaled.x/4.0)&&(org>0.05);
        } else {
            second_filter =(org>up1)&&(org>down1);
        }
        if (Key>=60){
            octave_filter =(org>over1+org*0.8*Scaled.x/4.0)&&(org>over2+org*0.8*Scaled.x/4.0)&&(org>lower1+org*0.8*Scaled.x/4.0)&&(over1>0.06);
        } else if (Key>=40){
            octave_filter =(org>over1+org*0.2*Scaled.x/4.0)&&(org>over2+org*0.2*Scaled.x/4.0)&&(org>lower1+org*0.2*Scaled.x/4.0)&&(over1>0.06);
        } else {
            octave_filter = (org>over1+org*0.1*Scaled.x/4.0)&&(org>over2+org*0.1*Scaled.x/4.0)&&(over1>0.04);
        }
        if(Scaled.y<Piano_height){
            //white keys
            Color = vec3(1);

            //black keys
            if(Note==0||Note==2||Note==5||Note==7||Note==10){
                if ((Scaled.y<Piano_height)&&(Scaled.y>Piano_height/4.0)){
                    Color = vec3(.1);
                } else {
                    Color = vec3(1.);
                }
            }

            //special keys
            if (second_filter && octave_filter) {
                vec3 rgb_color = hsv2rgb_smooth(vec3(amp,1.0,amp));
                //Color = rgb_color;
                if(Note==0||Note==2||Note==5||Note==7||Note==10){
                    if ((Scaled.y<Piano_height)&&(Scaled.y>Piano_height/4.0)){
                        Color = rgb_color;
                    } else {
                        Color = vec3(1.);
                    }
                } else {
                    Color = rgb_color;
                }
            }
        } else if (Scaled.y<Intensity_height+Piano_height){
            if (second_filter && octave_filter) {
                Color = vec3(.5, .5, 1.0);
            } else {
                Color = vec3(.2, .2, .7);
            }
        } else {
            if (second_filter && octave_filter){
                Color = max(Color,color2);
            } else {
                #ifdef FFT_CONTRAST_VIEW
                Color = max(Color,0.5*color2);
                #else
                Color = max(Color,color2);
                #endif
            }
        }

    fragColor_out = vec4(Color,1);
}

void main(){
    vec4 color = vec4(0.0);
    mainImage(color, gl_FragCoord.xy);
#ifdef GL_ES
    gl_FragColor = color;
#else
    fragColor = color;
#endif
}
