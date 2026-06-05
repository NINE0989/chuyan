"""API 设置对话框：API Key / Base URL / Model 输入界面。"""
from __future__ import annotations

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QGroupBox, QComboBox, QMessageBox,
)
from PyQt5.QtCore import Qt

from WebEngine.settings import Settings


class SettingsDialog(QDialog):
    """API 配置对话框，支持 OpenAI / DeepSeek 预设。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = Settings()
        self.setWindowTitle("API 设置")
        self.setFixedSize(480, 380)
        self.setStyleSheet("QDialog { background-color: #f5f5f5; }")
        self._build_ui()
        self._load_current()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # --- 预设选择 ---
        preset_group = QGroupBox("快速预设")
        preset_layout = QHBoxLayout(preset_group)
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("自定义")
        self.preset_combo.addItem("OpenAI (GPT-4.1-mini)")
        self.preset_combo.addItem("DeepSeek (deepseek-chat)")
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_layout.addWidget(QLabel("选择平台:"))
        preset_layout.addWidget(self.preset_combo, 1)
        layout.addWidget(preset_group)

        # --- API Key ---
        key_group = QGroupBox("API 密钥")
        key_layout = QVBoxLayout(key_group)
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("输入 API Key（如 sk-...）")
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setStyleSheet("QLineEdit { padding: 8px; font-size: 13px; border: 1px solid #ccc; border-radius: 4px; }")

        show_key_btn = QPushButton("👁 显示/隐藏")
        show_key_btn.setFixedWidth(100)
        show_key_btn.clicked.connect(self._toggle_key_visibility)
        show_key_btn.setStyleSheet("QPushButton { background: #ddd; border-radius: 4px; padding: 4px; }")

        key_row = QHBoxLayout()
        key_row.addWidget(self.key_input, 1)
        key_row.addWidget(show_key_btn)
        key_layout.addLayout(key_row)
        layout.addWidget(key_group)

        # --- Base URL ---
        url_group = QGroupBox("API 地址")
        url_layout = QVBoxLayout(url_group)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://api.openai.com/v1")
        self.url_input.setStyleSheet("QLineEdit { padding: 8px; font-size: 13px; border: 1px solid #ccc; border-radius: 4px; }")
        url_layout.addWidget(self.url_input)
        layout.addWidget(url_group)

        # --- Model ---
        model_group = QGroupBox("模型名称")
        model_layout = QVBoxLayout(model_group)
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("gpt-4.1-mini")
        self.model_input.setStyleSheet("QLineEdit { padding: 8px; font-size: 13px; border: 1px solid #ccc; border-radius: 4px; }")
        model_layout.addWidget(self.model_input)
        layout.addWidget(model_group)

        # --- 状态提示 ---
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.status_label)

        # --- 按钮 ---
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("""
            QPushButton { background-color: #1c1c1c; color: white; border-radius: 4px; padding: 8px 24px; font-weight: bold; }
            QPushButton:hover { background-color: #333333; }
        """)
        save_btn.clicked.connect(self._on_save)

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("QPushButton { background-color: #ddd; border-radius: 4px; padding: 8px 24px; }")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def _load_current(self):
        """加载当前配置到 UI。"""
        s = self.settings
        self.key_input.setText(s.api_key)
        self.url_input.setText(s.base_url)
        self.model_input.setText(s.model)

        # 判断当前是哪个预设
        if s.base_url == "https://api.openai.com/v1" and s.model == "gpt-4.1-mini":
            self.preset_combo.setCurrentIndex(1)
        elif s.base_url == "https://api.deepseek.com/v1" and s.model == "deepseek-chat":
            self.preset_combo.setCurrentIndex(2)
        else:
            self.preset_combo.setCurrentIndex(0)

        if s.has_api_key:
            masked = s.api_key[:8] + "****" + s.api_key[-4:] if len(s.api_key) > 12 else "****"
            self.status_label.setText(f"已加载密钥: {masked}")
        else:
            self.status_label.setText("未配置 API 密钥（将使用 Mock 模式）")

    def _on_preset_changed(self, idx: int):
        if idx == 0:
            return  # 自定义
        if idx == 1:
            preset = self.settings.get_openai_presets()
        else:
            preset = self.settings.get_deepseek_presets()
        self.url_input.setText(preset["base_url"])
        self.model_input.setText(preset["model"])

    def _toggle_key_visibility(self):
        if self.key_input.echoMode() == QLineEdit.Password:
            self.key_input.setEchoMode(QLineEdit.Normal)
        else:
            self.key_input.setEchoMode(QLineEdit.Password)

    def _on_save(self):
        api_key = self.key_input.text().strip()
        base_url = self.url_input.text().strip()
        model = self.model_input.text().strip()

        if not base_url:
            QMessageBox.warning(self, "提示", "API 地址不能为空")
            return
        if not model:
            QMessageBox.warning(self, "提示", "模型名称不能为空")
            return

        self.settings.update(api_key=api_key, base_url=base_url, model=model)
        self.status_label.setText("✅ 配置已保存，重启后生效。部分模块需重新初始化。")
        self.accept()
