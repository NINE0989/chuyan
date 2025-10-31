"""
Audio processing and FFT analysis
"""
import numpy as np
import logging
from typing import Optional
import pyaudiowpatch as pyaudio
import threading

# Local imports for audio processing functions
from . import audioUtils

# 导入音频处理工具函数

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioSource:
    """Audio input with FFT using PyAudioWPatch (WASAPI loopback supported)"""
    def __init__(self, sample_rate: int = 44100, chunk_size: int = 4096, fft_size: int = 1024):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size

        self.fft_size = fft_size
        self.fft_len = fft_size
        self.fft = np.zeros(self.fft_len, dtype=np.float32)
        self._spec_smoothed = np.zeros(self.fft_len, dtype=np.float32)
        # audio feature state
        self.prev_spec = np.zeros(self.fft_len, dtype=np.float32)
        self._running_peak = 0.0  # 用于自适应归一化的运行峰值
        self._audio_buffer = np.zeros(chunk_size, dtype=np.float32)
        # running peak for spectrum normalization (exponential decay)
        self._peak_decay = 0.995  # decay factor (closer to 1 = slower decay)
        self._lock = threading.Lock()
        self._thread = None
        self._running = False
        self.pa = pyaudio.PyAudio()

    def start_capture(self, prefer_loopback: bool = True, device_index: Optional[int] = None) -> None:
        """Start audio capture.

        On Windows with WASAPI, prefer a loopback (output) device so the app
        listens to system output rather than the microphone. If no loopback
        device is found, fall back to the default input device.

        prefer_loopback: when True, try to auto-select a device whose name
        contains 'loopback' or 'stereo' (case-insensitive). This is a best-effort
        heuristic that works with PyAudioWPatch / WASAPI where loopback device
        names commonly include 'loopback' or 'stereo mix'.
        """
        pa = self.pa
        # request stereo frames; store channels to correctly de-interleave later
        self._channels = 2

        try:
            # Get default WASAPI info
            wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        except OSError:
            logger.error("WASAPI host API not found; is PyAudioWPatch installed and running on Windows?")
            exit()
        
        # Get default WASAPI speakers
        default_speakers = pa.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
        
        if not default_speakers["isLoopbackDevice"]:
            for loopback in pa.get_loopback_device_info_generator():
                """
                Try to find loopback device with same name(and [Loopback suffix]).
                Unfortunately, this is the most adequate way at the moment.
                """
                if default_speakers["name"] in loopback["name"]:
                    default_speakers = loopback
                    break
            else:
                logger.warning("No loopback device found; using default input device instead.")
                exit()
        
        self._stream = pa.open(format=pyaudio.paInt16,
                channels=default_speakers["maxInputChannels"],
                rate=int(default_speakers["defaultSampleRate"]),
                frames_per_buffer=self.chunk_size,
                input=True,
                input_device_index=default_speakers["index"],
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
                # If stream is paInt16, convert to float32 in range -1..1
                arr = np.frombuffer(data, dtype=np.int16)
                arr = arr.astype(np.float32) / 32768.0
                if arr.size == 0:
                    continue

                # If interleaved stereo, reshape to (n_frames, channels) then average
                try:
                    ch = getattr(self, '_channels', 1)
                    if ch > 1 and arr.size % ch == 0:
                        arr = arr.reshape(-1, ch).mean(axis=1)
                except Exception:
                    pass

                # Ensure buffer has expected length (frames per channel)
                if arr.size != self.chunk_size:
                    if arr.size > self.chunk_size:
                        arr = arr[: self.chunk_size]
                    else:
                        a = np.zeros(self.chunk_size, dtype=np.float32)
                        a[: arr.size] = arr
                        arr = a

                with self._lock:
                    self._audio_buffer = arr.astype(np.float32)
            except Exception as e:
                logger.error(f"Audio read error: {e}")

    def update(self):
        """更新音频特征 - 只计算FFT频谱"""
        # 获取最新音频数据
        with self._lock:
            x = self._audio_buffer.copy()
        
        if x.size == 0:
            return
        
        # 1. 计算FFT频谱 (使用fft)
        win = np.hanning(self.fft_size)
        padded = np.zeros(self.fft_size)
        padded[:min(len(x), self.fft_size)] = x[:min(len(x), self.fft_size)]
        spec = np.fft.fft(padded * win)
        
        # 2. 计算频率数组 (使用fftfreq)
        freqs = np.fft.fftfreq(self.fft_size, d=1.0/float(self.sample_rate))
        
        # 3. 处理频谱用于可视化
        spec_processed, _, self._running_peak = audioUtils.process_spectrum_for_visualization(
            spec=spec,
            freqs=freqs,
            prev_smoothed=self._spec_smoothed,
            running_peak=self._running_peak,
            smoothing=0.8
        )
        
        # 4. 保存平滑后的频谱供下次使用
        self._spec_smoothed = spec_processed
        
        # 5. 将处理后的频谱拷贝到纹理
        with self._lock:
            self.fft = spec_processed.copy()
                
        # 6. 打印诊断信息
        buf_peak = np.max(np.abs(x))
        tex_peak = np.max(self.fft)
        if hasattr(self, 'frame_count'):
            self.frame_count += 1
        else:
            self.frame_count = 0
        if self.frame_count % 100 == 0:  # 每100帧打印一次
            print(f"[audio] frame={self.frame_count} tex_peak={tex_peak:.6f} buf_peak={buf_peak:.6f} running_peak={self._running_peak:.6f}")

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
    # 尝试启动真实采集；如果在没有设备的环境中会抛出异常，我们仍然运行合成信号的自测
    try:
        au.start_capture()
        started = True
    except Exception as e:
        logger.warning(f"start_capture failed: {e}")
        started = False

    # 简单自测：生成一个 440Hz 正弦，写入音频缓冲并运行 update(), 打印 FFT 诊断信息
    t = np.arange(au.chunk_size) / float(au.sample_rate)
    freq = 440.0
    sine = (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    with au._lock:
        au._audio_buffer = sine
    au.update()
    fft = au.get_fft_data()
    if fft is not None:
        peak_idx = int(np.argmax(fft))
        print(f"FFT peak index: {peak_idx}, peak value: {np.max(fft):.6f}")
        print("FFT first 16:", np.round(fft[:16], 6))
    else:
        print("No FFT data available")

    if started:
        try:
            au.stop_capture()
        except Exception:
            pass
