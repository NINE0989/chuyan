"""
Minimal ShaderToy-like GLSL viewer.

Usage: python viewer.py [shader_file]

Dependencies: glfw, PyOpenGL, numpy, sounddevice

This loader provides the following uniforms to fragment shaders:
 - vec3 iResolution: (width, height, 0)
 - float iTime: seconds since start
 - sampler2D iChannel0: 1D audio FFT stored as a 2D texture (height=1)

The program will attempt to read audio using the existing `audio_recorder.py` if present
or fallback to `sounddevice` for a quick demo.
"""
import os
import sys
import time
import ctypes

import numpy as np
import glfw
from OpenGL import GL

BASE_DIR = os.path.dirname(__file__)
DEFAULT_SHADER = os.path.join(BASE_DIR, 'shaders/test.glsl')


def compile_shader(src, shader_type):
    shader = GL.glCreateShader(shader_type)
    GL.glShaderSource(shader, src)
    GL.glCompileShader(shader)
    status = GL.glGetShaderiv(shader, GL.GL_COMPILE_STATUS)
    if not status:
        log = GL.glGetShaderInfoLog(shader).decode('utf-8')
        raise RuntimeError('Shader compile error:\n' + log)
    return shader


def link_program(vs, fs):
    prog = GL.glCreateProgram()
    GL.glAttachShader(prog, vs)
    GL.glAttachShader(prog, fs)
    GL.glLinkProgram(prog)
    status = GL.glGetProgramiv(prog, GL.GL_LINK_STATUS)
    if not status:
        log = GL.glGetProgramInfoLog(prog).decode('utf-8')
        raise RuntimeError('Program link error:\n' + log)
    return prog


VERTEX_SRC = '''#version 330 core
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec2 aUV;
out vec2 vUV;
void main(){
    vUV = aUV;
    gl_Position = vec4(aPos, 0.0, 1.0);
}
'''


def load_fragment_shader(path):
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


class AudioFFT:
    """Provides a rolling FFT buffer and a method to get a normalized 1D FFT array.
    Falls back to generating a fake sine if no audio device available."""
    def __init__(self, size=1024):
        self.size = size
        self.fft = np.zeros(size, dtype=np.float32)
        self.t0 = time.time()
        # try to import local audio recorder
        try:
            from audio_recorder import AudioRecorder
            self.rec = AudioRecorder(rate=44100, chunk_size=4096)
            ok = self.rec.start()
            if not ok:
                self.rec = None
        except Exception:
            self.rec = None

    def update(self):
        if self.rec:
            data = self.rec.read()
            if data is None:
                return
            # stereo -> mono
            if data.ndim > 1:
                data = np.mean(data, axis=1)
            # convert to float32
            x = data.astype(np.float32)
            # window and FFT
            win = np.hanning(len(x))
            spec = np.abs(np.fft.rfft(x * win))
            spec = spec[:self.size]
            spec = spec / (np.max(spec) + 1e-9)
            self.fft[:len(spec)] = spec
        else:
            # synthetic animated FFT for demo
            t = time.time() - self.t0
            freqs = np.linspace(0, 1.0, self.size)
            spec = 0.5 + 0.5*np.sin(2.0*np.pi*(freqs*10.0 - t*1.5))
            self.fft = np.clip(spec, 0.0, 1.0).astype(np.float32)

    def get_texture(self):
        # return as 2D array height=1, width=size, RGBA float32
        arr = np.zeros((1, self.size, 4), dtype=np.float32)
        arr[0, :, 0] = self.fft
        return arr


def run(shader_path):
    if not glfw.init():
        raise RuntimeError('glfw.init() failed')

    width, height = 800, 600
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    win = glfw.create_window(width, height, 'ShaderToy-like Viewer', None, None)
    if not win:
        glfw.terminate()
        raise RuntimeError('Failed to create window')

    glfw.make_context_current(win)

    # compile shaders
    vs = compile_shader(VERTEX_SRC, GL.GL_VERTEX_SHADER)
    fs_src = load_fragment_shader(shader_path)
    fs = compile_shader(fs_src, GL.GL_FRAGMENT_SHADER)
    prog = link_program(vs, fs)

    # fullscreen quad
    quad = np.array([
        -1.0, -1.0, 0.0, 0.0,
         1.0, -1.0, 1.0, 0.0,
        -1.0,  1.0, 0.0, 1.0,
         1.0,  1.0, 1.0, 1.0,
    ], dtype=np.float32)

    vao = GL.glGenVertexArrays(1)
    GL.glBindVertexArray(vao)
    vbo = GL.glGenBuffers(1)
    GL.glBindBuffer(GL.GL_ARRAY_BUFFER, vbo)
    GL.glBufferData(GL.GL_ARRAY_BUFFER, quad.nbytes, quad, GL.GL_STATIC_DRAW)
    GL.glEnableVertexAttribArray(0)
    GL.glVertexAttribPointer(0, 2, GL.GL_FLOAT, GL.GL_FALSE, 16, ctypes.c_void_p(0))
    GL.glEnableVertexAttribArray(1)
    GL.glVertexAttribPointer(1, 2, GL.GL_FLOAT, GL.GL_FALSE, 16, ctypes.c_void_p(8))

    # audio texture
    fft_src = AudioFFT(size=1024)
    tex = GL.glGenTextures(1)
    GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)

    start_time = time.time()

    GL.glUseProgram(prog)
    loc_iResolution = GL.glGetUniformLocation(prog, 'iResolution')
    loc_iTime = GL.glGetUniformLocation(prog, 'iTime')
    loc_iChannel0 = GL.glGetUniformLocation(prog, 'iChannel0')

    while not glfw.window_should_close(win):
        glfw.poll_events()
        w, h = glfw.get_framebuffer_size(win)
        GL.glViewport(0, 0, w, h)

        # update audio
        fft_src.update()
        tex_data = fft_src.get_texture()
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA32F, fft_src.size, 1, 0, GL.GL_RGBA, GL.GL_FLOAT, tex_data)

        GL.glClearColor(0.0, 0.0, 0.0, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)

        GL.glUseProgram(prog)
        GL.glUniform3f(loc_iResolution, float(w), float(h), 0.0)
        GL.glUniform1f(loc_iTime, float(time.time() - start_time))
        if loc_iChannel0 != -1:
            GL.glActiveTexture(GL.GL_TEXTURE0)
            GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
            GL.glUniform1i(loc_iChannel0, 0)

        GL.glBindVertexArray(vao)
        GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)

        glfw.swap_buffers(win)

    glfw.terminate()


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SHADER
    run(path)
