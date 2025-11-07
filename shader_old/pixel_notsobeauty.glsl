#version 330 core

#ifdef GL_ES
precision mediump float;
#endif

uniform vec3 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;
uniform float iSampleRate;
out vec4 fragColor;

// Mitsync, 2023

/*
    I did some experiments with the audio inputs in Shadertoy and accidentally wrote documentation for it.
    Most of this is purely theoretical and does not matter if you just want to draw a pretty graph.
        The most important part for that is how the frequency axis works:
            UV coordinates 0.0-1.0 correspond to 0 - 11/12 kHz, linearly.
            Make this logarithmic to get prettier graphs, as done in helper function `fft_log()` below.
    If you use code from this file it would be nice if you linked back here :)
    All testing done in Google Chrome on Windows 10, using signals generated in Audacity:
        Filetype: uncompressed WAV, samplerate: 44.1 and 48 kHz, sample format: 32-bit float
    
    Basics:
        Audio inputs are accesible in shaders as a 512x2 texture with a single color channel (red).
        The top row (y-coordinate 1) is the 512 most recent audio samples. Use this to draw a waveform.
        The bottom row (y-coordinate 0) is 512 points of spectrum between 0 and 11/12 kHz. Use this to draw a spectrum/equaliser.
        The stored values are medium precision floats between 0.0 and 1.0 inclusive for both the wave and FFT rows.
            This means silence is a constant value of 0.5 (DC offset).
        The easiest way to access values is using the `texture()` function:
            For samples: `texture(iChannelX, vec2(x, 1.0)).r`
            For spectrum: `texture(iChannelX, vec2(x, 0.0)).r`
            Where `x` is a float between 0.0 and 1.0 inclusive. Replace `iChannelX` with the channel you're using. The `.r` makes these return a float.
            Note that this does linear interpolation if you ask a value between two measured values (samples or bins).
                This can't be disabled with the channel settings, use `texelFetch()` instead.
        Another way is using the `texelFetch()` function:
            For samples: `texelFetch(iChannelX, ivec2(x, 1), 0).r`
            For spectrum: `texelFetch(iChannelX, ivec2(x, 0), 0).r`
            Where `x` is an integer between 0 and 511 inclusive. Replace `iChannelX` with the channel you're using. The `.r` makes these return a float.
                Eg: `int x = int(x_float*512.)`
            This does not do interpolation (as you can only input integers).
        Or just use the helper functions below. :)
        All inputs get converted to the samplerate of the audio output on your device before they reach the shader:
            Setting output to 44.1 kHz (in Windows in my case) means the FFT goes between 0 and 11 kHz for both 44.1 kHz AND 48 kHz sources.
            The current samplerate is available in the uniform `iSampleRate` (even outside sound shaders, unlike what the official documentation implies)
        You can import custom audio using this Chrome extension and just dropping a file on one of the input channels:
            https://chrome.google.com/webstore/detail/shadertoy-custom-texures/jgeibpcndpjboeebilehgbpkopkgkjda
            Supported filetypes depend on OS and browser.

    FFT specifics:
        The bottom row (y-coordinate 0) is 512 points of spectrum of the incoming audio signal.
        The frequency axis is linear between 0 and 1/4 samplerate inclusive (so usually 11025 Hz or 12000 Hz):
            Minimum UV coordinate (0.0) corresponds to 0 Hz (DC component, this is not removed!).
            Maximum UV coordinate (1.0) corresponds to 1/4 times the output samplerate (so usually 11025 Hz or 12000 Hz).
            Frequency resolution (bin size) is 21.5 Hz at 44.1 kHz samplerate, 23.4 Hz at 48 kHz samplerate.
                These are approximately the differences between F#4 (370.0 Hz), G4 (392.0 Hz), and G#4 (415.3 Hz),
                    Notes below that can't be accurately distinguished from neighbors.
            All this implies Shadertoy is resampling, then doing a 2048-point FFT, but only making the first 512 points available.
                (These are by far the most interesting anyway, we're not losing much)
                This also means frequencies between 1/4 and 3/4 samplerate do NOT cause aliasing!
                Frequencies above 3/4 samplerate DO cause aliasing (be careful with pure squarewaves for example).
        Amplitude is linear with dB power between -87 and -17 dB:
            Minimum returned value (0.0) corresponds to a signal power of -87 dB or lower.
            Maximum returned value (1.0) corresponds to -17 dB or higher.
            Values inbetween are linear with amplitude in dB.
            Note: values are clipped! It is not possible to measure amplitudes outside this range!
                Spectrum clipping is common, even (especially!) with properly mastered audio!
            Amplitude is smoothed over time by what looks like decaying peak-hold.
                A 0 dB sine takes approximately 0.5 seconds to drop below minimum amplitude (-87 dB).
        Window is unknown but acts as follows:
            A pure 0 dB sine at an exact bin frequency (aligned to the pixels) is 5 bins wide (total).
            A pure 0 dB sine exactly between bins is also 5/6 pixels wide but with 5 extra bins of sidelobe on both sides.
                So 15 bins around centre have significant value.
            Harmonics are not surpressed (which is the correct way to do it).
    
    Contents of this demo:
        Comments with example inputs and outputs assume constants as defined at the top of this file
        Several helper functions for accessing and converting the audio data:
            Getting amplitude of wave
            Conversion between musical note, octave and frequency
    
    Useful links:
        Table of notes and frequencies, also coupled to piano, organ and MIDI notes:
            https://www.inspiredacoustics.com/en/MIDI_note_numbers_and_center_frequencies
        More may come later
*/



