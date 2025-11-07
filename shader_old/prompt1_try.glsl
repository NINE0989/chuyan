// Ethereal audio nebula - rgbshift, radial scaling, fractal detail

#define MAX_PARTICLES 128
#define PARTICLE_ITERATIONS 32
#define NEBULA_OCTAVES 4
#define GLOW_INTENSITY 1.2

uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;

// Hash function
float hash(vec2 p) {
    return fract(sin(dot(p, vec2(27.619, 57.583))) * 43758.5453);
}

// Simplex noise derivative
vec2 noised(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    
    vec2 u = f * f * (3.0 - 2.0 * f);
    vec2 du = 6.0 * f * (1.0 - f);
    
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    
    float k0 = a;
    float k1 = b - a;
    float k2 = c - a;
    float k3 = a - b - c + d;
    
    float n = k0 + k1 * u.x + k2 * u.y + k3 * u.x * u.y;
    
    vec2 dn = vec2(k1 * du.x + k3 * u.y * du.x,
                   k2 * du.y + k3 * u.x * du.y);
    
    return vec2(n, dn.x + dn.y);
}

// Fractal noise for nebula
float fractalNoise(vec2 p, int octaves) {
    float total = 0.0;
    float amplitude = 0.5;
    float frequency = 1.0;
    
    for (int i = 0; i < octaves; i++) {
        total += noised(p * frequency).x * amplitude;
        amplitude *= 0.5;
        frequency *= 2.0;
    }
    
    return total;
}

// Get audio sample with safety
float getAudio(float u) {
    return texture(iChannel0, vec2(clamp(u, 0.0, 1.0), 0.0)).r;
}

// Get frequency band energy
float getBandEnergy(float start, float end, int samples) {
    float energy = 0.0;
    for (int i = 0; i < samples; i++) {
        float u = start + float(i) / float(samples) * (end - start);
        energy += getAudio(u);
    }
    return energy / float(samples);
}

// Get bass energy (u < 0.2)
float getBass() {
    return getBandEnergy(0.0, 0.2, 8);
}

// Get mid energy (0.2 ≤ u ≤ 0.5)
float getMid() {
    return getBandEnergy(0.2, 0.5, 12);
}

// Get treble energy (u > 0.5)
float getTreble() {
    return getBandEnergy(0.5, 1.0, 16);
}

// Get overall volume
float getVolume() {
    return (getBass() + getMid() + getTreble()) / 3.0;
}

// Draw nebula with rgb shift
vec3 drawNebula(vec2 uv, float bass, float mid) {
    // Radial scaling based on bass
    float scale = 0.8 + bass * 0.6;
    vec2 scaledUV = uv / scale;
    
    // Rotation for animation
    float angle = iTime * 0.1;
    mat2 rot = mat2(cos(angle), -sin(angle), sin(angle), cos(angle));
    vec2 rotatedUV = scaledUV * rot;
    
    // Add mid-driven turbulence
    float turb = getMid() * 0.3;
    rotatedUV += noised(rotatedUV * 2.0 + iTime * 0.5).xy * turb;
    
    // Fractal noise for nebula structure
    float n = fractalNoise(rotatedUV * 2.5 + iTime * 0.1, NEBULA_OCTAVES);
    n = (n + 1.0) * 0.5; // Normalize to [0,1]
    
    // Radial falloff with bass influence
    float radius = length(scaledUV);
    float falloff = 1.0 - smoothstep(0.0, 1.2 + bass * 0.5, radius);
    falloff = pow(falloff, 2.0);
    
    // Core glow
    float core = 1.0 - smoothstep(0.0, 0.4 + bass * 0.3, radius);
    core = pow(core, 3.0) * (1.0 + bass * 3.0);
    
    // RGB shift effect
    float shift = 0.005 * (1.0 + mid * 2.0);
    float r = fractalNoise(rotatedUV + vec2(shift, 0.0) + iTime * 0.05, NEBULA_OCTAVES);
    float g = n;
    float b = fractalNoise(rotatedUV - vec2(shift, 0.0) - iTime * 0.05, NEBULA_OCTAVES);
    
    // Base nebula color (purple/blue)
    vec3 color = vec3(r, g, b) * 0.8;
    color = mix(color, vec3(0.3, 0.1, 0.5), 0.5);
    
    // Apply falloff and core glow
    color *= falloff * (1.0 + n * 0.5);
    color += vec3(0.4, 0.2, 0.6) * core;
    
    return color;
}

// Draw particles responding to treble
vec3 drawParticles(vec2 uv, float treble) {
    vec3 color = vec3(0.0);
    float speed = 1.5 + treble * 3.0;
    int activeParticles = min(MAX_PARTICLES, int(float(MAX_PARTICLES) * (1.0 + treble * 1.5)));
    
    for (int i = 0; i < activeParticles; i++) {
        // Particle parameters
        float seed = float(i) * 7.312;
        vec2 dir = vec2(cos(seed), sin(seed));
        float angle = hash(vec2(seed, 0.1)) * 6.283;
        dir = vec2(cos(angle), sin(angle));
        
        // Particle movement
        float t = iTime * speed + hash(vec2(seed, 0.2)) * 100.0;
        float dist = fract(t);
        float life = 1.0 - dist;
        
        // Spawn more with higher treble
        float spawnChance = 0.7 - treble * 0.5;
        if (dist > spawnChance) continue;
        
        // Position with slight variation
        vec2 pos = dir * dist * 1.5;
        pos += noised(vec2(seed, iTime * 0.2)).xy * 0.02 * treble;
        
        // Draw particle with trail
        float d = length(uv - pos);
        float size = 0.01 + treble * 0.008;
        
        // Multiple iterations for glow effect
        float particle = 0.0;
        for (int j = 0; j < PARTICLE_ITERATIONS; j++) {
            float s = size * (1.0 + float(j) * 0.1);
            particle += exp(-d * 40.0 / s) * (1.0 - float(j)/float(PARTICLE_ITERATIONS));
        }
        particle *= life * 0.1;
        
        // Cyan/white color
        vec3 particleColor = mix(vec3(0.3, 1.0, 1.0), vec3(1.0, 1.0, 1.0), hash(vec2(seed, 0.3)));
        color += particle * particleColor * (1.0 + treble);
    }
    
    return color;
}

// Apply bloom effect
vec3 applyGlow(vec3 color, float glowAmount) {
    float brightness = dot(color, vec3(0.299, 0.587, 0.114));
    vec3 glow = vec3(pow(brightness, 2.0)) * glowAmount;
    return color + glow * 0.8;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // Normalized UV coordinates
    vec2 uv = (fragCoord * 2.0 - iResolution.xy) / min(iResolution.x, iResolution.y);
    
    // Get audio data
    float bass = getBass();
    float mid = getMid();
    float treble = getTreble();
    float volume = getVolume();
    
    // Draw elements
    vec3 nebula = drawNebula(uv, bass, mid);
    vec3 particles = drawParticles(uv, treble);
    
    // Combine and apply effects
    vec3 total = nebula + particles;
    total = applyGlow(total, GLOW_INTENSITY * (1.0 + volume * 2.0));
    
    // Clamp to prevent overexposure
    total = clamp(total, 0.0, 1.5);
    
    // Output with black background
    fragColor = vec4(total, 1.0);
}

// Desktop adapter
void main() {
    mainImage(gl_FragColor, gl_FragCoord.xy);
}