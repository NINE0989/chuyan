"""配置管理器：环境变量 > settings.json > 默认值。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


class Settings:
    """单例配置管理器，优先级：配置文件 > 环境变量 > 默认值。

    设置页写入 settings.json 后应立即成为应用有效配置，避免被父进程里
    残留的 OPENAI_* 环境变量覆盖。若确实需要环境变量优先，可设置
    MS_PREFER_ENV=1。
    """

    _instance: Optional["Settings"] = None
    _config_path: Path

    # 默认值
    DEFAULTS = {
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4.1-mini",
        "speech_api_key": "",
        "speech_base_url": "https://api.openai.com/v1",
        "speech_model": "whisper-1",
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
    def speech_api_key(self) -> str:
        return self._get("speech_api_key", "OPENAI_SPEECH_API_KEY")

    @speech_api_key.setter
    def speech_api_key(self, value: str):
        self._set("speech_api_key", value)

    @property
    def speech_base_url(self) -> str:
        return self._get("speech_base_url", "OPENAI_SPEECH_BASE_URL")

    @speech_base_url.setter
    def speech_base_url(self, value: str):
        self._set("speech_base_url", value)

    @property
    def speech_model(self) -> str:
        return self._get("speech_model", "OPENAI_SPEECH_MODEL")

    @speech_model.setter
    def speech_model(self, value: str):
        self._set("speech_model", value)

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    @property
    def has_speech_api_key(self) -> bool:
        return bool(self.speech_api_key)

    # --- 读取逻辑 ---
    def _get(self, config_key: str, env_var: str) -> str:
        """默认配置文件优先；MS_PREFER_ENV=1 时环境变量优先。"""
        env_val = os.getenv(env_var, "").strip()
        file_val = self._read_file().get(config_key, "")

        if os.getenv("MS_PREFER_ENV", "").strip() == "1":
            if env_val:
                return env_val
            if file_val:
                return file_val
        else:
            if file_val:
                return file_val
            if env_val:
                return env_val

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
            "speech_api_key": self.speech_api_key,
            "speech_base_url": self.speech_base_url,
            "speech_model": self.speech_model,
        }

    def update(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
        speech_api_key: str = "",
        speech_base_url: str = "",
        speech_model: str = "",
    ):
        """批量更新并持久化。"""
        if api_key:
            self.api_key = api_key
        if base_url:
            self.base_url = base_url
        if model:
            self.model = model
        if speech_api_key:
            self.speech_api_key = speech_api_key
        if speech_base_url:
            self.speech_base_url = speech_base_url
        if speech_model:
            self.speech_model = speech_model

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
