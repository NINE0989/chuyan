"""会话类工具：从 conversations.json 加载和保存多轮对话。"""
from __future__ import annotations

import json
from pathlib import Path

from langchain_core.tools import tool


_CONVERSATIONS_PATH: Path | None = None


def _get_path() -> Path:
    global _CONVERSATIONS_PATH
    if _CONVERSATIONS_PATH is None:
        root = Path(__file__).resolve().parent.parent.parent
        _CONVERSATIONS_PATH = root / "ai_pipeline" / "conversations.json"
    return _CONVERSATIONS_PATH


@tool
def load_conversation(session_id: str = "") -> str:
    """加载指定 session 的历史对话。

    Args:
        session_id: 会话 ID

    Returns:
        JSON 字符串，含对话消息列表
    """
    path = _get_path()
    if not path.is_file():
        return json.dumps([])
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    messages = data.get(session_id, [])
    return json.dumps(messages, ensure_ascii=False)


@tool
def save_conversation(session_id: str = "", messages_json: str = "[]") -> str:
    """保存当前对话到 conversations.json。

    Args:
        session_id: 会话 ID
        messages_json: 消息列表的 JSON 字符串

    Returns:
        保存结果
    """
    path = _get_path()
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    else:
        data = {}

    try:
        messages = json.loads(messages_json)
    except Exception:
        messages = []

    data[session_id] = messages
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return json.dumps({"saved": True, "session_id": session_id, "message_count": len(messages)})
