from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional


_DEFAULT_IDLE_RESET_SEC = 45.0
_DEFAULT_MAX_HISTORY = 40


class EventMemory:
    file_path: str
    log_messages: bool
    history: List[Dict[str, Any]]

    def __init__(
        self,
        facts_path: str,
        session_idle_reset_sec: float = _DEFAULT_IDLE_RESET_SEC,
        max_history_messages: int = _DEFAULT_MAX_HISTORY,
        log_messages: bool = True,
        on_session_reset: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    ) -> None:
        self.file_path = facts_path
        self.log_messages = log_messages

        self._idle_reset_sec = float(session_idle_reset_sec or 0)
        self._max_history = max(2, int(max_history_messages or _DEFAULT_MAX_HISTORY))
        self._on_session_reset = on_session_reset

        self._lock = threading.RLock()
        self._session: List[Dict[str, Any]] = []
        self._last_activity: float = 0.0
        self._facts: List[Dict[str, Any]] = self._load_facts()

    @property
    def history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._session)

    @history.setter
    def history(self, value: List[Dict[str, Any]]) -> None:
        with self._lock:
            self._session = list(value or [])

    def add_message(self, role: str, text: str) -> None:
        if not self.log_messages:
            return
        with self._lock:
            self._auto_reset_if_idle()
            self._session.append({
                "id": uuid.uuid4().hex,
                "role": role,
                "content": text,
                "ts": time.time(),
            })
            if len(self._session) > self._max_history:
                self._session = self._session[-self._max_history:]
            self._last_activity = time.time()

    def add_summary(self, summary_text: str) -> None:
        text = (summary_text or "").strip()
        if not text:
            self.reset_session()
            return
        fact = {
            "id": uuid.uuid4().hex,
            "kind": "summary",
            "content": text,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._facts.append(fact)
            self._persist_facts_locked()
        self.reset_session()

    def record_question(
        self,
        question: str,
        answer: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> Dict[str, Any]:
        question = (question or "").strip()
        if not question:
            return {"recorded": False, "reason": "empty question"}
        fact = {
            "id": uuid.uuid4().hex,
            "kind": "question",
            "question": question,
            "answer": (answer or "").strip() or None,
            "topic": (topic or "").strip() or None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._facts.append(fact)
            self._persist_facts_locked()
        return {"recorded": True, "fact": fact}

    def reset_session(self) -> List[Dict[str, Any]]:
        with self._lock:
            old = list(self._session)
            self._session = []
            self._last_activity = 0.0
        if self._on_session_reset:
            try:
                self._on_session_reset(old)
            except Exception:
                pass
        return old

    def get_context_string(self) -> str:
        with self._lock:
            self._auto_reset_if_idle()
            if not self._session:
                return "Текущий разговор только начинается — это новый собеседник."

            lines = ["ТЕКУЩИЙ РАЗГОВОР (только эта сессия, прошлых собеседников не помнить):"]
            for msg in self._session[-self._max_history:]:
                role = msg.get("role", "user")
                speaker = {"assistant": "Ты", "user": "Собеседник", "system": "Система"}.get(role, role)
                content = (msg.get("content") or "").strip()
                if content:
                    lines.append(f"- {speaker}: {content}")
            return "\n".join(lines)

    def get_full_history_log(self) -> str:
        with self._lock:
            tail = self._session[-10:]
        rows = []
        for msg in tail:
            role = "AI" if msg.get("role") == "assistant" else "User"
            content = msg.get("content") or ""
            if len(content) > 100:
                content = content[:100] + "..."
            rows.append(f"[{role}] {content}")
        return "\n".join(rows)

    def update_message(self, msg_id: str, new_content: str) -> bool:
        with self._lock:
            for msg in self._session:
                if msg.get("id") == msg_id:
                    msg["content"] = new_content
                    return True
        return False

    def delete_message(self, msg_id: str) -> bool:
        with self._lock:
            before = len(self._session)
            self._session = [m for m in self._session if m.get("id") != msg_id]
            return len(self._session) != before

    def load(self) -> List[Dict[str, Any]]:
        return self.history

    def save(self) -> None:
        with self._lock:
            self._persist_facts_locked()

    def facts(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._facts)

    def _auto_reset_if_idle(self) -> None:
        if self._idle_reset_sec <= 0 or not self._session:
            return
        if time.time() - self._last_activity >= self._idle_reset_sec:
            old = list(self._session)
            self._session = []
            self._last_activity = 0.0
            if self._on_session_reset:
                try:
                    self._on_session_reset(old)
                except Exception:
                    pass

    def _load_facts(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.file_path):
            return []
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _persist_facts_locked(self) -> None:
        os.makedirs(os.path.dirname(self.file_path) or ".", exist_ok=True)
        tmp = self.file_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._facts, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.file_path)
