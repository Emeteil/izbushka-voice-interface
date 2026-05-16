from settings import va, settings
from gemini_engine import BaseTool
from typing import Any, Dict, List
import logging
import requests

logger = logging.getLogger("set_emotion")

DEFAULT_EMOTIONS: List[str] = [
    "happy", "sad", "angry", "surprised",
    "neutral", "wink", "aggressive", "confused",
]


def _web_core_base_url() -> str:
    web_core = settings.get("web_core", {})
    host = web_core.get("host", "127.0.0.1")
    port = web_core.get("port", 80)
    return f"http://{host}:{port}"


def _fetch_emotion_ids() -> List[str]:
    try:
        response = requests.get(f"{_web_core_base_url()}/api/emotions", timeout=3)
        response.raise_for_status()
        payload = response.json().get("data", {})
        items = payload.get("emotions", [])
        ids = [item["id"] for item in items if isinstance(item, dict) and "id" in item]
        if ids:
            return ids
    except Exception as e:
        logger.warning(f"Failed to fetch emotions from web-core: {e}; using defaults")
    return DEFAULT_EMOTIONS


_EMOTION_IDS = _fetch_emotion_ids()


@va.tool
class SetEmotion(BaseTool):
    @property
    def name(self) -> str:
        return "set_emotion"

    @property
    def description(self) -> str:
        return "Изменить текущую эмоцию (лицо) робота."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "OBJECT",
            "properties": {
                "emotion": {
                    "type": "STRING",
                    "description": f"ID эмоции. Допустимые значения: {', '.join(_EMOTION_IDS)}.",
                    "enum": list(_EMOTION_IDS),
                }
            },
            "required": ["emotion"],
        }

    def execute(self, emotion: str) -> Dict[str, Any]:
        url = f"{_web_core_base_url()}/api/emotions/current"
        headers = {"Authorization": f"Bearer {settings.get('MASTER_TOKEN')}"}
        try:
            response = requests.put(url, headers=headers, json={"emotion": emotion}, timeout=5)
            response.raise_for_status()
            return {"status": "success", "result": response.json()}
        except Exception as e:
            return {"status": "error", "message": str(e)}
