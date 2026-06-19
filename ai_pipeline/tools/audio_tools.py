"""音频类工具：音频数据加载与分析、音乐文件库发现。"""
from __future__ import annotations

import json
from pathlib import Path

from langchain_core.tools import tool

_MUSIC_DIR_CACHE: Path | None = None


def _get_music_dir() -> Path:
    global _MUSIC_DIR_CACHE
    if _MUSIC_DIR_CACHE is None:
        root = Path(__file__).resolve().parent.parent.parent
        _MUSIC_DIR_CACHE = root / "MusicLib"
        _MUSIC_DIR_CACHE.mkdir(parents=True, exist_ok=True)
    return _MUSIC_DIR_CACHE


@tool
def summarize_audio(audio_array: list[float] | None = None) -> str:
    """分析音频数组的统计特征：长度、均值、峰值、RMS、32点均匀采样。不做任何主观判断。"""
    if not audio_array:
        return json.dumps({"length": 0, "mean": 0.0, "peak": 0.0, "rms": 0.0, "samples": []}, ensure_ascii=False)
    length = len(audio_array)
    arr = [abs(x) for x in audio_array]
    mean_v = sum(arr) / length if length else 0.0
    peak = max(arr) if length else 0.0
    rms = (sum(x * x for x in audio_array) / length) ** 0.5 if length else 0.0
    # 32 点均匀采样
    step = max(1, length // 32)
    samples = [round(float(audio_array[i]), 4) for i in range(0, length, step)][:32]
    return json.dumps({
        "length": length,
        "mean": round(mean_v, 6),
        "peak": round(peak, 6),
        "rms": round(rms, 6),
        "samples": samples,
    }, ensure_ascii=False)


@tool
def load_audio_from_file(path: str) -> str:
    """从音频文件加载采样数组。

    path 可以是绝对路径、相对路径或仅文件名。仅文件名时自动在 MusicLib/ 查找。
    返回 JSON：{"audio_array": [float, ...]} 或 {"audio_array": [], "error": "..."}
    """
    p = Path(path)
    if not p.is_file():
        music_dir = _get_music_dir()
        # 去掉可能的 MusicLib/ 前缀，防止路径重复
        rel = path.replace("\\", "/")
        if rel.startswith("MusicLib/"):
            rel = rel[len("MusicLib/"):]
        p2 = Path(rel)
        if str(p2.parent) == ".":
            candidates = list(music_dir.rglob(p2.name))
        else:
            candidates = [music_dir / p2]
        for c in candidates:
            if c.is_file():
                p = c
                break
        else:
            return json.dumps({"audio_array": [], "error": f"文件不存在: {path}"})

    ext = p.suffix.lower()

    # ---- 二进制音频格式 ----
    if ext in (".wav", ".mp3", ".flac", ".ogg", ".aac", ".m4a", ".wma", ".aiff", ".opus"):
        try:
            wav_path = p
            if ext != ".wav":
                # 通过系统 PATH 查找 ffmpeg（conda 安装后会自动在 PATH 中）
                import shutil, tempfile, subprocess
                ffmpeg_path = shutil.which("ffmpeg")
                if ffmpeg_path is None:
                    return json.dumps({"audio_array": [], "error": "需要 ffmpeg 才能解码非 WAV 音频。请运行: conda install -c conda-forge ffmpeg"})

                # 非 WAV → 用 ffmpeg 转为临时 WAV
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    wav_path = Path(tmp.name)
                result = subprocess.run(
                    [ffmpeg_path, "-y", "-i", str(p), "-ac", "1", "-ar", "44100", "-f", "wav", str(wav_path)],
                    capture_output=True, timeout=30,
                )
                if result.returncode != 0:
                    wav_path.unlink(missing_ok=True)
                    return json.dumps({"audio_array": [], "error": f"{ext} 格式无法解码。请将音频转为 WAV 或 JSON 采样数组后放入 MusicLib/"})

            # 解码 WAV
            import struct, wave
            import numpy as np
            with wave.open(str(wav_path), "rb") as wf:
                n_frames = wf.getnframes()
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                raw = wf.readframes(n_frames)
            # 清理临时文件
            if ext != ".wav":
                wav_path.unlink(missing_ok=True)
            if sampwidth == 2:
                fmt = "<%dh" % (n_frames * n_channels)
                data = np.array(struct.unpack(fmt, raw), dtype=np.float32)
            elif sampwidth == 4:
                fmt = "<%di" % (n_frames * n_channels)
                data = np.array(struct.unpack(fmt, raw), dtype=np.float32)
            else:
                return json.dumps({"audio_array": [], "error": f"不支持的位深度: {sampwidth * 8}bit"})
            data = data.reshape(-1, n_channels).mean(axis=1) if n_channels > 1 else data
            max_val = float(2 ** (sampwidth * 8 - 1))
            data = (data / max_val).astype(np.float32)
            # 降采样到 ~8000 点
            if len(data) > 8000:
                step = max(1, len(data) // 8000)
                data = data[::step]
            return json.dumps({"audio_array": [round(float(x), 6) for x in data]})
        except Exception as e:
            return json.dumps({"audio_array": [], "error": f"解码失败: {str(e)[:100]}"})

    # ---- 文本格式（JSON/CSV/TXT）----
    text = p.read_text(encoding="utf-8-sig", errors="ignore").strip()
    data = []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            data = [float(x) for x in parsed]
    except Exception:
        for token in text.replace("\n", ",").split(","):
            t = token.strip()
            if not t: continue
            try: data.append(float(t))
            except Exception: continue
    return json.dumps({"audio_array": data})


@tool
def list_music_files(folder: str = "") -> str:
    """列出音乐库中的所有音频文件（扫描 music/ 目录）。"""
    music_dir = _get_music_dir()
    target = music_dir / folder if folder else music_dir
    if not target.is_dir():
        return json.dumps([], ensure_ascii=False)
    files = []
    for fp in sorted(target.rglob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if fp.is_file() and fp.suffix.lower() in (".json", ".csv", ".txt", ".wav", ".mp3", ".flac", ".ogg", ".aac", ".m4a", ".wma", ".aiff", ".opus"):
            try:
                st = fp.stat()
                rel = str(fp.relative_to(music_dir)).replace("\\", "/")
                files.append({
                    "name": fp.name, "path": rel,
                    "folder": str(fp.parent.relative_to(music_dir)).replace("\\", "/") if fp.parent != music_dir else "",
                    "size": st.st_size, "suffix": fp.suffix.lower(),
                })
            except OSError: continue
    return json.dumps(files, ensure_ascii=False)


@tool
def find_music_by_name(query: str = "") -> str:
    """按名称搜索音乐库中的音频文件（部分匹配，支持评分排序）。"""
    if not query:
        return json.dumps([], ensure_ascii=False)
    music_dir = _get_music_dir()
    results = []
    query_lower = query.lower()
    for fp in music_dir.rglob("*"):
        if fp.is_file() and fp.suffix.lower() in (".json", ".csv", ".txt", ".wav", ".mp3", ".flac", ".ogg", ".aac", ".m4a", ".wma", ".aiff", ".opus"):
            name_lower = fp.name.lower(); stem_lower = fp.stem.lower()
            score = 0
            if query_lower == stem_lower: score = 100
            elif query_lower == name_lower: score = 90
            elif stem_lower.startswith(query_lower): score = 70
            elif query_lower in stem_lower: score = 50
            elif query_lower in name_lower: score = 30
            if score > 0:
                rel = str(fp.relative_to(music_dir)).replace("\\", "/")
                results.append({"name": fp.name, "path": rel, "folder": str(fp.parent.relative_to(music_dir)).replace("\\", "/") if fp.parent != music_dir else "", "score": score})
    results.sort(key=lambda x: -x["score"])
    return json.dumps(results[:10], ensure_ascii=False)
