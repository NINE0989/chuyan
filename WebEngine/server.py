"""统一 HTTP 服务：启动/停止，端口自动递增。"""
from __future__ import annotations

import socket
import threading
from http.server import ThreadingHTTPServer
from typing import Optional

from WebEngine.api import APIHandler

DEFAULT_PORT = 18090
MAX_PORT = 18099

_server: Optional[ThreadingHTTPServer] = None
_server_thread: Optional[threading.Thread] = None
_lock = threading.Lock()


def _find_port(start: int = DEFAULT_PORT) -> int:
    for port in range(start, MAX_PORT + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No port available in {DEFAULT_PORT}-{MAX_PORT}")


def start_server(port: int = DEFAULT_PORT) -> int:
    global _server, _server_thread
    with _lock:
        if _server is not None:
            return _server.server_address[1]

    actual = _find_port(port)
    _server = ThreadingHTTPServer(("127.0.0.1", actual), APIHandler)
    _server_thread = threading.Thread(target=_server.serve_forever, daemon=True)
    _server_thread.start()
    return actual


def stop_server():
    global _server, _server_thread
    with _lock:
        if _server is not None:
            _server.shutdown()
            _server.server_close()
            _server = None
        _server_thread = None


def get_port() -> int | None:
    if _server is not None:
        return _server.server_address[1]
    return None
