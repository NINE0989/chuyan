"""ShaderPage module: lists available shader files and emits selection signal."""
from __future__ import annotations
import os
import time
from typing import List
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QScrollArea, QGridLayout
)
from PyQt5.QtGui import QFont

from ..paths import SHADERS_DIR

class ShaderPage(QWidget):
    shaderChosen = pyqtSignal(str)

    def __init__(self, switch_to_main, shader_library: List[str]):
        super().__init__()
        self.switch_to_main = switch_to_main
        self.shader_library = shader_library
        self._build_ui()

    def _build_ui(self):
        top_bar = QFrame(); top_bar.setStyleSheet("background-color: #2b6dad; color: white;"); top_bar.setFixedHeight(60)
        title = QLabel("Shader库"); title.setFont(QFont("Arial", 14, QFont.Bold)); title.setStyleSheet("color: white; margin-left: 10px;")
        btn_close = QPushButton("×"); btn_close.setStyleSheet("""
            QPushButton { background-color: white; color: #2b6dad; font-weight: bold; padding: 6px 12px; border-radius: 8px; }
            QPushButton:hover { background-color: #e0e0e0; }
        """); btn_close.clicked.connect(self.switch_to_main)
        top_layout = QHBoxLayout(); top_layout.addWidget(title); top_layout.addStretch(); top_layout.addWidget(btn_close); top_layout.setContentsMargins(10,0,10,0); top_bar.setLayout(top_layout)

        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setStyleSheet("background-color: #f0f0f0; border: none;")
        container = QWidget(); self.grid_layout = QGridLayout(container); self.grid_layout.setSpacing(20); self.grid_layout.setContentsMargins(30,30,30,30); self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.scroll.setWidget(container)
        layout = QVBoxLayout(self); layout.addWidget(top_bar); layout.addWidget(self.scroll); self.setLayout(layout)

    def _list_shader_files(self):
        try:
            files = [f for f in os.listdir(SHADERS_DIR) if f.lower().endswith((".glsl", ".frag"))]
            files.sort(key=lambda n: (SHADERS_DIR / n).stat().st_mtime, reverse=True)
            return files
        except Exception as e:  # noqa: BLE001
            print(f"[ShaderPage] 列表读取失败: {e}"); return []

    def showEvent(self, event):  # noqa: D401
        for i in reversed(range(self.grid_layout.count())):
            w = self.grid_layout.itemAt(i).widget()
            if w: w.deleteLater()
        shader_files = self._list_shader_files()
        if not shader_files:
            label = QLabel("目录中暂无 Shader 文件"); label.setAlignment(Qt.AlignCenter); label.setFont(QFont("Arial", 12))
            self.grid_layout.addWidget(label,0,0); return
        cols = 4
        for idx, filename in enumerate(shader_files):
            r, c = divmod(idx, cols)
            self.grid_layout.addWidget(self._create_shader_card(filename), r, c, Qt.AlignTop | Qt.AlignLeft)

    def _create_shader_card(self, filename: str):
        full_path = SHADERS_DIR / filename
        try:
            mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(full_path.stat().st_mtime))
        except Exception:
            mtime = "--"
        card = QFrame(); card.setStyleSheet("""
            QFrame { background-color: #ffffff; border-radius: 8px; border: 2px solid #e0e0e0; }
            QFrame:hover { border: 2px solid #2b6dad; }
        """); card.setFixedSize(250, 190)
        layout = QVBoxLayout(card); layout.setContentsMargins(10,10,10,10); layout.setSpacing(6)
        preview = QLabel("🖼️"); preview.setAlignment(Qt.AlignCenter); preview.setStyleSheet("QLabel { background-color: #e6e6e6; border-radius: 6px; font-size:28px; }"); preview.setFixedHeight(100)
        name_label = QLabel(filename); name_label.setFont(QFont("Arial", 10, QFont.Bold)); name_label.setStyleSheet("color: #333333;"); name_label.setWordWrap(True)
        date_label = QLabel(mtime); date_label.setFont(QFont("Arial", 9)); date_label.setStyleSheet("color: #666666;")
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                head = ''.join([next(f) for _ in range(5)])
            card.setToolTip(head)
        except Exception:
            pass
        layout.addWidget(preview); layout.addWidget(name_label); layout.addWidget(date_label); layout.addStretch()
        def _on_click(ev, p=str(full_path)):
            try: self.shaderChosen.emit(p)
            except Exception as e: print(f"[ShaderPage] 点击事件出错: {e}")
            ev.accept()
        card.mousePressEvent = _on_click  # type: ignore
        return card