/*  ------------------------
      MACROS AND CONSTANTS
    ------------------------*/

// Constants
#define INPUT iChannel0
#define SAMPLERATE iSampleRate
// These brackets are required because the preprocessor is dumb
#define MAX_F (0.25*SAMPLERATE)
// Reference note for the conversions between note/octave and frequency, a good default is C4, aka middle C, 261.63 Hz
#define REF_NOTE 261.63

// Macros
#define ILN10 0.4343

/*  --------------------
      HELPER FUNCTIONS
    --------------------*/

// GETTING WAVE DATA
// Get wave amplitude at UV coordinate (input between 0.0 and 1.0 inclusive)
float wave(in float x)                  {  return texture(INPUT, vec2(x, 1.0)).r;  }
// Get wave amplitude of sample, so not interpolated (input between 0 and 511 inclusive)
float wave(in int s)                    {  return texelFetch(INPUT, ivec2(s, 0), 1).r;  }

// GETTING FFT DATA
// Get FFT at UV coordinate (input between 0.0 and 1.0 inclusive)
float fft(in float x)                   {  return texture(INPUT, vec2(x, 0.0)).r;  }
// Get FFT of frequency bin, so not interpolated (input between 0 and 511 inclusive)
float fft(in int bin)                   {  return texelFetch(INPUT, ivec2(bin, 0), 0).r;  }
// Get FFT of frequency (input between 0.0 and MAX_F)
float fft_freq(in float freq)           {  return fft(freq/MAX_F);  }
// Get FFT of log UV coordinate, between 50 and 10000 Hz (input between 0.0 and 1.0 inclusive) (!! use this one for pretty graphs !!)
float fft_log(in float x)               {  return fft(50. * pow(10.0, 2.3*x) / MAX_F);  }

// CONVERTING AMPLITUDE REPRESENTATIONS
// Convert the amplitude returned from FFT to decibel power or amplitude
float fft_to_db(in float val)           {  return 70.*val - 87.;  }
float fft_to_amplitude(in float val)    {  return pow(10., fft_to_db(val)/10.);  }

