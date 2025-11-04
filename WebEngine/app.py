import sys
import os
import time
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QLabel,
    QVBoxLayout, QHBoxLayout, QStackedWidget, QFrame,
    QTextEdit, QLineEdit, QSizePolicy, QScrollArea, QGridLayout
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QPixmap, QFont

# 路径：项目根目录下的 shaders 文件夹
SHADERS_DIR = (Path(__file__).resolve().parent.parent / "shaders").as_posix()
os.makedirs(SHADERS_DIR, exist_ok=True)


class ChatBubble(QFrame):
    """简单的左右对齐聊天气泡"""
    def __init__(self, text, is_user=False):
        super().__init__()
        self.setStyleSheet("border: none;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        avatar = QLabel("😎" if is_user else "AI")
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setFixedSize(40, 40)
        if is_user:
            avatar.setStyleSheet("""
                QLabel { font-size: 22px; }
            """)
        else:
            avatar.setStyleSheet("""
                QLabel { background-color: #1c1c1c; color: white; border-radius: 20px; font-size: 16px; }
            """)

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
            layout.addStretch()
            layout.addWidget(bubble)
            layout.addWidget(avatar)
        else:
            layout.addWidget(avatar)
            layout.addWidget(bubble)
            layout.addStretch()


class MainPage(QWidget):
    """主界面：聊天 + Shader 预览 + 代码显示"""
    def __init__(self, switch_to_shader, shader_library):
        super().__init__()
        self.switch_to_shader = switch_to_shader
        self.shader_library = shader_library
        self.current_shader = "// GLSL shader code will appear here"
        self.initUI()

    def initUI(self):
        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: #2b6dad; color: white;")
        top_bar.setFixedHeight(60)

        title = QLabel("NAME")
        title.setFont(QFont("Arial", 14))
        title.setStyleSheet("color: white;")

        btn_shader = QPushButton("Shader库")
        btn_shader.setStyleSheet("""
            QPushButton { background-color: white; color: #2b6dad; font-weight: bold; padding: 6px 12px; border-radius: 8px; }
            QPushButton:hover { background-color: #e0e0e0; }
        """)
        btn_shader.clicked.connect(self.switch_to_shader)

        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("😎"))
        top_layout.addWidget(title)
        top_layout.addStretch()
        top_layout.addWidget(btn_shader)
        top_bar.setLayout(top_layout)

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        chat_area = QVBoxLayout()
        chat_area.setContentsMargins(15, 15, 15, 15)

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_widget = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_widget)
        self.chat_layout.addStretch()
        self.chat_scroll.setWidget(self.chat_widget)
        self.chat_scroll.setStyleSheet("background-color: #d9d9d9; border-radius: 8px;")

        chat_area.addWidget(self.chat_scroll, 1)

        input_layout = QHBoxLayout()
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("请输入您的需求……")
        self.input_box.setStyleSheet("""
            QLineEdit { background-color: white; border: none; border-radius: 6px; padding: 8px; font-size: 14px; }
        """)
        send_btn = QPushButton("发送")
        send_btn.setStyleSheet("""
            QPushButton { background-color: #1c1c1c; color: white; border-radius: 4px; padding: 8px 16px; }
            QPushButton:hover { background-color: #333333; }
        """)
        send_btn.clicked.connect(self.send_message)

        input_layout.addWidget(self.input_box, 1)
        input_layout.addWidget(send_btn)
        chat_area.addLayout(input_layout)

        right_panel = QVBoxLayout()
        right_panel.setContentsMargins(10, 15, 15, 15)
        right_panel.setSpacing(10)

        self.shader_container = QFrame()
        self.shader_container.setStyleSheet("""
            QFrame { background-color: #e0e0e0; border-radius: 8px; }
        """)
        self.shader_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.shader_container.setFixedHeight(360)

        shader_layout = QVBoxLayout(self.shader_container)
        shader_layout.setContentsMargins(0, 0, 0, 0)
        shader_layout.setSpacing(0)

        self.shader_display = QLabel("🎞️")
        self.shader_display.setAlignment(Qt.AlignCenter)
        self.shader_display.setStyleSheet("font-size: 40px; color: #bfbfbf;")
        shader_layout.addWidget(self.shader_display, 1)

        shader_bottom_bar = QFrame()
        shader_bottom_bar.setStyleSheet("background-color: #2b6dad; border-radius: 0 0 8px 8px;")
        shader_bottom_bar.setFixedHeight(50)

        bottom_bar_layout = QHBoxLayout(shader_bottom_bar)
        bottom_bar_layout.setContentsMargins(10, 0, 10, 0)

        self.heart_label = QPushButton("♡")
        self.heart_label.setStyleSheet("""
            QPushButton { color: white; font-size: 22px; background: transparent; border: none; }
        """)
        self.heart_label.clicked.connect(self.toggle_favorite)
        bottom_bar_layout.addWidget(self.heart_label)
        bottom_bar_layout.addStretch()

        self.apply_btn = QPushButton("应用")
        self.apply_btn.setFixedSize(80, 30)
        self.apply_btn.setStyleSheet("""
            QPushButton { background-color: #1c1c1c; color: white; border-radius: 12px; font-weight: bold; }
            QPushButton:hover { background-color: #333333; }
        """)
        self.apply_btn.clicked.connect(self.apply_shader)
        bottom_bar_layout.addWidget(self.apply_btn)
        shader_layout.addWidget(shader_bottom_bar)

        self.code_preview = QTextEdit()
        self.code_preview.setReadOnly(True)
        self.code_preview.setStyleSheet("""
            QTextEdit { background-color: black; color: white; font-family: Consolas; font-size: 13px; border-radius: 8px; }
        """)
        self.code_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        right_panel.addWidget(self.shader_container)
        right_panel.addWidget(self.code_preview)

        main_layout.addLayout(chat_area, 2)
        main_layout.addLayout(right_panel, 3)

        layout = QVBoxLayout()
        layout.addWidget(top_bar)
        layout.addLayout(main_layout)
        self.setLayout(layout)

    def send_message(self):
        text = self.input_box.text().strip()
        if not text:
            return
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, ChatBubble(text, is_user=True))
        self.input_box.clear()
        ai_reply = "这是一个示例 GLSL Shader 代码。"
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, ChatBubble(ai_reply))
        self.current_shader = """void setup() {
    // put your setup code here, to run once:
}

void loop() {
    // put your main code here, to run repeatedly:
}"""
        self.shader_display.setText("🌀")

    def apply_shader(self):
        self.code_preview.setText(self.current_shader)

    def toggle_favorite(self):
        """收藏当前 Shader：写入到 shaders 目录，并标记收藏。

        命名规则：fav_<时间戳>.glsl 例如 fav_20251104_142530.glsl
        如果代码第一行包含形如 // name: xxx 则使用 xxx 作为基础文件名（去空格、非法字符）。
        不执行取消收藏时的删除操作，避免误删。再次点击只切换图标。
        """
        if self.heart_label.text() == "♡":
            # 切换 UI 状态
            self.heart_label.setText("❤️")

            # 解析可选名称
            first_line = self.current_shader.strip().splitlines()[0] if self.current_shader.strip().splitlines() else ""
            base_name = None
            if first_line.startswith("//") and ":" in first_line:
                # 例如 // name: MyShader
                parts = first_line[2:].strip().split(":", 1)
                if len(parts) == 2 and parts[0].lower().strip() == "name":
                    candidate = parts[1].strip()
                    # 过滤非法文件名字符
                    base_name = "".join(ch for ch in candidate if ch.isalnum() or ch in ('_','-')) or None
            if not base_name:
                base_name = time.strftime("fav_%Y%m%d_%H%M%S")

            filename = f"{base_name}.glsl"
            target_path = os.path.join(SHADERS_DIR, filename)
            # 若已存在则附加序号
            counter = 1
            stem, ext = os.path.splitext(filename)
            while os.path.exists(target_path):
                target_path = os.path.join(SHADERS_DIR, f"{stem}_{counter}{ext}")
                counter += 1
            try:
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(self.current_shader if self.current_shader.endswith("\n") else self.current_shader + "\n")
                # 记录到内存收藏列表（存文件路径或名称）
                self.shader_library.append(target_path)
            except Exception as e:
                # 失败则回退图标
                self.heart_label.setText("♡")
                print(f"[Favorite] 保存失败: {e}")
        else:
            # 这里只切换显示，不删除文件
            # TODO: 添加删除功能
            self.heart_label.setText("♡")


