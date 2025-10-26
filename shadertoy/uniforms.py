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

    iChannels: List[TextureChannel] = field(default_factory=lambda: [
        TextureChannel() for _ in range(4)
    ])