"""
ShaderToy uniform variables definitions
"""
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import numpy as np

@dataclass
class TextureChannel:
    """Represents a texture channel in ShaderToy"""
    texture_id: int = -1
    resolution: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    data: Optional[np.ndarray] = None
    time: float = 0.0

@dataclass
class ShaderToyUniforms:
    """Holds all ShaderToy uniform variables"""
    iResolution: Tuple[float, float, float] = (800.0, 600.0, 0.0)
    iTime: float = 0.0
    iTimeDelta: float = 0.0
    iFrameRate: float = 0.0
    iFrame: int = 0
    iMouse: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    iDate: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    iSampleRate: float = 44100.0
    iHandPos: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    iHandAction: float = 0.0
    iHandDepthRef: float = 0.0  # 手掌中心深度参考，用于深度感知补偿
    iPinchEnabled: float = 1.0  # 握拳检测开关（0.0=关闭，1.0=开启）
    iSatControl: float = 0.2
    iDisturbControl: float = 0.2

    iChannels: List[TextureChannel] = field(default_factory=lambda: [
        TextureChannel() for _ in range(4)
    ])