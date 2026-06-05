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
        _MUSIC_DIR_CACHE = root / "music"
        _MUSIC_DIR_CACHE.mkdir(parents=True, exist_ok=True)
    return _MUSIC_DIR_CACHE


@tool
def summarize_audio(audio_array: list[float] | None = None) -> str:
    """分析音频数组的统计特征：长度、均值、最大值、最小值、下采样抽样。"""
    if not audio_array:
        return json.dumps({"length": 0, "mean": 0.0, "max": 0.0, "min": 0.0, "samples": []}, ensure_ascii=False)
    length = len(audio_array)
    mean_v = sum(audio_array) / length
    max_v = max(audio_array)
    min_v = min(audio_array)
    step = max(1, length // 32)
    samples = [float(audio_array[i]) for i in range(0, length, step)][:32]
    return json.dumps({"length": length, "mean": float(mean_v), "max": float(max_v), "min": float(min_v), "samples": samples}, ensure_ascii=False)


@tool
def load_audio_from_file(path: str) -> str:
    """从 JSON/CSV 文件加载音频采样数组。"""
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
        if fp.is_file() and fp.suffix.lower() in (".json", ".csv", ".txt", ".wav"):
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
        if fp.is_file() and fp.suffix.lower() in (".json", ".csv", ".txt", ".wav"):
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
