"""
Audio processing utilities and feature extraction algorithms
音频处理工具和特征提取算法
"""
import numpy as np
from typing import Tuple, Optional

def process_spectrum_for_visualization(
    spec: np.ndarray,
    freqs: np.ndarray,
    smoothing: float = 0.65,
    prev_smoothed: Optional[np.ndarray] = None
) -> Tuple[np.ndarray, np.ndarray]:
    """
    处理频谱以优化可视化效果
    
    算法步骤：
    1. 裁剪有效频率范围
    2. 对数频率重采样
    3. 动态范围压缩
    4. 频率加权
    5. 时间平滑
    
    Args:
        spec: 原始频谱
        freqs: 频率数组
        fft_size: 输出FFT大小
        compression_factor: 动态范围压缩系数
        smoothing: 平滑系数 (0-1, 越大越平滑)
        prev_smoothed: 上一帧平滑后的频谱
    
    Returns:
        (processed_spec, log_freqs): 处理后的频谱和对应的对数频率
    """
    
    # 5. 时间平滑 (指数移动平均)
    # if prev_smoothed is None:
    #     spec_smoothed = spec.copy()
    # else:
    #     spec_smoothed = smoothing * prev_smoothed + (1 - smoothing) * spec
    
    return spec, freqs