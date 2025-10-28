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
    """
    处理频谱以优化可视化效果
    
    算法步骤：
    1. 对数频率重采样
    2. 频率平滑
    3. 时间平滑
    4. fft归一化
    
    Args:
        spec: 原始频谱
        freqs: 频率数组
        prev_smoothed: 上一帧平滑后的频谱
        running_peak: 运行中的峰值，用于自适应归一化
        smoothing: 平滑系数 (0-1, 越大越平滑)
    
    Returns:
        (processed_spec, freqs, new_running_peak): 处理后的频谱、频率和新的运行峰值
    """
    
    if np.sum(np.abs(spec)) < 0.5:
        return np.zeros_like(prev_smoothed), freqs, running_peak

    # 1. 取正频率部分并对数放大
    spec = np.abs(spec[:len(freqs)])  # 取正频率部分
    spec = np.log1p(spec * 1000)  # 对数放大，避免0值问题
    
    # 2. 频率域平滑 (高斯滤波)
    window_size = 5
    gaussian_kernel = np.exp(-np.linspace(-2, 2, window_size)**2/2)
    gaussian_kernel = gaussian_kernel / np.sum(gaussian_kernel)
    spec = np.convolve(spec, gaussian_kernel, mode='same')
    
    # 3. 时间平滑 (指数移动平均)
    spec_smoothed = None
    if prev_smoothed is None or smoothing <= 0.0:
        spec_smoothed = spec.copy()
    else:
        try:
            # 如果prev_smoothed是元组，取第一个元素（频谱数据）
            prev_data = prev_smoothed[0] if isinstance(prev_smoothed, tuple) else prev_smoothed
            # 确保数据类型和形状一致
            prev_data = np.asarray(prev_data).reshape(-1)  # 强制转为1维数组
            if len(prev_data) != len(spec):
                spec_smoothed = spec.copy()  # 形状不匹配时，使用当前帧
            else:
                spec_smoothed = smoothing * prev_data + (1 - smoothing) * spec
        except (ValueError, IndexError, TypeError):
            # 任何转换错误，都使用当前帧
            spec_smoothed = spec.copy()
    
    # 4. 对低频部分进行插值，扩展到完整频谱宽度
    n_bins = len(spec_smoothed)
    # 只取前1/2频谱（低频部分）
    cutoff_bin = n_bins // 2
    low_spec = spec_smoothed[:cutoff_bin]

    # 源数据点 (low_spec的索引)
    source_points = np.arange(len(low_spec))
    # 目标数据点 (将low_spec拉伸到n_bins的范围)
    target_points = np.linspace(0, len(low_spec) - 1, n_bins)
    # 执行线性插值
    interpolated_spec = np.interp(target_points, source_points, low_spec)
    # 将插值结果赋给spec_smoothed
    spec_smoothed = interpolated_spec

    # 5. 自适应幅度缩放 (动态调整参考电平以匹配音量)
    peak = np.max(spec_smoothed)
    if peak > running_peak:
        running_peak = peak
    else:
        running_peak *= 0.99  # 平滑衰减

    # 避免除以零
    if running_peak < 1e-3:
        running_peak = 1e-3

    spec_smoothed = spec_smoothed / running_peak

    # 7. 最后进行裁剪
    spec_smoothed = np.clip(spec_smoothed, 0.0, 1.0)

    return spec_smoothed, freqs, running_peak
