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
    VERTEX_SRC = '''#version 330 core
    layout(location = 0) in vec2 aPos;
    layout(location = 1) in vec2 aUV;
    out vec2 vUV;
    void main(){
        vUV = aUV;
        gl_Position = vec4(aPos, 0.0, 1.0);
    }
    '''

    def __init__(self, width: int = 1920, height: int = 480, title: str = 'ShaderToy-like Viewer'):
        if not glfw.init():
            raise RuntimeError('glfw.init() failed')

        # Window creation
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        self.window = glfw.create_window(width, height, title, None, None)
        if not self.window:
            glfw.terminate()
            raise RuntimeError('Failed to create window')

        glfw.make_context_current(self.window)
        self.setup_quad()
        self.uniforms: Dict[str, int] = {}

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

        # Compile shaders
        vs = self._compile_shader(self.VERTEX_SRC, GL.GL_VERTEX_SHADER)
        fs = self._compile_shader(fs_src, GL.GL_FRAGMENT_SHADER)
        self.program = self._link_program(vs, fs)

        # Get uniform locations
        uniform_names = [
            'iResolution', 'iTime', 'iTimeDelta', 'iFrameRate', 'iFrame',
            'iMouse', 'iDate', 'iSampleRate'
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
            log = GL.glGetShaderInfoLog(shader).decode('utf-8')
            raise RuntimeError('Shader compile error:\n' + log)
        return shader

    def _link_program(self, vs: int, fs: int) -> int:
        prog = GL.glCreateProgram()
        GL.glAttachShader(prog, vs)
        GL.glAttachShader(prog, fs)
        GL.glLinkProgram(prog)
        status = GL.glGetProgramiv(prog, GL.GL_LINK_STATUS)
        if not status:
            log = GL.glGetProgramInfoLog(prog).decode('utf-8')
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
        GL.glClearColor(0.0, 0.0, 0.0, 1.0)
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
    VERTEX_SRC = '''#version 330 core
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

        # Compile shaders
        vs = self._compile_shader(self.VERTEX_SRC, GL.GL_VERTEX_SHADER)
        fs = self._compile_shader(fs_src, GL.GL_FRAGMENT_SHADER)
        self.program = self._link_program(vs, fs)

        # Get uniform locations
        uniform_names = [
            'iResolution', 'iTime', 'iTimeDelta', 'iFrameRate', 'iFrame',
            'iMouse', 'iDate', 'iSampleRate'
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
            log = GL.glGetShaderInfoLog(shader).decode('utf-8')
            raise RuntimeError('Shader compile error:\n' + log)
        return shader

    def _link_program(self, vs: int, fs: int) -> int:
        prog = GL.glCreateProgram()
        GL.glAttachShader(prog, vs)
        GL.glAttachShader(prog, fs)
        GL.glLinkProgram(prog)
        if not GL.glGetProgramiv(prog, GL.GL_LINK_STATUS):
            log = GL.glGetProgramInfoLog(prog).decode('utf-8')
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