"""
Main application entry point for ShaderToy-like application.
"""
import sys
import os
from pathlib import Path
import time
import datetime

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shadertoy.shader import ShaderViewer
from shadertoy.audio import AudioSource
from shadertoy.uniforms import ShaderToyUniforms, TextureChannel

class ShaderToyApp:
    """Main application class managing uniforms and rendering"""
    def __init__(self, shader_path: str, width: int = 1920, height: int = 480, borderless: bool = False,
                 monitor_index: int | None = None, center: bool = False, offset: tuple[int, int] | None = None):
        self.viewer = ShaderViewer(width, height, borderless=borderless)
        if monitor_index is not None:
            # place window on monitor before loading heavy resources
            self.viewer.place_on_monitor(monitor_index, center=center, offset=offset)
        self.viewer.load_shader(shader_path)
        
        # Setup audio
        self.audio = AudioSource()
        # Try to start audio capture; if it fails we continue but note the state
        try:
            self.audio.start_capture()
            self._audio_started = True
            print("[audio] capture started")
        except Exception as e:
            self._audio_started = False
            print(f"[audio] capture not started: {e}")
        
        # Initialize uniforms
        self.uniforms = ShaderToyUniforms()
        self.start_time = time.time()
        self.last_time = self.start_time
        self.frame_count = 0
        
        # Setup audio channel
        self.setup_audio_channel()
        
    def setup_audio_channel(self):
        """Setup audio as iChannel0"""
        import OpenGL.GL as GL
        # Create two textures: iChannel0 for time-domain waveform, iChannel1 for FFT spectrum
        tex_time = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex_time)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)

        tex_fft = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex_fft)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)

        # iChannel0: time-domain buffer (width = chunk_size, height = 1)
        self.uniforms.iChannels[0] = TextureChannel(
            texture_id=tex_time,
            resolution=(self.audio.chunk_size, 1, 0)
        )
        # iChannel1: FFT spectrum (width = fft_size, height = 1)
        self.uniforms.iChannels[1] = TextureChannel(
            texture_id=tex_fft,
            resolution=(self.audio.fft_size, 1, 0)
        )

    def update_uniforms(self):
        """Update uniform values"""
        current_time = time.time()
        
        # Update time uniforms
        self.uniforms.iTime = current_time - self.start_time
        self.uniforms.iTimeDelta = current_time - self.last_time
        self.last_time = current_time
        
        # Update resolution
        w, h = self.viewer.get_window_size()
        self.uniforms.iResolution = (float(w), float(h), 0.0)
        
        # Update frame counter
        self.uniforms.iFrame = self.frame_count
        self.frame_count += 1
        
        # Update date
        now = datetime.datetime.now()
        self.uniforms.iDate = (
            float(now.year),
            float(now.month - 1),
            float(now.day),
            float(now.hour*3600 + now.minute*60 + now.second)
        )
        
        # Update audio channel(s)
        self.audio.update()
        # FFT texture data (shape: 1 x fft_size x 4)
        texdata_fft = self.audio.get_texture_data()

        # Time-domain buffer: copy current audio buffer into a 1xchunk_size RGBA texture
        import numpy as _np
        with self.audio._lock:
            td = self.audio._audio_buffer.copy()
        # Ensure correct length
        if td.size != self.audio.chunk_size:
            a = _np.zeros(self.audio.chunk_size, dtype=_np.float32)
            a[:td.size] = td
            td = a
        texdata_time = _np.zeros((1, td.size, 4), dtype=_np.float32)
        texdata_time[0, :, 0] = td  # R channel holds time-domain samples

        # Assign into uniform channels
        # iChannel0 -> time-domain
        self.uniforms.iChannels[0].data = texdata_time
        self.uniforms.iChannels[0].time = self.uniforms.iTime
        # iChannel1 -> FFT
        self.uniforms.iChannels[1].data = texdata_fft
        self.uniforms.iChannels[1].time = self.uniforms.iTime
        # fill audio-related uniforms - only sample rate
        try:
            self.uniforms.iSampleRate = float(self.audio.sample_rate)
        except Exception:
            pass

        # Log a basic diagnostic every 60 frames so user can confirm capture
        if self.frame_count % 60 == 0:
            try:
                import numpy as _np
                peak = float(_np.max(texdata_fft)) if texdata_fft is not None else 0.0
                # Also report raw audio buffer amplitude (before FFT/normalization)
                try:
                    with self.audio._lock:
                        buf = self.audio._audio_buffer.copy()
                    buf_peak = float(_np.max(_np.abs(buf)))
                except Exception:
                    buf_peak = 0.0

                # print a concise message to console with running_peak
                running_pk = getattr(self.audio, '_running_peak', 0.0)
                print(f"[audio] frame={self.frame_count} tex_peak={peak:.6f} buf_peak={buf_peak:.6f} running_peak={running_pk:.6f}")
            except Exception:
                pass

    def run(self):
        """Main application loop"""
        try:
            while not self.viewer.should_close():
                self.viewer.poll_events()
                self.update_uniforms()
                self.viewer.render(self.uniforms)
        finally:
            # Stop audio capture if we started it
            try:
                if getattr(self, '_audio_started', False):
                    self.audio.stop_capture()
            except Exception:
                pass
            self.viewer.cleanup()


def main():
    """Main application entry point"""
    # Get shader file path from command line or use default
    if len(sys.argv) > 1:
        shader_path = Path(sys.argv[1])
        if not shader_path.is_file():
            print(f"Shader file not found: {shader_path}")
            sys.exit(1)
    else:
        # Use default shader
        default_shader = Path(__file__).parent.parent / "shaders" / "ink_wash.glsl"
        if not default_shader.is_file():
            print("No shader file specified and default shader not found.")
            print("Usage: python -m shadertoy [shader_file]")
            sys.exit(1)
        shader_path = default_shader
    
    # Allow optional monitor selection via env: SHADER_MONITOR_INDEX
    mon_env = os.environ.get("SHADER_MONITOR_INDEX")
    mon_index = None
    try:
        if mon_env is not None:
            mon_index = int(mon_env)
    except Exception:
        mon_index = None
    app = ShaderToyApp(str(shader_path), monitor_index=mon_index, borderless=False)
    app.run()


if __name__ == "__main__":
    main()