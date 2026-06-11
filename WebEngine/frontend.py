"""
PyQt5前端，用于加载HTML并与Python后端交互
"""
import os
import sys
from PyQt5.QtCore import QObject, pyqtSlot, QUrl
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel

# 获取当前文件所在目录的绝对路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

class Backend(QObject):
    """
    后端对象，暴露给JavaScript调用的方法
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent

    @pyqtSlot(str)
    def on_button_click(self, text):
        """
        处理来自HTML按钮点击事件的回调
        
        Args:
            text (str): 从HTML文本框中获取的文本
        """
        print(f"[Python] HTML按钮被点击，收到的文本: '{text}'")
        
        # 调用JavaScript函数，更新HTML页面内容
        self.main_window.view.page().runJavaScript(f"update_text('来自Python的问候: {text}')")

class MainWindow(QMainWindow):
    """
    主窗口类
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PyQt5 HTML前端")
        self.setGeometry(100, 100, 800, 600)

        # 1. 创建 QWebEngineView
        self.view = QWebEngineView()
        self.setCentralWidget(self.view)

        # 2. 创建 QWebChannel 和后端对象
        self.channel = QWebChannel()
        self.backend = Backend(self)
        self.channel.registerObject("backend", self.backend)
        self.view.page().setWebChannel(self.channel)

        # 3. 加载HTML文件
        # 使用绝对路径确保文件能被找到
        html_path = os.path.join(CURRENT_DIR, "html/frontend.html")
        self.view.setUrl(QUrl.fromLocalFile(html_path))

def main():
    """
    应用主入口
    """
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
