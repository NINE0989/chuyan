"""MainPage module: chat + AI generation + shader preview logic."""
from __future__ import annotations
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from PyQt5.QtCore import QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QScrollArea,
    QLineEdit, QTextEdit, QSizePolicy, QFileDialog, QCheckBox
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

try:  # local import preference
    from visualizer import VisualizerWidget  # type: ignore
except Exception:
    from WebEngine.visualizer import VisualizerWidget  # type: ignore

from WebEngine.ai_service import AIService
from ..paths import SHADERS_DIR

# ---------------- Data & Worker -----------------
@dataclass
class GenerationResult:
    success: bool
    code: str = ""
    error: str = ""

class GenerationWorker(QThread):
    finished = pyqtSignal(object)  # Emits GenerationResult

    def __init__(self, service: AIService, prompt: str, is_adjust: bool):
        super().__init__()
        self.service = service
        self.prompt = prompt
        self.is_adjust = is_adjust

    def run(self):  # pragma: no cover - thread
        if self.service is None:
            self.finished.emit(GenerationResult(False, error="AIService 未初始化"))
            return
        try:
            code = self.service.generate(self.prompt, adjust=self.is_adjust)
            if not code:
                self.finished.emit(GenerationResult(False, error="未返回代码"))
            else:
                self.finished.emit(GenerationResult(True, code=code))
        except Exception as e:  # noqa: BLE001
            self.finished.emit(GenerationResult(False, error=str(e)))

