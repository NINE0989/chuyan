"""统一 API handler：chat / shaders / launch / settings。"""
from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from WebEngine.settings import Settings
from WebEngine.ai_service import AIService


class APIHandler(BaseHTTPRequestHandler):
    """处理所有 API 路由和静态文件。"""

    _settings: Settings | None = None
    _ai_service: AIService | None = None
    _lock = threading.Lock()

    @property
    def settings(self) -> Settings:
        if self.__class__._settings is None:
            self.__class__._settings = Settings()
        return self.__class__._settings

    @property
    def ai(self) -> AIService:
        if self.__class__._ai_service is None:
            self.__class__._ai_service = AIService()
        return self.__class__._ai_service

    def _html_dir(self) -> Path:
        return Path(__file__).resolve().parent / "html"

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, content_type):
        fp = self._html_dir() / path
        if fp.is_file():
            content = fp.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    # ---- Static files ----
    def do_GET(self):
        path = self.path.split("?")[0]
        params = {}
        if "?" in self.path:
            from urllib.parse import parse_qs
            params = {k: v[0] for k, v in parse_qs(self.path.split("?", 1)[1]).items()}

        if path == "/" or path == "/index.html":
            self._send_file("index.html", "text/html; charset=utf-8")
        elif path == "/settings.html":
            self._send_file("settings.html", "text/html; charset=utf-8")
        elif path == "/api/settings":
            self._send_json(self.settings.to_dict())
        elif path == "/api/shaders":
            self._handle_list_shaders()
        elif path == "/api/shader":
            self._handle_get_shader(params.get("path", ""))
        else:
            self.send_error(404)

    def do_POST(self):
        path = self.path.split("?")[0]
        body = self._read_body()

        if path == "/api/chat":
            self._handle_chat(body)
        elif path == "/api/settings":
            self._handle_save_settings(body)
        elif path == "/api/shader":
            self._handle_save_shader(body)
        elif path == "/api/launch":
            self._handle_launch(body)
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ---- Chat ----
    def _handle_chat(self, body: dict):
        prompt = body.get("prompt", "").strip()
        adjust = body.get("adjust", False)
        if not prompt:
            self._send_json({"success": False, "error": "空 prompt"}, 400)
            return

        try:
            code = self.ai.generate(prompt, adjust=adjust)
            self._send_json({"success": True, "code": code})
        except Exception as e:
            self._send_json({"success": False, "error": str(e)}, 500)

    # ---- Shaders ----
    def _handle_list_shaders(self):
        shaders_dir = Path(__file__).resolve().parent.parent / "shaders"
        files = []
        if shaders_dir.is_dir():
            for fp in sorted(shaders_dir.rglob("*.glsl"), key=lambda p: p.stat().st_mtime, reverse=True):
                try:
                    st = fp.stat()
                    files.append({
                        "name": fp.name,
                        "path": str(fp.relative_to(shaders_dir.parent)).replace("\\", "/"),
                        "size": st.st_size,
                        "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime)),
                    })
                except OSError:
                    continue
        self._send_json(files)

    def _handle_get_shader(self, relative_path: str):
        if not relative_path:
            self._send_json({"code": "", "error": "缺少 path 参数"}, 400)
            return
        root = Path(__file__).resolve().parent.parent
        fp = root / relative_path
        if not fp.is_file():
            self._send_json({"code": "", "error": f"文件不存在: {relative_path}"}, 404)
            return
        try:
            code = fp.read_text(encoding="utf-8", errors="ignore")
            self._send_json({"code": code, "path": str(relative_path)})
        except Exception as e:
            self._send_json({"code": "", "error": str(e)}, 500)

    def _handle_save_shader(self, body: dict):
        code = body.get("code", "")
        name = body.get("name", time.strftime("web_%Y%m%d_%H%M%S"))
        if not code.strip():
            self._send_json({"ok": False, "error": "空代码"}, 400)
            return
        root = Path(__file__).resolve().parent.parent
        out_dir = root / "shaders" / "AI_shaders"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c for c in name if c.isalnum() or c in "_-") or "shader"
        fp = out_dir / f"{safe_name}.glsl"
        fp.write_text(code, encoding="utf-8")
        self._send_json({"ok": True, "path": str(fp.relative_to(root)).replace("\\", "/")})

    # ---- Launch ----
    def _handle_launch(self, body: dict):
        code = body.get("code", "")
        source_path = body.get("path", "")
        if not code.strip():
            self._send_json({"ok": False, "error": "空代码"}, 400)
            return
        try:
            from WebEngine.launch import launch_borderless_process
            proc = launch_borderless_process(code, source_path if source_path else None)
            self._send_json({"ok": True, "pid": proc.pid})
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, 500)

    # ---- Settings ----
    def _handle_save_settings(self, body: dict):
        with self._lock:
            self.settings.update(
                api_key=body.get("api_key", ""),
                base_url=body.get("base_url", ""),
                model=body.get("model", ""),
            )
        # 同步更新 AI service
        if self.__class__._ai_service:
            self.__class__._ai_service.provider = "openai" if self.settings.has_api_key else "mock"
        self._send_json({"ok": True})

    def log_message(self, format, *args):
        pass  # 静默
