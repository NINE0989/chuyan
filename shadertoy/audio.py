"""
Audio processing and FFT analysis
"""
import numpy as np
import logging
from typing import Optional
import pyaudiowpatch as pyaudio
import threading
import audioUtils
import os

# 导入音频处理工具函数

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioSource:
    """Audio input with FFT using PyAudioWPatch (WASAPI loopback supported)"""
    def __init__(self, sample_rate: int = 44100, chunk_size: int = 4096, fft_size: int = 1024):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.fft_size = fft_size
        self.fft = np.zeros(fft_size, dtype=np.float32)
        self._spec_smoothed = np.zeros(fft_size, dtype=np.float32)
        # audio feature state
        self.prev_spec = np.zeros(fft_size, dtype=np.float32)
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
        """更新音频特征 - 只计算FFT频谱"""
        # 获取最新音频数据
        with self._lock:
            x = self._audio_buffer.copy()
        
        if x.size == 0:
            return
        
        # 1. 计算FFT频谱
        spec = np.fft.fft(x, self.fft_size, axis=0) / self.fft_size * 2
        
        # 2. 计算频率数组
        freqs = np.fft.rfftfreq(len(x), d=1.0 / float(self.sample_rate))[:self.fft_size]
        
        # 3. 处理频谱用于可视化
        spec_processed = audioUtils.process_spectrum_for_visualization(
            spec=spec,
            freqs=freqs,
            prev_smoothed=self._spec_smoothed
        )
        
        # # 保存平滑后的频谱供下次使用
        self._spec_smoothed = spec_processed
        
        spec_processed = spec
        
        # 5. 存储最终结果
        self.fft[:len(spec_processed)] = spec_processed

    def get_fft_data(self) -> Optional[np.ndarray]:
        return self.fft

    def get_texture_data(self) -> np.ndarray:
        """
        返回FFT频谱纹理数据
        只使用R通道存储频谱
        """
        arr = np.zeros((1, self.fft_size, 4), dtype=np.float32)
        # R channel: normalized spectrum
        arr[0, :, 0] = self.fft
        return arr


# 测试代码：检测PyAudioWPatch采集电脑输出音频
if __name__ == "__main__":
    au = AudioSource()
    au.start_capture()
