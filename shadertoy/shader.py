"""
ShaderToy-compatible GLSL shader viewer
"""
import os
import ctypes
from typing import Dict

import numpy as np
import glfw
from OpenGL import GL
import re
from pathlib import Path

from .uniforms import ShaderToyUniforms, TextureChannel

# The old ShaderViewer class is now obsolete and has been removed.
# It's replaced by the VisualizerWidget in visualizer.py
class ShaderViewer:
    """OpenGL shader viewer with ShaderToy compatibility, test Version 1.0"""
    VERTEX_SRC = '''#version 330
    layout(location = 0) in vec2 aPos;
    layout(location = 1) in vec2 aUV;
    out vec2 vUV;
    void main(){
        vUV = aUV;
        gl_Position = vec4(aPos, 0.0, 1.0);
    }
    '''

    def __init__(self, width: int = 1920, height: int = 480, title: str = 'ShaderToy-like Viewer', borderless: bool = False):
        if not glfw.init():
            raise RuntimeError('glfw.init() failed')

        # Window creation — 强制桌面 OpenGL，避免回退到 OpenGL ES
        glfw.window_hint(glfw.CLIENT_API, glfw.OPENGL_API)
        glfw.window_hint(glfw.CONTEXT_CREATION_API, glfw.NATIVE_CONTEXT_API)
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        
        if borderless:
            glfw.window_hint(glfw.DECORATED, glfw.FALSE)

        self.window = glfw.create_window(width, height, title, None, None)
        if not self.window:
            glfw.terminate()
            raise RuntimeError('Failed to create window')

        glfw.make_context_current(self.window)
        self.width = width
        self.height = height

        # 检测实际获得的 GL 版本，若为 ES 则启用兼容适配
        gl_ver = GL.glGetString(GL.GL_VERSION)
        if isinstance(gl_ver, bytes):
            gl_ver = gl_ver.decode('utf-8', errors='replace')
        self._is_gles = 'OpenGL ES' in gl_ver if isinstance(gl_ver, str) else False
        print(f"[GL] {gl_ver}" + (" (ES compat mode)" if self._is_gles else ""))
        if self._is_gles:
            # 改写顶点着色器为 ES 兼容版本
            self.VERTEX_SRC = self.VERTEX_SRC.replace('#version 330', '#version 300 es\nprecision mediump float;')

        # install key callback for ESC to close
        glfw.set_key_callback(self.window, self._on_key)
        self.setup_quad()
        self.uniforms: Dict[str, int] = {}

    # ---------------- input & window placement helpers -----------------
    def _on_key(self, window, key, scancode, action, mods):
        if key == glfw.KEY_ESCAPE and action == glfw.PRESS:
            glfw.set_window_should_close(self.window, True)

    def place_on_monitor(self, monitor_index: int = 0, center: bool = False, offset: tuple[int, int] | None = None):
        """Place window on the given monitor (multi-monitor setups). Fallback to primary.
        monitor_index: index into glfw.get_monitors()
        center: if True, center window on target monitor else top-left
        offset: optional (dx, dy) applied after chosen anchor
        """
        try:
            monitors = glfw.get_monitors() or []
            if not monitors:
                return
            if monitor_index < 0 or monitor_index >= len(monitors):
                monitor_index = 0
            else:
                monitor_index = 1
            mon = monitors[monitor_index]
            mx, my = glfw.get_monitor_pos(mon)
            mode = glfw.get_video_mode(mon)
            mw, mh = mode.size.width, mode.size.height if hasattr(mode, 'size') else (mode.width, mode.height)  # type: ignore
            if center:
                x = mx + max(0, (mw - self.width) // 2)
                y = my + max(0, (mh - self.height) // 2)
            else:
                x, y = mx, my
            if offset:
                x += offset[0]
                y += offset[1]
            glfw.set_window_pos(self.window, int(x), int(y))
        except Exception:
            pass

    def setup_quad(self) -> None:
        """Setup fullscreen quad for rendering"""
        quad = np.array([
            -1.0, -1.0, 0.0, 0.0,
             1.0, -1.0, 1.0, 0.0,
            -1.0,  1.0, 0.0, 1.0,
             1.0,  1.0, 1.0, 1.0,
        ], dtype=np.float32)

        self.vao = GL.glGenVertexArrays(1)
        GL.glBindVertexArray(self.vao)
        vbo = GL.glGenBuffers(1)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, quad.nbytes, quad, GL.GL_STATIC_DRAW)
        GL.glEnableVertexAttribArray(0)
        GL.glVertexAttribPointer(0, 2, GL.GL_FLOAT, GL.GL_FALSE, 16, ctypes.c_void_p(0))
        GL.glEnableVertexAttribArray(1)
        GL.glVertexAttribPointer(1, 2, GL.GL_FLOAT, GL.GL_FALSE, 16, ctypes.c_void_p(8))

    def load_shader(self, path: str) -> None:
        """Load and compile shader program"""
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
            
        with open(path, 'r', encoding='utf-8') as f:
            fs_src = f.read()

        # Resolve #include directives by inlining the referenced files.
        # Includes are resolved relative to the shader file's directory.
        def _resolve_includes(src: str, base_dir: Path, seen: set[str] | None = None) -> str:
            if seen is None:
                seen = set()
            out_lines: list[str] = []
            for line in src.splitlines():
                m = re.match(r'^\s*#include\s+"([^"]+)"', line)
                if m:
                    inc_name = m.group(1)
                    inc_path = (base_dir / inc_name).resolve()
                    inc_key = str(inc_path)
                    if inc_key in seen:
                        # already inlined; skip to avoid recursion
                        continue
                    if not inc_path.is_file():
                        raise FileNotFoundError(f"Included shader not found: {inc_path}")
                    seen.add(inc_key)
                    inc_text = inc_path.read_text(encoding='utf-8')
                    # strip any #version directives from included files
                    inc_text = re.sub(r"^\s*#version.*$", "", inc_text, flags=re.MULTILINE)
                    inc_text = _resolve_includes(inc_text, inc_path.parent, seen)
                    out_lines.append(inc_text)
                else:
                    out_lines.append(line)
            return "\n".join(out_lines)

        fs_src = _resolve_includes(fs_src, Path(path).parent)

        # 剥离 BOM 和非法控制字符，避免 #version 解析失败
        fs_src = fs_src.lstrip('\ufeff')
        fs_src = fs_src.replace('\r\n', '\n').replace('\r', '\n')

        # 运行时检测 GL 版本：若为 ES 则适配 shader
        gl_ver_str = GL.glGetString(GL.GL_VERSION)
        if isinstance(gl_ver_str, bytes):
            gl_ver_str = gl_ver_str.decode('utf-8', errors='replace')
        is_es = 'OpenGL ES' in gl_ver_str if isinstance(gl_ver_str, str) else False
        if is_es:
            # 改写顶点着色器
            self.VERTEX_SRC = self.VERTEX_SRC.replace('#version 330', '#version 300 es')
            if 'precision' not in self.VERTEX_SRC[:200]:
                self.VERTEX_SRC = self.VERTEX_SRC.replace('#version 300 es', '#version 300 es\nprecision mediump float;')
            # 改写片段着色器
            fs_src = fs_src.replace('#version 330', '#version 300 es')
            if 'precision' not in fs_src[:300]:
                idx = fs_src.find('#version')
                if idx >= 0:
                    eol = fs_src.find('\n', idx)
                    fs_src = fs_src[:eol + 1] + 'precision mediump float;\n' + fs_src[eol + 1:]
            print(f"[GL] ES 兼容模式: 顶点/片段着色器已适配为 #version 300 es")

        # Compile shaders
        vs = self._compile_shader(self.VERTEX_SRC, GL.GL_VERTEX_SHADER)
        fs = self._compile_shader(fs_src, GL.GL_FRAGMENT_SHADER)
        self.program = self._link_program(vs, fs)

        # Get uniform locations
        uniform_names = [
            'iResolution', 'iTime', 'iTimeDelta', 'iFrameRate', 'iFrame',
            'iMouse', 'iDate', 'iSampleRate', 'iHandPos', 'iHandAction',
            'iHandDepthRef', 'iPinchEnabled', 'iSatControl', 'iDisturbControl'
        ]
        self.uniforms = {
            name: GL.glGetUniformLocation(self.program, name)
            for name in uniform_names
        }
        
        # Get channel uniform locations
        for i in range(4):
            self.uniforms[f'iChannel{i}'] = GL.glGetUniformLocation(self.program, f'iChannel{i}')

    def _compile_shader(self, src: str, shader_type: int) -> int:
        shader = GL.glCreateShader(shader_type)
        GL.glShaderSource(shader, src)
        GL.glCompileShader(shader)
        status = GL.glGetShaderiv(shader, GL.GL_COMPILE_STATUS)
        if not status:
            log = GL.glGetShaderInfoLog(shader)
            if isinstance(log, bytes):
                log = log.decode('utf-8')
            raise RuntimeError('Shader compile error:\n' + log)
        return shader

    def _link_program(self, vs: int, fs: int) -> int:
        prog = GL.glCreateProgram()
        GL.glAttachShader(prog, vs)
        GL.glAttachShader(prog, fs)
        GL.glLinkProgram(prog)
        status = GL.glGetProgramiv(prog, GL.GL_LINK_STATUS)
        if not status:
            log = GL.glGetProgramInfoLog(prog)
            if isinstance(log, bytes):
                log = log.decode('utf-8')
            raise RuntimeError('Program link error:\n' + log)
        return prog

    def update_uniforms(self, uniforms: ShaderToyUniforms) -> None:
        """Update shader uniforms from ShaderToyUniforms object"""
        GL.glUseProgram(self.program)
        
        # Update basic uniforms
        if self.uniforms['iResolution'] != -1:
            GL.glUniform3f(self.uniforms['iResolution'], *uniforms.iResolution)
        if self.uniforms['iTime'] != -1:
            GL.glUniform1f(self.uniforms['iTime'], uniforms.iTime)
        if self.uniforms['iTimeDelta'] != -1:
            GL.glUniform1f(self.uniforms['iTimeDelta'], uniforms.iTimeDelta)
        if self.uniforms['iFrameRate'] != -1:
            GL.glUniform1f(self.uniforms['iFrameRate'], uniforms.iFrameRate)
        if self.uniforms['iFrame'] != -1:
            GL.glUniform1i(self.uniforms['iFrame'], uniforms.iFrame)
        if self.uniforms['iMouse'] != -1:
            GL.glUniform4f(self.uniforms['iMouse'], *uniforms.iMouse)
        if self.uniforms['iDate'] != -1:
            GL.glUniform4f(self.uniforms['iDate'], *uniforms.iDate)
        if self.uniforms['iSampleRate'] != -1:
            GL.glUniform1f(self.uniforms['iSampleRate'], uniforms.iSampleRate)
        if self.uniforms['iHandPos'] != -1:
            GL.glUniform3f(self.uniforms['iHandPos'], *uniforms.iHandPos)
        if self.uniforms['iHandAction'] != -1:
            GL.glUniform1f(self.uniforms['iHandAction'], uniforms.iHandAction)
        if self.uniforms['iHandDepthRef'] != -1:
            GL.glUniform1f(self.uniforms['iHandDepthRef'], uniforms.iHandDepthRef)
        if self.uniforms['iPinchEnabled'] != -1:
            GL.glUniform1f(self.uniforms['iPinchEnabled'], uniforms.iPinchEnabled)
        if self.uniforms['iSatControl'] != -1:
            GL.glUniform1f(self.uniforms['iSatControl'], uniforms.iSatControl)
        if self.uniforms['iDisturbControl'] != -1:
            GL.glUniform1f(self.uniforms['iDisturbControl'], uniforms.iDisturbControl)

        # Update channel textures
        for i, channel in enumerate(uniforms.iChannels):
            if channel.data is not None and channel.texture_id != -1:
                GL.glActiveTexture(GL.GL_TEXTURE0 + i)
                GL.glBindTexture(GL.GL_TEXTURE_2D, channel.texture_id)
                GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA32F,
                            channel.data.shape[1], channel.data.shape[0], 0,
                            GL.GL_RGBA, GL.GL_FLOAT, channel.data)
                if self.uniforms[f'iChannel{i}'] != -1:
                    GL.glUniform1i(self.uniforms[f'iChannel{i}'], i)

    def render(self, uniforms: ShaderToyUniforms) -> None:
        """Render one frame with given uniforms"""
        # Enable alpha blending so shaders can output transparent pixels
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        # Use transparent clear color so alpha=0 pixels become holes
        GL.glClearColor(0.0, 0.0, 0.0, 0.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)

        self.update_uniforms(uniforms)
        
        GL.glBindVertexArray(self.vao)
        GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)

        glfw.swap_buffers(self.window)

    def should_close(self) -> bool:
        """Check if window should close"""
        return glfw.window_should_close(self.window)

    def poll_events(self) -> None:
        """Poll window events"""
        glfw.poll_events()

    def get_window_size(self) -> tuple[int, int]:
        """Get current window size"""
        return glfw.get_framebuffer_size(self.window)

    def cleanup(self) -> None:
        """Clean up resources"""
        glfw.terminate()