class ShaderPage(QWidget):
    """展示 shaders 目录下所有 .glsl / .frag 文件，并显示收藏文件。"""
    def __init__(self, switch_to_main, shader_library):
        super().__init__()
        self.switch_to_main = switch_to_main
        self.shader_library = shader_library  # 仍保留：可用于后续标识收藏
        self.initUI()

    def initUI(self):
        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: #2b6dad; color: white;")
        top_bar.setFixedHeight(60)

        title = QLabel("Shader库")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        title.setStyleSheet("color: white; margin-left: 10px;")

        btn_close = QPushButton("×")
        btn_close.setStyleSheet("""
            QPushButton { background-color: white; color: #2b6dad; font-weight: bold; padding: 6px 12px; border-radius: 8px; }
            QPushButton:hover { background-color: #e0e0e0; }
        """)
        btn_close.clicked.connect(self.switch_to_main)

        top_layout = QHBoxLayout()
        top_layout.addWidget(title)
        top_layout.addStretch()
        top_layout.addWidget(btn_close)
        top_layout.setContentsMargins(10, 0, 10, 0)
        top_bar.setLayout(top_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: #f0f0f0; border: none;")

        container = QWidget()
        self.grid_layout = QGridLayout(container)
        self.grid_layout.setSpacing(20)
        self.grid_layout.setContentsMargins(30, 30, 30, 30)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(container)

        layout = QVBoxLayout(self)
        layout.addWidget(top_bar)
        layout.addWidget(scroll)
        self.setLayout(layout)

    def _list_shader_files(self):
        try:
            files = [f for f in os.listdir(SHADERS_DIR) if f.lower().endswith((".glsl", ".frag"))]
            # 最新修改时间靠前
            files.sort(key=lambda n: os.path.getmtime(os.path.join(SHADERS_DIR, n)), reverse=True)
            return files
        except Exception as e:
            print(f"[ShaderPage] 列表读取失败: {e}")
            return []

    def showEvent(self, event):  # 动态刷新：进入页面/窗口显示时触发
        for i in reversed(range(self.grid_layout.count())):
            item = self.grid_layout.itemAt(i).widget()
            if item:
                item.deleteLater()

        shader_files = self._list_shader_files()
        if not shader_files:
            label = QLabel("目录中暂无 Shader 文件")
            label.setAlignment(Qt.AlignCenter)
            label.setFont(QFont("Arial", 12))
            self.grid_layout.addWidget(label, 0, 0)
            return

        cols = 4
        for idx, filename in enumerate(shader_files):
            row = idx // cols
            col = idx % cols
            card = self.create_shader_card(filename)
            self.grid_layout.addWidget(card, row, col, Qt.AlignTop | Qt.AlignLeft)

    def create_shader_card(self, filename: str):
        full_path = os.path.join(SHADERS_DIR, filename)
        mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(full_path))) if os.path.exists(full_path) else "--"
        card = QFrame()
        card.setStyleSheet("""
            QFrame { background-color: #ffffff; border-radius: 8px; border: 2px solid #e0e0e0; }
            QFrame:hover { border: 2px solid #2b6dad; }
        """)
        card.setFixedSize(250, 190)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        preview = QLabel("🖼️")
        preview.setAlignment(Qt.AlignCenter)
        preview.setStyleSheet("QLabel { background-color: #e6e6e6; border-radius: 6px; font-size:28px; }")
        preview.setFixedHeight(100)

        name_label = QLabel(filename)
        name_label.setFont(QFont("Arial", 10, QFont.Bold))
        name_label.setStyleSheet("color: #333333;")
        name_label.setWordWrap(True)

        date_label = QLabel(mtime)
        date_label.setFont(QFont("Arial", 9))
        date_label.setStyleSheet("color: #666666;")

        # 读取前几行作为 tooltip
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                head = ''.join([next(f) for _ in range(5)])
            card.setToolTip(head)
        except Exception:
            pass

        layout.addWidget(preview)
        layout.addWidget(name_label)
        layout.addWidget(date_label)
        layout.addStretch()
        return card


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Shader 界面演示")
        self.setGeometry(200, 100, 1280, 720)
        self.shader_library = []
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.main_page = MainPage(self.show_shader_page, self.shader_library)
        self.shader_page = ShaderPage(self.show_main_page, self.shader_library)
        self.stack.addWidget(self.main_page)
        self.stack.addWidget(self.shader_page)

    def show_shader_page(self):
        self.stack.setCurrentWidget(self.shader_page)

    def show_main_page(self):
        self.stack.setCurrentWidget(self.main_page)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())