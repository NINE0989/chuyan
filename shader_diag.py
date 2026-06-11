"""GLSL 编译诊断脚本 —— 运行后把全部输出贴回来。"""
import sys, os, shutil
from pathlib import Path

# 确保路径正确
sys.path.insert(0, str(Path(__file__).resolve().parent))

# 清缓存
for p in Path('.').rglob('__pycache__'):
    shutil.rmtree(p, ignore_errors=True)

print("=" * 50)
print("1. stars.glsl 文件诊断")
print("=" * 50)
p = Path("shaders/stars.glsl")
raw = p.read_bytes()
print(f"文件大小: {len(raw)} bytes")
print(f"前60字节 hex: {raw[:60].hex()}")
print(f"BOM: {raw[:3] == b'\xef\xbb\xbf'}")
cr_count = raw.count(b'\r')
lf_count = raw.count(b'\n')
crlf_count = raw.count(b'\r\n')
print(f"CR 数量: {cr_count}, LF 数量: {lf_count}, CRLF 对数量: {crlf_count}")

# 前5行原始内容
text = raw.decode("utf-8", errors="replace")
for i, line in enumerate(text.split("\n")[:5]):
    print(f"  L{i} (repr): {repr(line)[:80]}")

# 检查 #version
first = text.split("\n")[0]
print(f"首行 hex: {first.encode().hex()}")
print(f"首行 repr: {repr(first)}")

print()
print("=" * 50)
print("2. GL 上下文诊断")
print("=" * 50)
import glfw
from OpenGL import GL

if not glfw.init():
    print("GLFW.init 失败!")
    sys.exit(1)

glfw.window_hint(glfw.CLIENT_API, glfw.OPENGL_API)
glfw.window_hint(glfw.CONTEXT_CREATION_API, glfw.NATIVE_CONTEXT_API)
glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
glfw.window_hint(glfw.VISIBLE, 0)

window = glfw.create_window(64, 64, "diag", None, None)
if not window:
    print("窗口创建失败！尝试无 hint...")
    glfw.default_window_hints()
    glfw.window_hint(glfw.VISIBLE, 0)
    window = glfw.create_window(64, 64, "diag2", None, None)
    if not window:
        print("完全无法创建 GL 上下文")
        glfw.terminate()
        sys.exit(1)

glfw.make_context_current(window)

gl_ver = GL.glGetString(GL.GL_VERSION)
if isinstance(gl_ver, bytes):
    gl_ver = gl_ver.decode()
glsl_ver = GL.glGetString(GL.GL_SHADING_LANGUAGE_VERSION)
if isinstance(glsl_ver, bytes):
    glsl_ver = glsl_ver.decode()
renderer = GL.glGetString(GL.GL_RENDERER)
if isinstance(renderer, bytes):
    renderer = renderer.decode()

print(f"  GL 版本: {gl_ver}")
print(f"  GLSL 版本: {glsl_ver}")
print(f"  渲染器: {renderer}")
print(f"  是否 ES: {'OpenGL ES' in gl_ver}")

print()
print("=" * 50)
print("3. 实际编译测试")
print("=" * 50)

# 读文件
fs_src = p.read_text(encoding="utf-8", errors="replace")
print(f"  读取后首行 repr: {repr(fs_src.split(chr(10))[0])}")

# 适配逻辑
fs_src = fs_src.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
print(f"  清理后首行 repr: {repr(fs_src.split(chr(10))[0])}")

if "OpenGL ES" in gl_ver:
    print("  >>> 检测到 ES，执行适配 <<<")
    fs_src = fs_src.replace("#version 330", "#version 300 es")
    if "precision" not in fs_src[:300]:
        idx = fs_src.find("#version")
        eol = fs_src.find("\n", idx)
        fs_src = fs_src[:eol+1] + "precision mediump float;\n" + fs_src[eol+1:]
    print(f"  适配后首行: {repr(fs_src.split(chr(10))[0][:60])}")
else:
    print("  桌面 GL，无需适配")

# 编译
vertex_src = "#version 330\nlayout(location=0) in vec2 aPos;layout(location=1) in vec2 aUV;out vec2 vUV;void main(){vUV=aUV;gl_Position=vec4(aPos,0.0,1.0);}"
if "OpenGL ES" in gl_ver:
    vertex_src = vertex_src.replace("#version 330", "#version 300 es")
    vertex_src = vertex_src.replace("#version 300 es", "#version 300 es\nprecision mediump float;")

vs = GL.glCreateShader(GL.GL_VERTEX_SHADER)
GL.glShaderSource(vs, vertex_src)
GL.glCompileShader(vs)
vs_ok = GL.glGetShaderiv(vs, GL.GL_COMPILE_STATUS)
vs_log = GL.glGetShaderInfoLog(vs)
if isinstance(vs_log, bytes):
    vs_log = vs_log.decode()
if vs_ok:
    print(f"  顶点着色器: OK")
else:
    print(f"  顶点着色器: FAIL\n{vs_log}")

fs = GL.glCreateShader(GL.GL_FRAGMENT_SHADER)
GL.glShaderSource(fs, fs_src)
GL.glCompileShader(fs)
fs_ok = GL.glGetShaderiv(fs, GL.GL_COMPILE_STATUS)
fs_log = GL.glGetShaderInfoLog(fs)
if isinstance(fs_log, bytes):
    fs_log = fs_log.decode()
if fs_ok:
    print(f"  片段着色器: OK")
else:
    print(f"  片段着色器: FAIL\n{fs_log}")

GL.glDeleteShader(vs)
GL.glDeleteShader(fs)
glfw.destroy_window(window)
glfw.terminate()

print()
print("=" * 50)
print("诊断完成 —— 请把以上全部输出贴回来")
print("=" * 50)