// Convert between decibel power and amplitude
float amplitude_to_db(in float amp)     {  return 20.*log(amp)*ILN10;  }
float db_to_amplitude(in float db)      {  return pow(10., db/20.);  }

// CONVERTING FREQUENCY REPRESENTATIONS
// Convert between octave relative to REF_NOTE and frequency (0.=C4, -1.=C3, (2./12.)=D4, etc.)
// This is similar to volt/octave in modular synthesis
float octave_to_freq(in float octave)   {  return REF_NOTE * exp2(octave);  }
float freq_to_octave(in float freq)     {  return log2(freq / REF_NOTE);  }

// Convert between note relative to REF_NOTE and frequency (0.=C4, -12.=C3, 2.=D4, etc.)
float note_to_freq(in float note)       {  return REF_NOTE * exp2(note/12.);  }
float freq_to_note(in float freq)       {  return log2(freq / REF_NOTE) * 12.;  }

// Convert between note and octave (note 12. is octave 1., note -18. is octave -1.5)
float note_to_octave(in float note)     {  return note / 12.;  }
float octave_to_note(in float octave)   {  return octave * 12.;  }

// Round frequency to that of nearest note
float round_to_note(in float freq)      {  return note_to_freq(round(freq_to_note(freq)));  }

// OTHER
// Construct a grayscale colour from a single float
vec4 col(in float val)                  {  return vec4(val, val, val, 1.0);  }
// Construct a RG colour from a vec2
vec4 col(in vec2 val)                   {  return vec4(val, 0.0, 1.0);  }
// Construct a RGB colour from a vec3
vec4 col(in vec3 val)                   {  return vec4(val, 1.0);  }

// TODO: note with sum harmonics???
// Summed power at first through fourth harmonics of this frequency (in dB)
float freq_harmonic_power(in float freq) {
    vec4 amp;
    amp.x = fft_to_amplitude(fft_freq(freq));
    amp.y = fft_to_amplitude(fft_freq(2. * freq));
    amp.z = fft_to_amplitude(fft_freq(3. * freq));
    amp.w = fft_to_amplitude(fft_freq(4. * freq));
    return amplitude_to_db(amp.x + amp.y + amp.z + amp.w);
}
// Get FFT amplitude of note
float fft_note(in float note)           {  return fft_freq(note_to_freq(note));  }

// Get approximate total volume by summing FFT
float total_power() {
    float sum = 0.0;
    for (int i = 32; i < 512; i += 8) {
        sum += fft(i);
    }
    return 8. * sum / 480.;
}



/*  -----------------------
      MAIN IMAGE FUNCTION
    -----------------------*/

void mainImage( out vec4 fragColor, in vec2 fragCoord )
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = fragCoord/iResolution.xy;
    
    float avg_pwr = total_power();

    float note = 72.*uv.x - 24.;
    float p_cont = fft_note(note);
    float p_note = fft_note(round(note));
    
    vec3 p_neighbors;
    p_neighbors.x = fft_note(round(note)-1.0);
    p_neighbors.y = fft_note(round(note));
    p_neighbors.z = fft_note(round(note)+1.0);
    float p_rel = dot(p_neighbors, vec3(-0.45, 1.0, -0.45));
    p_rel = p_rel/(uv.x+1.);
    
    // Contrived example
    float amp_c4 = fft_to_amplitude(fft_freq(note_to_freq(0.0)));
    
    fragColor = abs(uv.y-p_cont) < 0.005 ? col(1.0) : (abs(uv.y-p_rel) < 0.005 ? col(1.0) : col(pow(p_rel*1., 7.)));
    fragColor += abs(uv.y-avg_pwr) < 0.005 ? col(1.0) : col(0.0);
    //fragColor = col(fft(uv.x));
}

void main()
{
    vec4 colOut = vec4(0.0);
    mainImage(colOut, gl_FragCoord.xy);
#ifdef GL_ES
    gl_FragColor = colOut;
#else
    fragColor = colOut;
#endif
}