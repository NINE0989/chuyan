// Target: desktop (#version 330 core)
#version 330 core

// Created by anatole duprat - XT95/2013 (adapted)
// License Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported License.

// Desktop GLSL adapter + audio-reactive additions

#ifdef GL_ES
precision mediump float;
#endif

// helper TEX macro (keeps compatibility with older shadertoy macros)
#ifndef TEX
#ifdef GL_ES
#define TEX(s, uv) texture2D(s, uv)
#else
#define TEX(s, uv) texture(s, uv)
#endif
#endif

uniform vec3 iResolution;
uniform float iTime;
uniform vec4 iMouse;
uniform sampler2D iChannel0; // audio spectrum (1D horizontally, y=0)

#ifndef GL_ES
out vec4 fragColor;
#endif

#define PI 3.14159265359

// ------------------ original noise (kept) ------------------
float noise(vec3 p) //Thx to Las^Mercury
{
	vec3 i = floor(p);
	vec4 a = dot(i, vec3(1.0, 57.0, 21.0)) + vec4(0.0, 57.0, 21.0, 78.0);
	vec3 f = cos((p - i) * PI) * (-0.5) + 0.5;
	a = mix(sin(cos(a) * a), sin(cos(1.0 + a) * (1.0 + a)), f.x);
	a.xy = mix(a.xz, a.yw, f.y);
	return mix(a.x, a.y, f.z);
}

float sphere(vec3 p, vec4 spr)
{
	return length(spr.xyz - p) - spr.w;
}

// ------------------ audio sampling helpers ------------------
const int BANDS = 64;

// NOTE: some GLSL drivers reject array parameters in function signatures.
// To maximize compatibility we perform band sampling and analysis inline in mainImage.

// ------------------ flame model ------------------
// flame intensity and motion controlled by audio:
// - rms (volume) -> scales noise amplitude and sway
// - centroid (frequency centroid) -> controls color temperature and fast flicker

float flame(vec3 p, float rms, float spectralCentroid)
{
	// base signed distance to ellipsoid flame body
	float d = sphere(p * vec3(1.0, 0.5, 1.0), vec4(0.0, -1.0, 0.0, 1.0));

	// audio-influenced parameters
	float amp = 1.0 + rms * 6.0; // louder -> bigger noise amplitude
	float speed = 1.0 + spectralCentroid * 3.0; // higher freq -> faster flicker
	float verticalInfluence = clamp(p.y * 0.8 + 0.2, 0.0, 1.0);

	// noise terms
	float n1 = noise(p + vec3(0.0, iTime * 2.0 * speed, 0.0));
	float n2 = noise(p * 3.0 + vec3(0.0, iTime * 1.5 * speed, 0.0));
	float noiseTerm = (n1 + 0.5 * n2) * 0.25 * amp * verticalInfluence;

	// add frequency-dependent ripple: high freq -> more small-scale detail
	float freqDetail = pow(spectralCentroid, 0.5) * noise(p * (5.0 + spectralCentroid * 10.0)) * 0.06 * amp;

	return d + noiseTerm + freqDetail;
}

float scene(vec3 p, float rms, float spectralCentroid)
{
	return min(100.0 - length(p), abs(flame(p, rms, spectralCentroid)));
}

// raymarch returns hit point and glow amount
vec4 raymarch(vec3 org, vec3 dir, float rms, float spectralCentroid)
{
	float d = 0.0;
	float glow = 0.0;
	float eps = 0.02;
	vec3 p = org;
	bool glowed = false;

	// raymarch steps - increase steps when loud (bounded)
	int STEPS = 48;
	STEPS = int(clamp(float(STEPS) + rms * 40.0, 24.0, 96.0));

	for (int i = 0; i < STEPS; i++) {
	d = scene(p, rms, spectralCentroid) + eps;
		p += d * dir;
		if (d > eps) {
			if (flame(p, rms, spectralCentroid) < 0.0) glowed = true;
			if (glowed) glow = float(i) / float(STEPS);
		}
		// safety: if p goes very far, break
		if (length(p) > 200.0) break;
	}
	return vec4(p, glow);
}

// color mapping: centroid controls color temperature (higher -> bluer/whiter)
vec3 flameColor(float v, float spectralCentroid)
{
	// base warm orange
	vec3 warm = vec3(1.0, 0.45, 0.12);
	// high-temp (whitish-blue-ish) — lean toward white with slight blue
	vec3 hot = vec3(1.0, 0.95, 0.8);
	vec3 cool = vec3(0.9, 0.6, 0.2);
	// centroid 0..1: 0 -> warm, 1 -> hotter (whiter)
	float t = pow(spectralCentroid, 0.8);
	vec3 base = mix(warm, hot, t);
	// modulate by vertical coordinate v (height) to get variation
	return mix(base * 0.8, vec3(1.0), clamp(v * 0.02 + 0.2, 0.0, 1.0));
}

void mainImage(out vec4 fragCol, in vec2 fragCoord)
{
	// sample audio (inline for GLSL compatibility)
	float bands[BANDS];
	float power = 0.0;
	float sumFreq = 0.0;
	float totalAmp = 0.0;
	for (int i = 0; i < BANDS; i++) {
		float u = (float(i) + 0.5) / float(BANDS);
		float bv = TEX(iChannel0, vec2(u, 0.0)).r;
		bands[i] = bv;
		power += bv * bv;
		sumFreq += bv * (float(i) + 0.5);
		totalAmp += bv;
	}
	float rms = sqrt(power / float(BANDS) + 1e-8);
	float spectralCentroid = 0.0;
	if (totalAmp > 1e-6) spectralCentroid = (sumFreq / totalAmp) / float(BANDS - 1);

	// screen coords
	vec2 v = -1.0 + 2.0 * fragCoord.xy / iResolution.xy;
	v.x *= iResolution.x / iResolution.y;

	vec3 org = vec3(0.0, -2.0, 4.0);
	vec3 dir = normalize(vec3(v.x * 1.6, -v.y, -1.5));

	vec4 p = raymarch(org, dir, rms, spectralCentroid);
	float glow = p.w;

	// compute color using flameColor and height of hit point
	float heightFactor = clamp(p.y * 0.02 + 0.4, 0.0, 1.0);
	vec3 baseCol = flameColor(p.y, spectralCentroid);
	vec3 col = baseCol * (0.6 + heightFactor * 0.8);

	// make glow responsive to volume
	float glowAmp = 1.0 + rms * 3.0;
	fragCol = mix(vec4(0.0), vec4(col, 1.0), pow(glow * 2.0 * glowAmp, 4.0));
}

void main()
{
	vec4 color;
	mainImage(color, gl_FragCoord.xy);
#ifdef GL_ES
	gl_FragColor = color;
#else
	fragColor = color;
#endif
}

