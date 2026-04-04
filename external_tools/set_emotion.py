from settings import va, settings
from gemini_engine import BaseTool
from typing import Dict, Any
import requests

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
                    "description": "ID эмоции ('happy', 'sad', 'angry', 'surprised', 'neutral', 'wink', 'aggressive', 'confused').",
                    "enum": ["happy", "sad", "angry", "surprised", "neutral", "wink", "aggressive", "confused"]
                }
            },
            "required": ["emotion"]
        }
    
    def execute(self, emotion: str) -> Dict[str, Any]:
        master_token = settings.get("MASTER_TOKEN")
        host = "127.0.0.1"
        port = 80
        url = f"http://{host}:{port}/api/emotions/current"
        
        params = {"token": master_token}
        data = {"emotion": emotion}
        
        try:
            response = requests.put(url, params=params, json=data, timeout=5)
            response.raise_for_status()
            return {"status": "success", "result": response.json()}
        except Exception as e:
            return {"status": "error", "message": str(e)}
