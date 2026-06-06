"""MusicShader Web 前端入口 —— 启动本地 HTTP 服务并在浏览器打开。"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from WebEngine.server import start_server, stop_server


def run():
    port = start_server()
    url = f"http://127.0.0.1:{port}"
    print(f"[MusicShader] http://127.0.0.1:{port}")
    print("[MusicShader] 按 Ctrl+C 退出")

    # 打开浏览器（Windows / Linux / macOS）
    try:
        subprocess.Popen(["cmd", "/c", "start", url], shell=True)
    except Exception:
        import webbrowser
        webbrowser.open(url)

    try:
        print("[MusicShader] 等待中...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[MusicShader] 退出...")
    finally:
        stop_server()


if __name__ == "__main__":
    run()
