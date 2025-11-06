"""Main window module tying pages together."""
from __future__ import annotations
import os
from PyQt5.QtWidgets import QMainWindow, QStackedWidget

from .main_page import MainPage
from .shader_page import ShaderPage
from ..paths import SHADERS_DIR
from ..launch import launch_borderless_process

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Shader 界面演示 (AI 集成)")
        self.setGeometry(200, 100, 1280, 720)
        self.shader_library: list[str] = []
        self.stack = QStackedWidget(); self.setCentralWidget(self.stack)
        self._viewer_processes = []
        self.main_page = MainPage(self.show_shader_page, self.shader_library, self.launch_borderless_shader)
        self.shader_page = ShaderPage(self.show_main_page, self.shader_library)
        self.stack.addWidget(self.main_page); self.stack.addWidget(self.shader_page)
        self.shader_page.shaderChosen.connect(self.on_shader_selected)

    # Navigation
    def show_shader_page(self):
        self.stack.setCurrentWidget(self.shader_page)

    def show_main_page(self):
        self.stack.setCurrentWidget(self.main_page)

    # Events
    def on_shader_selected(self, path: str):
        if not os.path.exists(path):
            print(f"[MainWindow] 文件不存在: {path}"); return
        try:
            self.main_page.load_from_file(path)
            self.show_main_page()
        except Exception as e:  # noqa: BLE001
            print(f"[MainWindow] 加载 Shader 失败: {e}")

    # Launch external
    def launch_borderless_shader(self, shader_code: str, source_path: str | None):
        try:
            p = launch_borderless_process(shader_code, source_path)
            self._viewer_processes.append(p)
            self.main_page._add_ai_message("🚀 已启动无边框预览窗口")
        except Exception as e:  # noqa: BLE001
            self.main_page._add_ai_message(f"❌ 无法启动无边框窗口: {e}")
