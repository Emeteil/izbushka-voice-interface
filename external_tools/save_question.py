from typing import Any, Dict

import requests

from gemini_engine import BaseTool
from settings import va, settings, event_memory


_ALLOWED_TOPICS = [
    "admission", "programs", "scores", "docs",
    "dorm", "scholarship", "contacts", "campus", "other",
]


def _web_core_base_url() -> str:
    cfg = settings.get("web_core", {})
    host = cfg.get("host", "127.0.0.1")
    port = cfg.get("port", 80)
    return f"http://{host}:{port}"


@va.tool
class SaveQuestion(BaseTool):
    @property
    def name(self) -> str:
        return "save_question"

    @property
    def description(self) -> str:
        return (
            "Зафиксировать вопрос абитуриента в журнале приёмной комиссии. "
            "Сохраняй каждый содержательный вопрос вместе с твоим коротким ответом и темой — "
            "по этим данным сотрудники потом увидят, что чаще всего спрашивают."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "OBJECT",
            "properties": {
                "question": {
                    "type": "STRING",
                    "description": "Вопрос абитуриента в исходной формулировке.",
                },
                "answer": {
                    "type": "STRING",
                    "description": "Краткий ответ, который ты дал (или признание, что ответа нет).",
                },
                "topic": {
                    "type": "STRING",
                    "description": "Тема вопроса.",
                    "enum": _ALLOWED_TOPICS,
                },
            },
            "required": ["question"],
        }

    def execute(self, question: str, answer: str = "", topic: str = "other") -> Dict[str, Any]:
        topic = topic if topic in _ALLOWED_TOPICS else "other"
        event_memory.record_question(question=question, answer=answer, topic=topic)

        url = f"{_web_core_base_url()}/api/questions"
        params = {"token": settings.get("MASTER_TOKEN")}
        body = {
            "question": question,
            "answer": answer or None,
            "topic": topic,
            "source": "voice",
        }
        try:
            response = requests.post(url, params=params, json=body, timeout=5)
            response.raise_for_status()
            return {"status": "success", "remote": response.json().get("data")}
        except Exception as e:
            return {"status": "local_only", "message": f"Saved locally; remote failed: {e}"}
