"""Application entrypoint for modular Shader UI.

This file now only wires up path handling and launches the Qt MainWindow
implemented in WebEngine.ui.window. All prior monolithic UI code has
been moved into dedicated modules under the ui/ package.
"""
from pathlib import Path
import sys

# Ensure project root on sys.path for package imports when invoked directly
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt5.QtWidgets import QApplication  # noqa: E402
from WebEngine.ui.window import MainWindow  # noqa: E402


def run():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(run())