"""会话类工具：从 conversations.json 加载和保存多轮对话。"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

from langchain_core.tools import tool


_LOCK = threading.Lock()


_CONVERSATIONS_PATH: Path | None = None
_META_PATH: Path | None = None


def _get_path() -> Path:
    global _CONVERSATIONS_PATH
    if _CONVERSATIONS_PATH is None:
        root = Path(__file__).resolve().parent.parent.parent
        _CONVERSATIONS_PATH = root / "ai_pipeline" / "conversations.json"
    return _CONVERSATIONS_PATH


def _get_meta_path() -> Path:
    global _META_PATH
    if _META_PATH is None:
        root = Path(__file__).resolve().parent.parent.parent
        _META_PATH = root / "ai_pipeline" / "conversations_meta.json"
    return _META_PATH


def list_conversations() -> list[dict]:
    """列出所有会话（含元数据），置顶优先，然后按 updated_at 降序。"""
    path = _get_path()
    meta_path = _get_meta_path()

    convs: dict[str, list] = {}
    if path.is_file():
        convs = json.loads(path.read_text(encoding="utf-8-sig"))

    metas: dict[str, dict] = {}
    if meta_path.is_file():
        metas = json.loads(meta_path.read_text(encoding="utf-8-sig"))

    result = []
    for sid in convs:
        if sid.startswith("_"):
            continue
        meta = metas.get(sid, {})
        result.append({
            "session_id": sid,
            "title": meta.get("title", sid),
            "created_at": meta.get("created_at", ""),
            "updated_at": meta.get("updated_at", ""),
            "message_count": len(convs[sid]) if isinstance(convs.get(sid), list) else 0,
            "pinned": meta.get("pinned", False),
        })

    result.sort(key=lambda x: (not x["pinned"], x.get("updated_at", "") or ""), reverse=False)
    # 降序排序（置顶的各自内部也按时间降序）
    pinned = [c for c in result if c["pinned"]]
    unpinned = [c for c in result if not c["pinned"]]
    pinned.sort(key=lambda x: x["updated_at"], reverse=True)
    unpinned.sort(key=lambda x: x["updated_at"], reverse=True)
    return pinned + unpinned


def _infer_title(messages: list) -> str:
    """从消息列表推断标题：取第一条 user 消息前 50 字符。"""
    for m in messages:
        if isinstance(m, dict) and m.get("role") == "user":
            text = (m.get("content") or "").strip()
            if text:
                return text[:50] + ("…" if len(text) > 50 else "")
    return "新对话"


def update_meta(session_id: str, title: str = "") -> None:
    """更新会话元数据（标题、时间戳、消息数）。"""
    if session_id.startswith("_"):
        return

    with _LOCK:
        meta_path = _get_meta_path()
        metas: dict = {}
        if meta_path.is_file():
            metas = json.loads(meta_path.read_text(encoding="utf-8-sig"))

        now = time.strftime("%Y-%m-%d %H:%M:%S")
        existing = metas.get(session_id, {})

        # 读取实际消息数
        path = _get_path()
        msgs = []
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            msgs = data.get(session_id, []) or []

        if not title:
            title = _infer_title(msgs)

        metas[session_id] = {
            "title": title or existing.get("title", "新对话"),
            "created_at": existing.get("created_at", now),
            "updated_at": now,
            "message_count": len(msgs),
        }

        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(metas, ensure_ascii=False, indent=2), encoding="utf-8")


def pin_conversation(session_id: str, pinned: bool = True) -> bool:
    """置顶或取消置顶会话。"""
    if session_id.startswith("_"):
        return False
    meta_path = _get_meta_path()
    metas: dict = {}
    if meta_path.is_file():
        metas = json.loads(meta_path.read_text(encoding="utf-8-sig"))
    if session_id not in metas:
        return False
    metas[session_id]["pinned"] = pinned
    meta_path.write_text(json.dumps(metas, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def delete_session(session_id: str) -> bool:
    """删除指定会话及其元数据。"""
    if session_id.startswith("_"):
        return False

    path = _get_path()
    removed = False

    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if session_id in data:
            del data[session_id]
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            removed = True

    meta_path = _get_meta_path()
    if meta_path.is_file():
        metas = json.loads(meta_path.read_text(encoding="utf-8-sig"))
        if session_id in metas:
            del metas[session_id]
            meta_path.write_text(json.dumps(metas, ensure_ascii=False, indent=2), encoding="utf-8")

    return removed


def rename_session(session_id: str, new_title: str) -> bool:
    """重命名会话标题。"""
    if session_id.startswith("_"):
        return False
    with _LOCK:
        meta_path = _get_meta_path()
        metas: dict = {}
        if meta_path.is_file():
            metas = json.loads(meta_path.read_text(encoding="utf-8-sig"))
        if session_id not in metas:
            return False
        metas[session_id]["title"] = new_title
        meta_path.write_text(json.dumps(metas, ensure_ascii=False, indent=2), encoding="utf-8")
        return True


def new_session() -> str:
    """创建新会话，返回 session_id。"""
    seed = hashlib.md5(str(time.time()).encode("utf-8")).hexdigest()[:10]
    session_id = f"web_{seed}"

    path = _get_path()
    data: dict = {}
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8-sig"))

    # 处理冲突
    while session_id in data:
        seed = hashlib.md5(str(time.time()).encode("utf-8")).hexdigest()[:10]
        session_id = f"web_{seed}"

    data[session_id] = []
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    update_meta(session_id, "新对话")
    return session_id


def load_messages(session_id: str) -> list[dict]:
    """加载指定会话的消息列表（供 WebEngine 直接调用）。"""
    path = _get_path()
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return data.get(session_id, [])


def save_messages(session_id: str, messages: list[dict]) -> None:
    """保存消息列表到 conversations.json（供 WebEngine 直接调用）。"""
    with _LOCK:
        path = _get_path()
        data: dict = {}
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        data[session_id] = messages
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@tool
def load_conversation(session_id: str = "") -> str:
    """加载指定 session 的历史对话。

    Args:
        session_id: 会话 ID

    Returns:
        JSON 字符串，含对话消息列表
    """
    return json.dumps(load_messages(session_id), ensure_ascii=False)


@tool
def save_conversation(session_id: str = "", messages_json: str = "[]") -> str:
    """保存当前对话到 conversations.json。

    Args:
        session_id: 会话 ID
        messages_json: 消息列表的 JSON 字符串

    Returns:
        保存结果
    """
    try:
        messages = json.loads(messages_json)
    except Exception:
        messages = []

    save_messages(session_id, messages)

    msgs = load_messages(session_id)
    return json.dumps({"saved": True, "session_id": session_id, "message_count": len(msgs)})
