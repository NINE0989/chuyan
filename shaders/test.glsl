// Simple example fragment shader (ShaderToy-like uniforms)
// Save other shaders into the `shaders/` folder and load them with the viewer.

#version 330 core
out vec4 fragColor;
uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0; // audio FFT in the red channel
in vec2 vUV;

void main(){
	vec2 uv = vUV;
	float x = uv.x;
	float fft = texture(iChannel0, vec2(x, 0.0)).r;
	float y = uv.y;
	vec3 col = vec3(0.0);
	// simple bar-like visualization
	float h = fft;
	float bar = smoothstep(h - 0.02, h, y) - smoothstep(h, h + 0.02, y);
	col = mix(vec3(0.05,0.05,0.12), vec3(0.2,0.7,1.0), bar + 0.2*fft);
	// add a time-based shimmer
	col += 0.05*sin(6.2831*(x*4.0 + iTime*0.5))*fft;
	fragColor = vec4(col, 1.0);
}
