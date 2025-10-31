"""
Audio processing utilities and feature extraction algorithms
音频处理工具和特征提取算法
"""
import numpy as np
from typing import Tuple, Optional

def process_spectrum_for_visualization(
    spec: np.ndarray,
    freqs: np.ndarray,
    prev_smoothed: np.ndarray,
    running_peak: np.float32,
    smoothing: np.float32 = 0.65
) -> Tuple[np.ndarray, np.ndarray, np.float32]:
    # ... (docstring) ...
    
    if np.sum(np.abs(spec)) < 0.5:
        return np.zeros_like(prev_smoothed), freqs, running_peak

    # 步骤 2. 取正频率部分并对数放大
    spec = np.abs(spec[:len(freqs)])
    spec = np.log1p(spec * 1000)

    # 步骤 3. 频率域平滑 (高斯滤波)
    window_size = 5
    gaussian_kernel = np.exp(-np.linspace(-2, 2, window_size)**2/2)
    gaussian_kernel /= np.sum(gaussian_kernel)
    spec = np.convolve(spec, gaussian_kernel, mode='same')

    # 步骤 4. 时间平滑 (指数移动平均) - 在这里计算 spec_smoothed
    spec_smoothed = None
    if prev_smoothed is None or smoothing <= 0.0:
        spec_smoothed = spec.copy()
    else:
        try:
            prev_data = prev_smoothed[0] if isinstance(prev_smoothed, tuple) else prev_smoothed
            prev_data = np.asarray(prev_data).reshape(-1)
            if len(prev_data) != len(spec):
                spec_smoothed = spec.copy()
            else:
                spec_smoothed = smoothing * prev_data + (1 - smoothing) * spec
        except (ValueError, IndexError, TypeError):
            spec_smoothed = spec.copy()

    # 步骤 1. 截取低频并插值 - 现在可以安全使用 spec_smoothed
    n_bins = len(spec_smoothed)
    cutoff_bin = n_bins // 2
    low_spec = spec_smoothed[:cutoff_bin]

    source_points = np.arange(len(low_spec))
    target_points = np.linspace(0, len(low_spec) - 1, n_bins)
    interpolated_spec = np.interp(target_points, source_points, low_spec)
    spec_smoothed = interpolated_spec

    # 步骤 5. 自适应幅度缩放
    peak = np.max(spec_smoothed)
    if peak > running_peak:
        running_peak = peak
    else:
        running_peak *= 0.99

    if running_peak < 1e-3:
        running_peak = 1e-3

    spec_smoothed = spec_smoothed / running_peak

    # 步骤 6. 最后进行裁剪
    spec_smoothed = np.clip(spec_smoothed, 0.0, 1.0)

    return spec_smoothed, freqs, running_peak