"""
Main application entry point for ShaderToy-like application.
"""
import sys
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
    def __init__(self, shader_path: str, width: int = 1920, height: int = 480):
        self.viewer = ShaderViewer(width, height)
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
        tex = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        
        self.uniforms.iChannels[0] = TextureChannel(
            texture_id=tex,
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
        
        # Update audio channel
        self.audio.update()
        texdata = self.audio.get_texture_data()
        self.uniforms.iChannels[0].data = texdata
        self.uniforms.iChannels[0].time = self.uniforms.iTime
        # fill audio-related uniforms - only sample rate
        try:
            self.uniforms.iSampleRate = float(self.audio.sample_rate)
        except Exception:
            pass

        # Log a basic diagnostic every 60 frames so user can confirm capture
        if self.frame_count % 60 == 0:
            try:
                import numpy as _np
                peak = float(_np.max(texdata)) if texdata is not None else 0.0
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
    
    app = ShaderToyApp(str(shader_path))
    app.run()


if __name__ == "__main__":
    main()