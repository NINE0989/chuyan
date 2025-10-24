"""
Audio processing and FFT analysis
"""
import numpy as np
import logging
from typing import Optional
import pyaudiowpatch as pyaudio
import threading
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioSource:
    """Audio input with FFT using PyAudioWPatch (WASAPI loopback supported)"""
    def __init__(self, sample_rate: int = 44100, chunk_size: int = 4096, fft_size: int = 1024):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.fft_size = fft_size
        self.fft = np.zeros(fft_size, dtype=np.float32)
        # audio feature state
        self.prev_spec = np.zeros(fft_size, dtype=np.float32)
        self.peak = 0.0
        self.rms = 0.0
        self.centroid = 0.0
        self.flux = 0.0
        self.rolloff = 0.0
        # four-band energies: low, low-mid, mid-high, high
        self.band_energies = np.zeros(4, dtype=np.float32)
        self._audio_buffer = np.zeros(chunk_size, dtype=np.float32)
        # running peak for spectrum normalization (exponential decay)
        self._running_peak = 0.0
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
        # 取最新音频数据做FFT
        with self._lock:
            x = self._audio_buffer.copy()
        # compute raw metrics
        if x.size == 0:
            return

        self.rms = float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))
        self.peak = float(np.max(np.abs(x)))

        # windowed FFT
        win = np.hanning(len(x))
        spec_raw = np.abs(np.fft.rfft(x * win))
        spec = spec_raw[:self.fft_size].astype(np.float32)

        # spectral centroid
        freqs = np.fft.rfftfreq(len(x), d=1.0 / float(self.sample_rate))[: self.fft_size]
        mag = spec.astype(np.float64)
        mag_sum = float(np.sum(mag) + 1e-12)
        self.centroid = float(np.sum(freqs * mag) / mag_sum) if mag_sum > 0 else 0.0

        # spectral flux (difference from previous spec)
        prev = self.prev_spec[: len(spec)] if self.prev_spec is not None else np.zeros_like(spec)
        self.flux = float(np.sqrt(np.sum((spec.astype(np.float64) - prev.astype(np.float64)) ** 2)))
        self.prev_spec[: len(spec)] = spec

        # spectral rolloff (frequency at which cumulative energy reaches 85%)
        cumsum = np.cumsum(mag)
        roll_thresh = 0.85 * cumsum[-1] if cumsum.size > 0 else 0.0
        idx = int(np.searchsorted(cumsum, roll_thresh)) if cumsum.size > 0 else 0
        self.rolloff = float(freqs[min(idx, len(freqs) - 1)]) if freqs.size > 0 else 0.0

        # band energies (simple bands)
        nyq = float(self.sample_rate) / 2.0
        bands = [ (20,250), (250,1000), (1000,4000), (4000, nyq) ]
        band_vals = []
        for lo, hi in bands:
            # find indices
            mask = (freqs >= lo) & (freqs < hi)
            if np.any(mask):
                band_energy = float(np.mean(mag[mask]))
            else:
                band_energy = 0.0
            band_vals.append(band_energy)
        self.band_energies = np.array(band_vals, dtype=np.float32)

        # Running-peak normalization for spectrum:
        # Update running peak with exponential decay
        spec_max = np.max(spec)
        self._running_peak = max(spec_max, self._running_peak * self._peak_decay)
        
        # Normalize spectrum by running peak (so tex_peak varies with loudness)
        # When running_peak is very small (near silence), set spectrum to zero
        # to avoid amplifying noise
        MIN_PEAK_THRESHOLD = 0.1  # below this, treat as silence
        if self._running_peak > MIN_PEAK_THRESHOLD:
            spec_norm = spec / self._running_peak
        else:
            # Near silence: scale down proportionally or zero out
            spec_norm = spec * (self._running_peak / MIN_PEAK_THRESHOLD)
        self.fft[: len(spec_norm)] = spec_norm

    def get_fft_data(self) -> Optional[np.ndarray]:
        return self.fft

    def get_texture_data(self) -> np.ndarray:
        arr = np.zeros((1, self.fft_size, 4), dtype=np.float32)
        # R channel: normalized spectrum (as before)
        arr[0, :, 0] = self.fft
        # Pack a few scalar audio features into the first texel's other channels:
        # G: normalized spectral centroid (0..1 relative to Nyquist)
        # B: RMS (raw)
        # A: peak (raw)
        nyq = float(self.sample_rate) / 2.0
        centroid_norm = float(self.centroid / nyq) if nyq > 0 else 0.0
        arr[0, 0, 1] = centroid_norm
        arr[0, 0, 2] = float(self.rms)
        arr[0, 0, 3] = float(self.peak)
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
