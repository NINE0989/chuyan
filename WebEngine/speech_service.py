"""语音识别服务：录音（pyaudio） + OpenAI Whisper API 转录。"""
from __future__ import annotations

import io
import json
import os
import threading
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pyaudio


# 录音参数 —— Whisper API 推荐 16kHz 单声道
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1024
FORMAT = pyaudio.paInt16
MAX_RECORD_SECONDS = 30  # 最长录音 30 秒


@dataclass
class TranscriptionResult:
    success: bool
    text: str = ""
    error: str = ""


class SpeechService:
    """封装麦克风录音与 Whisper API 转录。"""

    def __init__(self):
        self._audio = pyaudio.PyAudio()
        self._stream: Optional[pyaudio.Stream] = None
        self._frames: list[bytes] = []
        self._is_recording = False
        self._lock = threading.Lock()

        # 优先从 Settings 管理器读取 API key，fallback 到环境变量
        try:
            from WebEngine.settings import get_settings
            s = get_settings()
            chat_base_url = (s and s.base_url or "").rstrip("/")
            can_reuse_chat_key = "api.openai.com" in chat_base_url
            self._api_key = (
                (s and s.speech_api_key)
                or os.getenv("OPENAI_SPEECH_API_KEY", "").strip()
                or ((s and s.api_key) if can_reuse_chat_key else "")
            )
            self._base_url = (
                (s and s.speech_base_url)
                or os.getenv("OPENAI_SPEECH_BASE_URL", "")
                or "https://api.openai.com/v1"
            ).rstrip("/")
            self._model = (
                (s and s.speech_model)
                or os.getenv("OPENAI_SPEECH_MODEL", "")
                or "whisper-1"
            )
        except Exception:
            self._api_key = os.getenv("OPENAI_SPEECH_API_KEY", "").strip()
            self._base_url = os.getenv("OPENAI_SPEECH_BASE_URL", "https://api.openai.com/v1").rstrip("/")
            self._model = os.getenv("OPENAI_SPEECH_MODEL", "whisper-1")

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def api_available(self) -> bool:
        return bool(self._api_key)

    def list_input_devices(self) -> list[dict]:
        """列出所有可用的音频输入设备。"""
        devices = []
        for i in range(self._audio.get_device_count()):
            info = self._audio.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                devices.append({
                    "index": i,
                    "name": info.get("name", ""),
                    "sample_rate": int(info.get("defaultSampleRate", 0)),
                })
        return devices

    def start_recording(self, device_index: int | None = None) -> bool:
        """开始录音（非阻塞，在后台线程写入帧缓冲）。"""
        with self._lock:
            if self._is_recording:
                return False
            self._frames = []
            self._is_recording = True

        try:
            self._stream = self._audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=CHUNK_SIZE,
                stream_callback=self._audio_callback,
            )
            self._stream.start_stream()
        except Exception:
            self._is_recording = False
            raise

        # 启动超时定时器
        threading.Thread(target=self._auto_stop_timer, daemon=True).start()
        return True

    def _audio_callback(self, in_data, frame_count, time_info, status):
        self._frames.append(in_data)
        return (None, pyaudio.paContinue)

    def _auto_stop_timer(self):
        """最长录音时间后自动停止。"""
        import time
        elapsed = 0
        while self._is_recording and elapsed < MAX_RECORD_SECONDS:
            time.sleep(1)
            elapsed += 1
        if self._is_recording:
            self.stop_recording()

    def stop_recording(self) -> bytes:
        """停止录音，返回 WAV 格式的音频字节。"""
        with self._lock:
            if not self._is_recording:
                return b""
            self._is_recording = False

        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None

        return self._frames_to_wav()

    def cancel_recording(self):
        """取消录音（丢弃已录数据）。"""
        with self._lock:
            self._is_recording = False
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        self._frames = []

    def _frames_to_wav(self) -> bytes:
        """将音频帧编码为 WAV 字节。"""
        if not self._frames:
            return b""

        audio_data = b"".join(self._frames)

        import struct
        import wave

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self._audio.get_sample_size(FORMAT))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_data)
        return buf.getvalue()

    def transcribe(self, wav_bytes: bytes, language: str = "zh") -> TranscriptionResult:
        """调用 OpenAI Whisper API 转录音频。

        Args:
            wav_bytes: WAV 格式音频字节
            language: 语言代码（zh/en/ja 等），空字符串为自动检测

        Returns:
            TranscriptionResult
        """
        if not wav_bytes:
            return TranscriptionResult(False, error="空音频数据")
        if not self._api_key:
            return TranscriptionResult(False, error="未配置语音识别 API Key。DeepSeek 不支持 /audio/transcriptions，请在设置中配置 OpenAI/Whisper 兼容的语音识别 Key。")

        # 构造 multipart/form-data
        boundary = f"----WhisperBoundary{uuid.uuid4().hex[:8]}"
        body = self._build_multipart(wav_bytes, boundary, language)

        url = f"{self._base_url}/audio/transcriptions"
        req = urllib.request.Request(
            url=url,
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            return TranscriptionResult(True, text=data.get("text", "").strip())
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", errors="ignore")
            # 413 = audio too large
            return TranscriptionResult(False, error=f"HTTP {e.code}: {msg[:200]}")
        except Exception as e:
            return TranscriptionResult(False, error=str(e))

    def _build_multipart(self, wav_bytes: bytes, boundary: str, language: str) -> bytes:
        """构造 multipart/form-data 请求体。"""
        lines = []
        # model field
        lines.append(f"--{boundary}")
        lines.append('Content-Disposition: form-data; name="model"')
        lines.append("")
        lines.append(self._model or "whisper-1")

        # language field (optional)
        if language:
            lines.append(f"--{boundary}")
            lines.append('Content-Disposition: form-data; name="language"')
            lines.append("")
            lines.append(language)

        # file field
        filename = f"recording_{uuid.uuid4().hex[:6]}.wav"
        lines.append(f"--{boundary}")
        lines.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"')
        lines.append("Content-Type: audio/wav")
        lines.append("")

        header = "\r\n".join(lines).encode("utf-8") + b"\r\n"
        footer = f"\r\n--{boundary}--\r\n".encode("utf-8")

        return header + wav_bytes + footer

    def close(self):
        """释放 PyAudio 资源。"""
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        self._audio.terminate()