# 模块测试
class Shader:
    """
    Manages a single GLSL shader program, including loading from file,
    handling #include directives, and updating uniforms.
    """
    VERTEX_SRC = '''#version 330
    layout(location = 0) in vec2 aPos;
    void main(){
        gl_Position = vec4(aPos, 0.0, 1.0);
    }
    '''

    def __init__(self, path: str):
        """
        Initializes and loads the shader from the given path.
        """
        self.program = None
        self.uniforms: Dict[str, int] = {}
        self.load_shader(path)

    def load_shader(self, path: str):
        """Load and compile shader program"""
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
            
        with open(path, 'r', encoding='utf-8') as f:
            fs_src = f.read()

        # Resolve #include directives
        def _resolve_includes(src: str, base_dir: Path, seen: set = None) -> str:
            if seen is None: seen = set()
            out_lines: list[str] = []
            for line in src.splitlines():
                m = re.match(r'^\s*#include\s+"([^"]+)"', line)
                if m:
                    inc_name = m.group(1)
                    inc_path = (base_dir / inc_name).resolve()
                    inc_key = str(inc_path)
                    if inc_key in seen:
                        continue
                    if not inc_path.is_file():
                        raise FileNotFoundError(f"Included shader not found: {inc_path}")
                    seen.add(inc_key)
                    inc_text = inc_path.read_text(encoding='utf-8')
                    inc_text = re.sub(r"^\s*#version.*$", "", inc_text, flags=re.MULTILINE)
                    inc_text = _resolve_includes(inc_text, inc_path.parent, seen)
                    out_lines.append(inc_text)
                else:
                    out_lines.append(line)
            return "\n".join(out_lines)

        fs_src = _resolve_includes(fs_src, Path(path).parent)

        # 剥离 BOM 和非法控制字符，避免 #version 解析失败
        fs_src = fs_src.lstrip('\ufeff')
        fs_src = fs_src.replace('\r\n', '\n').replace('\r', '\n')

        # 运行时检测 GL 版本：若为 ES 则适配 shader
        gl_ver_str = GL.glGetString(GL.GL_VERSION)
        if isinstance(gl_ver_str, bytes):
            gl_ver_str = gl_ver_str.decode('utf-8', errors='replace')
        is_es = 'OpenGL ES' in gl_ver_str if isinstance(gl_ver_str, str) else False
        if is_es:
            # 改写顶点着色器
            self.VERTEX_SRC = self.VERTEX_SRC.replace('#version 330', '#version 300 es')
            if 'precision' not in self.VERTEX_SRC[:200]:
                self.VERTEX_SRC = self.VERTEX_SRC.replace('#version 300 es', '#version 300 es\nprecision mediump float;')
            # 改写片段着色器
            fs_src = fs_src.replace('#version 330', '#version 300 es')
            if 'precision' not in fs_src[:300]:
                idx = fs_src.find('#version')
                if idx >= 0:
                    eol = fs_src.find('\n', idx)
                    fs_src = fs_src[:eol + 1] + 'precision mediump float;\n' + fs_src[eol + 1:]
            print(f"[GL] ES 兼容模式: 顶点/片段着色器已适配为 #version 300 es")

        # Compile shaders
        vs = self._compile_shader(self.VERTEX_SRC, GL.GL_VERTEX_SHADER)
        fs = self._compile_shader(fs_src, GL.GL_FRAGMENT_SHADER)
        self.program = self._link_program(vs, fs)

        # Get uniform locations
        uniform_names = [
            'iResolution', 'iTime', 'iTimeDelta', 'iFrameRate', 'iFrame',
            'iMouse', 'iDate', 'iSampleRate', 'iHandPos', 'iHandAction',
            'iHandDepthRef', 'iPinchEnabled', 'iSatControl', 'iDisturbControl'
        ]
        self.uniforms = {
            name: GL.glGetUniformLocation(self.program, name)
            for name in uniform_names
        }
        
        for i in range(4):
            self.uniforms[f'iChannel{i}'] = GL.glGetUniformLocation(self.program, f'iChannel{i}')

    def _compile_shader(self, src: str, shader_type: int) -> int:
        shader = GL.glCreateShader(shader_type)
        GL.glShaderSource(shader, src)
        GL.glCompileShader(shader)
        if not GL.glGetShaderiv(shader, GL.GL_COMPILE_STATUS):
            log = GL.glGetShaderInfoLog(shader)
            if isinstance(log, bytes):
                log = log.decode('utf-8')
            raise RuntimeError('Shader compile error:\n' + log)
        return shader

    def _link_program(self, vs: int, fs: int) -> int:
        prog = GL.glCreateProgram()
        GL.glAttachShader(prog, vs)
        GL.glAttachShader(prog, fs)
        GL.glLinkProgram(prog)
        if not GL.glGetProgramiv(prog, GL.GL_LINK_STATUS):
            log = GL.glGetProgramInfoLog(prog)
            if isinstance(log, bytes):
                log = log.decode('utf-8')
            raise RuntimeError('Program link error:\n' + log)
        return prog

    def update_uniforms(self, uniforms: ShaderToyUniforms):
        """Update shader uniforms from ShaderToyUniforms object"""
        if self.uniforms['iResolution'] != -1:
            GL.glUniform3f(self.uniforms['iResolution'], *uniforms.iResolution)
        if self.uniforms['iTime'] != -1:
            GL.glUniform1f(self.uniforms['iTime'], uniforms.iTime)
        if self.uniforms['iTimeDelta'] != -1:
            GL.glUniform1f(self.uniforms['iTimeDelta'], uniforms.iTimeDelta)
        if self.uniforms['iFrame'] != -1:
            GL.glUniform1i(self.uniforms['iFrame'], uniforms.iFrame)
        if self.uniforms['iSampleRate'] != -1:
            GL.glUniform1f(self.uniforms['iSampleRate'], uniforms.iSampleRate)
        if self.uniforms['iHandPos'] != -1:
            GL.glUniform3f(self.uniforms['iHandPos'], *uniforms.iHandPos)
        if self.uniforms['iHandAction'] != -1:
            GL.glUniform1f(self.uniforms['iHandAction'], uniforms.iHandAction)
        if self.uniforms['iHandDepthRef'] != -1:
            GL.glUniform1f(self.uniforms['iHandDepthRef'], uniforms.iHandDepthRef)
        if self.uniforms['iPinchEnabled'] != -1:
            GL.glUniform1f(self.uniforms['iPinchEnabled'], uniforms.iPinchEnabled)
        if self.uniforms['iSatControl'] != -1:
            GL.glUniform1f(self.uniforms['iSatControl'], uniforms.iSatControl)
        if self.uniforms['iDisturbControl'] != -1:
            GL.glUniform1f(self.uniforms['iDisturbControl'], uniforms.iDisturbControl)

        # Update channel textures
        for i, channel in enumerate(uniforms.iChannels):
            if channel and channel.data is not None and channel.texture_id != -1:
                GL.glActiveTexture(GL.GL_TEXTURE0 + i)
                GL.glBindTexture(GL.GL_TEXTURE_2D, channel.texture_id)
                
                # Determine format based on data shape
                if len(channel.data.shape) == 2: # Grayscale (FFT data)
                    height, width = channel.data.shape
                    internal_format = GL.GL_R32F
                    data_format = GL.GL_RED
                else: # Assuming RGBA
                    height, width, _ = channel.data.shape
                    internal_format = GL.GL_RGBA32F
                    data_format = GL.GL_RGBA

                GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, internal_format,
                                width, height, 0,
                                data_format, GL.GL_FLOAT, channel.data)
                
                if self.uniforms.get(f'iChannel{i}', -1) != -1:
                    GL.glUniform1i(self.uniforms[f'iChannel{i}'], i)