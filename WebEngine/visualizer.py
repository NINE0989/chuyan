"""
OpenGL widget for rendering shaders using PyQt5.
"""
import time
import traceback
import sys
from pathlib import Path
from PyQt5.QtWidgets import QOpenGLWidget
from PyQt5.QtCore import QTimer, pyqtSignal
import OpenGL.GL as GL

# --- Robust import of project-local shadertoy package ---
try:
    from shadertoy.shader import Shader  # type: ignore
    from shadertoy.uniforms import ShaderToyUniforms, TextureChannel  # type: ignore
except ModuleNotFoundError:
    # Add project root (parent of WebEngine) to sys.path then retry
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    try:
        from shadertoy.shader import Shader  # type: ignore
        from shadertoy.uniforms import ShaderToyUniforms, TextureChannel  # type: ignore
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(
            f"无法导入 shadertoy 包：{e}. 请确认项目根目录在 PYTHONPATH 且包含 shadertoy/__init__.py")

class VisualizerWidget(QOpenGLWidget):
    """A QOpenGLWidget that renders a GLSL shader, similar to ShaderToy."""
    initialized = pyqtSignal()
    compileError = pyqtSignal(str)  # Emits error log when shader compile fails

    def __init__(self, parent=None):
        super().__init__(parent)
        self.shader = None
        self.uniforms = ShaderToyUniforms()
        self.start_time = time.time()
        self.last_time = self.start_time
        self.frame_count = 0
        self._is_initialized = False
        
        # Timer to trigger updates
        self.timer = QTimer(self)
        self.timer.setInterval(16)  # Target ~60 FPS
        self.timer.timeout.connect(self.update)
        self.timer.start()

    def load_shader(self, shader_path: str):
        """
        Loads and compiles the GLSL shader.
        """
        if not self._is_initialized:
            print("[Visualizer] Warning: load_shader called before OpenGL is initialized.")
            return
            
        try:
            self.makeCurrent()
            self.shader = Shader(shader_path)
            self.doneCurrent()
            print(f"[Visualizer] Shader '{shader_path}' loaded successfully.")
        except Exception as e:
            # Capture traceback text
            err_lines = traceback.format_exc().splitlines()
            short_log = '\n'.join(err_lines[-10:])  # limit size
            print(f"[Visualizer] Error loading shader: {e}\n{short_log}")
            self.shader = None
            self.compileError.emit(short_log)

    def setup_audio_texture(self, fft_size: int):
        """
        Creates and configures the texture for audio data (iChannel0).
        This must be called after initializeGL has completed.
        """
        if not self._is_initialized:
            print("[Visualizer] Error: setup_audio_texture called before initialization.")
            return

        print(f"[Visualizer] Setting up audio texture (iChannel0) with FFT size: {fft_size}")
        self.makeCurrent()
        
        tex_id = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex_id)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        
        self.uniforms.iChannels[0] = TextureChannel(
            texture_id=tex_id,
            resolution=(fft_size, 1, 0)
        )
        
        self.doneCurrent()
        print(f"[Visualizer] Audio texture configured with texture ID: {tex_id}")

    def update_channel_texture_data(self, channel_index: int, data):
        """
        Updates the data for a given channel's texture.
        """
        if 0 <= channel_index < len(self.uniforms.iChannels):
            if self.uniforms.iChannels[channel_index] is not None:
                self.uniforms.iChannels[channel_index].data = data

    def initializeGL(self):
        """
        Called once when the OpenGL context is created.
        """
        GL.glClearColor(0.0, 0.0, 0.0, 1.0)
        print("[Visualizer] OpenGL Initialized.")
        print(f"  Vendor: {GL.glGetString(GL.GL_VENDOR).decode()}")
        print(f"  Renderer: {GL.glGetString(GL.GL_RENDERER).decode()}")
        print(f"  OpenGL Version: {GL.glGetString(GL.GL_VERSION).decode()}")
        print(f"  GLSL Version: {GL.glGetString(GL.GL_SHADING_LANGUAGE_VERSION).decode()}")
        self._is_initialized = True
        self.initialized.emit()

    def paintGL(self):
        """
        The main rendering loop.
        """
        if not self.shader or not self.shader.program:
            GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            return

        # Update time-based uniforms
        current_time = time.time()
        self.uniforms.iTime = current_time - self.start_time
        self.uniforms.iTimeDelta = current_time - self.last_time
        self.last_time = current_time
        self.uniforms.iFrame = self.frame_count
        self.frame_count += 1
        
        # Update resolution
        self.uniforms.iResolution = (self.width(), self.height(), 0.0)

        # Use the shader program
        GL.glUseProgram(self.shader.program)

        # Update all uniforms
        self.shader.update_uniforms(self.uniforms)

        # Draw a full-screen quad
        GL.glBegin(GL.GL_QUADS)
        GL.glVertex2f(-1, -1)
        GL.glVertex2f(1, -1)
        GL.glVertex2f(1, 1)
        GL.glVertex2f(-1, 1)
        GL.glEnd()

        GL.glUseProgram(0)

    def resizeGL(self, w: int, h: int):
        """
        Called whenever the widget is resized.
        """
        GL.glViewport(0, 0, w, h)
        self.uniforms.iResolution = (w, h, 1.0)