"""
Backup of original app.py prior to UI refactor.
"""
import os
import sys
import traceback
from pathlib import Path
import multiprocessing

from PyQt5.QtCore import QObject, pyqtSlot, QUrl, QThread, pyqtSignal, Qt
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QSplitter, QFileDialog, QListWidget,
                             QListWidgetItem)

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shadertoy.audio import AudioSource
from WebEngine.visualizer import VisualizerWidget
from shadertoy.__main__ import ShaderToyApp

# Get the directory of the current script
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SHADER_DIR = os.path.join(Path(CURRENT_DIR).parent, "shaders")

class AudioThread(QThread):
    """
    Runs audio capture and FFT processing in a separate thread.
    Emits the raw texture data for the visualizer.
    """
    newData = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.audio = None
        self.is_running = False

    def run(self):
        try:
            self.audio = AudioSource()
            self.audio.start_capture()
            self.is_running = True
            print("[AudioThread] Audio capture started.")
        except Exception as e:
            print(f"[AudioThread] Error starting audio capture: {e}")
            traceback.print_exc()
            self.is_running = False
            return

        while self.is_running:
            try:
                self.audio.update()
                texture_data = self.audio.get_texture_data()
                if texture_data is not None:
                    self.newData.emit(texture_data)
            except Exception as e:
                print(f"[AudioThread] Error during update: {e}")
            self.msleep(10) # ~100 FPS update rate, adjust as needed

    def stop(self):
        print("[AudioThread] Stopping...")
        self.is_running = False
        if self.audio:
            self.audio.stop_capture()
        self.wait()
        print("[AudioThread] Stopped.")

class Backend(QObject):
    """
    Backend object for JavaScript communication.
    Handles interactions from the web UI.
    """
    shaderChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent

    @pyqtSlot(str)
    def on_shader_selected(self, shader_name):
        """Called when a shader is selected in the web UI."""
        print(f"[Backend] Shader selected from web UI: {shader_name}")
        shader_path = os.path.join(SHADER_DIR, shader_name)
        if os.path.exists(shader_path):
            self.shaderChanged.emit(shader_path)
        else:
            print(f"[Backend] Error: Shader file not found at '{shader_path}'")
    
    @pyqtSlot()
    def request_shader_list(self):
        """Scans the shader directory and sends the list to the frontend."""
        try:
            shaders = [f for f in os.listdir(SHADER_DIR) if f.endswith(('.glsl', '.frag'))]
            print(f"[Backend] Found shaders: {shaders}")
            # Call the JavaScript function to populate the UI
            self.main_window.web_view.page().runJavaScript(f"setShaderList({shaders})")
        except Exception as e:
            print(f"[Backend] Error getting shader list: {e}")

    @pyqtSlot()
    def on_apply_clicked(self):
        """
        处理 'Apply' 按钮点击事件，在一个新进程中启动无边框窗口。
        """
        if not self.main_window.current_shader_path:
            print("[Backend] No shader selected to apply.")
            return
        
        print(f"[Backend] Applying shader '{self.main_window.current_shader_path}' to borderless window.")
        
        # 使用多进程以避免阻塞PyQt事件循环和处理OpenGL上下文冲突
        p = multiprocessing.Process(
            target=run_shader_viewer, 
            args=(self.main_window.current_shader_path, 1280, 200) #可以自定义分辨率
        )
        p.start()
        # 我们不调用 p.join()，让它成为一个独立的窗口

    @pyqtSlot(str)
    def on_chat_message_sent(self, message: str):
        """处理从前端发送的聊天消息 (占位符)"""
        print(f"[Backend] Chat message received: {message}")
        
        # 模拟AI回复
        reply = f"我已经收到你的消息 '{message}'。但我还没有真正的智能。"
        self.main_window.web_view.page().runJavaScript(f"add_ai_message('{reply}')")

def run_shader_viewer(shader_path, width, height):
    """
    在一个独立的进程中运行基于GLFW的无边框ShaderViewer。
    直接调用 shadertoy.__main__ 中的 ShaderToyApp。
    """
    try:
        # 创建 ShaderToyApp 实例，并请求无边框窗口
        app = ShaderToyApp(shader_path, width, height, borderless=True)
        # 运行主循环
        app.run()
    except Exception as e:
        print(f"[ShaderViewerProcess] Error: {e}")
        traceback.print_exc()

class MainWindow(QMainWindow):
    """
    The main application window, containing the visualizer and control panel.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Real-time Audio Visualizer")
        self.setGeometry(100, 100, 1280, 720)
        self.current_shader_path = None # 用于存储当前选择的着色器路径
        self.shader_viewer_process = None # 用于跟踪独立窗口进程

        # --- Central Widget and Layout ---
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # --- OpenGL Visualizer Widget ---
        self.visualizer = VisualizerWidget(self)
        
        # --- Control Panel (Web View) ---
        self.web_view = QWebEngineView()
        self.web_channel = QWebChannel()
        self.backend = Backend(self)
        self.web_channel.registerObject("backend", self.backend)
        self.web_view.page().setWebChannel(self.web_channel)
        
        # Load the HTML file for the control panel
        control_html_path = os.path.join(CURRENT_DIR, "html", "frontend.html")
        self.web_view.setUrl(QUrl.fromLocalFile(control_html_path))

        # --- Splitter to manage layout ---
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.visualizer)
        splitter.addWidget(self.web_view)
        splitter.setSizes([900, 380]) # Initial size distribution
        layout.addWidget(splitter)

        # --- Audio Processing Thread ---
        self.audio_thread = AudioThread(self)
        self.audio_thread.newData.connect(self.update_audio_texture)
        
        # --- Connect signals for safe initialization ---
        self.backend.shaderChanged.connect(self.on_shader_changed)
        self.visualizer.initialized.connect(self.on_visualizer_initialized)

    @pyqtSlot(str)
    def on_shader_changed(self, shader_path: str):
        """当着色器改变时，加载它并存储路径"""
        self.current_shader_path = shader_path
        self.visualizer.load_shader(shader_path)

    @pyqtSlot()
    def on_visualizer_initialized(self):
        """
        Called when the VisualizerWidget's OpenGL context is ready.
        """
        print("[MainWindow] Visualizer initialized. Setting up audio texture and loading shader.")
        # Use a dummy size for now, AudioSource will provide the real size
        fft_size = self.audio_thread.audio.fft_size if self.audio_thread.audio else 512
        self.visualizer.setup_audio_texture(fft_size)
        
        # Load initial shader
        initial_shader = os.path.join(SHADER_DIR, "test.glsl")
        if os.path.exists(initial_shader):
            self.on_shader_changed(initial_shader) # 使用新的槽来加载
        else:
            print(f"Warning: Initial shader '{initial_shader}' not found.")

        # Now it's safe to start the audio thread
        self.audio_thread.start()

    @pyqtSlot(object)
    def update_audio_texture(self, texture_data):
        """Updates the iChannel0 texture with new data from the audio thread."""
        self.visualizer.update_channel_texture_data(0, texture_data)

    def closeEvent(self, event):
        """Ensures threads and processes are stopped cleanly on exit."""
        print("[MainWindow] Closing application...")
        self.audio_thread.stop()
        # 如果需要，可以在这里终止独立窗口进程
        if self.shader_viewer_process and self.shader_viewer_process.is_alive():
            self.shader_viewer_process.terminate()
        event.accept()

def main():
    """Application entry point."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
