"""音频类工具：音频数据加载与分析。"""
from __future__ import annotations

import json
from pathlib import Path

from langchain_core.tools import tool


@tool
def summarize_audio(audio_array: list[float] | None = None) -> str:
    """分析音频数组的统计特征：长度、均值、最大值、最小值、下采样抽样。

    Args:
        audio_array: 音频采样浮点数列表

    Returns:
        JSON 字符串，含 length/mean/max/min/samples 字段
    """
    if not audio_array:
        return json.dumps({"length": 0, "mean": 0.0, "max": 0.0, "min": 0.0, "samples": []}, ensure_ascii=False)

    length = len(audio_array)
    mean_v = sum(audio_array) / length
    max_v = max(audio_array)
    min_v = min(audio_array)
    step = max(1, length // 32)
    samples = [float(audio_array[i]) for i in range(0, length, step)][:32]

    return json.dumps(
        {"length": length, "mean": float(mean_v), "max": float(max_v), "min": float(min_v), "samples": samples},
        ensure_ascii=False,
    )


@tool
def load_audio_from_file(path: str) -> str:
    """从 JSON 或 CSV 文件加载音频采样数组。

    Args:
        path: 音频数据文件的路径

    Returns:
        JSON 字符串，含 audio_array 字段（采样值列表）
    """
    p = Path(path)
    if not p.is_file():
        return json.dumps({"audio_array": []})

    text = p.read_text(encoding="utf-8-sig", errors="ignore").strip()
    data = []

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            data = [float(x) for x in parsed]
    except Exception:
        for token in text.replace("\n", ",").split(","):
            t = token.strip()
            if not t:
                continue
            try:
                data.append(float(t))
            except Exception:
                continue

    return json.dumps({"audio_array": data})
