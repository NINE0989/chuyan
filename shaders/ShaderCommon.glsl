// Common shader uniforms shared by project shaders.
// Do NOT include a #version directive here; keep #version in each shader source.

uniform vec3 iResolution;
uniform float iTime;
uniform float iTimeDelta;
uniform int iFrame;
uniform float iFrameRate;
uniform vec4 iMouse;
uniform vec4 iDate;
uniform float iSampleRate;
uniform sampler2D iChannel0;
out vec4 fragColor;
// audio-related uniforms
uniform float iAudioPeak;
uniform float iAudioRMS;
uniform float iAudioCentroid;
uniform float iAudioFlux;
uniform float iAudioRolloff;
uniform vec4 iAudioBands; // low, low-mid, mid-high, high