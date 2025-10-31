"""
Main application entry point for the PyQt5-based audio visualizer.
"""
import os
import sys
import traceback
from pathlib import Path

import numpy as np
import OpenGL.GL as GL
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

class MainWindow(QMainWindow):
    """
    The main application window, containing the visualizer and control panel.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Real-time Audio Visualizer")
        self.setGeometry(100, 100, 1280, 720)

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
        self.backend.shaderChanged.connect(self.visualizer.load_shader)
        self.visualizer.initialized.connect(self.on_visualizer_initialized)

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
            self.visualizer.load_shader(initial_shader)
        else:
            print(f"Warning: Initial shader '{initial_shader}' not found.")

        # Now it's safe to start the audio thread
        self.audio_thread.start()

    @pyqtSlot(object)
    def update_audio_texture(self, texture_data):
        """Updates the iChannel0 texture with new data from the audio thread."""
        self.visualizer.update_channel_texture_data(0, texture_data)

    def closeEvent(self, event):
        """Ensures the audio thread is stopped cleanly on exit."""
        print("[MainWindow] Closing application...")
        self.audio_thread.stop()
        event.accept()

def main():
    """Application entry point."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
