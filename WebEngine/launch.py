"""Launch utilities for borderless external shader viewer process."""
from __future__ import annotations
import multiprocessing
import traceback
import time
import os
from pathlib import Path
from typing import Optional

from shadertoy.__main__ import ShaderToyApp
from .paths import SHADERS_DIR

DEFAULT_BORDERLESS_MONITOR = int(os.environ.get("SHADER_BORDERLESS_MONITOR", "0"))


def _ensure_version(code: str) -> str:
    code = code.lstrip('\ufeff')  # BOM
    if code.lstrip().startswith('#version'):
        return code
    return '#version 330 core\n' + code


def run_shader_viewer(shader_path: str, width: int = 1280, height: int = 360, monitor_index: int | None = None):
    """Target executed inside child process to render given shader."""
    try:
        app = ShaderToyApp(shader_path, width, height, borderless=True, monitor_index=monitor_index, center=False)
        app.run()
    except Exception as e:  # pragma: no cover - runtime logging
        print(f"[BorderlessViewer] Failed: {e}")
        traceback.print_exc()


def launch_borderless_process(shader_code: str, source_path: Optional[str]) -> multiprocessing.Process:
    """Launch a borderless viewer process for current shader.

    If source_path is provided and exists, we reuse it; else we write to shaders/_preview.
    Returns the multiprocessing.Process instance (already started).
    """
    if source_path and os.path.exists(source_path):
        shader_path = source_path
    else:
        preview_dir = SHADERS_DIR / "_preview"
        preview_dir.mkdir(exist_ok=True, parents=True)
        ts = time.strftime("applied_%Y%m%d_%H%M%S")
        shader_path = str(preview_dir / f"{ts}.glsl")
        code = _ensure_version(shader_code)
        with open(shader_path, 'w', encoding='utf-8') as f:
            f.write(code if code.endswith('\n') else code + '\n')

    # Determine monitor index
    monitor_index: int | None
    try:
        env_mon = os.environ.get("SHADER_BORDERLESS_MONITOR")
        if env_mon is not None:
            monitor_index = int(env_mon)
        else:
            monitor_index = DEFAULT_BORDERLESS_MONITOR
    except Exception:
        monitor_index = None

    p = multiprocessing.Process(target=run_shader_viewer, args=(shader_path, 1920, 480, monitor_index))
    p.daemon = False
    p.start()
    return p

__all__ = ["launch_borderless_process", "DEFAULT_BORDERLESS_MONITOR"]