# ---------------- UI Elements -----------------
class ChatBubble(QFrame):
    def __init__(self, text: str, is_user: bool = False):
        super().__init__()
        self.setStyleSheet("border: none;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        avatar = QLabel("😎" if is_user else "AI")
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setFixedSize(40, 40)
        if is_user:
            avatar.setStyleSheet("QLabel { font-size: 22px; }")
        else:
            avatar.setStyleSheet("QLabel { background-color: #1c1c1c; color: white; border-radius: 20px; font-size: 16px; }")

        bubble_color = "#bfbfbf" if is_user else "#efefef"
        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bubble.setStyleSheet(f"""
            background-color: {bubble_color};
            border-radius: 12px;
            padding: 10px 14px;
            font-size: 14px;
            max-width: 280px;
        """)

        if is_user:
            layout.addStretch(); layout.addWidget(bubble); layout.addWidget(avatar)
        else:
            layout.addWidget(avatar); layout.addWidget(bubble); layout.addStretch()

# ---------------- Main Page -----------------
class MainPage(QWidget):
    def __init__(self, switch_to_shader: Callable[[], None], shader_library: list, launch_borderless_cb: Optional[Callable[[str, Optional[str]], None]] = None):
        super().__init__()
        self.switch_to_shader = switch_to_shader
        self.shader_library = shader_library
        self.launch_borderless_cb = launch_borderless_cb

        self.current_shader = "// GLSL shader code will appear here"
        self.current_shader_path: Optional[str] = None
        self.ai_service: Optional[AIService] = None
        self.has_generated_once = False
        self.current_worker: Optional[GenerationWorker] = None
        self.preview_ready = False
        self._pending_code: Optional[str] = None
        self.hot_reload_enabled = False
        self.reload_timer = None  # type: Optional[QTimer]
        self.is_dirty = False
        self.attach_code_enabled = False

        self._build_ui()
        self._init_ai()

    # --- UI construction ---
    def _build_ui(self):
        top_bar = QFrame(); top_bar.setStyleSheet("background-color: #2b6dad; color: white;"); top_bar.setFixedHeight(60)
        self.title_label = QLabel("NAME"); self.title_label.setFont(QFont("Arial", 14)); self.title_label.setStyleSheet("color: white;")
        btn_shader = QPushButton("Shader库"); btn_shader.setStyleSheet("""
            QPushButton { background-color: white; color: #2b6dad; font-weight: bold; padding: 6px 12px; border-radius: 8px; }
            QPushButton:hover { background-color: #e0e0e0; }
        """); btn_shader.clicked.connect(self.switch_to_shader)
        top_layout = QHBoxLayout(); top_layout.addWidget(QLabel("😎")); top_layout.addWidget(self.title_label)
        # New Session button
        self.new_session_btn = QPushButton("新会话")
        self.new_session_btn.setStyleSheet("""
            QPushButton { background-color: #1c1c1c; color: white; border-radius: 6px; padding: 6px 10px; }
            QPushButton:hover { background-color: #333333; }
        """)
        self.new_session_btn.clicked.connect(self.new_session)
        top_layout.addWidget(self.new_session_btn)
        top_layout.addStretch(); top_layout.addWidget(btn_shader); top_bar.setLayout(top_layout)

        main_layout = QHBoxLayout(); main_layout.setContentsMargins(0,0,0,0)
        chat_area = QVBoxLayout(); chat_area.setContentsMargins(15,15,15,15)

        self.chat_scroll = QScrollArea(); self.chat_scroll.setWidgetResizable(True)
        self.chat_widget = QWidget(); self.chat_layout = QVBoxLayout(self.chat_widget); self.chat_layout.addStretch()
        self.chat_scroll.setWidget(self.chat_widget); self.chat_scroll.setStyleSheet("background-color: #d9d9d9; border-radius: 8px;")
        chat_area.addWidget(self.chat_scroll, 1)

        input_layout = QHBoxLayout(); self.input_box = QLineEdit(); self.input_box.setPlaceholderText("请输入您的需求……")
        self.input_box.setStyleSheet("QLineEdit { background-color: white; border: none; border-radius: 6px; padding: 8px; font-size: 14px; }")
        # Attach code checkbox
        self.attach_code_cb = QCheckBox("附加代码")
        self.attach_code_cb.setToolTip("开启后，每次对话会附加当前代码区域内容供AI参考（自动截断过长片段）")
        self.attach_code_cb.stateChanged.connect(self._toggle_attach_code)
        self.attach_code_cb.setStyleSheet("QCheckBox { color: black; } QCheckBox::indicator { width:16px; height:16px; }")
        send_btn = QPushButton("发送"); send_btn.setStyleSheet("""
            QPushButton { background-color: #1c1c1c; color: white; border-radius: 4px; padding: 8px 16px; }
            QPushButton:hover { background-color: #333333; }
        """); send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(self.input_box,1); input_layout.addWidget(self.attach_code_cb); input_layout.addWidget(send_btn); chat_area.addLayout(input_layout)

        right_panel = QVBoxLayout(); right_panel.setContentsMargins(10,15,15,15); right_panel.setSpacing(10)
        self.shader_container = QFrame(); self.shader_container.setStyleSheet("QFrame { background-color: #e0e0e0; border-radius: 8px; }")
        self.shader_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding); self.shader_container.setFixedHeight(360)
        shader_layout = QVBoxLayout(self.shader_container); shader_layout.setContentsMargins(0,0,0,0); shader_layout.setSpacing(0)

        self.preview_widget = VisualizerWidget(self.shader_container)
        self.preview_widget.initialized.connect(self._on_preview_initialized)
        if hasattr(self.preview_widget, 'compileError'):
            self.preview_widget.compileError.connect(self._on_compile_error)
        shader_layout.addWidget(self.preview_widget, 1)

        shader_bottom_bar = QFrame(); shader_bottom_bar.setStyleSheet("background-color: #2b6dad; border-radius: 0 0 8px 8px;"); shader_bottom_bar.setFixedHeight(50)
        bottom_bar_layout = QHBoxLayout(shader_bottom_bar); bottom_bar_layout.setContentsMargins(10,0,10,0)
        self.heart_label = QPushButton("♡"); self.heart_label.setStyleSheet("QPushButton { color: white; font-size: 22px; background: transparent; border: none; }"); self.heart_label.clicked.connect(self.toggle_favorite)
        bottom_bar_layout.addWidget(self.heart_label); bottom_bar_layout.addStretch()
        # Save button
        self.save_btn = QPushButton("保存"); self.save_btn.setFixedSize(70,30); self.save_btn.setStyleSheet("""
            QPushButton { background-color: #1c1c1c; color: white; border-radius: 12px; font-weight: bold; }
            QPushButton:hover { background-color: #333333; }
        """); self.save_btn.clicked.connect(self.save_shader); bottom_bar_layout.addWidget(self.save_btn)

        self.apply_btn = QPushButton("应用"); self.apply_btn.setFixedSize(80,30); self.apply_btn.setStyleSheet("""
            QPushButton { background-color: #1c1c1c; color: white; border-radius: 12px; font-weight: bold; }
            QPushButton:hover { background-color: #333333; }
        """); self.apply_btn.clicked.connect(self.apply_shader); bottom_bar_layout.addWidget(self.apply_btn)
        shader_layout.addWidget(shader_bottom_bar)

        self.code_preview = QTextEdit(); self.code_preview.setReadOnly(False); self.code_preview.setStyleSheet("""
            QTextEdit { background-color: black; color: white; font-family: Consolas; font-size: 13px; border-radius: 8px; }
        """)
        self.code_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.code_preview.textChanged.connect(self._on_code_changed)

        # Hot reload controls (button placed in shader bottom bar later)
        self.hot_reload_btn = QPushButton("热重载:关")
        self.hot_reload_btn.setFixedSize(90,30)
        self.hot_reload_btn.setStyleSheet("""
            QPushButton { background-color: #1c1c1c; color: white; border-radius: 10px; }
            QPushButton:hover { background-color: #333333; }
        """)
        self.hot_reload_btn.clicked.connect(self._toggle_hot_reload)

        right_panel.addWidget(self.shader_container); right_panel.addWidget(self.code_preview)
        main_layout.addLayout(chat_area,2); main_layout.addLayout(right_panel,3)
        root_layout = QVBoxLayout(); root_layout.addWidget(top_bar); root_layout.addLayout(main_layout); self.setLayout(root_layout)

        # Insert hot reload button into shader bottom bar (after heart, before stretch if available)
        try:
            # shader_layout local scope ended, so locate bottom bar layout via children
            # We added bottom_bar_layout earlier; fetch via findChildren
            for frame in self.findChildren(QFrame):
                if frame.maximumHeight() == 50 and frame.minimumHeight() == 50:  # heuristic for shader_bottom_bar
                    layout = frame.layout()
                    if layout and self.hot_reload_btn not in [layout.itemAt(i).widget() for i in range(layout.count()) if layout.itemAt(i).widget()]:
                        layout.insertWidget(1, self.hot_reload_btn)
                        break
        except Exception:
            pass

    # --- AI init ---
    def _init_ai(self):
        try:
            self.ai_service = AIService()
            self._add_ai_message("🤖 AI 已直接连接，输入描述生成 Shader。后续消息将进行微调。")
        except Exception as e:  # noqa: BLE001
            self.ai_service = None
            self._add_ai_message(f"❌ AI初始化失败: {e}")

    # --- Chat helpers ---
    def _add_ai_message(self, text: str):
        self.chat_layout.insertWidget(self.chat_layout.count()-1, ChatBubble(text, is_user=False))

    def _add_user_message(self, text: str):
        self.chat_layout.insertWidget(self.chat_layout.count()-1, ChatBubble(text, is_user=True))

    # --- Interaction ---
    def send_message(self):
        text = self.input_box.text().strip()
        if not text:
            return
        # Optionally append current code context
        if self.attach_code_enabled and self.current_shader and not self.current_shader.startswith("// GLSL shader code will appear here"):
            code = self.current_shader.strip()
            # Limit to avoid overly large prompts
            max_chars = 6000
            if len(code) > max_chars:
                code = code[:max_chars] + "\n/* ...代码已截断 ... */"
            # Wrap for clarity
            text += "\n\n当前代码如下:\n```glsl\n" + code + "\n```\n请基于上述代码进行回答或改进。"
        self._add_user_message(text); self.input_box.clear()
        if self.ai_service is None:
            self._add_ai_message("AI 未就绪，无法生成。"); return
        if self.current_worker and self.current_worker.isRunning():
            self._add_ai_message("⏳ 正在生成或调整，请稍候…"); return
        is_adjust = self.has_generated_once
        phase = "调整" if is_adjust else "生成"
        self._add_ai_message(f"🔄 开始{phase}，请稍候…")
        self.current_worker = GenerationWorker(self.ai_service, prompt=text, is_adjust=is_adjust)
        self.current_worker.finished.connect(self._on_generation_finished)
        self.current_worker.start()

    def _on_generation_finished(self, result: GenerationResult):
        if not result.success:
            self._add_ai_message(f"❌ 失败: {result.error}"); return
        self.has_generated_once = True
        self.current_shader = result.code
        self._add_ai_message("✅ Shader 生成完成，已加载预览，可点“应用”查看代码或“♡”收藏。")
        self.code_preview.setText(self.current_shader)
        self._auto_save_latest(); self._update_preview_from_code(); self._set_dirty(True)

    # --- New session ---
    def new_session(self):
        # Clear chat bubbles except stretch
        for i in reversed(range(self.chat_layout.count()-1)):
            item = self.chat_layout.itemAt(i)
            w = item.widget()
            if w:
                w.setParent(None)
        # Reset AI history / state
        if self.ai_service:
            try:
                self.ai_service.history.clear()
            except Exception:
                pass
        self.has_generated_once = False
        self._add_ai_message("🆕 已开始新会话。请输入新的需求。")

    # --- Hot reload logic ---
    def _toggle_hot_reload(self):
        self.hot_reload_enabled = not self.hot_reload_enabled
        self.hot_reload_btn.setText("热重载:开" if self.hot_reload_enabled else "热重载:关")
        if self.hot_reload_enabled:
            # Initialize timer if needed and trigger immediate reload
            if self.reload_timer is None:
                self.reload_timer = QTimer(self)
                self.reload_timer.setInterval(500)
                self.reload_timer.setSingleShot(True)
                self.reload_timer.timeout.connect(self._perform_hot_reload)
            # Immediate schedule
            self.reload_timer.start()
        else:
            if self.reload_timer:
                self.reload_timer.stop()

    def _on_code_changed(self):
        # Update in-memory shader text only; do not auto-save
        self.current_shader = self.code_preview.toPlainText()
        self._set_dirty(True)
        if self.hot_reload_enabled:
            if self.reload_timer is None:
                self.reload_timer = QTimer(self)
                self.reload_timer.setInterval(500)
                self.reload_timer.setSingleShot(True)
                self.reload_timer.timeout.connect(self._perform_hot_reload)
            self.reload_timer.start()  # debounce restart

    def _toggle_attach_code(self, state):
        self.attach_code_enabled = state == Qt.Checked

    def _perform_hot_reload(self):
        # Debounced call to update preview
        self._update_preview_from_code()

    # --- Save logic ---
    def save_shader(self):
        code = self.current_shader if self.current_shader is not None else ""
        if not code.strip():
            self._add_ai_message("⚠️ 没有代码可保存。")
            return
        target_path = None
        # If existing path is under shaders root (not _preview) reuse
        if self.current_shader_path:
            p = Path(self.current_shader_path)
            if p.exists() and p.is_file():
                target_path = p
        # If no existing path or existing is in _preview create new file
        if (not target_path) or ('_preview' in str(target_path.parent)):
            # Try to derive name from first comment line
            base_name = None
            first_line = (code.strip().splitlines() or [""])[0]
            if first_line.startswith("//") and ":" in first_line:
                parts = first_line[2:].strip().split(":",1)
                if len(parts)==2 and parts[0].lower().strip()=="name":
                    candidate = ''.join(ch for ch in parts[1].strip() if ch.isalnum() or ch in ('_','-')) or None
                    base_name = candidate
            if not base_name:
                base_name = time.strftime("shader_%Y%m%d_%H%M%S")
            default_filename = f"{base_name}.glsl"
            # Optional: ask user for path (Save As). If dialog canceled, fallback to auto path.
            dlg_path, _ = QFileDialog.getSaveFileName(self, "保存 Shader", str(SHADERS_DIR / default_filename), "GLSL Files (*.glsl)")
            if dlg_path:
                target_path = Path(dlg_path)
            else:
                target_path = SHADERS_DIR / default_filename
                counter = 1
                while target_path.exists():
                    target_path = SHADERS_DIR / f"{base_name}_{counter}.glsl"; counter += 1
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(code if code.endswith('\n') else code + '\n')
            self.current_shader_path = str(target_path)
            # Add to library if not present
            if str(target_path) not in self.shader_library:
                self.shader_library.append(str(target_path))
            # Mark as favorite if saved under root shaders dir
            try:
                if Path(self.current_shader_path).parent == SHADERS_DIR:
                    self.heart_label.setText("❤️")
            except Exception:
                pass
            self._add_ai_message(f"💾 已保存: {target_path.name}")
            self._set_dirty(False)
        except Exception as e:  # noqa: BLE001
            self._add_ai_message(f"❌ 保存失败: {e}")

    def _auto_save_latest(self):
        try:
            ai_dir = SHADERS_DIR / "AI_shaders"; ai_dir.mkdir(exist_ok=True, parents=True)
            timestamp = time.strftime("gen_%Y%m%d_%H%M%S")
            fp = ai_dir / f"{timestamp}.glsl"
            with open(fp, 'w', encoding='utf-8') as f:
                f.write(self.current_shader if self.current_shader.endswith('\n') else self.current_shader + '\n')
            if str(fp) not in self.shader_library: self.shader_library.append(str(fp))
        except Exception as e:  # noqa: BLE001
            print(f"[AutoSave] 失败: {e}")

    def apply_shader(self):
        self.code_preview.setText(self.current_shader)
        self._update_preview_from_code()
        if self.launch_borderless_cb:
            try:
                self.launch_borderless_cb(self.current_shader, self.current_shader_path)
            except Exception as e:  # noqa: BLE001
                self._add_ai_message(f"❌ 启动无边框窗口失败: {e}")

    def toggle_favorite(self):
        # Favoriting new shader: write into root shaders dir.
        if self.heart_label.text() == "♡":
            self.heart_label.setText("❤️")
            # If already loaded from a file in SHADERS_DIR root, nothing to do
            if self.current_shader_path and Path(self.current_shader_path).parent == SHADERS_DIR:
                return
            first_line = (self.current_shader.strip().splitlines() or [""])[0]
            base_name = None
            if first_line.startswith("//") and ":" in first_line:
                parts = first_line[2:].strip().split(":",1)
                if len(parts)==2 and parts[0].lower().strip()=="name":
                    candidate = ''.join(ch for ch in parts[1].strip() if ch.isalnum() or ch in ('_','-')) or None
                    base_name = candidate
            if not base_name:
                base_name = time.strftime("fav_%Y%m%d_%H%M%S")
            filename = f"{base_name}.glsl"; target_path = SHADERS_DIR / filename
            counter = 1; stem = target_path.stem
            while target_path.exists():
                target_path = SHADERS_DIR / f"{stem}_{counter}.glsl"; counter += 1
            try:
                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(self.current_shader if self.current_shader.endswith('\n') else self.current_shader + '\n')
                self.current_shader_path = str(target_path)
                if str(target_path) not in self.shader_library:
                    self.shader_library.append(str(target_path))
            except Exception as e:  # noqa: BLE001
                self.heart_label.setText("♡"); print(f"[Favorite] 保存失败: {e}")
        else:
            # Unfavorite: delete file if it resides directly under SHADERS_DIR
            to_delete = None
            if self.current_shader_path:
                p = Path(self.current_shader_path)
                if p.exists() and p.parent == SHADERS_DIR:
                    to_delete = p
            if to_delete:
                try:
                    os.remove(str(to_delete))
                    if str(to_delete) in self.shader_library:
                        self.shader_library.remove(str(to_delete))
                    self._add_ai_message(f"🗑️ 已删除收藏文件: {to_delete.name}")
                except Exception as e:  # noqa: BLE001
                    self._add_ai_message(f"❌ 删除失败: {e}")
            self.current_shader_path = None
            self.heart_label.setText("♡")

    # --- Preview logic ---
    def _on_preview_initialized(self):
        self.preview_ready = True
        if self._pending_code:
            code = self._pending_code; self._pending_code = None; self._write_and_load_preview(code)

    def _write_and_load_preview(self, code: str):
        try:
            preview_dir = SHADERS_DIR / "_preview"; preview_dir.mkdir(exist_ok=True, parents=True)
            target = preview_dir / "live_preview.glsl"
            code_to_save = self._sanitize_shader_source(code)
            with open(target, 'w', encoding='utf-8') as f:
                f.write(code_to_save if code_to_save.endswith('\n') else code_to_save + '\n')
            if self.preview_ready:
                self.preview_widget.load_shader(str(target))
        except Exception as e:  # noqa: BLE001
            print(f"[Preview] 写入/加载失败: {e}")

    def _update_preview_from_code(self):
        if not self.current_shader.strip():
            return
        if not self.preview_ready:
            self._pending_code = self.current_shader; return
        self._write_and_load_preview(self.current_shader)

    def load_from_file(self, file_path: str):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                code = f.read()
            self.current_shader = code; self.current_shader_path = file_path
            self.code_preview.setText(code)
            self._add_ai_message(f"加载 Shader: {os.path.basename(file_path)}")
            self._update_preview_from_code()
            # Library shaders are considered favorited by default
            self.heart_label.setText("❤️")
            self._set_dirty(False)
        except Exception as e:  # noqa: BLE001
            self._add_ai_message(f"❌ 加载失败: {e}")

    # --- Sanitize & compile error ---
    def _sanitize_shader_source(self, code: str) -> str:
        lines = code.splitlines(); version_line = None; rest = []
        for ln in lines:
            stripped = ln.strip()
            if stripped.startswith('#version') and version_line is None:
                version_line = stripped
            elif stripped.startswith('#version'):
                continue
            else:
                rest.append(ln)
        if version_line is None:
            version_line = '#version 330 core'
        else:
            parts = version_line.split(); ver = parts[1] if len(parts) >= 2 else '330'; profile = 'core'
            if len(parts) >= 3 and parts[2] in ('core','es','compatibility'):
                profile = parts[2]
            version_line = f'#version {ver} {profile}'
        return version_line + '\n' + '\n'.join(rest)

    def _on_compile_error(self, log: str):
        txt = log.strip(); lines = txt.splitlines()
        if len(lines) > 12: lines = lines[:12] + ['... (更多省略)']
        self._add_ai_message('❌ 编译失败:\n' + '\n'.join(lines))
        # compile error doesn't change dirty flag

    # --- Dirty indicator helper ---
    def _set_dirty(self, dirty: bool):
        if self.is_dirty == dirty:
            return
        self.is_dirty = dirty
        # Update title label and save button text with asterisk
        try:
            if dirty:
                if not self.title_label.text().startswith('*'):
                    self.title_label.setText('*' + self.title_label.text())
                if not self.save_btn.text().startswith('*'):
                    self.save_btn.setText('*' + self.save_btn.text().lstrip('*'))
            else:
                self.title_label.setText(self.title_label.text().lstrip('*'))
                self.save_btn.setText(self.save_btn.text().lstrip('*'))
        except Exception:
            pass
