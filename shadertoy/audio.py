"""
Audio processing and FFT analysis
"""
import numpy as np
import logging
from typing import Optional
import pyaudiowpatch as pyaudio
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioSource:
    """Audio input with FFT using PyAudioWPatch (WASAPI loopback supported)"""
    def __init__(self, sample_rate: int = 44100, chunk_size: int = 4096, fft_size: int = 1024):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.fft_size = fft_size
        self.fft = np.zeros(fft_size, dtype=np.float32)
        self._audio_buffer = np.zeros(chunk_size, dtype=np.float32)
        self._lock = threading.Lock()
        self._thread = None
        self._running = False
        self.pa = pyaudio.PyAudio()

    def start_capture(self) -> None:
        """Start WASAPI loopback capture (if device_idx=None, auto-detect)"""
        pa = self.pa
        self._stream = pa.open(
            format=pyaudio.paFloat32,
            channels=2,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
            as_loopback=True
        )
        self._running = True
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def stop_capture(self):
        self._running = False
        if self._thread is not None:
            self._thread.join()
            self._thread = None
        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None

    def _reader(self):
        while self._running and self._stream is not None:
            try:
                data = self._stream.read(self.chunk_size, exception_on_overflow=False)
                arr = np.frombuffer(data, dtype=np.float32)
                if arr.ndim > 1:
                    arr = np.mean(arr, axis=1)
                with self._lock:
                    self._audio_buffer = arr
            except Exception as e:
                logger.error(f"Audio read error: {e}")

    def update(self):
        # 取最新音频数据做FFT
        with self._lock:
            x = self._audio_buffer.copy()
        if np.max(np.abs(x)) > 1e-6:
            x = x / (np.max(np.abs(x)) + 1e-9)
        win = np.hanning(len(x))
        spec = np.abs(np.fft.rfft(x * win))
        spec = spec[:self.fft_size]
        if np.max(spec) > 1e-6:
            spec = spec / (np.max(spec) + 1e-9)
        self.fft[:len(spec)] = spec

    def get_fft_data(self) -> Optional[np.ndarray]:
        return self.fft

    def get_texture_data(self) -> np.ndarray:
        arr = np.zeros((1, self.fft_size, 4), dtype=np.float32)
        arr[0, :, 0] = self.fft
        return arr


# 测试代码：检测PyAudioWPatch采集电脑输出音频
if __name__ == "__main__":
    au = AudioSource()
    au.start_capture()
