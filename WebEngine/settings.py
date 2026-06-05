"""配置管理器：环境变量 > settings.json > 默认值。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


class Settings:
    """单例配置管理器，优先级：环境变量 > 配置文件 > 默认值。"""

    _instance: Optional["Settings"] = None
    _config_path: Path

    # 默认值
    DEFAULTS = {
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4.1-mini",
    }

    def __new__(cls, config_dir: Path | None = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_dir: Path | None = None):
        if self._initialized:
            return
        self._initialized = True

        if config_dir is None:
            # 默认项目根目录
            config_dir = Path(__file__).resolve().parent.parent
        self._config_path = config_dir / "settings.json"

    # --- 属性访问 ---
    @property
    def api_key(self) -> str:
        return self._get("api_key", "OPENAI_API_KEY")

    @api_key.setter
    def api_key(self, value: str):
        self._set("api_key", value)

    @property
    def base_url(self) -> str:
        return self._get("base_url", "OPENAI_BASE_URL")

    @base_url.setter
    def base_url(self, value: str):
        self._set("base_url", value)

    @property
    def model(self) -> str:
        return self._get("model", "OPENAI_MODEL")

    @model.setter
    def model(self, value: str):
        self._set("model", value)

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    # --- 读取逻辑 ---
    def _get(self, config_key: str, env_var: str) -> str:
        """环境变量优先，否则读 JSON 文件，否则默认值。"""
        env_val = os.getenv(env_var, "").strip()
        if env_val:
            return env_val

        file_val = self._read_file().get(config_key, "")
        if file_val:
            return file_val

        return self.DEFAULTS.get(config_key, "")

    def _set(self, config_key: str, value: str):
        """写入 JSON 文件（不覆盖环境变量）。"""
        data = self._read_file()
        data[config_key] = value
        self._write_file(data)

    def _read_file(self) -> dict:
        if not self._config_path.is_file():
            return {}
        try:
            return json.loads(self._config_path.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_file(self, data: dict):
        self._config_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # --- 便捷方法 ---
    def to_dict(self) -> dict:
        return {
            "api_key": self.api_key,
            "base_url": self.base_url,
            "model": self.model,
        }

    def update(self, api_key: str = "", base_url: str = "", model: str = ""):
        """批量更新并持久化。"""
        if api_key:
            self.api_key = api_key
        if base_url:
            self.base_url = base_url
        if model:
            self.model = model

    def get_deepseek_presets(self) -> dict:
        """DeepSeek 预设值。"""
        return {
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
        }

    def get_openai_presets(self) -> dict:
        """OpenAI 预设值。"""
        return {
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4.1-mini",
        }


# 全局单例
def get_settings() -> Settings:
    return Settings()
