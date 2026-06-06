"""统一 API handler：chat / shaders / launch / speech / settings。"""
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
    _speech_service = None  # 延迟初始化
    _speech_lock = threading.Lock()
    _lock = threading.Lock()

    @staticmethod
    def _get_speech():
        if APIHandler._speech_service is None:
            with APIHandler._speech_lock:
                if APIHandler._speech_service is None:
                    from WebEngine.speech_service import SpeechService
                    APIHandler._speech_service = SpeechService()
        return APIHandler._speech_service

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
        elif path == "/api/music":
            self._handle_list_music(params.get("path", ""))
        elif path == "/api/speech/status":
            self._handle_speech_status()
        else:
            self.send_error(404)

    def do_POST(self):
        path = self.path.split("?")[0]
        body = self._read_body()

        if path == "/api/chat":
            self._handle_chat(body)
        elif path == "/api/chat/analyze":
            self._handle_chat_analyze(body)
        elif path == "/api/chat/build":
            self._handle_chat_build(body)
        elif path == "/api/chat/stream":
            self._handle_chat_stream(body)
        elif path == "/api/settings":
            self._handle_save_settings(body)
        elif path == "/api/shader":
            self._handle_save_shader(body)
        elif path == "/api/launch":
            self._handle_launch(body)
        elif path == "/api/speech/start":
            self._handle_speech_start()
        elif path == "/api/speech/stop":
            self._handle_speech_stop(body)
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
        mode = body.get("mode", "plan")
        if not prompt:
            self._send_json({"success": False, "error": "空 prompt"}, 400)
            return

        if mode == "build":
            self._send_json({"success": False, "error": "Build 模式已升级为两阶段。请先 POST /api/chat/analyze 进行分析，确认后再 POST /api/chat/build 生成代码。"})
            return

        try:
            code = self.ai.generate(prompt, adjust=adjust, mode=mode)
            is_shader = "#version" in code or "void main" in code
            self._send_json({"success": True, "code": code, "type": "shader" if is_shader else "chat"})
        except Exception as e:
            self._send_json({"success": False, "error": str(e)}, 500)

    def _sse_stream(self, text: str, rtype: str):
        """SSE 流式发送文本（模拟逐字输出效果）。"""
        import time as _time
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        # 禁用 Nagle 算法，确保小块数据立即发送
        if hasattr(self.connection, "socket"):
            self.connection.socket.setsockopt(6, 1, 1)  # TCP_NODELAY
        try:
            chunk_size = max(2, len(text) // 60) if len(text) > 60 else 1
            for i in range(0, len(text), chunk_size):
                chunk = text[i:i + chunk_size]
                data = json.dumps({"chunk": chunk, "type": rtype}, ensure_ascii=False)
                self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                self.wfile.flush()
                _time.sleep(0.04)
            self.wfile.write("data: [DONE]\n\n".encode("utf-8"))
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _handle_chat_analyze(self, body: dict):
        """Analyze 端点：需求分析（先发心跳，再阻塞调用，最后流式输出）。"""
        prompt = body.get("prompt", "").strip()
        if not prompt:
            self._send_json({"success": False, "error": "空 prompt"}, 400)
            return

        import time as _time
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        if hasattr(self.connection, "socket"):
            try: self.connection.socket.setsockopt(6, 1, 1)
            except Exception: pass

        # 立即发送心跳，让前端开始渲染
        self.wfile.write(b"data: {\"chunk\":\".\",\"type\":\"chat\"}\n\n")
        self.wfile.flush()

        # 阻塞调用 Agent
        analysis = ""
        try:
            analysis = self.ai.analyze(prompt)
        except Exception:
            analysis = "分析失败，请重试。"

        # 流式输出分析结果
        chunk_size = max(2, len(analysis) // 50) if len(analysis) > 50 else 1
        for i in range(0, len(analysis), chunk_size):
            chunk = analysis[i:i + chunk_size]
            data = json.dumps({"chunk": chunk, "type": "chat"}, ensure_ascii=False)
            try:
                self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                self.wfile.flush()
                _time.sleep(0.05)
            except (BrokenPipeError, ConnectionResetError, OSError):
                return
        try:
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _handle_chat_build(self, body: dict):
        """Build 端点：生成 GLSL（先发心跳，再阻塞调用，最后流式输出）。"""
        prompt = body.get("prompt", "").strip()
        analysis_context = body.get("analysis_context", "")
        if not prompt:
            self._send_json({"success": False, "error": "空 prompt"}, 400)
            return

        import time as _time
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        if hasattr(self.connection, "socket"):
            try: self.connection.socket.setsockopt(6, 1, 1)
            except Exception: pass

        self.wfile.write(b"data: {\"chunk\":\".\",\"type\":\"chat\"}\n\n")
        self.wfile.flush()

        code = ""
        try:
            code = self.ai._build_shader(prompt, adjust=False, analysis_context=analysis_context)
        except Exception:
            code = "生成失败，请重试。"

        is_shader = "#version" in code or "void main" in code
        rtype = "shader" if is_shader else "chat"
        chunk_size = max(1, len(code) // 50) if len(code) > 50 else 1
        for i in range(0, len(code), chunk_size):
            chunk = code[i:i + chunk_size]
            data = json.dumps({"chunk": chunk, "type": rtype}, ensure_ascii=False)
            try:
                self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                self.wfile.flush()
                _time.sleep(0.05)
            except (BrokenPipeError, ConnectionResetError, OSError):
                return
        try:
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _handle_chat_stream(self, body: dict):
        """SSE 流式对话端点。"""
        prompt = body.get("prompt", "").strip()
        adjust = body.get("adjust", False)
        mode = body.get("mode", "plan")
        if not prompt:
            self._send_json({"success": False, "error": "空 prompt"}, 400)
            return

        import time as _time
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        try:
            full = self.ai.generate(prompt, adjust=adjust, mode=mode)
            is_shader = "#version" in full or "void main" in full
            rtype = "shader" if is_shader else "chat"
            # 按字符块流式发送
            chunk_size = max(1, len(full) // 30) if len(full) > 30 else len(full)
            for i in range(0, len(full), chunk_size):
                chunk = full[i:i + chunk_size]
                data = json.dumps({"chunk": chunk, "type": rtype}, ensure_ascii=False)
                self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                self.wfile.flush()
                _time.sleep(0.02)
            self.wfile.write("data: [DONE]\n\n".encode("utf-8"))
            self.wfile.flush()
        except Exception as e:
            data = json.dumps({"error": str(e)}, ensure_ascii=False)
            self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
            self.wfile.flush()

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

    # ---- Music Library ----
    def _music_dir(self):
        root = Path(__file__).resolve().parent.parent
        d = root / "MusicLib"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _handle_list_music(self, sub_path: str = ""):
        """GET /api/music → 列表；GET /api/music?path=... → 返回该文件的音频采样数据"""
        music_dir = self._music_dir()

        if sub_path:
            # 返回指定文件的音频内容（JSON/CSV 格式的采样数组，或 WAV 文件的原始数据）
            fp = music_dir / sub_path
            if not fp.is_file():
                self._send_json({"error": f"文件不存在: {sub_path}"}, 404)
                return
            try:
                import numpy as np
                # 尝试作为 JSON/CSV 采样数组加载
                text = fp.read_text(encoding="utf-8-sig", errors="ignore").strip()
                try:
                    data = json.loads(text)
                    if isinstance(data, list):
                        samples = [float(x) for x in data]
                        self._send_json({"name": fp.name, "samples": samples[:500], "total_length": len(samples)})
                        return
                except json.JSONDecodeError:
                    pass
                # CSV fallback
                values = []
                for token in text.replace("\n", ",").split(","):
                    t = token.strip()
                    if t:
                        try: values.append(float(t))
                        except ValueError: continue
                self._send_json({"name": fp.name, "samples": values[:500], "total_length": len(values)})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
        else:
            # 列出所有音乐文件
            files = []
            if music_dir.is_dir():
                for fp in sorted(music_dir.rglob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
                    if fp.is_file() and fp.suffix.lower() in (".json", ".csv", ".wav", ".mp3", ".txt"):
                        try:
                            st = fp.stat()
                            rel = str(fp.relative_to(music_dir)).replace("\\", "/")
                            files.append({
                                "name": fp.name,
                                "path": rel,
                                "folder": str(fp.parent.relative_to(music_dir)).replace("\\", "/") if fp.parent != music_dir else "",
                                "size": st.st_size,
                                "suffix": fp.suffix.lower(),
                                "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime)),
                            })
                        except OSError:
                            continue
            self._send_json(files)

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

    # ---- Speech ----
    def _handle_speech_start(self):
        try:
            speech = self._get_speech()
            speech.start_recording()
            self._send_json({"ok": True, "recording": True})
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, 500)

    def _handle_speech_stop(self, body: dict):
        try:
            speech = self._get_speech()
            language = body.get("language", "zh")
            wav = speech.stop_recording()
            if not wav:
                self._send_json({"ok": False, "error": "无录音数据"}, 400)
                return
            result = speech.transcribe(wav, language=language)
            self._send_json({
                "ok": result.success,
                "text": result.text,
                "error": result.error,
            })
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, 500)

    def _handle_speech_status(self):
        try:
            speech = self._get_speech()
            self._send_json({"recording": speech.is_recording, "api_available": speech.api_available})
        except Exception as e:
            self._send_json({"recording": False, "api_available": False, "error": str(e)})
